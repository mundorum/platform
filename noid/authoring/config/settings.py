import os
from pathlib import Path

# Load .env if present (dev convenience; production uses real env vars)
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent.parent / '.env')
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get('SECRET_KEY', 'noid-authoring-dev-key-not-for-production')
DEBUG = os.environ.get('DEBUG', 'true').lower() != 'false'
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '*').split(',')

# Django's default LOGGING only prints unhandled-exception tracebacks to
# console when DEBUG=True, and otherwise tries to email ADMINS (unconfigured
# here, so it silently does nothing). Without this, a 500 in production
# leaves no trace anywhere — override so tracebacks always reach stderr,
# which `docker compose logs authoring` picks up.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
        },
        'django.request': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'rest_framework',
    'rest_framework.authtoken',
    'accounts',
    'editor',
    'scenes',
    'libraries',
    'resources',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
]

ROOT_URLCONF = 'config.urls'

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

# ── database ──────────────────────────────────────────────────────────────────
# Default: SQLite in authoring/  (dev only — PostgreSQL required for production)
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
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
}

# ── Google OAuth ──────────────────────────────────────────────────────────────
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')

# ── CORS ──────────────────────────────────────────────────────────────────────
_cors_origins = os.environ.get('CORS_ALLOWED_ORIGINS', '')
CORS_ALLOWED_ORIGINS = [o.strip() for o in _cors_origins.split(',') if o.strip()]
CORS_ALLOW_CREDENTIALS = True

# ── initial manager seed ──────────────────────────────────────────────────────
INITIAL_MANAGER_EMAIL = os.environ.get('INITIAL_MANAGER_EMAIL', '')

# ── scene packages ────────────────────────────────────────────────────────────
_NOID_ROOT = BASE_DIR.parent  # noid/ — used to anchor relative env-var paths


def _resolve_noid_path(env_var: str, default_name: str) -> str:
    raw = os.environ.get(env_var, '')
    if raw:
        p = Path(raw)
        return str(p if p.is_absolute() else (_NOID_ROOT / p).resolve())
    return str(_NOID_ROOT / default_name)


SCENE_PACKAGES_DIR = _resolve_noid_path('SCENE_PACKAGES_DIR', 'scene_packages')

# ── shared resource store ─────────────────────────────────────────────────────
SHARED_RESOURCES_DIR = _resolve_noid_path('SHARED_RESOURCES_DIR', 'shared_resources')

# ── processing machine ────────────────────────────────────────────────────────
PROCESSING_URL = os.environ.get('PROCESSING_URL', 'http://localhost:8001')
PROCESSING_API_KEY = os.environ.get('PROCESSING_API_KEY', 'dev-key')
