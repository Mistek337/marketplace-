"""Настройки только для pytest (SQLite in-memory)."""

from .settings import *  # noqa: F403

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

B2B_BASE_URL = 'https://b2b.example'
MODERATION_TO_B2B_KEY = 'test-mod-b2b-key'
B2B_TO_MODERATION_KEY = 'test-b2b-mod-key'
