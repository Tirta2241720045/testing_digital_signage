from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from django.utils.translation import gettext as _
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.forms import DateTimeInput
from django.utils import timezone
from .models import Content, Playlist, Schedule, Device, DeviceGroup
import re
import os

User = get_user_model()

class SignUpForm(forms.ModelForm):
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
    )
    password2 = forms.CharField(
        label='Password confirmation',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
        }
        error_messages = {
            'username': {
                'required': 'Username harus diisi.',
                'max_length': 'Username maksimal 150 karakter.',
                'unique': 'Username sudah digunakan. Pilih username lain.',
            },
            'email': {
                'required': 'Email harus diisi.',
                'invalid': 'Format email tidak valid.',
                'unique': 'Email sudah terdaftar. Gunakan email lain atau login.',
            },
            'first_name': {
                'required': 'Nama harus diisi.',
                'max_length': 'Nama terlalu panjang (maksimal 150 karakter).',
            },
            'last_name': {
                'required': 'Posisi/jabatan harus diisi.',
                'max_length': 'Posisi terlalu panjang (maksimal 150 karakter).',
            },
        }

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if not username:
            raise ValidationError("Username harus diisi.")
        
        username = username.strip()
        if len(username) < 4:
            raise ValidationError("Username minimal 4 karakter.")
        if not re.match(r'^[A-Za-z0-9]+$', username):
            raise ValidationError("Username hanya boleh mengandung huruf dan angka.")
        
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("Username sudah digunakan. Pilih username lain.")
        
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not email:
            raise ValidationError("Email harus diisi.")
        
        email = email.strip().lower()
        
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("Email sudah terdaftar. Gunakan email lain atau login.")
        
        return email

    def clean_first_name(self):
        first_name = self.cleaned_data.get('first_name')
        if not first_name:
            raise ValidationError("Nama harus diisi.")
        
        first_name = first_name.strip()
        if len(first_name) < 2:
            raise ValidationError("Nama minimal 2 karakter.")
        
        return first_name

    def clean_last_name(self):
        last_name = self.cleaned_data.get('last_name', '')
        if last_name:
            last_name = last_name.strip()
            if len(last_name) < 2:
                raise ValidationError("Last name minimal 2 karakter.")
        return last_name

    def clean_password1(self):
        password1 = self.cleaned_data.get('password1')
        if not password1:
            raise ValidationError("Password harus diisi.")
        
        if len(password1) < 8:
            raise ValidationError("Password minimal 8 karakter.")
        
        try:
            validate_password(password1)
        except ValidationError as e:
            raise ValidationError(e.messages)
        
        return password1

    def clean_password2(self):
        password2 = self.cleaned_data.get("password2")
        if not password2:
            raise ValidationError("Konfirmasi password harus diisi.")
        return password2

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        
        if password1 and password2 and password1 != password2:
            raise ValidationError("Password dan konfirmasi password tidak sama.")
        
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data.get("last_name", "")
        
        if commit:
            user.save()
            
            try:
                from django.contrib.admin.models import LogEntry, ADDITION
                from django.contrib.contenttypes.models import ContentType
                LogEntry.objects.log_action(
                    user_id=user.id,
                    content_type_id=ContentType.objects.get_for_model(user).pk,
                    object_id=user.pk,
                    object_repr=str(user),
                    action_flag=ADDITION,
                    change_message="User registered via signup form",
                )
            except Exception:
                pass
                
        return user

class ResetPasswordForm(forms.Form):
    username = forms.CharField(
        label="Username",
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
        }),
        error_messages={
            'required': 'Username is required.',
            'max_length': 'Username is too long.'
        }
    )

    old_password = forms.CharField(
        label="Old Password",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
        }),
        error_messages={
            'required': 'Old password is required.'
        }
    )

    new_password1 = forms.CharField(
        label="New Password",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
        }),
        error_messages={
            'required': 'New password is required.'
        }
    )

    new_password2 = forms.CharField(
        label="Confirm New Password",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
        }),
        error_messages={
            'required': 'Password confirmation is required.'
        }
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_cache = None

    def clean_username(self):
        username = self.cleaned_data.get('username')

        if not username:
            raise ValidationError('Username is required.')

        try:
            user = User.objects.get(username=username)
            self.user_cache = user
            return username
        except User.DoesNotExist:
            raise ValidationError('Username not found.')

    def clean_old_password(self):
        old_password = self.cleaned_data.get('old_password')

        if not old_password:
            raise ValidationError('Old password is required.')

        if hasattr(self, 'user_cache') and self.user_cache:
            if not self.user_cache.check_password(old_password):
                raise ValidationError('Old password is incorrect.')

        return old_password

    def clean_new_password1(self):
        new_password1 = self.cleaned_data.get('new_password1')

        if not new_password1:
            raise ValidationError('New password is required.')

        if len(new_password1) < 8:
            raise ValidationError('Password must be at least 8 characters.')

        username = self.cleaned_data.get('username', '')
        if username and username.lower() in new_password1.lower():
            raise ValidationError('Password cannot contain your username.')

        common_passwords = ['password', '12345678', 'qwerty', 'admin', 'letmein']
        if new_password1.lower() in common_passwords:
            raise ValidationError('Password is too common. Please choose a stronger one.')

        if new_password1.isdigit():
            raise ValidationError('Password cannot be entirely numeric.')

        try:
            if hasattr(self, 'user_cache') and self.user_cache:
                validate_password(new_password1, user=self.user_cache)
        except ValidationError as error:
            messages = []
            for message in error.messages:
                if 'too short' in message.lower():
                    messages.append('Password must be at least 8 characters.')
                elif 'too common' in message.lower():
                    messages.append('Password is too common.')
                elif 'entirely numeric' in message.lower():
                    messages.append('Password cannot be entirely numeric.')
                elif 'too similar' in message.lower():
                    messages.append('Password is too similar to your personal information.')
                else:
                    messages.append(message)

            if messages:
                raise ValidationError(messages[0])

        return new_password1

    def clean_new_password2(self):
        new_password2 = self.cleaned_data.get('new_password2')

        if not new_password2:
            raise ValidationError('Password confirmation is required.')

        return new_password2

    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get('username')
        old_password = cleaned_data.get('old_password')
        new_password1 = cleaned_data.get('new_password1')
        new_password2 = cleaned_data.get('new_password2')

        if self.errors:
            return cleaned_data

        if username and old_password:
            try:
                user = User.objects.get(username=username)

                if not user.is_active:
                    raise ValidationError('Your account is inactive. Please contact the administrator.')

                if not user.check_password(old_password):
                    raise ValidationError('Username or old password is incorrect.')

                if old_password == new_password1:
                    raise ValidationError('New password cannot be the same as old password.')

                cleaned_data['user'] = user

            except User.DoesNotExist:
                raise ValidationError('Username not found.')

        if new_password1 and new_password2:
            if new_password1 != new_password2:
                raise ValidationError('New password and confirmation do not match.')

        return cleaned_data

class DateTimeInput(forms.DateTimeInput):
    input_type = 'datetime-local'

class ContentForm(forms.ModelForm):
    device = forms.ModelChoiceField(
        queryset=Device.objects.none(), 
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'device-select'
        }),
        required=False
    )

    class Meta:
        model = Content
        fields = ['content_name', 'file', 'device', 'expiration_date']
        widgets = {
            'content_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter content name'
            }),
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/jpeg, image/png, video/mp4, video/webm, video/quicktime, video/x-msvideo'
            }),
            'expiration_date': DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'form-control',
                'min': timezone.now().strftime('%Y-%m-%dT%H:%M')
            }, format='%Y-%m-%dT%H:%M'),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        self.fields['device'].queryset = Device.objects.select_related('group').order_by('group__name', 'resolution')
        self.fields['device'].label_from_instance = lambda obj: (
            f"{obj.group.name if obj.group else 'No Group'} ({obj.resolution if obj.resolution != 'Unknown' else 'Unknown Resolution'})"
        )

        self.fields['device'].empty_label = "Select Device (Optional)"

        if self.instance and self.instance.expiration_date:
            self.initial['expiration_date'] = self.instance.expiration_date.strftime('%Y-%m-%dT%H:%M')
        if user:
            self.initial['creator'] = user
        
        self.fields['content_name'].required = True
        self.fields['file'].required = True

        if 'supported_device' in self.fields:
            del self.fields['supported_device']

    def clean(self):
        cleaned_data = super().clean()
        file = cleaned_data.get('file')
        
        if file:
            ext = os.path.splitext(file.name)[1].lower()
            valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.mp4', '.mov', '.avi', '.webm']
            if ext not in valid_extensions:
                self.add_error('file', "Unsupported file type. Please upload an image or video file.")
        
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        if commit:
            instance.save()
        return instance


class PlaylistForm(forms.ModelForm):
    device = forms.ModelChoiceField(
        queryset=Device.objects.none(), 
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'playlist-device-select'
        }),
        required=False
    )

    class Meta:
        model = Playlist
        fields = ['playlist_name', 'device', 'expiration_date']
        widgets = {
            'playlist_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter playlist name'
            }),
            'expiration_date': DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'form-control',
                'min': timezone.now().strftime('%Y-%m-%dT%H:%M')
            }, format='%Y-%m-%dT%H:%M')
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        self.fields['device'].queryset = Device.objects.select_related('group').order_by('group__name', 'resolution')
        self.fields['device'].label_from_instance = lambda obj: (
            f"{obj.group.name if obj.group else 'No Group'} ({obj.resolution if obj.resolution != 'Unknown' else 'Unknown Resolution'})"
        )
        
        self.fields['device'].empty_label = "Select Device (Optional)"
        
        self.fields['playlist_name'].required = True
        
        if self.user:
            self.initial['creator'] = self.user
            
        if self.instance and self.instance.expiration_date:
            self.initial['expiration_date'] = self.instance.expiration_date.strftime('%Y-%m-%dT%H:%M')

        if 'supported_device' in self.fields:
            del self.fields['supported_device']

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.user:
            instance.creator = self.user
        
        if commit:
            instance.save()
        return instance

class ScheduleForm(forms.ModelForm):
    class Meta:
        model = Schedule
        fields = [
            'schedule_name',
            'schedule_type',
            'publish_status',
            'content',
            'playlist',
            'playback_date',
            'never_expire',
            'repeat',
            'playback_start',
            'playback_end',
            'publish_to',
            'description',
        ]
        widgets = {
            'schedule_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter schedule name'
            }),
            'schedule_type': forms.Select(attrs={
                'class': 'form-select',
                'id': 'schedule-type-select'
            }),
            'publish_status': forms.Select(attrs={
                'class': 'form-select',
                'id': 'publish-status-select'
            }),
            'content': forms.Select(attrs={
                'class': 'form-select',
                'id': 'content-select'
            }),
            'playlist': forms.Select(attrs={
                'class': 'form-select',
                'id': 'playlist-select'
            }),
            'playback_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
                'id': 'playback-date'
            }, format='%Y-%m-%d'),
            'playback_start': forms.TimeInput(attrs={
                'type': 'time',
                'class': 'form-control',
                'id': 'playback-start'
            }, format='%H:%M'),
            'playback_end': forms.TimeInput(attrs={
                'type': 'time',
                'class': 'form-control',
                'id': 'playback-end'
            }, format='%H:%M'),
            'never_expire': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'id': 'never-expire'
            }),
            'repeat': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'id': 'repeat'
            }),
            'publish_to': forms.SelectMultiple(attrs={
                'class': 'form-select',
                'id': 'publish-to-select'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter schedule description'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['content'].required = False
        self.fields['playlist'].required = False
        self.fields['content'].queryset = Content.objects.all()
        self.fields['playlist'].queryset = Playlist.objects.all()
        self.fields['publish_to'].queryset = Device.objects.all().select_related('group')

        self.fields['playback_date'].input_formats = ['%Y-%m-%d']
        self.fields['playback_start'].input_formats = ['%H:%M']
        self.fields['playback_end'].input_formats = ['%H:%M']

    def clean(self):
        cleaned_data = super().clean()
        content = cleaned_data.get('content')
        playlist = cleaned_data.get('playlist')
        playback_start = cleaned_data.get('playback_start')
        playback_end = cleaned_data.get('playback_end')
        playback_date = cleaned_data.get('playback_date')
        never_expire = cleaned_data.get('never_expire')

        if content and playlist:
            raise forms.ValidationError("You can only select either Content OR Playlist, not both.")
        if not content and not playlist:
            raise forms.ValidationError("You must select either Content or Playlist.")
        
        if playback_start and playback_end and playback_start >= playback_end:
            raise forms.ValidationError("Playback end time must be after start time.")
        
        if not never_expire and playback_date and playback_date < timezone.now().date():
            raise forms.ValidationError("Playback date cannot be in the past unless 'Never Expire' is checked.")
            
        return cleaned_data

class DeviceForm(forms.ModelForm):
    class Meta:
        model = Device
        fields = ['name', 'ip_address', 'resolution', 'group', 'user_agent']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter device name'
            }),
            'ip_address': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter IP address'
            }),
            'resolution': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter resolution (e.g., 1920x1080)'
            }),
            'group': forms.Select(attrs={
                'class': 'form-select',
                'id': 'device-group-select'
            }),
            'user_agent': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'User agent string'
            }),
        }

    def clean_ip_address(self):
        ip_address = self.cleaned_data.get('ip_address')
        return ip_address

    def clean_resolution(self):
        resolution = self.cleaned_data.get('resolution')
        try:
            if 'x' in resolution:
                width, height = map(int, resolution.split('x'))
                if width <= 0 or height <= 0:
                    raise ValidationError("Resolution dimensions must be positive numbers")
            else:
                raise ValidationError("Resolution must be in WxH format (e.g., 1920x1080)")
        except ValueError:
            raise ValidationError("Resolution must be in WxH format with numbers (e.g., 1920x1080)")
        return resolution

class DeviceGroupForm(forms.ModelForm):
    class Meta:
        model = DeviceGroup
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter group name'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter group description'
            }),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if DeviceGroup.objects.filter(name__iexact=name).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise ValidationError("A group with this name already exists.")
        return name

class ManageForm(forms.ModelForm):
    device_group = forms.ModelChoiceField(
        queryset=DeviceGroup.objects.none(),  
        required=True,
        label="Device Group"
    )
    
    class Meta:
        model = Schedule
        fields = [
            'schedule_name',
            'schedule_type',
            'content',
            'playlist',
            'playback_date',
            'never_expire',
            'repeat',
            'playback_start',
            'playback_end',
            'description',
            'device_group'
        ]
        widgets = {
            'playback_date': forms.DateInput(attrs={'type': 'date'}),
            'playback_start': forms.TimeInput(attrs={'type': 'time'}),
            'playback_end': forms.TimeInput(attrs={'type': 'time'}),
            'schedule_type': forms.HiddenInput(),
            'repeat': forms.HiddenInput(),
            'never_expire': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['device_group'].queryset = DeviceGroup.objects.filter(devices__isnull=False).distinct()
        
        self.fields['publish_status'] = forms.CharField(
            initial='Published',
            widget=forms.HiddenInput(),
            required=False
        )
        self.fields['schedule_type'].initial = 'None'
        self.fields['repeat'].initial = False
        self.fields['never_expire'].initial = False