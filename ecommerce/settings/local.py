"""Development settings and globals."""
from __future__ import absolute_import

import os
from os.path import join, normpath

from ecommerce.settings.base import *
from ecommerce.settings.logger import get_logger_config


########## DEBUG CONFIGURATION
# See: https://docs.djangoproject.com/en/dev/ref/settings/#debug
DEBUG = True

# See: https://docs.djangoproject.com/en/dev/ref/settings/#template-debug
TEMPLATE_DEBUG = DEBUG
########## END DEBUG CONFIGURATION


########## EMAIL CONFIGURATION
# See: https://docs.djangoproject.com/en/dev/ref/settings/#email-backend
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
########## END EMAIL CONFIGURATION


########## DATABASE CONFIGURATION
# See: https://docs.djangoproject.com/en/dev/ref/settings/#databases
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': normpath(join(DJANGO_ROOT, 'default.db')),
        'USER': '',
        'PASSWORD': '',
        'HOST': '',
        'PORT': '',
    }
}
########## END DATABASE CONFIGURATION


########## CACHE CONFIGURATION
# See: https://docs.djangoproject.com/en/dev/ref/settings/#caches
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}
########## END CACHE CONFIGURATION


########## TOOLBAR CONFIGURATION
# See: http://django-debug-toolbar.readthedocs.org/en/latest/installation.html#explicit-setup

if os.environ.get('ENABLE_DJANGO_TOOLBAR', False):
    INSTALLED_APPS += (
        'debug_toolbar',
    )

    MIDDLEWARE_CLASSES += (
        'debug_toolbar.middleware.DebugToolbarMiddleware',
    )

    DEBUG_TOOLBAR_PATCH_SETTINGS = False

# http://django-debug-toolbar.readthedocs.org/en/latest/installation.html
INTERNAL_IPS = ('127.0.0.1',)
########## END TOOLBAR CONFIGURATION


########## AUTHENTICATION
# Set these to the correct values for your OAuth2/OpenID Connect provider (e.g., devstack)
SOCIAL_AUTH_EDX_OIDC_KEY = 'replace-me'
SOCIAL_AUTH_EDX_OIDC_SECRET = 'replace-me'
SOCIAL_AUTH_EDX_OIDC_URL_ROOT = 'http://127.0.0.1:8000/oauth2'
SOCIAL_AUTH_EDX_OIDC_ID_TOKEN_DECRYPTION_KEY = SOCIAL_AUTH_EDX_OIDC_SECRET

EDX_API_KEY = 'replace-me'
########## END AUTHENTICATION


LMS_COURSE_SHORTCUT_BASE_URL = 'https://courses.edx.org/courses'


########## BRANDING
PLATFORM_NAME = 'edX'
########## END BRANDING


########## SEGMENT
# 'None' disables tracking.  This will be turned on for test and production.
SEGMENT_KEY = os.environ.get('SEGMENT_WRITE_KEY')
########## END SEGMENT


LOGGING = get_logger_config(debug=DEBUG, dev_env=True, local_loglevel='DEBUG')