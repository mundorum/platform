import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get('SECRET_KEY', 'noid-authoring-dev-key-not-for-production')
DEBUG = os.environ.get('DEBUG', 'true').lower() != 'false'
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '*').split(',')

INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'django.contrib.staticfiles',
    'rest_framework',
    'editor',
    'scenes',
]

MIDDLEWARE = [
    'django.middleware.common.CommonMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': False,
        'OPTIONS': {'context_processors': []},
    },
]

# ── database ──────────────────────────────────────────────────────────────────
# Default: SQLite in authoring/.
# Production: set DATABASE_URL=postgres://user:pass@host/dbname
_db_url = os.environ.get('DATABASE_URL', '')
if _db_url:
    import dj_database_url
    DATABASES = {'default': dj_database_url.config(default=_db_url)}
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'authoring.db',
        }
    }

# ── static files ──────────────────────────────────────────────────────────────
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']

WSGI_APPLICATION = 'config.wsgi.application'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── DRF ───────────────────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [],
    'DEFAULT_PERMISSION_CLASSES': [],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
}

# ── scene packages ────────────────────────────────────────────────────────────
# Unpacked scene packages live at noid/scene_packages/ in dev.
# Each production machine mounts its own volume and sets this env var.
SCENE_PACKAGES_DIR = os.environ.get(
    'SCENE_PACKAGES_DIR',
    str(BASE_DIR.parent / 'scene_packages'),
)

# ── processing machine ────────────────────────────────────────────────────────
PROCESSING_URL = os.environ.get('PROCESSING_URL', 'http://localhost:8001')
PROCESSING_API_KEY = os.environ.get('PROCESSING_API_KEY', 'dev-key')
