"""
Django settings for the b2b project.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

SECRET_KEY = 'django-insecure-change-me-in-production'

DEBUG = True

ALLOWED_HOSTS: list[str] = [
    h.strip()
    for h in os.environ.get(
        "DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver"
    ).split(",")
    if h.strip()
]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'catalog',
    'invoices',
    'sellers',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'b2b.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'b2b.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('POSTGRES_DB', 'b2b'),
        'USER': os.environ.get('POSTGRES_USER', 'postgres'),
        'PASSWORD': os.environ.get('POSTGRES_PASSWORD')
        or os.environ.get('PGPASSWORD', ''),
        'HOST': os.environ.get('POSTGRES_HOST', '127.0.0.1'),
        'PORT': os.environ.get('POSTGRES_PORT', '5432'),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'EXCEPTION_HANDLER': 'b2b.api_exceptions.b2b_exception_handler',
}

B2C_TO_B2B_KEY = os.environ.get("B2C_TO_B2B_KEY", "dev-b2c-key")

# Локальная отладка B2C↔B2B: список товаров для витрины без фильтра MODERATED/остатка (только deleted=False).
# На продакшене переменная должна быть выключена.
CATALOG_DEV_VISIBILITY = os.environ.get("CATALOG_DEV_VISIBILITY", "").lower() in (
    "1",
    "true",
    "yes",
)

MODERATION_BASE_URL = os.environ.get("MODERATION_BASE_URL", "")
B2B_TO_MODERATION_KEY = os.environ.get("B2B_TO_MODERATION_KEY", "")
MODERATION_TIMEOUT = float(os.environ.get("MODERATION_TIMEOUT", "5"))
MODERATION_TO_B2B_KEY = os.environ.get("MODERATION_TO_B2B_KEY", "")
