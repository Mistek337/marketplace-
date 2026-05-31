"""
WSGI config for the moderation project.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'moderation.settings')

application = get_wsgi_application()
