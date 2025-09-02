import os
from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
from django.utils.timezone import now, timedelta

def content_file_path(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    
    if ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
        file_type = 'image'
    elif ext in ['.mp4', '.mov', '.avi', '.webm']:
        file_type = 'video'
    else:
        file_type = 'file'
    
    content_name = getattr(instance, 'name', None) or \
                  getattr(instance, 'title', None) or \
                  getattr(instance, 'content_name', 'content')
    
    import re
    content_name = re.sub(r'[^\w\s-]', '', content_name).strip().lower()
    content_name = re.sub(r'[-\s]+', '_', content_name)
    
    current_time = timezone.now().strftime("%Y%m%d")
    new_filename = f"{file_type}_{content_name}_{current_time}{ext}"
    
    return os.path.join('content_uploads', new_filename)

class Content(models.Model):
    content_name = models.CharField(max_length=100)
    file = models.FileField(upload_to=content_file_path)
    supported_device = models.CharField(
        max_length=200,  
        blank=True,
        help_text="Auto-set dari device yang dipilih (Group + Resolution)"
    )
    device = models.ForeignKey(
        'Device', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='contents'
    )
    creator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    expiration_date = models.DateTimeField(blank=True, null=True)
    date_modified = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.content_name

    def file_type_content(self):
        """Determine the file type of the content"""
        ext = self.file.name.split('.')[-1].lower() if self.file else ''
        if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
            return 'Image'
        elif ext in ['mp4', 'mov', 'avi', 'webm']:
            return 'Video'
        else:
            return 'Unknown'

    def file_size_kb(self):
        """Return file size in KB"""
        return f"{round(self.file.size / 1024)} KB" if self.file else "0 KB"

    def file_details(self):
        """Return combined file type and size information"""
        return f"{self.file_type_content()} - {self.file_size_kb()}"

    def get_available_devices(self):
        """
        Ambil daftar device dari semua DeviceGroup dengan format:
        [('device_id', 'Group Name (Resolution)')]
        """
        device_choices = []
        
        for device in Device.objects.select_related('group').all():
            group_name = device.group.name if device.group else 'No Group'
            resolution = device.resolution if device.resolution != 'Unknown' else 'Unknown Resolution'
            display_name = f"{group_name} ({resolution})"
            device_choices.append((device.id, display_name))
        
        return device_choices

    def save(self, *args, **kwargs):
        """Auto-set supported_device berdasarkan device yang dipilih"""
        if self.device:
            group_name = self.device.group.name if self.device.group else 'No Group'
            resolution = self.device.resolution if self.device.resolution != 'Unknown' else 'Unknown Resolution'
            self.supported_device = f"{group_name} ({resolution})"
        else:
            self.supported_device = ""

        super().save(*args, **kwargs)


class Playlist(models.Model):
    playlist_name = models.CharField(max_length=100)
    file = models.FileField(upload_to='playlist_uploads/')
    supported_device = models.CharField(
        max_length=200,  
        blank=True,
        help_text="Auto-set dari device yang dipilih (Group + Resolution)"
    )
    device = models.ForeignKey(
        'Device', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='playlists'
    )
    creator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    expiration_date = models.DateTimeField(blank=True, null=True)
    date_modified = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.playlist_name

    def file_type_playlist(self):
        """Determine the file type of the playlist file"""
        ext = self.file.name.split('.')[-1].lower() if self.file else ''
        if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
            return 'Image'
        elif ext in ['mp4', 'mov', 'avi', 'webm']:
            return 'Video'
        else:
            return 'Unknown'

    def file_size_kb(self):
        """Return file size in KB"""
        return f"{round(self.file.size / 1024)} KB" if self.file else "0 KB"

    def file_details(self):
        """Return combined file type and size information"""
        return f"{self.file_type_playlist()} - {self.file_size_kb()}"

    def get_available_devices(self):
        """
        Ambil daftar device dari semua DeviceGroup dengan format:
        [('device_id', 'Group Name (Resolution)')]
        """
        device_choices = []
        
        for device in Device.objects.select_related('group').all():
            group_name = device.group.name if device.group else 'No Group'
            resolution = device.resolution if device.resolution != 'Unknown' else 'Unknown Resolution'
            display_name = f"{group_name} ({resolution})"
            device_choices.append((device.id, display_name))
        
        return device_choices

    def save(self, *args, **kwargs):
        """Auto-set supported_device berdasarkan device yang dipilih"""
        if self.device:
            group_name = self.device.group.name if self.device.group else 'No Group'
            resolution = self.device.resolution if self.device.resolution != 'Unknown' else 'Unknown Resolution'
            self.supported_device = f"{group_name} ({resolution})"
        else:
            self.supported_device = ""

        super().save(*args, **kwargs)

class DeviceGroup(models.Model):
    """
    Model untuk grup perangkat dengan counter device dan schedule
    """
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Nama grup (Contoh: Ballroom 1, Ivory 2)"
    )
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Deskripsi tambahan grup"
    )
    device_count = models.PositiveIntegerField(
        default=0,
        editable=False,
        verbose_name="Jumlah Perangkat"
    )
    schedule_count = models.PositiveIntegerField(
        default=0,
        editable=False,
        verbose_name="Jumlah Schedule"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Device Group"
        verbose_name_plural = "Device Groups"
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['device_count']),
            models.Index(fields=['schedule_count']),
        ]

    def __str__(self):
        return f"{self.name} ({self.device_count} devices, {self.schedule_count} schedules)"

    def update_device_count(self):
        """Update counter jumlah perangkat"""
        count = self.devices.count()
        if self.device_count != count:
            self.device_count = count
            self.save(update_fields=['device_count'])

    def update_schedule_count(self):
        """Update counter jumlah schedule"""
        from django.db.models import Count
        count = Schedule.objects.filter(
            publish_to__group=self
        ).distinct().count()
        if self.schedule_count != count:
            self.schedule_count = count
            self.save(update_fields=['schedule_count'])

class Device(models.Model):
    """
    Model perangkat dengan relasi ke DeviceGroup
    """
    name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Nama perangkat (opsional)"
    )
    user_agent = models.TextField(
        help_text="Identifikasi browser/perangkat"
    )
    ip_address = models.CharField(
        max_length=50,
        help_text="Alamat IP perangkat"
    )
    resolution = models.CharField(
        max_length=50,
        default='Unknown',
        help_text="Resolusi layar (format: WxH)"
    )
    is_online = models.BooleanField(
        default=False,
        help_text="Status koneksi perangkat"
    )
    group = models.ForeignKey(
        DeviceGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='devices',
        help_text="Grup tempat perangkat ini berada"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(
        default=timezone.now,
        help_text="Terakhir update status"
    )

    class Meta:
        verbose_name = "Device"
        verbose_name_plural = "Devices"
        ordering = ['group__name', 'name']
        indexes = [
            models.Index(fields=['ip_address']),
            models.Index(fields=['is_online']),
            models.Index(fields=['group']),
        ]

    def __str__(self):
        group_name = self.group.name if self.group else 'No Group'
        return f"{self.name} ({self.ip_address}) - {group_name}"

    def save(self, *args, **kwargs):
        """
        Override save untuk handle perubahan grup
        """
        old_group = None
        if self.pk:  
            old_group = Device.objects.get(pk=self.pk).group
        
        super().save(*args, **kwargs)
        
        if old_group and old_group != self.group:
            old_group.update_device_count()
        if self.group:
            self.group.update_device_count()

    def delete(self, *args, **kwargs):
        """
        Override delete untuk update counter
        """
        group = self.group
        super().delete(*args, **kwargs)
        if group:
            group.update_device_count()

    def current_schedule(self):
        """
        Mendapatkan jadwal aktif untuk perangkat ini
        """
        from django.utils.timezone import localtime
        
        now_time = localtime().time()
        today_date = localtime().date()
        
        return self.published_schedules.filter(
            playback_start__lte=now_time,
            playback_end__gte=now_time,
            playback_date=today_date,
            publish_status='Published'
        ).select_related('content', 'playlist').first()

class Schedule(models.Model):
    """
    Model schedule dengan relasi ke DeviceGroup via Device
    """
    SCHEDULE_TYPE_CHOICES = [
        ('None', 'None'),
        ('Daily', 'Daily'),
        ('Weekly', 'Weekly'),
        ('Monthly', 'Monthly'),
        ('List', 'List'),
    ]

    PUBLISH_STATUS_CHOICES = [
        ('Draft', 'Draft'),
        ('Published', 'Published'),
    ]

    schedule_name = models.CharField(max_length=100)
    schedule_type = models.CharField(max_length=20, choices=SCHEDULE_TYPE_CHOICES)
    publish_status = models.CharField(max_length=10, choices=PUBLISH_STATUS_CHOICES, default='Draft')    
    content = models.ForeignKey('Content', on_delete=models.SET_NULL, null=True, blank=True)
    playlist = models.ForeignKey('Playlist', on_delete=models.SET_NULL, null=True, blank=True)
    playback_date = models.DateField(null=True, blank=True)
    never_expire = models.BooleanField(default=False)
    repeat = models.BooleanField(default=False)
    playback_start = models.TimeField(null=True, blank=True)
    playback_end = models.TimeField(null=True, blank=True)
    publish_to = models.ManyToManyField(Device, related_name='published_schedules', blank=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['publish_status']),
            models.Index(fields=['playback_date']),
        ]

    def __str__(self):
        return self.schedule_name

    def get_related_groups(self):
        """Dapatkan semua grup yang menerima schedule ini"""
        return DeviceGroup.objects.filter(
            devices__in=self.publish_to.all()
        ).distinct()

    def save(self, *args, **kwargs):
        """
        Override save untuk update counter grup
        """
        super().save(*args, **kwargs)
        for group in self.get_related_groups():
            group.update_schedule_count()

    def delete(self, *args, **kwargs):
        """
        Override delete untuk update counter grup
        """
        groups = list(self.get_related_groups())
        super().delete(*args, **kwargs)
        for group in groups:
            group.update_schedule_count()

    @property
    def is_content(self):
        return bool(self.content) and not self.playlist

    @property
    def is_playlist(self):
        return bool(self.playlist) and not self.content

@receiver(post_save, sender=Device)
def update_device_count_on_save(sender, instance, **kwargs):
    if instance.group:
        instance.group.update_device_count()
    if kwargs.get('old_group'):
        kwargs['old_group'].update_device_count()

@receiver(post_delete, sender=Device)
def update_device_count_on_delete(sender, instance, **kwargs):
    if instance.group:
        instance.group.update_device_count()

@receiver([post_save, post_delete], sender=Schedule)
def update_schedule_count_on_change(sender, instance, **kwargs):
    for group in instance.get_related_groups():
        group.update_schedule_count()

def mark_offline_devices():
    """
    Menandai perangkat offline yang tidak update dalam 1 menit
    """
    timeout_limit = now() - timedelta(minutes=1)
    Device.objects.filter(
        last_updated__lt=timeout_limit,
        is_online=True
    ).update(is_online=False)