from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.views.generic.base import RedirectView
from django.urls import path
from .views import (
    DigitalSignageViews, SignUp,ResetPassword, device_group_create, device_group_delete, logout, DashboardView,
    content_view, UploadContent, content_recycle_bin_view, export_content, design_view, delete_expired_content, UploadDesign,
    playlist_view, UploadPlaylist, playlist_recycle_bin_view, export_playlist, delete_expired_playlists, content_playlist_combined_view,
    SchedulesView, ManagePageView, SchedulesRecycleBinView, export_schedule,
    device_view, device_update, export_device,
)

urlpatterns = [
#-------------------------Auth-----------------------------#
    path('', RedirectView.as_view(url='/signage/display/', permanent=False)),
    path('login/', auth_views.LoginView.as_view(template_name='auth/login_page.html', redirect_authenticated_user=True), name='login'),
    path('signup/', SignUp.as_view(), name='signup'),
    path('reset-password/', ResetPassword.as_view(), name='reset_password'),
    path('logout/', logout, name='logout'),
    path('signage/display/', DigitalSignageViews.signage_display, name='signage_display'),
#----------------------------------------------------------#

#-----------------------dashboard--------------------------#
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
#----------------------------------------------------------#

#------------------------content---------------------------#
    path('content/', content_view, name='content'),
    path('recycle-bin/', content_recycle_bin_view, name='recycle_bin'),
    path('design/', design_view, name='design_view'),
    path('content/upload/', UploadContent.as_view(), name='upload_content'),
    path('design/upload/', UploadDesign.as_view(), name='design_upload'),
    path('content', export_content, name='export'),
    path('content/delete-expired/', delete_expired_content, name='delete_expired_content'),
#----------------------------------------------------------#

#------------------------playlist--------------------------#
    path('playlist/', playlist_view, name='playlist'),
    path('recycle-bin-playlist/', playlist_recycle_bin_view, name='playlist_recycle_bin'),
    path('playlist/upload/', UploadPlaylist.as_view(), name='upload_playlist'),
    path('export-playlist/', export_playlist, name='export_playlist'),
    path('content-playlist/', content_playlist_combined_view, name='content_playlist_combined'),
    path('playlists/delete-expired/', delete_expired_playlists, name='delete_expired_playlists'),
#----------------------------------------------------------#

#------------------------schedules-------------------------#
    path('schedules/', SchedulesView.as_view(), name='schedules'),
    path('schedules/manage-page/', ManagePageView.as_view(), name='manage_schedules'),
    path('export-schedule/', export_schedule, name='export_schedule'),
    path('recycle-bin-schedules/', SchedulesRecycleBinView.as_view(), name='schedules_recycle_bin'),
#----------------------------------------------------------#

#-------------------------device---------------------------#
    path('device/', device_view, name='device_view'),
    path('export-device/', export_device, name='export_device'),
    path('devices/create/', device_group_create, name='device_group_create'),
    path('devices/<int:pk>/update/', device_update, name='device_update'),
    path('devices/delete/<int:pk>/', device_group_delete, name='device_group_delete'),
#----------------------------------------------------------#
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
