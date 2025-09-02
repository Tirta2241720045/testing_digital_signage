"""
Django settings for signage_project project.
"""

import os
from pathlib import Path
from sys import stdout

if stdout.isatty():
    from django.core.servers.basehttp import WSGIServer
    WSGIServer.handle_error = lambda *args, **kwargs: None

LOGIN_URL = '/login/' 
LOGIN_REDIRECT_URL = '/dashboard/' 
LOGOUT_REDIRECT_URL = '/login/'

SESSION_COOKIE_AGE = 3600 
SESSION_SAVE_EVERY_REQUEST = True

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings
SECRET_KEY = 'django-insecure-+1(ealmglh1s6^v3b*f-abxff*q=(uso427g1rs%n+sd96c3_w'
DEBUG = True
ALLOWED_HOSTS = ['*']

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'signage',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'signage.middleware.DeviceTrackerMiddleware',
    'signage.middleware.DigitalSignageMiddleware', 
]

ROOT_URLCONF = 'signage_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'signage' / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.media',
            ],
        },
    },
]

WSGI_APPLICATION = 'signage_project.wsgi.application'

# Database - FIXED: removed init_command for PostgreSQL
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'Signage',
        'USER': 'postgres',
        'PASSWORD': 'polinema',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 8,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
USE_I18N = True
USE_TZ = True
TIME_ZONE = 'Asia/Jakarta'

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# CSRF Settings
CSRF_COOKIE_SECURE = False
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_TRUSTED_ORIGINS = ['http://localhost:8000', 'http://127.0.0.1:8000']

# File Upload Settings
DATA_UPLOAD_MAX_MEMORY_SIZE = 52428800  # 50MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 52428800  # 50MB
ALLOWED_FILE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp', '.mp4', '.mov', '.avi', '.mkv']

# Digital Signage Settings
SIGNAGE_SETTINGS = {
    'DEVICE_PING_INTERVAL': 300,
    'DEVICE_OFFLINE_THRESHOLD': 600,
    'DEFAULT_CONTENT_DURATION': 10000,
    'DEFAULT_REFRESH_INTERVAL': 30,
    'MAX_CONTENT_SIZE': 100 * 1024 * 1024,
    'SUPPORTED_IMAGE_FORMATS': ['JPEG', 'PNG', 'WEBP'],
    'SUPPORTED_VIDEO_FORMATS': ['MP4', 'AVI', 'MOV', 'MKV'],
}

# Cache settings
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'signage-cache',
        'TIMEOUT': 300,
        'OPTIONS': {
            'MAX_ENTRIES': 1000,
        }
    }
}

# Security settings
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'SAMEORIGIN'

# Create necessary directories
os.makedirs(BASE_DIR / 'staticfiles', exist_ok=True)
os.makedirs(BASE_DIR / 'media', exist_ok=True)
os.makedirs(BASE_DIR / 'logs', exist_ok=True)