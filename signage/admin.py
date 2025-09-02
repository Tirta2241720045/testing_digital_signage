from django.contrib import admin
from .models import Content, Playlist, Schedule, Device, DeviceGroup

class ContentAdmin(admin.ModelAdmin):
    list_display = ('content_name', 'device', 'creator', 'file_type_content', 
                   'file_size_kb', 'supported_device', 'expiration_date')
    list_filter = ('device__group', 'expiration_date', 'supported_device', 'creator')
    search_fields = ('content_name', 'device__name')
    raw_id_fields = ('device', 'creator')
    readonly_fields = ('date_modified', 'supported_device')
    fieldsets = (
        (None, {
            'fields': ('content_name', 'file', 'device', 'creator')
        }),
        ('Metadata', {
            'fields': ('supported_device', 'expiration_date', 'date_modified')
        }),
    )

admin.site.register(Content, ContentAdmin)

class PlaylistAdmin(admin.ModelAdmin):
    list_display = ('playlist_name', 'device', 'creator', 'file_type_playlist', 
                   'file_size_kb', 'supported_device', 'expiration_date')
    list_filter = ('device__group', 'supported_device', 'creator', 'expiration_date')
    search_fields = ('playlist_name', 'device__name')
    raw_id_fields = ('device', 'creator')
    readonly_fields = ('date_modified', 'supported_device')
    fieldsets = (
        (None, {
            'fields': ('playlist_name', 'file', 'device', 'creator')
        }),
        ('Metadata', {
            'fields': ('supported_device', 'expiration_date', 'date_modified')
        }),
    )

admin.site.register(Playlist, PlaylistAdmin)

class ScheduleAdmin(admin.ModelAdmin):
    list_display = ('schedule_name', 'schedule_type', 'publish_status', 
                   'playback_date', 'playback_start', 'playback_end', 'get_groups')
    list_filter = ('publish_status', 'schedule_type', 'playback_date')
    search_fields = ('schedule_name', 'description', 'content__content_name', 'playlist__playlist_name')
    filter_horizontal = ('publish_to',)
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('content', 'playlist')
    
    def get_groups(self, obj):
        groups = DeviceGroup.objects.filter(devices__in=obj.publish_to.all()).distinct()
        return ", ".join([g.name for g in groups])
    get_groups.short_description = 'Target Groups'

admin.site.register(Schedule, ScheduleAdmin)

@admin.register(DeviceGroup)
class DeviceGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'device_count', 'schedule_count', 'description')
    list_filter = ('device_count', 'schedule_count')
    search_fields = ('name', 'description')
    readonly_fields = ('device_count', 'schedule_count', 'created_at', 'updated_at')

@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ('name', 'ip_address', 'resolution', 'group', 'is_online', 'last_updated')
    list_filter = ('is_online', 'group', 'resolution')
    search_fields = ('name', 'ip_address', 'group__name', 'resolution')
    readonly_fields = ('created_at', 'last_updated')
    raw_id_fields = ('group',)
    
    fieldsets = (
        ('Device Info', {
            'fields': ('name', 'ip_address', 'group', 'resolution')
        }),
        ('Status', {
            'fields': ('is_online', 'last_updated', 'user_agent')
        }),
        ('Metadata', {
            'fields': ('created_at',)
        }),
    )