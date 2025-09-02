from django.utils import timezone
from django.http import JsonResponse
from django.db import transaction
from datetime import timedelta
from .models import Device, Schedule 
import re
import logging
import time


logger = logging.getLogger(__name__)

class DigitalSignageMiddleware:
    """
    Middleware untuk mencari device berdasarkan IP dan logging informasi
    """
    def __init__(self, get_response):
        self.get_response = get_response
        self.last_log_time = 0

    def __call__(self, request):
        if request.path.startswith('/signage/display/'):
            current_time = time.time()
            
            if current_time - self.last_log_time >= 60:
                ip_address = request.META.get('REMOTE_ADDR', '0.0.0.0')
                
                try:
                    device = Device.objects.get(ip_address=ip_address)
                    
                    request.signage_device = device
                    
                    self._log_device_info(device, ip_address)
                    
                except Device.DoesNotExist:
                    logger.info(f"[SIGNAGE] Device dengan IP {ip_address} tidak ditemukan")
                    request.signage_device = None
                
                self.last_log_time = current_time
        
        response = self.get_response(request)
        return response

    def _log_device_info(self, device, ip_address):
        """Log informasi device, group, dan schedule"""
        group_info = self._get_group_info(device)
        schedule_info = self._get_current_schedule(device)
        next_schedule_info = self._get_next_schedule(device)
        
        logger.info(f"[SIGNAGE] Device: {device.name} | IP: {ip_address}")
        logger.info(f"[SIGNAGE] Group: {group_info}")
        
        if schedule_info:
            logger.info(f"[SIGNAGE] Schedule Aktif: {schedule_info['name']}")
            logger.info(f"[SIGNAGE] Tanggal: {schedule_info['date']}")
            logger.info(f"[SIGNAGE] Jam: {schedule_info['start_time']} - {schedule_info['end_time']}")
            logger.info(f"[SIGNAGE] File Path: {schedule_info['file_path']}")
            logger.info(f"[SIGNAGE] Media Type: {schedule_info['media_type']}")
        elif next_schedule_info:
            logger.info(f"[SIGNAGE] Tidak ada schedule aktif")
            logger.info(f"[SIGNAGE] Schedule Berikutnya: {next_schedule_info['name']}")
            logger.info(f"[SIGNAGE] Jam Mulai: {next_schedule_info['start_time']}")
        else:
            logger.info(f"[SIGNAGE] Tidak ada schedule aktif maupun mendatang")

    def _get_group_info(self, device):
        """Mendapatkan informasi group dari device (untuk logging)"""
        if device.group:
            return f"{device.group.name} (ID: {device.group.id}, Devices: {device.group.device_count})"
        else:
            return "Tidak memiliki group"

    def _get_current_schedule(self, device):
        """Mendapatkan schedule aktif untuk device berdasarkan group (untuk logging)"""
        if not device or not device.group:
            return None
        
        now_time = timezone.localtime().time()
        today_date = timezone.localtime().date()
        
        active_schedules = Schedule.objects.filter(
            publish_to__group=device.group,
            publish_status='Published',
            playback_date=today_date,
            playback_start__lte=now_time,
            playback_end__gte=now_time
        ).select_related('content', 'playlist').order_by('-playback_start')
        
        if active_schedules.exists():
            schedule = active_schedules.first()
            file_path, media_type = self._get_file_info(schedule)
            
            return {
                'name': schedule.schedule_name,
                'date': schedule.playback_date.strftime("%Y-%m-%d"),
                'start_time': schedule.playback_start.strftime("%H:%M:%S"),
                'end_time': schedule.playback_end.strftime("%H:%M:%S"),
                'file_path': file_path,
                'media_type': media_type,
            }
        
        return None

    def _get_next_schedule(self, device):
        """Mendapatkan schedule berikutnya untuk device (untuk logging)"""
        if not device or not device.group:
            return None
        
        now_time = timezone.localtime().time()
        today_date = timezone.localtime().date()
        
        next_schedules = Schedule.objects.filter(
            publish_to__group=device.group,
            publish_status='Published',
            playback_date=today_date,
            playback_start__gt=now_time
        ).select_related('content', 'playlist').order_by('playback_start')
        
        if next_schedules.exists():
            schedule = next_schedules.first()
            file_path, media_type = self._get_file_info(schedule)
            
            return {
                'name': schedule.schedule_name,
                'start_time': schedule.playback_start.strftime("%H:%M:%S"),
            }
        
        return None

    def _get_file_info(self, schedule):
        """Mendapatkan file path dan media type dari schedule (untuk logging)"""
        file_obj = None
        media_type = 'unknown'
        
        if schedule.content:
            file_obj = schedule.content.file
            media_type = schedule.content.file_type_content().lower()
        elif schedule.playlist:
            file_obj = schedule.playlist.file
            media_type = schedule.playlist.file_type_playlist().lower()
        
        if file_obj:
            return file_obj.url, media_type
        else:
            return '/media/assets/loading.MP4', 'video'

logger = logging.getLogger(__name__)

class DeviceTrackerMiddleware:
    """Original device tracking middleware - keep existing functionality"""
    def __init__(self, get_response):
        self.get_response = get_response
        self.ping_interval = 30 
        self.offline_threshold = 60
        self.inject_paths = [
            '/device/',
            '/login/', 
            '/signage/display',
            '/dashboard/',
            '/content/',
            '/playlist/',
            '/schedules/'
        ]

    def __call__(self, request):
        start_time = timezone.now()
        
        if request.path == '/device/ping/':
            return self._handle_ping_request(request)
        
        if not self._is_excluded_path(request.path):
            self._track_device(request)
        
        response = self.get_response(request)
        
        if self._should_inject_script(request.path, response):
            self._inject_script(response)
        
        if hash(request.path) % 10 == 0:
            self._mark_offline_devices()
            
        logger.debug(f"Request to {request.path} processed in {(timezone.now() - start_time).total_seconds():.3f}s")
        return response

    def _should_inject_script(self, path, response):
        """Cek apakah path termasuk yang harus diinjeksi script"""
        if 'text/html' not in response.get('Content-Type', ''):
            return False
        
        for inject_path in self.inject_paths:
            if path.startswith(inject_path):
                return True
        return False

    def _is_excluded_path(self, path):
        """Path yang dikecualikan dari tracking (biarkan seperti semula)"""
        excluded_paths = ['/admin/', '/static/', '/favicon.ico', '/media/']
        return any(path.startswith(p) for p in excluded_paths)

    def _handle_ping_request(self, request):
        """Handle ping requests with thread safety"""
        ip_address = request.META.get('REMOTE_ADDR', '0.0.0.0')
        
        try:
            with transaction.atomic():
                device, created = Device.objects.select_for_update().get_or_create(
                    ip_address=ip_address,
                    defaults={
                        'last_updated': timezone.now(),
                        'is_online': True
                    }
                )
                
                if not created:
                    if (timezone.now() - device.last_updated).seconds >= self.ping_interval:
                        device.last_updated = timezone.now()
                        device.is_online = True
                        device.save()
                        logger.info(f"Ping from {ip_address} (updated)")
                    else:
                        logger.debug(f"Ping from {ip_address} (skipped, too frequent)")
                else:
                    logger.info(f"New device ping from {ip_address}")
                    
            return JsonResponse({'status': 'success', 'interval': self.ping_interval})
            
        except Exception as e:
            logger.error(f"Error handling ping from {ip_address}: {str(e)}")
            return JsonResponse({'status': 'error'}, status=500)

    def _track_device(self, request):
        """Track device with resolution and user agent"""
        ip_address = request.META.get('REMOTE_ADDR', '0.0.0.0')
        resolution = self._get_screen_resolution(request)
        user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')[:200]
        
        try:
            with transaction.atomic():
                device, created = Device.objects.select_for_update().get_or_create(
                    ip_address=ip_address,
                    defaults={
                        'user_agent': user_agent,
                        'name': f"Device-{ip_address.replace('.', '-')}",
                        'resolution': resolution,
                        'last_updated': timezone.now(),
                        'is_online': True,
                    }
                )
                
                if not created:
                    update_fields = {
                        'last_updated': timezone.now(),
                        'is_online': True
                    }
                    
                    if resolution != 'Unknown' and device.resolution != resolution:
                        update_fields['resolution'] = resolution
                        logger.debug(f"Updated resolution for {ip_address} to {resolution}")
                    
                    if user_agent != device.user_agent:
                        if len(user_agent) > 20 or user_agent.split()[0] != device.user_agent.split()[0]:
                            update_fields['user_agent'] = user_agent
                            logger.debug(f"Updated user agent for {ip_address}")
                    
                    if len(update_fields) > 2:
                        Device.objects.filter(pk=device.pk).update(**update_fields)
                        
        except Exception as e:
            logger.error(f"Error tracking device {ip_address}: {str(e)}")

    def _get_screen_resolution(self, request):
        """Get validated screen resolution from cookie or header"""
        sources = [
            request.COOKIES.get('screen_resolution'),
            request.META.get('HTTP_X_SCREEN_RESOLUTION')
        ]
        
        for res in sources:
            if validated := self._validate_resolution(res):
                return validated
        return 'Unknown'

    def _validate_resolution(self, resolution):
        """Validate resolution format and reasonable values"""
        if not resolution or resolution == 'Unknown':
            return None
            
        if match := re.match(r'^(\d+)[x:](\d+)$', resolution.strip()):
            try:
                width, height = map(int, match.groups())
                if 320 <= width <= 7680 and 240 <= height <= 4320:
                    return f"{width}x{height}"
            except (ValueError, TypeError):
                pass
        return None

    def _inject_script(self, response):
        """Inject JavaScript for resolution detection and periodic pinging"""
        js_script = f"""
        <script>
        (function() {{
            if (window._deviceTrackerInitialized) return;
            window._deviceTrackerInitialized = true;
            
            function getResolution() {{
                const width = Math.round(screen.width * (window.devicePixelRatio || 1));
                const height = Math.round(screen.height * (window.devicePixelRatio || 1));
                return width + 'x' + height;
            }}
            
            function setResolutionCookie() {{
                const res = getResolution();
                document.cookie = `screen_resolution=${{res}}; path=/; max-age=86400`;
                return res;
            }}
            
            function sendPing() {{
                const res = setResolutionCookie();
                
                fetch('/device/ping/', {{
                    method: 'GET',
                    headers: {{
                        'X-Screen-Resolution': res,
                        'X-Requested-With': 'XMLHttpRequest'
                    }},
                    credentials: 'same-origin'
                }}).then(response => {{
                    if (!response.ok) throw new Error('Ping failed');
                    console.debug('Ping successful at', new Date().toLocaleTimeString());
                }}).catch(err => {{
                    console.warn('Ping error:', err.message);
                }});
            }}
            
            const pingInterval = {self.ping_interval * 1000};
            
            setResolutionCookie();
            
            const firstPingDelay = 5000 + Math.random() * 10000;
            setTimeout(sendPing, firstPingDelay);
            
            setInterval(sendPing, pingInterval);
            
            window.addEventListener('visibilitychange', () => {{
                if (document.visibilityState === 'hidden') {{
                    navigator.sendBeacon('/device/ping/');
                }}
            }});
        }})();
        </script>
        """
        
        if hasattr(response, 'content'):
            try:
                response.content = response.content.replace(
                    b'</body>', 
                    js_script.encode('utf-8') + b'</body>'
                )
            except Exception as e:
                logger.error(f"Error injecting script: {str(e)}")

    def _mark_offline_devices(self):
        """Mark devices as offline if no ping received within threshold"""
        try:
            threshold = timezone.now() - timedelta(seconds=self.offline_threshold)
            offline_count = Device.objects.filter(
                last_updated__lt=threshold,
                is_online=True
            ).update(is_online=False)
            
            if offline_count > 0:
                logger.info(f"Marked {offline_count} devices as offline")
                
        except Exception as e:
            logger.error(f"Error marking offline devices: {str(e)}")