from django.template.loader import render_to_string
from django.core.files.base import ContentFile
from django.utils.timezone import now
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import logout as auth_logout
from django.views.generic.edit import FormView
from django.views.decorators.cache import never_cache
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View, TemplateView
from django.db import transaction
from django.db.models import Q, Count
from django.views import View
from django.core.exceptions import ValidationError
from django.utils.decorators import method_decorator
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db import models
from django.utils import timezone
from email.utils import localtime
from .forms import ContentForm, PlaylistForm, ResetPasswordForm, SignUpForm, ManageForm
from .models import Content, Device, DeviceGroup,  Playlist, Schedule
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
from PIL import Image, ImageEnhance
import json
import logging
import os
import shutil
import subprocess
import tempfile
import xlwt
import base64
import io
from io import BytesIO
import os

#------------------------Auth Views------------------------#
def root_redirect(request):
    return redirect('/login/')

class SignUp(FormView):
    template_name = "auth/signup.html"
    form_class = SignUpForm
    success_url = reverse_lazy("login")

    def get_template_names(self):
        if self._is_modal():
            return ["auth/components/sign_up_modal.html"]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            "page_title": "Daftar Akun Baru",
            "form_title": "Create Your Account",
            "form_subtitle": "Join our community today",
        })
        return context

    def form_valid(self, form):
        try:
            user = form.save()
            logger.info(f"New user registered: {user.username} ({user.email})")
            
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'Registrasi berhasil! Mengarahkan ke login...',  
                    'redirect': str(self.get_success_url()),
                }, status=200)  
                
            messages.success(self.request, "Your account has been created successfully.")
            return super().form_valid(form)
            
        except Exception as e:
            logger.error(f"Error creating user: {str(e)}")
            
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': 'Terjadi kesalahan saat membuat akun. Silakan coba lagi.',
                    'errors': {'__all__': ['Terjadi kesalahan sistem. Silakan coba lagi.']}
                }, status=500)
            
            messages.error(self.request, "An error occurred while creating your account.")
            return self.form_invalid(form)

    def form_invalid(self, form):
        logger.warning(f"Form validation failed: {dict(form.errors)}")
        
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            errors = {}
            for field, error_list in form.errors.items():
                if isinstance(error_list, list):
                    errors[field] = error_list
                else:
                    errors[field] = [str(error_list)]
            
            return JsonResponse({
                'success': False,
                'message': 'Mohon periksa kembali data yang Anda masukkan.',
                'errors': errors,
            }, status=400)
            
        return super().form_invalid(form)

    def post(self, request, *args, **kwargs):
        logger.debug(f"POST data received: {dict(request.POST)}")
        
        post_data = request.POST.copy()
        bait_fields = ['username_bait', 'email_bait', 'password_bait']
        for field in bait_fields:
            post_data.pop(field, None)
        
        request.POST = post_data
        
        return super().post(request, *args, **kwargs)

    def _is_modal(self) -> bool:
        req = self.request
        return str(req.GET.get("modal", "")).lower() in ("1", "true", "yes", "on") or \
               str(req.POST.get("modal", "")).lower() in ("1", "true", "yes", "on")

class ResetPassword(FormView):
    template_name = 'auth/components/reset_password_modal.html'
    form_class = ResetPasswordForm
    success_url = '/login/'

    def form_valid(self, form):
        try:
            user = form.cleaned_data['user']
            new_password = form.cleaned_data['new_password1']
            user.set_password(new_password)
            user.save()

            from django.contrib.admin.models import LogEntry, CHANGE
            from django.contrib.contenttypes.models import ContentType
            LogEntry.objects.log_action(
                user_id=user.id,
                content_type_id=ContentType.objects.get_for_model(user).pk,
                object_id=user.pk,
                object_repr=str(user),
                action_flag=CHANGE,
                change_message="Password changed via reset form"
            )

            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'Password successfully changed! You will be redirected to the login page.',
                    'redirect': reverse('login') + '?password_reset=success'
                })

            messages.success(self.request, 'Password successfully changed!')
            return super().form_valid(form)

        except Exception:
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': 'A system error occurred. Please try again.',
                    'errors': {'__all__': 'A system error occurred. Please try again.'}
                }, status=500)

            messages.error(self.request, 'A system error occurred. Please try again.')
            return self.form_invalid(form)

    def form_invalid(self, form):
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            errors = {}

            if form.non_field_errors():
                errors['__all__'] = form.non_field_errors()[0]

            for field_name, field_errors in form.errors.items():
                if field_name != '__all__':
                    errors[field_name] = field_errors[0] if field_errors else ''

            error_message = 'Please correct the following errors:'
            if '__all__' in errors:
                error_message = errors['__all__']

            return JsonResponse({
                'success': False,
                'errors': errors,
                'message': error_message
            }, status=400)

        return super().form_invalid(form)

def logout(request):
    if request.user.is_authenticated:
        request.user.last_login = localtime(now())
        request.user.save()
    
    auth_logout(request)
    messages.success(request, 'Anda telah berhasil logout.')
    return redirect('login')
#----------------------------------------------------------#


#-----------------------dashboard--------------------------#
class DashboardView(TemplateView):
    template_name = 'dashboard.html'
    
    def get_folder_size(self, folder_path):
        """Calculate folder size in MB"""
        total_size = 0
        try:
            for dirpath, dirnames, filenames in os.walk(folder_path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    try:
                        total_size += os.path.getsize(filepath)
                    except OSError:
                        pass
        except OSError:
            pass
        return round(total_size / (1024 * 1024), 2)
    
    def calculate_storage_percentage(self, size_mb, total_storage_mb=100):
        if total_storage_mb == 0:
            return 0
        percentage = (size_mb / total_storage_mb) * 100
        return min(round(percentage, 1), 100)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        frontend_size = self.get_folder_size(os.path.join(settings.BASE_DIR, 'signage'))
        backend_size = self.get_folder_size(os.path.join(settings.BASE_DIR, 'signage_project'))
        content_uploads_size = self.get_folder_size(os.path.join(settings.BASE_DIR, 'media', 'content_uploads'))
        playlist_uploads_size = self.get_folder_size(os.path.join(settings.BASE_DIR, 'media', 'playlist_uploads'))
        
        frontend_percentage = self.calculate_storage_percentage(frontend_size)
        backend_percentage = self.calculate_storage_percentage(backend_size)
        content_percentage = self.calculate_storage_percentage(content_uploads_size)
        playlist_percentage = self.calculate_storage_percentage(playlist_uploads_size)

        now = timezone.localtime(timezone.now())
        today = now.date()
        tomorrow = today + timedelta(days=1)

        upcoming_schedules = Schedule.objects.filter(
            Q(playback_date=today, playback_start__gt=now.time()) |
            Q(playback_date=tomorrow),
            publish_status='Published'
        ).select_related('content', 'playlist').order_by('playback_date', 'playback_start')[:3]

        total_content = Content.objects.count()
        content_active = Content.objects.filter(
            Q(expiration_date__isnull=True) | Q(expiration_date__gt=now)
        ).count()
        content_expired = Content.objects.filter(
            expiration_date__lte=now
        ).count()
        
        total_playlist = Playlist.objects.count()
        playlist_active = Playlist.objects.filter(
            Q(expiration_date__isnull=True) | Q(expiration_date__gt=now)
        ).count()
        playlist_expired = Playlist.objects.filter(
            expiration_date__lte=now
        ).count()

        total_device = Device.objects.count()
        online_device = Device.objects.filter(is_online=True).count()
        offline_device = total_device - online_device
        total_device_group = DeviceGroup.objects.count()

        device_groups = []
        for group in DeviceGroup.objects.all().prefetch_related('devices'):
            group_devices = group.devices.all()
            total_devices_in_group = group_devices.count()
            
            if total_devices_in_group == 0:
                continue
                
            online_devices_in_group = group_devices.filter(is_online=True).count()
            online_percentage = (online_devices_in_group / total_devices_in_group * 100) if total_devices_in_group > 0 else 0
            
            if online_percentage >= 75:
                status_class = 'online'
            elif online_percentage >= 25:
                status_class = 'partial'
            else:
                status_class = 'offline'
            
            group_schedules = Schedule.objects.filter(
                publish_to__group=group,
                publish_status='Published'
            ).distinct()
            
            total_schedules_in_group = group_schedules.count()
            
            if total_schedules_in_group == 0:
                continue
            
            device_groups.append({
                'name': group.name,
                'total_devices': total_devices_in_group,
                'online_devices': online_devices_in_group,
                'online_percentage': round(online_percentage),
                'status_class': status_class,
                'total_schedules': total_schedules_in_group,
            })

        content_by_user = Content.objects.values('creator__username').annotate(
            content_count=Count('id')
        ).order_by('-content_count')
        
        playlist_by_user = Playlist.objects.values('creator__username').annotate(
            playlist_count=Count('id')
        ).order_by('-playlist_count')
        
        creator_stats = {}
        for item in content_by_user:
            username = item['creator__username']
            if username and username not in creator_stats:
                creator_stats[username] = {'content_count': 0, 'playlist_count': 0}
            if username:
                creator_stats[username]['content_count'] = item['content_count']
        
        for item in playlist_by_user:
            username = item['creator__username']
            if username and username not in creator_stats:
                creator_stats[username] = {'content_count': 0, 'playlist_count': 0}
            if username:
                creator_stats[username]['playlist_count'] = item['playlist_count']
        
        top_creator_username = None
        max_total = 0
        for username, stats in creator_stats.items():
            total = stats['content_count'] + stats['playlist_count']
            if total > max_total:
                max_total = total
                top_creator_username = username
        
        top_creator = {
            'username': top_creator_username or 'No creator',
            'content_count': creator_stats.get(top_creator_username, {}).get('content_count', 0),
            'playlist_count': creator_stats.get(top_creator_username, {}).get('playlist_count', 0)
        }

        top_users = [
            {'username': 'admin', 'login_count': 42, 'usage_time': '15h 30m'},
            {'username': 'user1', 'login_count': 28, 'usage_time': '9h 45m'},
            {'username': 'user2', 'login_count': 19, 'usage_time': '6h 15m'}
        ]

        context.update({
            'frontend_size': frontend_size,
            'backend_size': backend_size,
            'content_uploads_size': content_uploads_size,
            'playlist_uploads_size': playlist_uploads_size,
            'frontend_percentage': frontend_percentage,
            'backend_percentage': backend_percentage,
            'content_percentage': content_percentage,
            'playlist_percentage': playlist_percentage,
            
            'upcoming_schedules': upcoming_schedules,
            'total_content': total_content,
            'content_active': content_active,
            'content_expired': content_expired,
            'total_playlist': total_playlist,
            'playlist_active': playlist_active,
            'playlist_expired': playlist_expired,
            'total_device': total_device,
            'online_device': online_device,
            'offline_device': offline_device,
            'total_device_group': total_device_group,
            'device_groups': device_groups,
            'top_creator': top_creator,
            'top_users': top_users,
        })
        
        return context
#----------------------------------------------------------#


#------------------------Content---------------------------#
def content_view(request):
    sort = request.GET.get('sort', 'date_modified')
    order = request.GET.get('order', 'desc')
    query = request.GET.get('q', '')

    sort_field = f"-{sort}" if order == "desc" else sort

    now = timezone.localtime(timezone.now())

    contents = Content.objects.select_related('device', 'device__group').filter(
        models.Q(expiration_date__isnull=True) | 
        models.Q(expiration_date__gt=now)
    )
    
    if query:
        contents = contents.filter(content_name__icontains=query)

    contents = contents.order_by(sort_field)

    context = {
        'contents': contents,
        'sort': sort,
        'order': order,
        'request': request,
        'now': now, 
        'table_config': {
            'show_image': True,
            'show_name': True,
            'show_details': True,
            'show_device': True,
            'show_date': True,
            'show_creator': True,
            'show_expiration': True,
        }
    }
    return render(request, 'content/content_page.html', context)

def content_recycle_bin_view(request):
    sort = request.GET.get('sort', 'date_modified')
    order = request.GET.get('order', 'desc')
    query = request.GET.get('q', '')

    sort_field = f"-{sort}" if order == "desc" else sort

    now = timezone.localtime(timezone.now())

    contents = Content.objects.select_related('device', 'device__group').filter(
        expiration_date__isnull=False,
        expiration_date__lte=now
    )
    
    if query:
        contents = contents.filter(content_name__icontains=query)

    contents = contents.order_by(sort_field)

    context = {
        'contents': contents,
        'sort': sort,
        'order': order,
        'request': request,
        'now': now,
        'table_config': {
            'show_image': True,
            'show_name': True,
            'show_details': True,
            'show_device': True,
            'show_date': True,
            'show_creator': True,
            'show_expiration': False,
        }
    }
    return render(request, 'content/recycle_bin_page.html', context)

class UploadContent(View):
    form_class = ContentForm
    template_name = 'content/upload_page.html'
    
    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, {'form': self.form_class()})
    
    def post(self, request, *args, **kwargs):
        import logging
        logger = logging.getLogger(__name__)
        
        form = self.form_class(request.POST, request.FILES)
        if form.is_valid():
            try:
                uploaded_file = request.FILES.get('file')
                if uploaded_file:
                    logger.info(f"Processing file upload: {uploaded_file.name}, size: {uploaded_file.size}")
                
                self.validate_file_size(uploaded_file)
                content = form.save(commit=False)
                content.creator = request.user
                
                if uploaded_file:
                    target_resolution = self.get_device_resolution(content.device)
                    logger.info(f"Target resolution: {target_resolution}")
                    
                    processed_file = self.process_file(uploaded_file, target_resolution)
                    
                    if not processed_file:
                        raise ValidationError("File processing returned empty result")
                    
                    processed_file.seek(0)
                    test_content = processed_file.read(1024)
                    if not test_content:
                        raise ValidationError("Processed file appears to be empty")
                    
                    processed_file.seek(0)  
                    content.file = processed_file
                    
                    logger.info(f"File processed successfully: {processed_file.name}")
                
                content.save()
                logger.info(f"Content saved to database with ID: {content.id}")
                
                if content.file and hasattr(content.file, 'url'):
                    logger.info(f"File saved at: {content.file.url}")
                else:
                    logger.error("File was not properly saved")
                    raise ValidationError("File was not properly saved to storage")
                
                messages.success(
                    request, 
                    f'Content "{content.content_name}" has been uploaded successfully!'
                )
                
                return redirect('content')
            
            except ValidationError as e:
                logger.error(f"ValidationError during upload: {str(e)}")
                messages.error(request, str(e))
            except Exception as e:
                logger.error(f"Unexpected error during upload: {str(e)}")
                messages.error(request, f"An unexpected error occurred: {str(e)}")
        else:
            logger.warning(f"Form validation failed: {form.errors}")
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
        
        return render(request, self.template_name, {'form': form})
    
    def get_device_resolution(self, device):
        """Get target resolution from device, with fallback to Full HD"""
        if device and device.resolution and device.resolution != 'Unknown':
            try:
                width, height = map(int, device.resolution.split('x'))
                return (width, height)
            except:
                pass
        
        return (1920, 1080)
    
    def process_file(self, uploaded_file, target_resolution):
        """Process file with resizing and compression based on target resolution"""
        import logging
        logger = logging.getLogger(__name__)
        
        filename = self.generate_filename(uploaded_file.name)
        ext = os.path.splitext(filename)[1].lower()
        
        target_width, target_height = target_resolution
        logger.info(f"Processing file: {uploaded_file.name} -> {filename}, target: {target_width}x{target_height}")
        
        try:
            if ext in ['.jpg', '.jpeg', '.png', '.webp']:
                logger.info("Processing as image")
                result = self.process_image(uploaded_file, filename, target_width, target_height)
                logger.info(f"Image processing completed: {result.name if result else 'None'}")
                return result
            
            elif ext in ['.mp4', '.mov', '.avi', '.webm']:
                logger.info("Processing as video")
                result = self.process_video(uploaded_file, filename, target_width, target_height)
                logger.info(f"Video processing completed: {result.name if result else 'None'}")
                return result
            
            else:
                logger.info("No processing needed for this file type")
                return uploaded_file
                
        except Exception as e:
            logger.error(f"Error in process_file: {str(e)}")
            raise
    
    def generate_filename(self, original_filename):
        """Generate filename according to content_file_path logic"""
        ext = os.path.splitext(original_filename)[1].lower()
        
        if ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
            file_type = 'image'
        elif ext in ['.mp4', '.mov', '.avi', '.webm']:
            file_type = 'video'
        else:
            file_type = 'file'
        
        current_time = timezone.now().strftime("%Y%m%d")
        return f"{file_type}_{current_time}{ext}"
    
    def get_video_quality_settings(self, target_width, target_height):
        """Return highest quality settings for video encoding"""
        if target_width >= 1920 or target_height >= 1080:  
            return {
                'crf': 18,           
                'preset': 'slow',    
                'bitrate': '8000k',  
                'audio_bitrate': '192k',
                'profile': 'high',   
                'tune': 'film'       
            }
        else:  
            return {
                'crf': 16,         
                'preset': 'slow',
                'bitrate': '5000k',
                'audio_bitrate': '192k',
                'profile': 'high',
                'tune': 'film'
            }
    
    def get_image_quality_settings(self, target_width, target_height):
        """Return highest quality settings for images"""
        return {'quality': 100}  
    
    def process_image(self, image_file, new_filename, target_width, target_height):
        """Process image file with resizing (stretch to fill) without cropping"""
        try:
            img = Image.open(image_file)
            
            img = img.resize((target_width, target_height), Image.LANCZOS)
            
            ext = os.path.splitext(new_filename)[1].lower()
            
            if ext == '.png':
                if img.mode not in ('RGBA', 'LA'):
                    img = img.convert('RGBA')
            else:
                if img.mode != 'RGB':
                    img = img.convert('RGB')
            
            output = io.BytesIO()
            
            quality_settings = self.get_image_quality_settings(target_width, target_height)
            
            if ext == '.webp':
                img.save(output, format='WEBP', quality=quality_settings['quality'], lossless=False)
                content_type = 'image/webp'
            elif ext == '.png':
                img.save(output, format='PNG', optimize=True)
                content_type = 'image/png'
            else: 
                img.save(output, format='JPEG', quality=quality_settings['quality'], 
                        progressive=True, optimize=True)
                content_type = 'image/jpeg'
            
            output.seek(0)  
            
            return InMemoryUploadedFile(
                output,
                'ImageField',
                new_filename,
                content_type,
                output.getvalue().__len__(),
                None
            )
            
        except Exception as e:
            raise ValidationError(f"Failed to process image: {str(e)}")

    def process_video(self, video_file, new_filename, target_width, target_height):
        """Process video file with highest quality settings"""
        import logging
        logger = logging.getLogger(__name__)
        
        temp_input = None
        temp_output = None
        
        try:
            ext = os.path.splitext(video_file.name)[1].lower()
            timestamp = str(datetime.now().timestamp()).replace('.', '')
            
            temp_dir = tempfile.gettempdir()
            temp_input = os.path.join(temp_dir, f"input_{timestamp}{ext}")
            temp_output = os.path.join(temp_dir, f"output_{timestamp}.mp4")
            
            logger.info(f"Processing video: {video_file.name}, size: {video_file.size} bytes")
            logger.info(f"Target resolution: {target_width}x{target_height}")
            
            video_file.seek(0)  
            with open(temp_input, 'wb') as dest:
                for chunk in video_file.chunks():
                    dest.write(chunk)
            
            if not os.path.exists(temp_input) or os.path.getsize(temp_input) == 0:
                raise ValidationError("Failed to save input video file")
            
            logger.info(f"Input file saved successfully: {os.path.getsize(temp_input)} bytes")
            
            try:
                probe_command = [
                    'ffprobe', '-v', 'quiet', '-select_streams', 'v:0',
                    '-show_entries', 'stream=width,height', '-of', 'csv=s=x:p=0', temp_input
                ]
                probe_result = subprocess.run(probe_command, capture_output=True, text=True, timeout=30)
                if probe_result.returncode == 0 and 'x' in probe_result.stdout:
                    dimensions = probe_result.stdout.strip().split('x')
                    input_width = int(dimensions[0])
                    input_height = int(dimensions[1])
                    logger.info(f"Input video dimensions: {input_width}x{input_height}")
                else:
                    input_width = input_height = 0
            except Exception as e:
                logger.warning(f"Could not probe video dimensions: {e}")
                input_width = input_height = 0
            
            has_audio = False
            try:
                audio_check = subprocess.run([
                    'ffprobe', '-v', 'quiet', '-select_streams', 'a:0', 
                    '-show_entries', 'stream=codec_name', '-of', 'csv=p=0', temp_input
                ], capture_output=True, text=True, timeout=10)
                
                if audio_check.returncode == 0 and audio_check.stdout.strip():
                    has_audio = True
                    logger.info("Audio track detected")
                else:
                    logger.info("No audio track detected")
            except Exception as e:
                logger.warning(f"Could not check for audio: {e}")
                has_audio = False
            
            even_width = target_width if target_width % 2 == 0 else target_width - 1
            even_height = target_height if target_height % 2 == 0 else target_height - 1
            
            logger.info(f"Adjusted resolution for encoder: {even_width}x{even_height}")
            
            quality_settings = self.get_video_quality_settings(even_width, even_height)
            logger.info(f"Using quality settings: {quality_settings}")
            
            command = [
                'ffmpeg', '-y', '-i', temp_input,
                '-vf', f'scale={even_width}:{even_height}:flags=lanczos',  
                '-c:v', 'libx264', 
                '-preset', quality_settings['preset'],
                '-crf', str(quality_settings['crf']),
                '-maxrate', quality_settings['bitrate'],
                '-bufsize', '2M',  
                '-profile:v', quality_settings['profile'],
                '-tune', quality_settings['tune'],
                '-pix_fmt', 'yuv420p',
                '-movflags', '+faststart',
                '-x264-params', 'ref=4:bframes=4:me=umh:subme=7:trellis=1'  
            ]
            
            if has_audio:
                command.extend([
                    '-c:a', 'aac', 
                    '-b:a', quality_settings['audio_bitrate'],
                    '-ar', '48000', 
                    '-ac', '2'       
                ])
            else:
                command.extend(['-an'])  
            
            command.append(temp_output)
            
            logger.info(f"FFmpeg command: {' '.join(command)}")
            
            result = subprocess.run(command, capture_output=True, text=True, timeout=600)  
            
            logger.info(f"FFmpeg return code: {result.returncode}")
            if result.stdout:
                logger.debug(f"FFmpeg stdout: {result.stdout}")
            if result.stderr:
                logger.debug(f"FFmpeg stderr: {result.stderr}")
            
            if result.returncode != 0:
                logger.warning("First attempt failed, trying fallback with medium preset")
                
                fallback_command = [
                    'ffmpeg', '-y', '-i', temp_input,
                    '-vf', f'scale={even_width}:{even_height}',
                    '-c:v', 'libx264', 
                    '-preset', 'medium', 
                    '-crf', '20',        
                    '-pix_fmt', 'yuv420p',
                    '-profile:v', 'high',
                    '-movflags', '+faststart'
                ]
                
                if has_audio:
                    fallback_command.extend(['-c:a', 'aac', '-b:a', '192k'])
                else:
                    fallback_command.extend(['-an'])
                
                fallback_command.append(temp_output)
                
                logger.info(f"Fallback FFmpeg command: {' '.join(fallback_command)}")
                
                fallback_result = subprocess.run(fallback_command, capture_output=True, text=True, timeout=300)
                
                if fallback_result.returncode != 0:
                    error_message = fallback_result.stderr if fallback_result.stderr else "Unknown FFmpeg error"
                    logger.error(f"Fallback FFmpeg failed: {error_message}")
                    raise ValidationError("Video processing failed. The video format may not be supported or the file may be corrupted.")
                
                logger.info("Fallback processing succeeded")
            
            if not os.path.exists(temp_output) or os.path.getsize(temp_output) == 0:
                raise ValidationError("Video processing did not produce a valid output file")
            
            output_size = os.path.getsize(temp_output)
            logger.info(f"Output file created successfully: {output_size} bytes")
            
            with open(temp_output, 'rb') as f:
                file_content = f.read()
            
            if not file_content or len(file_content) < 1000:  # Minimum reasonable file size
                raise ValidationError("Output video file is too small or empty")
            
            new_filename_mp4 = os.path.splitext(new_filename)[0] + '.mp4'
            
            logger.info(f"Creating InMemoryUploadedFile: {new_filename_mp4}, size: {len(file_content)} bytes")
            
            processed_file = InMemoryUploadedFile(
                io.BytesIO(file_content),
                'FileField',
                new_filename_mp4,
                'video/mp4',
                len(file_content),
                None
            )
            
            processed_file.seek(0)
            test_read = processed_file.read(1024) 
            if not test_read:
                raise ValidationError("Created file object is not readable")
            
            processed_file.seek(0)  
            logger.info("Video processing completed successfully")
            
            return processed_file
            
        except subprocess.TimeoutExpired:
            logger.error("Video processing timed out")
            raise ValidationError("Video processing timed out. Please try with a smaller file or shorter duration.")
        except ValidationError:
            raise  
        except Exception as e:
            logger.error(f"Video processing error: {str(e)}")
            raise ValidationError(f"Video processing failed due to an unexpected error. Please try with a different video file.")
        finally:
            for temp_file in [temp_input, temp_output]:
                if temp_file and os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                        logger.info(f"Cleaned up temp file: {temp_file}")
                    except Exception as cleanup_error:
                        logger.warning(f"Failed to cleanup {temp_file}: {cleanup_error}")
                        pass
    
    def validate_file_size(self, uploaded_file):
        """Validate file size doesn't exceed 10MB"""
        if uploaded_file and uploaded_file.size > 10 * 1024 * 1024:  
            raise ValidationError(f"File size exceeds maximum limit of 10MB. Your file: {uploaded_file.size/1024/1024:.1f}MB")

def export_content(request):
    wb = xlwt.Workbook()
    ws = wb.add_sheet('Content List')

    header_style = xlwt.easyxf(
        'font: bold on; pattern: pattern solid, fore_colour gray25; align: horiz center'
    )

    active_style = xlwt.easyxf(
        'pattern: pattern solid, fore_colour light_green'
    )

    expired_style = xlwt.easyxf(
        'pattern: pattern solid, fore_colour red'
    )

    headers = [
        "ID", "Content Name", "File Path", "File Type",
        "File Size", "Supported Device", "Creator",
        "Date Modified", "Expiration Date"
    ]
    for col_num, header in enumerate(headers):
        ws.write(0, col_num, header, header_style)

    contents = Content.objects.select_related('creator', 'device', 'device__group').all()
    now = timezone.now()

    for row_num, content in enumerate(contents, start=1):
        if content.expiration_date is None or content.expiration_date > now:
            row_style = active_style  
        else:
            row_style = expired_style 

        ws.write(row_num, 0, content.id, row_style)
        ws.write(row_num, 1, content.content_name, row_style)
        ws.write(row_num, 2, content.file.url if content.file else "", row_style)
        ws.write(row_num, 3, content.file_type_content(), row_style)
        ws.write(row_num, 4, content.file_size_kb(), row_style)
        ws.write(row_num, 5, content.supported_device, row_style)  
        ws.write(row_num, 6, content.creator.username if content.creator else "-", row_style)
        ws.write(row_num, 7, content.date_modified.strftime('%Y-%m-%d %H:%M'), row_style)
        ws.write(row_num, 8, content.expiration_date.strftime('%Y-%m-%d %H:%M') if content.expiration_date else "-", row_style)

    response = HttpResponse(content_type='application/vnd.ms-excel')
    response['Content-Disposition'] = 'attachment; filename=ContentList.xls'
    wb.save(response)
    return response

def delete_expired_content(request):
    if request.method == 'POST':
        try:
            expired_content = Content.objects.filter(
                expiration_date__isnull=False,
                expiration_date__lt=timezone.now()
            )
            
            deleted_files = 0
            for content in expired_content:
                if content.file and os.path.exists(content.file.path):
                    try:
                        os.remove(content.file.path)
                        deleted_files += 1
                    except Exception as e:
                        logger.error(f"Failed to delete file {content.file.path}: {str(e)}")
                        pass  
            
            deleted_count, _ = expired_content.delete()
            
            if deleted_count > 0:
                messages.success(
                    request, 
                    f'Successfully deleted {deleted_count} expired content items and {deleted_files} associated files.'
                )
            else:
                messages.info(
                    request,
                    'No expired content found to delete.'
                )
                
            return redirect('recycle_bin')
            
        except Exception as e:
            logger.error(f"Error deleting expired content: {str(e)}")
            messages.error(
                request, 
                f'An error occurred while deleting expired content: {str(e)}'
            )
            return redirect('recycle_bin')
            
    else:
        messages.error(request, 'Invalid request method. Please use POST.')
        return redirect('recycle_bin')

def design_view(request):
    """
    View untuk menampilkan halaman design editor dengan daftar device
    """
    devices = Device.objects.select_related('group').all()
    
    return render(request, 'content/design_page.html', {
        'devices': devices
    })

@method_decorator(csrf_exempt, name='dispatch')
class UploadDesign(View):
    
    def post(self, request, *args, **kwargs):
        try:
            design_image_data = request.POST.get('design_image')
            if not design_image_data:
                return JsonResponse({
                    'success': False,
                    'message': 'Missing required parameter: design_image'
                }, status=400)

            device_id = request.POST.get('device_id', '').strip()
            if not device_id:
                return JsonResponse({
                    'success': False,
                    'message': 'Device selection is required. Please select a device.'
                }, status=400)

            try:
                selected_device = Device.objects.get(id=device_id)
            except Device.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'Invalid device selection.'
                }, status=400)

            target_width, target_height = self.get_device_resolution(selected_device)

            processed_image_data = self.validate_image_data(design_image_data)
            
            filename = self.generate_filename('png') 

            processed_file = self.process_design_image(
                processed_image_data, 
                filename, 
                target_width, 
                target_height
            )

            title = request.POST.get('title', '').strip()
            if not title:
                title = f'Design {timezone.now().strftime("%Y%m%d_%H%M%S")}'

            content = Content(
                content_name=title,
                file=processed_file,
                device=selected_device,
                creator=request.user if request.user.is_authenticated else None,
                expiration_date=timezone.now() + timedelta(days=7),
            )
            content.save()

            messages.success(
                request, 
                f'Design "{title}" has been uploaded successfully for {selected_device}!'
            )

            return JsonResponse({
                'success': True,
                'message': 'Design berhasil disimpan!',
                'redirect_url': '/content/',
                'content_id': content.id,
                'file_url': content.file.url,
                'device_info': content.supported_device,
                'processed_dimensions': f"{target_width}x{target_height}"
            })

        except ValidationError as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=400)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f'Design upload error: {str(e)}', exc_info=True)
            
            return JsonResponse({
                'success': False,
                'message': f'Terjadi kesalahan: {str(e)}'
            }, status=500)

    def validate_image_data(self, image_data):
        """Validate and extract base64 image data"""
        if not image_data:
            raise ValidationError("Image data is required")
        
        if ';base64,' in image_data:
            format_part, imgstr = image_data.split(';base64,', 1)
            if 'image/' not in format_part:
                raise ValidationError("Invalid image format")
        else:
            imgstr = image_data

        try:
            file_data = base64.b64decode(imgstr)
        except Exception as e:
            raise ValidationError(f'Invalid image data: {str(e)}')

        max_size = 15 * 1024 * 1024  
        if len(file_data) > max_size:
            raise ValidationError(
                f'File size exceeds maximum limit of 15MB. Your file: {len(file_data)/1024/1024:.1f}MB'
            )

        min_size = 1024 
        if len(file_data) < min_size:
            raise ValidationError("Image file is too small or corrupted")

        return file_data

    def get_device_resolution(self, device):
        """Get target resolution from device, with smart fallbacks"""
        if device and device.resolution and device.resolution != 'Unknown':
            try:
                resolution_str = device.resolution.strip()
                if 'x' in resolution_str:
                    width, height = map(int, resolution_str.split('x'))
                    
                    if 100 <= width <= 7680 and 100 <= height <= 4320:  
                        return (width, height)
                    else:
                        print(f"Warning: Invalid resolution {width}x{height}, using fallback")
                        
            except (ValueError, AttributeError) as e:
                print(f"Warning: Could not parse resolution '{device.resolution}': {e}")
        
        return (1920, 1080) 

    def generate_filename(self, ext):
        """Generate filename for design image with better uniqueness"""
        current_time = timezone.now()
        timestamp = current_time.strftime("%Y%m%d_%H%M%S_%f")[:-3]  
        
        ext = ext.lower()
        if ext in ['jpg', 'jpeg']:
            ext = 'jpg'
        elif ext == 'png':
            ext = 'png'
        else:
            ext = 'png'  
        
        return f"design_{timestamp}.{ext}"

    def get_quality_settings(self, target_width, target_height):
        """Dynamic quality settings based on resolution"""
        total_pixels = target_width * target_height
        
        if total_pixels > 3840 * 2160:  
            return {'quality': 90, 'optimize': True}
        elif total_pixels > 1920 * 1080:  
            return {'quality': 92, 'optimize': True}
        else: 
            return {'quality': 95, 'optimize': True}

    def process_design_image(self, image_data, filename, target_width, target_height):
        """Enhanced image processing for design templates"""
        try:
            img = Image.open(io.BytesIO(image_data))
            
            if img.size[0] < 100 or img.size[1] < 100:
                raise ValidationError("Image dimensions too small (minimum 100x100)")
            
            original_size = img.size
            print(f"Processing image: {original_size[0]}x{original_size[1]} -> {target_width}x{target_height}")
            
            if img.mode not in ('RGBA', 'RGB'):
                if img.mode == 'P':
                    img = img.convert('RGBA')
                else:
                    img = img.convert('RGB')
            
            if img.mode == 'RGBA':
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[-1])  
                img = background
            
            img = img.resize((target_width, target_height), Image.LANCZOS)
            
            if self.should_enhance_image(target_width, target_height):
                img = self.enhance_for_display(img)
            
            quality_settings = self.get_quality_settings(target_width, target_height)
            
            output = io.BytesIO()
            
            img.save(output, format='PNG', optimize=quality_settings['optimize'])
            content_type = 'image/png'
            
            if not filename.lower().endswith('.png'):
                filename = os.path.splitext(filename)[0] + '.png'
            
            output.seek(0)
            
            output_size = len(output.getvalue())
            print(f"Processed image size: {output_size / 1024:.1f}KB")
            
            return ContentFile(
                output.read(),
                name=filename
            )
            
        except Exception as e:
            raise ValidationError(f"Failed to process image: {str(e)}")

    def should_enhance_image(self, width, height):
        """Determine if image should be enhanced based on target display"""
        return width >= 1920 and height >= 1080

    def enhance_for_display(self, img):
        """Apply subtle enhancements for better display visibility"""
        try:
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.05)  
            
            enhancer = ImageEnhance.Sharpness(img)
            img = enhancer.enhance(1.02)  
            
            return img
        except Exception:
            return img

    def get(self, request, *args, **kwargs):
        """Handle GET requests - return method not allowed"""
        return JsonResponse({
            'success': False,
            'message': 'Invalid request method. Only POST requests are allowed.'
        }, status=405)
#----------------------------------------------------------#


#-----------------------Playlist---------------------------#
def playlist_view(request):
    sort = request.GET.get('sort', 'date_modified')
    order = request.GET.get('order', 'desc')
    query = request.GET.get('q', '')

    sort_field = f"-{sort}" if order == 'desc' else sort

    now = timezone.localtime(timezone.now())

    contents = Playlist.objects.select_related('device', 'device__group').filter(
        models.Q(expiration_date__isnull=True) | 
        models.Q(expiration_date__gt=now)
    )
    
    if query:
        contents = contents.filter(playlist_name__icontains=query)

    contents = contents.order_by(sort_field)

    context = {
        'playlists': contents,
        'sort': sort,
        'order': order,
        'request': request,
        'now': now, 
        'table_config': {
            'show_image': True,
            'show_name': True,
            'show_details': True,
            'show_device': True,
            'show_supported_device': True,
            'show_date': True,
            'show_creator': True,
            'show_expiration': True,
        }
    }
    return render(request, 'playlist/playlist_page.html', context)

def playlist_recycle_bin_view(request):
    sort = request.GET.get('sort', 'date_modified')
    order = request.GET.get('order', 'desc')
    query = request.GET.get('q', '')

    sort_field = f"-{sort}" if order == 'desc' else sort

    now = timezone.localtime(timezone.now())

    contents = Playlist.objects.select_related('device', 'device__group').filter(
        expiration_date__isnull=False,
        expiration_date__lte=now
    )
    
    if query:
        contents = contents.filter(playlist_name__icontains=query)

    contents = contents.order_by(sort_field)

    context = {
        'playlists': contents,
        'sort': sort,
        'order': order,
        'request': request,
        'now': now,  
        'table_config': {
            'show_image': True,
            'show_name': True,
            'show_details': True,
            'show_device': True,
            'show_supported_device': True,
            'show_date': True,
            'show_creator': True,
            'show_expiration': False,
        }
    }
    return render(request, 'playlist/recycle_bin_page.html', context)

def export_playlist(request):
    wb = xlwt.Workbook()
    ws = wb.add_sheet('Playlist List')

    header_style = xlwt.easyxf(
        'font: bold on; pattern: pattern solid, fore_colour gray25; align: horiz center'
    )

    active_style = xlwt.easyxf(
        'pattern: pattern solid, fore_colour light_green'
    )

    expired_style = xlwt.easyxf(
        'pattern: pattern solid, fore_colour red'
    )

    headers = [
        "ID", "Playlist Name", "File Path", 
        "Supported Device", "Creator",
        "Date Modified", "Expiration Date"
    ]
    for col_num, header in enumerate(headers):
        ws.write(0, col_num, header, header_style)

    playlists = Playlist.objects.select_related('creator', 'device', 'device__group').all()
    now = timezone.now()

    for row_num, playlist in enumerate(playlists, start=1):
        if playlist.expiration_date is None or playlist.expiration_date > now:
            row_style = active_style  
        else:
            row_style = expired_style  

        ws.write(row_num, 0, playlist.id, row_style)
        ws.write(row_num, 1, playlist.playlist_name, row_style)
        ws.write(row_num, 2, playlist.file.url if playlist.file else "", row_style)
        ws.write(row_num, 3, playlist.supported_device, row_style) 
        ws.write(row_num, 4, playlist.creator.username if playlist.creator else "-", row_style)
        ws.write(row_num, 5, playlist.date_modified.strftime('%Y-%m-%d %H:%M'), row_style)
        ws.write(row_num, 6, playlist.expiration_date.strftime('%Y-%m-%d %H:%M') if playlist.expiration_date else "-", row_style)

    response = HttpResponse(content_type='application/vnd.ms-excel')
    response['Content-Disposition'] = 'attachment; filename=PlaylistList.xls'
    wb.save(response)
    return response

logger = logging.getLogger(__name__)

class UploadPlaylist(View):
    """Handle playlist upload and creation with sequence items"""
    
    CRF_SETTINGS = {
        (640, 480): 18,      
        (1280, 720): 18,    
        (1920, 1080): 18,   
        (2560, 1440): 17,   
        (3840, 2160): 16,  
        (7680, 4320): 15   
    }
    
    def get(self, request):
        """Show upload form with default device=None"""
        contents = Content.objects.all().order_by('-date_modified')
        playlists = Playlist.objects.all().order_by('-date_modified')
        
        context = {
            'form': PlaylistForm(user=request.user, initial={'device': None}),
            'contents': contents,
            'playlists': playlists,
        }
        return render(request, 'playlist/upload_page.html', context)

    def post(self, request):
        """Process form submission without AJAX"""
        form = PlaylistForm(request.POST, request.FILES, user=request.user)
        
        if not form.is_valid():
            messages.error(request, 'Form error: Please correct the fields below.')
            return self._show_upload_form(request, form)
        
        expiration_date = form.cleaned_data.get('expiration_date')
        if expiration_date and expiration_date < timezone.now():
            messages.error(request, 'Expiration date cannot be in the past.')
            return self._show_upload_form(request, form)
        
        sequence_data = self._process_sequences(request)
        if not sequence_data:
            messages.error(request, 'Add at least 1 item to the sequence.')
            return self._show_upload_form(request, form)
        
        try:
            playlist = form.save(commit=False)
            playlist.creator = request.user
            
            target_resolution = self.get_device_resolution(playlist.device)
            
            video_file = self._generate_playlist_video(sequence_data, target_resolution)
            
            filename = self._generate_playlist_filename(playlist.playlist_name)
            playlist.file.save(filename, ContentFile(video_file.read()), save=False)
            
            playlist.save()
            
            messages.success(request, f'Playlist "{playlist.playlist_name}" created successfully!')
            
            return redirect('playlist')
            
        except Exception as e:
            error_msg = f'Error creating playlist: {str(e)}'
            logger.error(f"Playlist creation error: {error_msg}")
            messages.error(request, error_msg)
            return self._show_upload_form(request, form)

    def get_device_resolution(self, device):
        """Get target resolution from device, with fallback to Full HD"""
        if device and device.resolution and device.resolution != 'Unknown':
            try:
                width, height = map(int, device.resolution.split('x'))
                return (width, height)
            except:
                pass
        
        return (1920, 1080)

    def get_crf_for_resolution(self, target_resolution):
        """Get appropriate CRF value for the target resolution"""
        target_width, target_height = target_resolution
        
        for (width, height), crf in self.CRF_SETTINGS.items():
            if target_width <= width and target_height <= height:
                return crf
        
        return 15

    def get_video_quality_settings(self, target_width, target_height):
        """Return highest quality settings for video encoding"""
        if target_width >= 1920 or target_height >= 1080:  
            return {
                'crf': 18,           
                'preset': 'slow',    
                'bitrate': '8000k',  
                'audio_bitrate': '192k',
                'profile': 'high',   
                'tune': 'film'      
            }
        else:  
            return {
                'crf': 16,           
                'preset': 'slow',
                'bitrate': '5000k',
                'audio_bitrate': '192k',
                'profile': 'high',
                'tune': 'film'
            }

    def _show_upload_form(self, request, form=None):
        """Helper: Show form with existing data"""
        contents = Content.objects.all().order_by('-date_modified')
        playlists = Playlist.objects.all().order_by('-date_modified')
        
        context = {
            'form': form if form else PlaylistForm(user=request.user, initial={'device': None}),
            'contents': contents,
            'playlists': playlists,
        }
        return render(request, 'playlist/upload_page.html', context)

    def _process_sequences(self, request):
        """Process all sequence items from the form"""
        sequence_data = []
        
        for i in range(1, 6):  
            sequence_item = self._process_single_sequence(request, i)
            if sequence_item:
                sequence_data.append(sequence_item)
        
        return sequence_data

    def _process_single_sequence(self, request, sequence_num):
        content_id = request.POST.get(f'sequence_{sequence_num}_content_id')
        content_type = request.POST.get(f'sequence_{sequence_num}_content_type')
        
        if not content_id or not content_type:
            return None
        
        try:
            hours = int(request.POST.get(f'sequence_{sequence_num}_duration_hours', 0))
            minutes = int(request.POST.get(f'sequence_{sequence_num}_duration_minutes', 0))
            seconds = int(request.POST.get(f'sequence_{sequence_num}_duration_seconds', 10))
            
            duration = (hours * 3600) + (minutes * 60) + seconds
            
            if content_type == 'content':
                content = Content.objects.get(id=content_id)
                file_path = content.file.path
                content_name = content.content_name
                file_extension = os.path.splitext(file_path)[1].lower()
                is_video = file_extension in ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv']
                
            elif content_type == 'playlist':
                playlist = Playlist.objects.get(id=content_id)
                file_path = playlist.file.path
                content_name = playlist.playlist_name
                is_video = True 
            else:
                return None
            
            if not os.path.exists(file_path):
                return None
            
            return {
                'sequence': sequence_num,
                'content_id': content_id,
                'content_type': content_type,
                'content_name': content_name,
                'duration': duration,
                'file_path': file_path,
                'is_video': is_video
            }
            
        except (ValueError, Content.DoesNotExist, Playlist.DoesNotExist) as e:
            return None

    def _generate_playlist_filename(self, playlist_name):
        """Generate a safe filename for the playlist video"""
        safe_name = "".join(c for c in playlist_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_name = safe_name.replace(' ', '_')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"playlist_{safe_name}_{timestamp}.mp4"

    def _generate_playlist_video(self, sequence_data, target_resolution):
        """Generate the final playlist video with proper resizing and compression"""
        temp_dir = tempfile.mkdtemp()
        concat_list = os.path.join(temp_dir, 'concat_list.txt')
        temp_files = []
        output_path = os.path.join(temp_dir, 'final_output.mp4')
        
        try:
            target_width, target_height = target_resolution
            
            even_width = target_width if target_width % 2 == 0 else target_width - 1
            even_height = target_height if target_height % 2 == 0 else target_height - 1
            
            quality_settings = self.get_video_quality_settings(even_width, even_height)
            target_crf = quality_settings['crf']
            
            with open(concat_list, 'w') as f:
                for item in sequence_data:
                    temp_file = os.path.join(temp_dir, f"temp_{item['sequence']}.mp4")
                    temp_files.append(temp_file)
                    
                    try:
                        self._process_sequence_item(
                            input_path=item['file_path'],
                            output_path=temp_file,
                            duration=item['duration'],
                            is_video=item['is_video'],
                            target_width=even_width,
                            target_height=even_height,
                            quality_settings=quality_settings
                        )
                        f.write(f"file '{temp_file}'\n")
                    except Exception as e:
                        raise Exception(f"Failed to process item {item['content_name']}: {str(e)}")
            
            try:
                self._concatenate_with_compression(
                    concat_list, output_path, 
                    even_width, even_height, quality_settings
                )
            except Exception as e:
                raise Exception(f"Failed to concatenate and compress videos: {str(e)}")
            
            with open(output_path, 'rb') as f:
                file_content = f.read()
            
            if not file_content or len(file_content) < 1000:
                raise Exception("Output video file is too small or empty")
            
            return BytesIO(file_content)
                
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _process_sequence_item(self, input_path, output_path, duration, is_video, target_width, target_height, quality_settings):
        """Process individual sequence item with precise duration control"""
        input_path = os.path.normpath(input_path)
        
        if not os.path.exists(input_path):
            raise Exception(f"Input file not found: {input_path}")
        
        file_extension = os.path.splitext(input_path)[1].lower()
        actual_is_video = file_extension in ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv']
        
        if actual_is_video:
            video_duration = self._get_video_duration(input_path)
            
            if video_duration <= 0:
                raise Exception(f"Could not determine video duration for {input_path}")
            
            if video_duration < duration:
                self._process_short_video(
                    input_path, output_path, duration, video_duration,
                    target_width, target_height, quality_settings
                )
            elif video_duration > duration:
                self._process_long_video(
                    input_path, output_path, duration,
                    target_width, target_height, quality_settings
                )
            else:
                self._process_exact_video(
                    input_path, output_path, duration,
                    target_width, target_height, quality_settings
                )
        else:
            self._process_image(
                input_path, output_path, duration,
                target_width, target_height, quality_settings
            )

    def _process_short_video(self, input_path, output_path, target_duration, video_duration, target_width, target_height, quality_settings):
        """Process video that needs looping to reach target duration"""
        temp_dir = os.path.dirname(output_path)
        loop_file = os.path.join(temp_dir, f"loop_{os.path.basename(output_path)}")
        
        try:
            loops_needed = int(target_duration / video_duration) + 1
            
            cmd_loop = [
                'ffmpeg', '-y',
                '-stream_loop', str(loops_needed - 1),
                '-i', input_path,
                '-c', 'copy',  
                loop_file
            ]
            
            subprocess.run(cmd_loop, check=True, capture_output=True, text=True, timeout=300)
            
            cmd_final = [
                'ffmpeg', '-y', 
                '-i', loop_file,
                '-t', str(target_duration),
                '-vf', f'scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,'
                      f'pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black',
                '-c:v', 'libx264', 
                '-preset', quality_settings['preset'],
                '-crf', str(quality_settings['crf']),
                '-maxrate', quality_settings['bitrate'],
                '-bufsize', '2M',
                '-profile:v', quality_settings['profile'],
                '-tune', quality_settings['tune'],
                '-pix_fmt', 'yuv420p',
                '-movflags', '+faststart',
                '-r', '30',
                output_path
            ]
            
            subprocess.run(cmd_final, check=True, capture_output=True, text=True, timeout=300)
            
        except subprocess.CalledProcessError as e:
            raise Exception(f"FFmpeg loop processing failed: {str(e)} - stderr: {e.stderr}")
        except subprocess.TimeoutExpired:
            raise Exception("Video processing timed out")
        finally:
            if os.path.exists(loop_file):
                os.remove(loop_file)

    def _process_long_video(self, input_path, output_path, target_duration, target_width, target_height, quality_settings):
        """Process video that needs cutting to reach target duration"""
        cmd = [
            'ffmpeg', '-y', 
            '-i', input_path,
            '-t', str(target_duration),
            '-vf', f'scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,'
                  f'pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black',
            '-c:v', 'libx264', 
            '-preset', quality_settings['preset'],
            '-crf', str(quality_settings['crf']),
            '-maxrate', quality_settings['bitrate'],
            '-bufsize', '2M',
            '-profile:v', quality_settings['profile'],
            '-tune', quality_settings['tune'],
            '-pix_fmt', 'yuv420p',
            '-movflags', '+faststart',
            '-r', '30',
            output_path
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=300)
        except subprocess.CalledProcessError as e:
            raise Exception(f"FFmpeg cutting failed: {str(e)} - stderr: {e.stderr}")
        except subprocess.TimeoutExpired:
            raise Exception("Video processing timed out")

    def _process_exact_video(self, input_path, output_path, target_duration, target_width, target_height, quality_settings):
        """Process video with exact duration match"""
        cmd = [
            'ffmpeg', '-y', 
            '-i', input_path,
            '-vf', f'scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,'
                  f'pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black',
            '-c:v', 'libx264', 
            '-preset', quality_settings['preset'],
            '-crf', str(quality_settings['crf']),
            '-maxrate', quality_settings['bitrate'],
            '-bufsize', '2M',
            '-profile:v', quality_settings['profile'],
            '-tune', quality_settings['tune'],
            '-pix_fmt', 'yuv420p',
            '-movflags', '+faststart',
            '-r', '30',
            output_path
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=300)
        except subprocess.CalledProcessError as e:
            raise Exception(f"FFmpeg exact processing failed: {str(e)} - stderr: {e.stderr}")
        except subprocess.TimeoutExpired:
            raise Exception("Video processing timed out")

    def _process_image(self, input_path, output_path, duration, target_width, target_height, quality_settings):
        """Process static image with exact duration"""
        cmd = [
            'ffmpeg', '-y', 
            '-loop', '1', 
            '-i', input_path,
            '-t', str(duration),
            '-vf', f'scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,'
                  f'pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black',
            '-c:v', 'libx264', 
            '-preset', quality_settings['preset'],
            '-crf', str(quality_settings['crf']),
            '-maxrate', quality_settings['bitrate'],
            '-pix_fmt', 'yuv420p',
            '-movflags', '+faststart',
            '-r', '30',
            output_path
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=300)
        except subprocess.CalledProcessError as e:
            raise Exception(f"FFmpeg image processing failed: {str(e)} - stderr: {e.stderr}")
        except subprocess.TimeoutExpired:
            raise Exception("Image processing timed out")

    def _get_video_duration(self, video_path):
        """Get video duration in seconds using FFprobe"""
        try:
            cmd = [
                'ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1', video_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
            return float(result.stdout.strip())
        except (subprocess.CalledProcessError, ValueError, subprocess.TimeoutExpired):
            return 0

    def _concatenate_with_compression(self, concat_list, output_path, target_width, target_height, quality_settings):
        """Concatenate videos with optimized compression settings"""
        temp_concat = output_path.replace('.mp4', '_temp_concat.mp4')
        
        try:
            cmd_concat = [
                'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
                '-i', concat_list, '-c', 'copy', temp_concat
            ]
            
            subprocess.run(cmd_concat, check=True, capture_output=True, text=True, timeout=300)
            
            cmd_compress = [
                'ffmpeg', '-y', '-i', temp_concat,
                '-vf', f'scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,'
                      f'pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black',
                '-c:v', 'libx264', 
                '-preset', quality_settings['preset'],
                '-crf', str(quality_settings['crf']),
                '-maxrate', quality_settings['bitrate'],
                '-bufsize', '2M',
                '-pix_fmt', 'yuv420p',
                '-movflags', '+faststart',
                '-c:a', 'aac', 
                '-b:a', quality_settings['audio_bitrate'],
                '-ar', '48000',
                '-ac', '2',
                '-r', '30',
                '-profile:v', quality_settings['profile'],
                '-tune', quality_settings['tune'],
                output_path
            ]
            
            subprocess.run(cmd_compress, check=True, capture_output=True, text=True, timeout=600)
            
        except subprocess.CalledProcessError as e:
            raise Exception(f"Concatenation/compression failed: {e.stderr}")
        except subprocess.TimeoutExpired:
            raise Exception("Concatenation processing timed out")
        finally:
            if os.path.exists(temp_concat):
                os.remove(temp_concat)
                
def content_playlist_combined_view(request):
    """API endpoint for combined content and playlist data"""
    try:
        sort = request.GET.get('sort', 'date_modified')
        order = request.GET.get('order', 'desc')
        query = request.GET.get('q', '')
        
        sort_field = f"-{sort}" if order == "desc" else sort
        
        contents = Content.objects.select_related('device', 'device__group').all()
        playlists = Playlist.objects.select_related('device', 'device__group').all()
        
        if query:
            contents = contents.filter(content_name__icontains=query)
            playlists = playlists.filter(playlist_name__icontains=query)
        
        context = {
            'contents': contents.order_by(sort_field),
            'playlists': playlists.order_by(sort_field),
            'sort': sort,
            'order': order,
            'request': request,
        }
        
        return render(request, 'playlist/components/content_list.html', context)
    
    except Exception as e:
        print(f"Error in content_playlist_combined_view: {str(e)}")
        return render(request, 'playlist/components/content_list.html', {
            'contents': [],
            'playlists': [],
            'request': request,
        })

def delete_expired_playlists(request):
    if request.method == 'POST':
        try:
            expired_playlists = Playlist.objects.filter(
                expiration_date__isnull=False,
                expiration_date__lt=timezone.now()
            )
            
            deleted_files = 0
            for playlist in expired_playlists:
                if playlist.file and os.path.exists(playlist.file.path):
                    try:
                        os.remove(playlist.file.path)
                        deleted_files += 1
                    except Exception as e:
                        logger.error(f"Failed to delete file {playlist.file.path}: {str(e)}")
                        pass          
            
            deleted_count, _ = expired_playlists.delete()
            
            if deleted_count > 0:
                messages.success(
                    request, 
                    f'Successfully deleted {deleted_count} expired playlists and {deleted_files} associated files.'
                )
            else:
                messages.info(
                    request,
                    'No expired playlists found to delete.'
                )
                
            return redirect('playlist_recycle_bin')
            
        except Exception as e:
            logger.error(f"Error deleting expired playlists: {str(e)}")
            messages.error(
                request, 
                f'An error occurred while deleting expired playlists: {str(e)}'
            )
            return redirect('playlist_recycle_bin')
            
    else:
        messages.error(request, 'Invalid request method.')
        return redirect('playlist_recycle_bin')
#----------------------------------------------------------#


#-----------------------Schedules--------------------------#
logger = logging.getLogger(__name__)

class SchedulesView(View):
    template_name = 'schedules/schedules_page.html'

    def get(self, request):
        if request.GET.get('action') == 'calendar':
            return self.get_calendar_data(request)

        today = timezone.localtime(timezone.now()).date()
        now = timezone.localtime(timezone.now()).time()

        group_filter = request.GET.get('group', '')
        
        todays_schedules = Schedule.objects.filter(
            playback_date=today,
            publish_status='Published',
            playback_end__gte=now  
        )
        
        if group_filter:
            group_ids = [int(id) for id in group_filter.split(',') if id.isdigit()]
            todays_schedules = todays_schedules.filter(
                publish_to__group__id__in=group_ids
            ).distinct()
        
        todays_schedules = todays_schedules.order_by('playback_start')

        current_schedule = None
        for schedule in todays_schedules:
            if schedule.playback_start and schedule.playback_end:
                if schedule.playback_start <= now <= schedule.playback_end:
                    current_schedule = schedule
                    break

        schedules_to_display = []
        if current_schedule:
            try:
                idx = list(todays_schedules).index(current_schedule)
                schedules_to_display = list(todays_schedules)[idx:idx+10]
            except ValueError:
                schedules_to_display = list(todays_schedules)[:10]
        else:
            schedules_to_display = list(todays_schedules)[:10]

        current_media_url = None
        current_media_type = None
        if current_schedule:
            if current_schedule.is_content and current_schedule.content and current_schedule.content.file:
                current_media_url = current_schedule.content.file.url
                current_media_type = current_schedule.content.file_type_content().lower()
            elif current_schedule.is_playlist and current_schedule.playlist and current_schedule.playlist.file:
                current_media_url = current_schedule.playlist.file.url
                current_media_type = current_schedule.playlist.file_type_playlist().lower()

        all_schedules = list(todays_schedules)
        current_index = 0
        if current_schedule:
            try:
                current_index = all_schedules.index(current_schedule)
            except ValueError:
                current_index = 0

        calendar_data = self.get_monthly_schedules(today.year, today.month)

        device_groups_with_schedules = DeviceGroup.objects.annotate(
            actual_schedule_count=Count('devices__published_schedules', distinct=True)
        ).filter(actual_schedule_count__gt=0).order_by('name')

        context = {
            'todays_schedules': schedules_to_display,  
            'current_schedule': current_schedule,
            'current_media_url': current_media_url,
            'current_media_type': current_media_type,
            'current_index': current_index,
            'total_schedules': len(all_schedules),
            'today': today,
            'now': now,
            'calendar_data': json.dumps(calendar_data),
            'device_groups_with_schedules': device_groups_with_schedules,
            'active_group_filter': group_filter,
        }
        return render(request, self.template_name, context)

    
    def get_calendar_data(self, request):
        """AJAX endpoint for calendar data"""
        try:
            year = int(request.GET.get('year', timezone.now().year))
            month = int(request.GET.get('month', timezone.now().month))
            
            group_filter = request.GET.get('group', '')
            
            calendar_data = self.get_monthly_schedules(year, month, group_filter)
            
            return JsonResponse({
                'status': 'success',
                'schedules': calendar_data['schedules']
            })
        except Exception as e:
            logger.error(f"Error getting calendar data: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)
    
    def get_monthly_schedules(self, year, month, group_filter=None):
        """Get all schedules for a specific month with optional device group filter"""
        first_day = date(year, month, 1)
        if month == 12:
            last_day = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = date(year, month + 1, 1) - timedelta(days=1)
        
        schedules = Schedule.objects.filter(
            playback_date__gte=first_day,
            playback_date__lte=last_day,
            publish_status='Published'
        )
        
        if group_filter:
            group_ids = [int(id) for id in group_filter.split(',') if id.isdigit()]
            schedules = schedules.filter(
                publish_to__group__id__in=group_ids
            ).distinct()
        
        schedules = schedules.order_by('playback_date', 'playback_start')
        
        schedules_data = []
        for schedule in schedules:
            schedule_data = {
                'id': schedule.id,
                'schedule_name': schedule.schedule_name,
                'playback_date': schedule.playback_date.isoformat(),
                'playback_start': schedule.playback_start.strftime('%H:%M') if schedule.playback_start else None,
                'playback_end': schedule.playback_end.strftime('%H:%M') if schedule.playback_end else None,
                'publish_status': schedule.publish_status,
            }
            
            if schedule.is_content and schedule.content and schedule.content.file:
                schedule_data['media_url'] = schedule.content.file.url
                schedule_data['media_type'] = schedule.content.file_type_content().lower()
            elif schedule.is_playlist and schedule.playlist and schedule.playlist.file:
                schedule_data['media_url'] = schedule.playlist.file.url
                schedule_data['media_type'] = schedule.playlist.file_type_playlist().lower()
            else:
                schedule_data['media_url'] = None
                schedule_data['media_type'] = None
            
            schedules_data.append(schedule_data)
        
        return {
            'year': year,
            'month': month,
            'schedules': schedules_data
        }
    
    def get_schedules_by_date(self, request):
        """Get all schedules for a specific date with device group filter"""
        try:
            date_str = request.GET.get('date')
            if not date_str:
                return JsonResponse({'status': 'error', 'message': 'Date parameter required'}, status=400)
            
            group_filter = request.GET.get('group', '')
            
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            schedules = Schedule.objects.filter(
                playback_date=target_date,
                publish_status='Published'
            )
            
            if group_filter:
                group_ids = [int(id) for id in group_filter.split(',') if id.isdigit()]
                schedules = schedules.filter(
                    publish_to__group__id__in=group_ids
                ).distinct()
            
            schedules = schedules.order_by('playback_start')
            
            schedules_data = []
            for schedule in schedules:
                schedule_data = {
                    'id': schedule.id,
                    'schedule_name': schedule.schedule_name,
                    'playback_date': schedule.playback_date.isoformat(),
                    'playback_start': schedule.playback_start.strftime('%H:%M') if schedule.playback_start else None,
                    'playback_end': schedule.playback_end.strftime('%H:%M') if schedule.playback_end else None,
                    'publish_status': schedule.publish_status,
                }
                
                if schedule.is_content and schedule.content and schedule.content.file:
                    schedule_data['media_url'] = schedule.content.file.url
                    schedule_data['media_type'] = schedule.content.file_type_content().lower()
                elif schedule.is_playlist and schedule.playlist and schedule.playlist.file:
                    schedule_data['media_url'] = schedule.playlist.file.url
                    schedule_data['media_type'] = schedule.playlist.file_type_playlist().lower()
                else:
                    schedule_data['media_url'] = None
                    schedule_data['media_type'] = None
                
                schedules_data.append(schedule_data)
            
            return JsonResponse({
                'status': 'success',
                'schedules': schedules_data
            })
            
        except ValueError as e:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid date format. Use YYYY-MM-DD'
            }, status=400)
        except Exception as e:
            logger.error(f"Error getting schedules by date: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)
    
    def post(self, request):
        action = request.POST.get('action')
        
        if action == 'delete':
            return self.delete_schedule(request)
        elif action == 'update':
            return self.update_schedule(request)
        elif action == 'navigate':
            return self.navigate_schedule(request)
        elif action == 'skip':
            return self.skip_schedule(request)
        elif action == 'fullscreen':
            return self.get_fullscreen_content(request)
        elif action == 'get_day_schedules':
            return self.get_day_schedules(request)
        else:
            return JsonResponse({'status': 'error', 'message': 'Invalid action'})
    
    def get_day_schedules(self, request):
        """Get all schedules for a specific day (for day modal) with device group filter"""
        try:
            date_str = request.POST.get('date')
            if not date_str:
                return JsonResponse({'status': 'error', 'message': 'Date parameter required'}, status=400)
            
            group_filter = request.POST.get('group', '')
            
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            schedules = Schedule.objects.filter(
                playback_date=target_date,
                publish_status='Published'
            )
            
            if group_filter:
                group_ids = [int(id) for id in group_filter.split(',') if id.isdigit()]
                schedules = schedules.filter(
                    publish_to__group__id__in=group_ids
                ).distinct()
            
            schedules = schedules.order_by('playback_start')
            
            schedules_data = []
            for schedule in schedules:
                schedule_data = {
                    'id': schedule.id,
                    'schedule_name': schedule.schedule_name,
                    'playback_start': schedule.playback_start.strftime('%H:%M') if schedule.playback_start else '',
                    'playback_end': schedule.playback_end.strftime('%H:%M') if schedule.playback_end else '',
                }
                schedules_data.append(schedule_data)
            
            return JsonResponse({
                'status': 'success',
                'schedules': schedules_data
            })
            
        except ValueError as e:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid date format. Use YYYY-MM-DD'
            }, status=400)
        except Exception as e:
            logger.error(f"Error getting day schedules: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)
    
    def navigate_schedule(self, request):
        """Handle previous/next navigation with device group filter"""
        try:
            direction = request.POST.get('direction')  # 'prev' or 'next'
            current_index = int(request.POST.get('current_index', 0))
            
            today = timezone.localtime(timezone.now()).date()
            now = timezone.localtime(timezone.now()).time()
            
            group_filter = request.POST.get('group', '')
            
            todays_schedules = Schedule.objects.filter(
                playback_date=today,
                publish_status='Published',
                playback_end__gte=now
            )
            
            if group_filter:
                group_ids = [int(id) for id in group_filter.split(',') if id.isdigit()]
                todays_schedules = todays_schedules.filter(
                    publish_to__group__id__in=group_ids
                ).distinct()
            
            todays_schedules = list(todays_schedules.order_by('playback_start'))
            
            if not todays_schedules:
                return JsonResponse({'status': 'error', 'message': 'No schedules available'})
            
            if direction == 'prev':
                new_index = max(0, current_index - 1)
            elif direction == 'next':
                new_index = min(len(todays_schedules) - 1, current_index + 1)
            else:
                return JsonResponse({'status': 'error', 'message': 'Invalid direction'})
            
            target_schedule = todays_schedules[new_index]
            
            media_url = None
            media_type = None
            
            if target_schedule.is_content and target_schedule.content and target_schedule.content.file:
                media_url = target_schedule.content.file.url
                media_type = target_schedule.content.file_type_content().lower()
            elif target_schedule.is_playlist and target_schedule.playlist and target_schedule.playlist.file:
                media_url = target_schedule.playlist.file.url
                media_type = target_schedule.playlist.file_type_playlist().lower()
            
            return JsonResponse({
                'status': 'success',
                'schedule': {
                    'id': target_schedule.id,
                    'name': target_schedule.schedule_name,
                    'start_time': target_schedule.playback_start.strftime('%H:%M') if target_schedule.playback_start else '',
                    'end_time': target_schedule.playback_end.strftime('%H:%M') if target_schedule.playback_end else '',
                    'media_url': media_url,
                    'media_type': media_type,
                },
                'new_index': new_index,
                'total_schedules': len(todays_schedules)
            })
            
        except Exception as e:
            logger.error(f"Error navigating schedule: {str(e)}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    
    def skip_schedule(self, request):
        """Handle skip functionality without confirmation"""
        try:
            schedule_id = request.POST.get('schedule_id')
            schedule = get_object_or_404(Schedule, id=schedule_id)
            
            today = timezone.localtime(timezone.now()).date()
            
            if schedule.playback_date != today:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Cannot skip schedule from another day'
                }, status=400)
            
            todays_schedules = Schedule.objects.filter(
                playback_date=today,
                publish_status='Published'
            ).exclude(id=schedule_id).order_by('playback_end')
            
            if not todays_schedules.exists():
                return JsonResponse({
                    'status': 'error',
                    'message': 'No other schedules to compare with'
                }, status=400)
            
            last_schedule = todays_schedules.last()
            
            if schedule.playback_start and schedule.playback_end and last_schedule.playback_end:
                current_duration = datetime.combine(today, schedule.playback_end) - datetime.combine(today, schedule.playback_start)
                
                new_start_time = (datetime.combine(today, last_schedule.playback_end) + timedelta(minutes=1)).time()
                new_end_time = (datetime.combine(today, new_start_time) + current_duration).time()
                
                conflicting_schedules = Schedule.objects.filter(
                    playback_date=today,
                    publish_status='Published',
                    playback_start__lt=new_end_time,
                    playback_end__gt=new_start_time
                ).exclude(id=schedule_id)
                
                if conflicting_schedules.exists():
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Cannot skip - would conflict with existing schedules'
                    }, status=400)
                
                schedule.playback_start = new_start_time
                schedule.playback_end = new_end_time
                schedule.save()
                
                return JsonResponse({'status': 'success'})
            else:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Schedule or last schedule missing time information'
                }, status=400)
                
        except Exception as e:
            logger.error(f"Error skipping schedule: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)
    
    def get_fullscreen_content(self, request):
        """Get content URL for fullscreen display"""
        try:
            schedule_id = request.POST.get('schedule_id')
            schedule = get_object_or_404(Schedule, id=schedule_id)
            
            media_url = None
            media_type = None
            
            if schedule.is_content and schedule.content and schedule.content.file:
                media_url = schedule.content.file.url
                media_type = schedule.content.file_type_content().lower()
            elif schedule.is_playlist and schedule.playlist and schedule.playlist.file:
                media_url = schedule.playlist.file.url
                media_type = schedule.playlist.file_type_playlist().lower()
            
            if media_url:
                return JsonResponse({
                    'status': 'success',
                    'media_url': media_url,
                    'media_type': media_type,
                    'schedule_name': schedule.schedule_name
                })
            else:
                return JsonResponse({'status': 'error'}, status=400)
                
        except Exception as e:
            logger.error(f"Error getting fullscreen content: {str(e)}")
            return JsonResponse({'status': 'error'}, status=400)
    
    def delete_schedule(self, request):
        """Delete a schedule without confirmation"""
        try:
            schedule_id = request.POST.get('schedule_id')
            schedule = get_object_or_404(Schedule, id=schedule_id)
            schedule.delete()
            return JsonResponse({'status': 'success'})
        except Exception as e:
            logger.error(f"Error deleting schedule: {str(e)}")
            return JsonResponse({'status': 'error'}, status=400)
    
    def update_schedule(self, request):
        """Update schedule without notifications"""
        try:
            schedule_id = request.POST.get('schedule_id')
            schedule = get_object_or_404(Schedule, id=schedule_id)
            
            schedule.schedule_name = request.POST.get('schedule_name', schedule.schedule_name)
            
            playback_date = request.POST.get('playback_date')
            if playback_date:
                schedule.playback_date = datetime.strptime(playback_date, '%Y-%m-%d').date()
            
            playback_start = request.POST.get('playback_start')
            if playback_start:
                schedule.playback_start = datetime.strptime(playback_start, '%H:%M').time()
            
            playback_end = request.POST.get('playback_end')
            if playback_end:
                schedule.playback_end = datetime.strptime(playback_end, '%H:%M').time()
            
            if schedule.playback_start and schedule.playback_end:
                if schedule.playback_start >= schedule.playback_end:
                    return JsonResponse({
                        'status': 'error', 
                        'message': 'Start time must be earlier than end time'
                    }, status=400)
            
            schedule.save()
            return JsonResponse({'status': 'success'})
        
        except Exception as e:
            logger.error(f"Error updating schedule: {str(e)}")
            return JsonResponse({'status': 'error'}, status=400)

logger = logging.getLogger(__name__)

class SchedulesRecycleBinView(View):
    template_name = 'schedules/recycle_bin_page.html'
    
    def get_filter_description(self, type_filter, group_filter, query):
        descriptions = []
        
        if type_filter:
            types = type_filter.split(',')
            type_names = {
                'Today': 'Today',
                'Daily': 'Daily',
                'Weekly': 'Weekly',
                'Monthly': 'Monthly',
                'Never Expire': 'Never Expire',
                'Expired': 'Expired'
            }
            descriptions.append(f"Type: {', '.join([type_names.get(t, t) for t in types])}")
        
        if group_filter:
            group_ids = group_filter.split(',')
            group_names = DeviceGroup.objects.filter(id__in=group_ids).values_list('name', flat=True)
            descriptions.append(f"Groups: {', '.join(group_names)}")
        
        if query:
            descriptions.append(f"Search: '{query}'")
        
        if not descriptions:
            return "All schedules"
        
        return " | ".join(descriptions)
    
    def get_current_filters(self, request):
        """Get current filters from either GET parameters or session"""
        if request.method == 'GET':
            return {
                'type': request.GET.get('type', ''),
                'group': request.GET.get('group', ''),
                'q': request.GET.get('q', ''),
                'sort': request.GET.get('sort', '-created_at'),
                'order': request.GET.get('order', 'desc')
            }
        return request.session.get('schedule_filter_params', {})
    
    def apply_filters(self, queryset, filters):
        """Apply all filters to the queryset"""
        today = timezone.localtime(timezone.now()).date()
        
        if filters.get('type'):
            types = filters['type'].split(',')
            type_filters = Q()
            
            if 'Today' in types:
                type_filters |= Q(playback_date=today)
            if 'Daily' in types:
                type_filters |= Q(schedule_type='Daily')
            if 'Weekly' in types:
                type_filters |= Q(schedule_type='Weekly')
            if 'Monthly' in types:
                type_filters |= Q(schedule_type='Monthly')
            if 'Never Expire' in types:
                type_filters |= Q(never_expire=True)
            if 'Expired' in types:
                type_filters |= Q(playback_date__lt=today, never_expire=False)
                
            queryset = queryset.filter(type_filters)
        
        if filters.get('group'):
            group_ids = [int(id) for id in filters['group'].split(',') if id.isdigit()]
            queryset = queryset.filter(
                publish_to__group__id__in=group_ids
            ).distinct()
        
        if filters.get('q'):
            query = filters['q']
            queryset = queryset.filter(
                Q(schedule_name__icontains=query) | 
                Q(schedule_type__icontains=query)
            )
        
        sort = filters.get('sort', '-created_at')
        order = filters.get('order', 'desc')
        if sort:
            sort_field = sort.lstrip('-')
            if order == 'desc' and not sort.startswith('-'):
                sort_field = f"-{sort_field}"
            elif order == 'asc' and sort.startswith('-'):
                sort_field = sort_field
            queryset = queryset.order_by(sort_field)
        
        return queryset
    
    def get_queryset(self, request):
        """Get the filtered queryset based on current request"""
        filters = self.get_current_filters(request)
        queryset = Schedule.objects.all().distinct()
        return self.apply_filters(queryset, filters)
    
    def get_context_data(self, request, queryset):
        """Prepare context data for template rendering"""
        today = timezone.localtime(timezone.now()).date()
        filters = self.get_current_filters(request)
        
        device_groups_with_schedules = DeviceGroup.objects.annotate(
            actual_schedule_count=Count('devices__published_schedules', distinct=True)
        ).filter(actual_schedule_count__gt=0).order_by('name')
        
        try:
            contents = Content.objects.all().order_by('-date_modified')
            playlists = Playlist.objects.all().order_by('-date_modified')
        except Exception as e:
            logger.error(f"Error fetching content/playlists: {str(e)}")
            contents = []
            playlists = []

        return {
            'schedules': queryset,
            'contents': contents,
            'playlists': playlists,
            'device_groups_with_schedules': device_groups_with_schedules,
            'query': filters.get('q', ''),
            'sort': filters.get('sort', '-created_at').lstrip('-'),
            'order': filters.get('order', 'desc'),
            'today': today,
            'is_recycle_bin': True,
            'table_config': {
                'show_name': True,
                'show_type': True,
                'show_status': True,
                'show_content': True,
                'show_date': True,
                'show_time': True,
                'show_repeat': True,
                'show_groups': True,
                'show_description': True,
                'show_updated': True,
            },
            'active_filters': {
                'types': filters.get('type', '').split(',') if filters.get('type') else [],
                'groups': filters.get('group', '').split(',') if filters.get('group') else [],
            },
            'current_filter_description': self.get_filter_description(
                filters.get('type', ''),
                filters.get('group', ''),
                filters.get('q', '')
            )
        }
    
    def get(self, request, *args, **kwargs):
        """Handle GET requests"""
        request.session['schedule_filter_params'] = self.get_current_filters(request)
        
        queryset = self.get_queryset(request)
        context = self.get_context_data(request, queryset)
        return render(request, self.template_name, context)
    
    def post(self, request, *args, **kwargs):
        """Handle POST requests (delete action)"""
        if 'delete_action' in request.POST:
            filters = request.session.get('schedule_filter_params', {})
            
            queryset = Schedule.objects.all().distinct()
            queryset = self.apply_filters(queryset, filters)
            
            delete_count = queryset.count()
            
            if delete_count > 0:
                try:
                    deleted_count, _ = queryset.delete()
                    messages.success(request, f'Successfully deleted {deleted_count} schedules from recycle bin.')
                    logger.info(f"User {request.user} deleted {deleted_count} schedules from recycle bin")
                except Exception as e:
                    messages.error(request, f'Error deleting schedules: {str(e)}')
                    logger.error(f"Error deleting schedules: {str(e)}")
            else:
                messages.warning(request, 'No schedules found matching current filters to delete.')
            
            return redirect('schedules_recycle_bin')
        
        messages.error(request, 'Invalid delete action.')
        return redirect('schedules_recycle_bin')

def export_schedule(request):
    wb = xlwt.Workbook()
    ws = wb.add_sheet('Schedule List')

    header_style = xlwt.easyxf(
        'font: bold on; pattern: pattern solid, fore_colour gray25; align: horiz center'
    )

    active_style = xlwt.easyxf(
        'pattern: pattern solid, fore_colour light_green'
    )

    expired_style = xlwt.easyxf(
        'pattern: pattern solid, fore_colour red'
    )

    draft_style = xlwt.easyxf(
        'pattern: pattern solid, fore_colour yellow'
    )

    headers = [
        "ID", "Schedule Name", "Schedule Type", "Status",
        "Content/Playlist", "Content Title", "Playlist Name",
        "Playback Date", "Never Expire", "Repeat",
        "Playback Start", "Playback End", "Devices",
        "Description", "Created At", "Updated At"
    ]
    
    for col_num, header in enumerate(headers):
        ws.write(0, col_num, header, header_style)

    column_widths = [
        2000,  
        5000,  
        4000,  
        3000,  
        4000,  
        5000,  
        5000,  
        4000,  
        3000,  
        3000,  
        4000,  
        4000,  
        6000,  
        6000,  
        5000,  
        5000  
    ]
    
    for col_num, width in enumerate(column_widths):
        ws.col(col_num).width = width

    today = timezone.now().date()
    current_time = timezone.now().time()

    active_schedules = Schedule.objects.filter(
        Q(never_expire=True) |
        Q(playback_date__gt=today) |
        Q(playback_date=today, playback_end__gte=current_time)
    ).select_related('content', 'playlist').prefetch_related('publish_to').order_by('playback_date', 'playback_start', 'playback_end')

    expired_schedules = Schedule.objects.filter(
        Q(never_expire=False) &
        (Q(playback_date__lt=today) |
         Q(playback_date=today, playback_end__lt=current_time))
    ).select_related('content', 'playlist').prefetch_related('publish_to').order_by('playback_date', 'playback_start', 'playback_end')

    schedules = list(active_schedules) + list(expired_schedules)
    
    for row_num, schedule in enumerate(schedules, start=1):
        if schedule.publish_status == 'Draft':
            row_style = draft_style
        elif schedule.never_expire or (schedule.playback_date and 
             (schedule.playback_date > today or 
              (schedule.playback_date == today and 
               (not schedule.playback_end or schedule.playback_end >= current_time)))):
            row_style = active_style
        else:
            row_style = expired_style

        content_playlist_type = ""
        content_title = str(schedule.content.id) if schedule.content else "-"
        playlist_name = str(schedule.playlist.id) if schedule.playlist else "-"
        
        if schedule.content:
            content_playlist_type = "Content"
            content_title = (
                getattr(schedule.content, 'title', None) or
                getattr(schedule.content, 'name', None) or
                f"Content-{schedule.content.id}"
            )
        
        if schedule.playlist:
            content_playlist_type = "Playlist" if not content_playlist_type else "Both"
            playlist_name = (
                getattr(schedule.playlist, 'name', None) or
                getattr(schedule.playlist, 'title', None) or
                f"Playlist-{schedule.playlist.id}"
            )
        
        playback_date = schedule.playback_date.strftime("%Y-%m-%d") if schedule.playback_date else "-"
        playback_start = schedule.playback_start.strftime("%H:%M:%S") if schedule.playback_start else "-"
        playback_end = schedule.playback_end.strftime("%H:%M:%S") if schedule.playback_end else "-"
        created_at = schedule.created_at.strftime("%Y-%m-%d %H:%M:%S")
        updated_at = schedule.updated_at.strftime("%Y-%m-%d %H:%M:%S")
        devices = ", ".join([d.name or f"Device-{d.id}" for d in schedule.publish_to.all()]) if schedule.publish_to.exists() else "-"
        
        ws.write(row_num, 0, schedule.id, row_style)
        ws.write(row_num, 1, schedule.schedule_name, row_style)
        ws.write(row_num, 2, schedule.schedule_type, row_style)
        ws.write(row_num, 3, schedule.publish_status, row_style)
        ws.write(row_num, 4, content_playlist_type, row_style)
        ws.write(row_num, 5, content_title, row_style)
        ws.write(row_num, 6, playlist_name, row_style)
        ws.write(row_num, 7, playback_date, row_style)
        ws.write(row_num, 8, "Yes" if schedule.never_expire else "No", row_style)
        ws.write(row_num, 9, "Yes" if schedule.repeat else "No", row_style)
        ws.write(row_num, 10, playback_start, row_style)
        ws.write(row_num, 11, playback_end, row_style)
        ws.write(row_num, 12, devices, row_style)
        ws.write(row_num, 13, schedule.description if schedule.description else "-", row_style)
        ws.write(row_num, 14, created_at, row_style)
        ws.write(row_num, 15, updated_at, row_style)

    response = HttpResponse(content_type='application/vnd.ms-excel')
    response['Content-Disposition'] = 'attachment; filename=ScheduleList.xls'
    wb.save(response)
    
    return response

logger = logging.getLogger(__name__)

class ManagePageView(View):
    template_name = 'schedules/manage_pages.html'
    
    def get_initial_data(self, request):
        """Handle auto-fill from schedule grid"""
        initial = {
            'publish_status': 'Published',
            'repeat': False,
            'never_expire': False,
            'schedule_type': 'None'
        }
        
        if request.GET.get('auto_fill') == 'true':
            try:
                content_id = request.GET.get('content_id')
                playlist_id = request.GET.get('playlist_id')
                playback_date = request.GET.get('playback_date')
                playback_start = request.GET.get('playback_start')
                
                if content_id:
                    initial['content'] = Content.objects.get(id=content_id)
                if playlist_id:
                    initial['playlist'] = Playlist.objects.get(id=playlist_id)
                if playback_date:
                    initial['playback_date'] = playback_date
                if playback_start:
                    initial['playback_start'] = playback_start + ':00'
                    initial['playback_end'] = str(int(playback_start.split(':')[0]) + ':59:00')
            except Exception as e:
                logger.error(f"Error in auto-fill: {str(e)}")
        
        return initial
    
    def get_context_data(self, request):
        """Prepare all context data for the template"""
        try:
            schedules = Schedule.objects.select_related('content', 'playlist') \
                                     .prefetch_related('publish_to') \
                                     .all()[:100]
            
            contents = Content.objects.all().order_by('-date_modified')[:100]
            playlists = Playlist.objects.all().order_by('-date_modified')[:100]
            
            devices = Device.objects.filter(is_online=True).order_by('name')
            
            schedule_types = Schedule.SCHEDULE_TYPE_CHOICES
            publish_statuses = Schedule.PUBLISH_STATUS_CHOICES
            
            with transaction.atomic():
                schedule_type_counts = {
                    choice[0]: Schedule.objects.filter(schedule_type=choice[0]).count()
                    for choice in schedule_types
                }
                publish_status_counts = {
                    status[0]: Schedule.objects.filter(publish_status=status[0]).count()
                    for status in publish_statuses
                }

            initial_data = self.get_initial_data(request)
            content_form = ContentForm(user=request.user)
            playlist_form = PlaylistForm(user=request.user)
            schedule_form = ManageForm(initial=initial_data)

            return {
                'schedules': schedules,
                'contents': contents,
                'playlists': playlists,
                'devices': devices,
                'schedule_types': schedule_types,
                'publish_statuses': publish_statuses,
                'schedule_type_counts': schedule_type_counts,
                'publish_status_counts': publish_status_counts,
                'current_time': timezone.localtime(timezone.now()),
                'model_fields': [f.name for f in Schedule._meta.get_fields()],
                'page_title': 'Manage Schedules',
                'content_form': content_form,
                'playlist_form': playlist_form,
                'schedule_form': schedule_form,
                'device_groups': DeviceGroup.objects.filter(devices__isnull=False).distinct(),
            }

        except Exception as e:
            logger.error(f"Error in manage_page: {str(e)}", exc_info=True)
            messages.error(request, f"Error loading data: {str(e)}")
            return {
                'schedules': [],
                'contents': [],
                'playlists': [],
                'devices': [],
                'schedule_types': [],
                'publish_statuses': [],
                'schedule_type_counts': {},
                'publish_status_counts': {},
                'current_time': timezone.localtime(timezone.now()),
                'model_fields': [],
                'page_title': 'Manage Schedules',
                'content_form': ContentForm(user=request.user),
                'playlist_form': PlaylistForm(user=request.user),
                'schedule_form': ManageForm(),
                'device_groups': DeviceGroup.objects.none(),
            }
    
    def create_schedules(self, form_data, request):
        """Handle schedule creation based on form data"""
        base_date = form_data['playback_date']
        schedule_type = form_data['schedule_type']
        device_group = form_data['device_group']
        content = form_data.get('content')
        playlist = form_data.get('playlist')
        
        if not content and not playlist:
            messages.error(request, "Please select either content or playlist")
            return 0
        
        devices_in_group = list(device_group.devices.all())
        if not devices_in_group:
            messages.error(request, "Selected device group has no devices")
            return 0
        
        media_name = content.content_name if content else playlist.playlist_name
        media_type = "Content" if content else "Playlist"
        description = (
            f"Device Group: {device_group.name}\n"
            f"Playback Date: {base_date}\n"
            f"{media_type}: {media_name}"
        )
        
        schedules_to_create = []
        
        if schedule_type == 'None':
            dates = [base_date]
        elif schedule_type == 'Daily':
            dates = [base_date + timedelta(days=i) for i in range(7)]
        elif schedule_type == 'Weekly':
            dates = []
            current_date = base_date
            while current_date.month == base_date.month:
                dates.append(current_date)
                current_date += timedelta(weeks=1)
        elif schedule_type == 'Monthly':
            dates = [base_date + relativedelta(months=i) for i in range(12)]
        elif schedule_type == 'List':
            dates = [base_date + timedelta(days=i) for i in range(365)]
        
        for playback_date in dates:
            schedule = Schedule(
                schedule_name=form_data['schedule_name'],
                schedule_type=schedule_type,
                content=content,
                playlist=playlist,
                playback_date=playback_date,
                never_expire=(schedule_type == 'List'),
                repeat=(schedule_type != 'None'),
                playback_start=form_data['playback_start'],
                playback_end=form_data['playback_end'],
                description=description,
                publish_status='Published'
            )
            schedules_to_create.append(schedule)
        
        with transaction.atomic():
            created_schedules = Schedule.objects.bulk_create(schedules_to_create)
            for schedule in created_schedules:
                schedule.publish_to.set(devices_in_group)
        
        return len(created_schedules)
    
    def get(self, request, *args, **kwargs):
        context = self.get_context_data(request)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'html_content': render_to_string(self.template_name, context, request=request),
                'stats': {
                    'schedule_type_counts': context['schedule_type_counts'],
                    'publish_status_counts': context['publish_status_counts']
                }
            })
        
        return render(request, self.template_name, context)
    
    def post(self, request, *args, **kwargs):
        form = ManageForm(request.POST)
        if form.is_valid():
            try:
                created_count = self.create_schedules(form.cleaned_data, request)
                if created_count > 0:
                    messages.success(request, f"Successfully created {created_count} schedules!")
                    return redirect('schedules')
                else:
                    messages.warning(request, "No schedules were created. Please check your input.")
            except Exception as e:
                logger.error(f"Error creating schedules: {str(e)}", exc_info=True)
                messages.error(request, f"Error creating schedules: {str(e)}")
        else:
            messages.error(request, "Invalid form data. Please correct the errors.")
            logger.error(f"Form errors: {form.errors}")
        
        context = self.get_context_data(request)
        return render(request, self.template_name, context)
#----------------------------------------------------------#


#------------------------Device----------------------------#
def device_view(request):
    group_id = request.GET.get('group_id')
    search_query = request.GET.get('q', '').strip()  
    
    devices = Device.objects.all().order_by('-is_online', '-last_updated')
    groups = DeviceGroup.objects.all().order_by('name')
    
    if group_id:
        devices = devices.filter(group_id=group_id)
        selected_group = DeviceGroup.objects.get(id=group_id)
        device_count = selected_group.device_count
        schedule_count = selected_group.schedule_count
    else:
        selected_group = None
        device_count = Device.objects.count()
        schedule_count = Schedule.objects.count()
    
    if search_query:
        devices = devices.filter(
            models.Q(name__icontains=search_query) | 
            models.Q(group__name__icontains=search_query)
        )

        device_count = devices.count()
    
    return render(request, 'device/device_page.html', {
        'devices': devices,
        'groups': groups,
        'selected_group': selected_group,
        'device_count': device_count,
        'schedule_count': schedule_count,
        'current_time': timezone.now(),
        'sort': request.GET.get('sort', ''),
        'order': request.GET.get('order', ''),
        'view': request.GET.get('view', 'table')
    })

def device_update(request, pk):
    device = get_object_or_404(Device, pk=pk)
    
    if request.method == 'POST':
        new_group_id = request.POST.get('group')
        
        old_group = device.group
        device.group_id = new_group_id if new_group_id else None
        device.save()
        
        if old_group:
            old_group.update_device_count()
        if device.group:
            device.group.update_device_count()
        
        schedules = Schedule.objects.filter(publish_to=device)
        
        affected_groups = set()
        if old_group:
            affected_groups.add(old_group)
        if device.group:
            affected_groups.add(device.group)
        
        for schedule in schedules:
            affected_groups.update(schedule.get_related_groups())
        
        for group in affected_groups:
            group.update_schedule_count()
        
        messages.success(request, 'Device group has been updated successfully!')
        return redirect('device_view') 
    
    groups = DeviceGroup.objects.all().order_by('name')
    
    return render(request, 'device_update.html', {
        'device': device,
        'groups': groups
    })

def device_group_create(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '').strip() or None
        
        if not name:
            messages.error(request, 'Nama grup tidak boleh kosong!')
            return redirect('device_group_create')  
        
        try:
            DeviceGroup.objects.create(
                name=name,
                description=description
            )
            messages.success(request, 'Grup perangkat berhasil dibuat!')
            return redirect('device_view')  
        except Exception as e:
            messages.error(request, f'Gagal membuat grup: {str(e)}')
            return redirect('device_group_create')
    
    return render(request, 'device/device_group_create.html')


def device_group_delete(request, pk):
    group = get_object_or_404(DeviceGroup, pk=pk)
    
    if request.method == 'POST':
        try:
            group_name = group.name
            group.delete()
            messages.success(request, f'Group "{group_name}" has been deleted successfully!')
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': f'Group "{group_name}" deleted successfully'})
                
            return redirect('device_view')
        except Exception as e:
            messages.error(request, f'Failed to delete group: {str(e)}')
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': str(e)}, status=400)
                
            return redirect('device_view')
    
    return JsonResponse({'success': False, 'message': 'Invalid request'}, status=400)

def export_device(request):
    wb = xlwt.Workbook()
    ws = wb.add_sheet('Device List')

    header_style = xlwt.easyxf(
        'font: bold on; pattern: pattern solid, fore_colour gray25; align: horiz center'
    )
    
    online_style = xlwt.easyxf(
        'pattern: pattern solid, fore_colour light_green'
    )
    
    offline_style = xlwt.easyxf(
        'pattern: pattern solid, fore_colour red'
    )

    headers = [
        "ID", "IP Address", "Hostname", 
        "User Agent", "Resolution", 
        "Group", "Is Online", "Created At",
        "Last Updated"
    ]
    
    for col_num, header in enumerate(headers):
        ws.write(0, col_num, header, header_style)

    col_widths = [2000, 5000, 5000, 10000, 4000, 5000, 3000, 5000, 5000]
    for col_num, width in enumerate(col_widths):
        ws.col(col_num).width = width

    devices = Device.objects.all().select_related('group')
    for row_num, device in enumerate(devices, start=1):
        row_style = online_style if device.is_online else offline_style
        
        ws.write(row_num, 0, device.id, row_style)
        ws.write(row_num, 1, device.ip_address, row_style)
        ws.write(row_num, 2, device.name if device.name else "", row_style)
        ws.write(row_num, 3, device.user_agent, row_style)
        ws.write(row_num, 4, device.resolution, row_style)
        ws.write(row_num, 5, device.group.name if device.group else "No Group", row_style)
        ws.write(row_num, 6, "Yes" if device.is_online else "No", row_style)
        ws.write(row_num, 7, device.created_at.strftime('%Y-%m-%d %H:%M:%S'), row_style)
        ws.write(row_num, 8, device.last_updated.strftime('%Y-%m-%d %H:%M:%S'), row_style)

    response = HttpResponse(content_type='application/vnd.ms-excel')
    response['Content-Disposition'] = 'attachment; filename=DeviceList.xls'
    wb.save(response)
    return response

logger = logging.getLogger(__name__)

@csrf_exempt
def device_ping(request):
    """Enhanced device ping with better resolution handling"""
    if request.method in ['GET', 'POST']:
        ip_address = request.META.get('REMOTE_ADDR', '0.0.0.0')
        
        try:
            if request.method == 'POST':
                body_data = json.loads(request.body.decode('utf-8'))
                resolution_data = body_data.get('resolution_info')
                is_heartbeat = body_data.get('is_heartbeat', False)
            else:
                resolution_data = None
                is_heartbeat = False
        except:
            resolution_data = None
            is_heartbeat = False
        
        update_fields = {
            'last_updated': timezone.now(),
            'is_online': True
        }
        
        if not is_heartbeat or not Device.objects.filter(
            ip_address=ip_address, 
            resolution__isnull=False
        ).exists():
            
            if resolution_data:
                formatted_resolution = format_resolution_data(resolution_data)
                if formatted_resolution:
                    update_fields['resolution'] = formatted_resolution
            else:
                resolution = (
                    request.META.get('HTTP_X_SCREEN_RESOLUTION') or
                    request.COOKIES.get('screen_resolution')
                )
                if resolution and resolution != 'Unknown':
                    update_fields['resolution'] = resolution
        
        Device.objects.update_or_create(
            ip_address=ip_address,
            defaults=update_fields
        )
        
        return JsonResponse({'status': 'success'})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=400)

def format_resolution_data(resolution_data):
    """Helper function untuk format resolusi"""
    if not isinstance(resolution_data, dict):
        return None
        
    try:
        physical_width = resolution_data.get('physical_width', 0)
        physical_height = resolution_data.get('physical_height', 0)
        
        if physical_width > 0 and physical_height > 0:
            return f"{physical_width}x{physical_height}"
            
        screen_width = resolution_data.get('screen_width', 0)
        screen_height = resolution_data.get('screen_height', 0)
        
        if screen_width > 0 and screen_height > 0:
            return f"{screen_width}x{screen_height}"
            
    except (KeyError, TypeError, ValueError):
        pass
        
    return None

logger = logging.getLogger(__name__)

class DigitalSignageViews:
    """
    Views untuk digital signage dengan informasi device, group, dan schedule
    """
    
    @staticmethod
    @never_cache
    def signage_display(request):
        """Main signage display view with AJAX support"""
        ip_address = request.META.get('REMOTE_ADDR', '0.0.0.0')
        
        device = getattr(request, 'signage_device', None)
        
        if device is None:
            try:
                device = Device.objects.get(ip_address=ip_address)
                request.signage_device = device
            except Device.DoesNotExist:
                device = None
        
        group_info = DigitalSignageViews._get_group_info(device)
        schedule_info = DigitalSignageViews._get_current_schedule(device)
        next_schedule_info = DigitalSignageViews._get_next_schedule(device)
        
        if device:
            logger.info(f"[VIEWS] Device ditemukan: {device.name}")
            logger.info(f"[VIEWS] Group: {group_info['name'] if group_info else 'None'}")
            
            if schedule_info:
                logger.info(f"[VIEWS] Schedule Aktif: {schedule_info['name']}")
                logger.info(f"[VIEWS] File Path: {schedule_info['file_path']}")
                logger.info(f"[VIEWS] Media Type: {schedule_info['media_type']}")
                logger.info(f"[VIEWS] Sampai: {schedule_info['end_time']}")
            elif next_schedule_info:
                logger.info(f"[VIEWS] Schedule Berikutnya: {next_schedule_info['name']}")
            else:
                logger.info(f"[VIEWS] Tidak ada schedule")
        else:
            logger.info(f"[VIEWS] Device dengan IP {ip_address} tidak ditemukan")
        
        media_content = None
        if schedule_info and schedule_info['file_path']:
            media_info = DigitalSignageViews._get_media_info(schedule_info)
            
            media_content = {
                'url': schedule_info['file_path'],
                'type': schedule_info['media_type'],
                'name': schedule_info['name'],
                'dimensions': media_info.get('dimensions'),
                'optimized': media_info.get('optimized', False)
            }
        
        current_timestamp = timezone.now().timestamp()
        schedule_end_timestamp = None
        next_schedule_timestamp = None
        
        if schedule_info and 'end_timestamp' in schedule_info:
            schedule_end_timestamp = schedule_info['end_timestamp']
        
        if next_schedule_info:
            next_date = timezone.datetime.strptime(next_schedule_info['date'], "%Y-%m-%d").date()
            next_start_time = timezone.datetime.strptime(next_schedule_info['start_time'], "%H:%M").time()
            next_schedule_datetime = timezone.make_aware(
                timezone.datetime.combine(next_date, next_start_time)
            )
            next_schedule_timestamp = next_schedule_datetime.timestamp()
        
        context = {
            'ip_address': ip_address,
            'device': device,
            'group_info': group_info,
            'schedule_info': schedule_info,
            'next_schedule_info': next_schedule_info,
            'media_content': media_content,
            'timestamp': timezone.now(),
            'title': 'Digital Signage Display',
            'current_timestamp': current_timestamp,
            'schedule_end_timestamp': schedule_end_timestamp,
            'next_schedule_timestamp': next_schedule_timestamp,
            'media_content_json': json.dumps(media_content) if media_content else 'null',
            'schedule_info_json': json.dumps(schedule_info) if schedule_info else 'null',
            'group_info_json': json.dumps(group_info) if group_info else 'null',
            'next_schedule_info_json': json.dumps(next_schedule_info) if next_schedule_info else 'null'
        }
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'data': {
                    'device': {
                        'name': device.name if device else None,
                        'ip': ip_address
                    } if device else None,
                    'group_info': group_info,
                    'schedule_info': schedule_info,
                    'next_schedule_info': next_schedule_info,
                    'media_content': media_content,
                    'timestamp': timezone.now().isoformat(),
                    'current_timestamp': current_timestamp,
                    'schedule_end_timestamp': schedule_end_timestamp,
                    'next_schedule_timestamp': next_schedule_timestamp
                }
            })
        
        return render(request, 'schedules/components/display.html', context)

    @staticmethod
    def _get_group_info(device):
        """Mendapatkan informasi group dari device"""
        if device and device.group:
            group = device.group
            return {
                'name': group.name,
                'id': group.id,
                'device_count': group.device_count,
                'schedule_count': group.schedule_count,
                'description': group.description
            }
        return None

    @staticmethod
    def _get_current_schedule(device):
        """Mendapatkan schedule aktif untuk device berdasarkan group"""
        if not device or not device.group:
            return None
        
        now_time = timezone.localtime().time()
        today_date = timezone.localtime().date()
        now_datetime = timezone.localtime()
        
        active_schedules = Schedule.objects.filter(
            publish_to__group=device.group,
            publish_status='Published',
            playback_date=today_date,
            playback_start__lte=now_time,
            playback_end__gte=now_time
        ).select_related('content', 'playlist').order_by('-playback_start')
        
        if active_schedules.exists():
            schedule = active_schedules.first()
            file_path, media_type = DigitalSignageViews._get_file_info(schedule)
            
            schedule_end_datetime = timezone.make_aware(
                timezone.datetime.combine(schedule.playback_date, schedule.playback_end)
            )
            
            return {
                'name': schedule.schedule_name,
                'date': schedule.playback_date.strftime("%Y-%m-%d"),
                'start_time': schedule.playback_start.strftime("%H:%M"),
                'end_time': schedule.playback_end.strftime("%H:%M"),
                'content_type': 'Content' if schedule.content else 'Playlist' if schedule.playlist else 'None',
                'file_path': file_path,
                'media_type': media_type,
                'is_current': True,
                'schedule_id': schedule.id,
                'end_timestamp': schedule_end_datetime.timestamp(),
                'remaining_seconds': max(0, (schedule_end_datetime - now_datetime).total_seconds())
            }
        
        return None

    @staticmethod
    def _get_next_schedule(device):
        """Mendapatkan schedule berikutnya untuk device"""
        if not device or not device.group:
            return None
        
        now_time = timezone.localtime().time()
        today_date = timezone.localtime().date()
        now_datetime = timezone.localtime()
        
        next_schedules = Schedule.objects.filter(
            publish_to__group=device.group,
            publish_status='Published',
            playback_date__gte=today_date
        ).filter(
            Q(playback_date__gt=today_date) | 
            Q(playback_date=today_date, playback_start__gt=now_time)
        ).select_related('content', 'playlist').order_by('playback_date', 'playback_start')
        
        if next_schedules.exists():
            schedule = next_schedules.first()
            file_path, media_type = DigitalSignageViews._get_file_info(schedule)
            
            schedule_start_datetime = timezone.make_aware(
                timezone.datetime.combine(schedule.playback_date, schedule.playback_start)
            )
            
            return {
                'name': schedule.schedule_name,
                'date': schedule.playback_date.strftime("%Y-%m-%d"),
                'start_time': schedule.playback_start.strftime("%H:%M"),
                'end_time': schedule.playback_end.strftime("%H:%M"),
                'content_type': 'Content' if schedule.content else 'Playlist' if schedule.playlist else 'None',
                'file_path': file_path,
                'media_type': media_type,
                'is_current': False,
                'schedule_id': schedule.id,
                'start_timestamp': schedule_start_datetime.timestamp(),
                'seconds_until_start': max(0, (schedule_start_datetime - now_datetime).total_seconds())
            }
        
        return None

    @staticmethod
    def _get_file_info(schedule):
        """Mendapatkan file path dan media type dari schedule"""
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
    
    @staticmethod
    def _get_media_info(schedule_info):
        """Mendapatkan informasi media dan mengoptimalkan untuk tampilan layar"""
        media_info = {
            'dimensions': None,
            'optimized': False,
            'aspect_ratio': None,
            'file_size': None
        }
        
        if not schedule_info or not schedule_info.get('file_path'):
            return media_info
        
        try:
            file_path = schedule_info['file_path']
            media_type = schedule_info['media_type']
            
            if file_path.startswith('/media/'):
                full_path = os.path.join(settings.MEDIA_ROOT, file_path[7:])
            else:
                full_path = file_path
            
            if not os.path.exists(full_path):
                logger.warning(f"[MEDIA_INFO] File tidak ditemukan: {full_path}")
                return media_info
            
            media_info['file_size'] = os.path.getsize(full_path)
            
            if media_type in ['image', 'jpg', 'jpeg', 'png', 'gif', 'bmp']:
                media_info = DigitalSignageViews._process_image_with_pil(full_path, media_info)
            elif media_type in ['video', 'mp4', 'avi', 'mov', 'mkv', 'wmv']:
                media_info = DigitalSignageViews._process_video_info(full_path, media_info)
            
        except Exception as e:
            logger.error(f"[MEDIA_INFO] Error processing media: {str(e)}")
        
        return media_info
    
    @staticmethod
    def _process_image_with_pil(file_path, media_info):
        """Process image file untuk mendapatkan dimensi dan optimasi menggunakan PIL"""
        try:
            with Image.open(file_path) as img:
                width, height = img.size
                media_info['dimensions'] = {
                    'width': width,
                    'height': height
                }
                media_info['aspect_ratio'] = width / height if height > 0 else 1
                
                common_resolutions = [
                    (1920, 1080),  # Full HD
                    (1366, 768),   # HD
                    (3840, 2160),  # 4K
                    (2560, 1440),  # 2K
                ]
                
                for res_width, res_height in common_resolutions:
                    if abs(width - res_width) <= 50 and abs(height - res_height) <= 50:
                        media_info['optimized'] = True
                        break
                
                aspect_16_9 = 16/9
                aspect_4_3 = 4/3
                current_aspect = media_info['aspect_ratio']
                
                if (abs(current_aspect - aspect_16_9) <= 0.1 or 
                    abs(current_aspect - aspect_4_3) <= 0.1):
                    media_info['optimized'] = True
                
                logger.info(f"[IMAGE_INFO] {file_path}: {width}x{height}, AR: {current_aspect:.2f}, Optimized: {media_info['optimized']}")
                
        except Exception as e:
            logger.error(f"[IMAGE_PROCESS] Error: {str(e)}")
        
        return media_info
    
    @staticmethod
    def _process_video_info(file_path, media_info):
        """Process video file untuk mendapatkan informasi dasar"""
        try:
            try:
                import subprocess
                import json
                
                cmd = [
                    'ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams',
                    file_path
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    video_info = json.loads(result.stdout)
                    
                    for stream in video_info.get('streams', []):
                        if stream.get('codec_type') == 'video':
                            width = stream.get('width')
                            height = stream.get('height')
                            
                            if width and height:
                                media_info['dimensions'] = {
                                    'width': width,
                                    'height': height
                                }
                                media_info['aspect_ratio'] = width / height if height > 0 else 1
                                
                                common_resolutions = [
                                    (1920, 1080),  # Full HD
                                    (1366, 768),   # HD
                                    (3840, 2160),  # 4K
                                    (2560, 1440),  # 2K
                                ]
                                
                                for res_width, res_height in common_resolutions:
                                    if abs(width - res_width) <= 50 and abs(height - res_height) <= 50:
                                        media_info['optimized'] = True
                                        break
                                
                                aspect_16_9 = 16/9
                                current_aspect = media_info['aspect_ratio']
                                
                                if abs(current_aspect - aspect_16_9) <= 0.1:
                                    media_info['optimized'] = True
                                
                                logger.info(f"[VIDEO_INFO] {file_path}: {width}x{height}, AR: {current_aspect:.2f}, Optimized: {media_info['optimized']}")
                                break
                    
                else:
                    logger.warning(f"[VIDEO_PROCESS] ffprobe failed for: {file_path}")
                    
            except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError) as e:
                logger.warning(f"[VIDEO_PROCESS] ffprobe not available or failed: {str(e)}")
                
                # Fallback: assume common video resolution
                media_info['dimensions'] = {
                    'width': 1920,
                    'height': 1080
                }
                media_info['aspect_ratio'] = 16/9
                media_info['optimized'] = True
                
                logger.info(f"[VIDEO_INFO] {file_path}: Using fallback 1920x1080 (16:9)")
                
        except Exception as e:
            logger.error(f"[VIDEO_PROCESS] Error: {str(e)}")
        
        return media_info
    
    @staticmethod
    def get_media_optimization_status(request):
        """API endpoint untuk mendapatkan status optimasi media"""
        ip_address = request.META.get('REMOTE_ADDR', '0.0.0.0')
        
        try:
            device = Device.objects.get(ip_address=ip_address)
            schedule_info = DigitalSignageViews._get_current_schedule(device)
            
            if schedule_info:
                media_info = DigitalSignageViews._get_media_info(schedule_info)
                return JsonResponse({
                    'success': True,
                    'media_info': media_info,
                    'schedule_name': schedule_info['name']
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'No active schedule'
                })
                
        except Device.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Device not found'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            })
#----------------------------------------------------------#