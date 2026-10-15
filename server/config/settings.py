"""
Shared Django settings for the Mundorum platform server.

One Django project serves every subproject that shares the server:
  /        portal (subproject chooser)
  /noid/   noid authoring (apps live in noid/authoring/)
  /vp/     VP Studio (apps live in vp/server/)
plus the shared /auth/, /admin/ and /static/.
"""
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent      # server/
REPO_ROOT = BASE_DIR.parent                            # platform/
NOID_ROOT = REPO_ROOT / 'noid'
VP_ROOT = REPO_ROOT / 'vp'

# Subproject apps live in their own folders; make them importable by their
# plain app names (scenes, editor, vp_studio, ...) — the same names noid used
# before the move, so app labels, table names and migration history are
# unchanged. Docker keeps this same relative layout under /app.
for _apps_dir in (NOID_ROOT / 'authoring', VP_ROOT / 'server'):
    if str(_apps_dir) not in sys.path:
        sys.path.insert(0, str(_apps_dir))

# Load .env if present (dev convenience; production uses real env vars).
# The repository-root .env is canonical; noid/.env is still read as a
# fallback so an existing dev setup keeps working (load_dotenv never
# overrides a variable that is already set, so the root file wins).
try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / '.env')
    load_dotenv(NOID_ROOT / '.env')
except ImportError:
    pass

# A relative COLLECTIONS_FILE is relative to noid/ (where collections.yaml
# lives), not to the CWD — so it is found regardless of where manage.py is
# run from. Must happen before noid_runner.catalog is imported.
_collections = os.environ.get('COLLECTIONS_FILE', '')
if _collections and not Path(_collections).is_absolute():
    os.environ['COLLECTIONS_FILE'] = str((NOID_ROOT / _collections).resolve())

SECRET_KEY = os.environ.get('SECRET_KEY', 'mundorum-server-dev-key-not-for-production')
DEBUG = os.environ.get('DEBUG', 'true').lower() != 'false'
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '*').split(',')

# Behind a TLS-terminating reverse proxy (e.g. Nginx Proxy Manager) this
# container only ever sees plain HTTP, so request.is_secure() is False unless
# told otherwise — and Django's CSRF check builds its expected Origin as
# scheme + host using is_secure(). Without this, that computed
# "http://<host>" never matches the browser's real "https://<host>" Origin
# header, and every unsafe request (including the admin login POST) gets
# rejected with a CSRF 403. Only safe with a proxy that sets this header
# itself and strips any client-supplied copy first (NPM does both).
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Django's default LOGGING only prints unhandled-exception tracebacks to
# console when DEBUG=True, and otherwise tries to email ADMINS (unconfigured
# here, so it silently does nothing). Without this, a 500 in production
# leaves no trace anywhere — override so tracebacks always reach stderr,
# which `docker compose logs server` picks up.
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
        'llm': {
            'handlers': ['console'],
            'level': 'INFO',
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
    # shared (server/)
    'accounts',
    'portal',
    'llm',
    # noid (noid/authoring/)
    'editor',
    'scenes',
    'libraries',
    'resources',
    # vp (vp/server/)
    'vp_studio',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
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
# Default: SQLite in server/  (dev only — PostgreSQL required for production)
# Production: set DATABASE_URL=postgres://user:pass@host/dbname
# Every subproject shares this one database; Django's app labels keep their
# tables apart (scenes_*, accounts_*, vp_*, llm_*).
_db_url = os.environ.get('DATABASE_URL', '')
if _db_url:
    import dj_database_url
    DATABASES = {'default': dj_database_url.config(default=_db_url)}
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'server.db',
        }
    }

# ── static files ──────────────────────────────────────────────────────────────
# Gunicorn never serves /static/ on its own, and there's no separate web
# server or nginx location for it in front of this container (NPM forwards
# straight to gunicorn) — so admin's own CSS/JS (and anything else under
# STATIC_URL) is 404 in production without something serving it from inside
# the app itself. Whitenoise does that, backed by a manifest built by
# `collectstatic` at image build time (see server/Dockerfile).
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

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

# Where the Google redirect callback may send the user back to, keyed by the
# `next` value the frontend passes on login_uri. Anything else falls back to
# the portal — never redirect to a caller-supplied URL (open redirect).
AUTH_NEXT_PATHS = {
    '': '/',
    'noid': '/noid/',
    'vp': '/vp/',
}

# ── CORS ──────────────────────────────────────────────────────────────────────
_cors_origins = os.environ.get('CORS_ALLOWED_ORIGINS', '')
CORS_ALLOWED_ORIGINS = [o.strip() for o in _cors_origins.split(',') if o.strip()]
CORS_ALLOW_CREDENTIALS = True

# ── CSRF ──────────────────────────────────────────────────────────────────────
# Belt-and-suspenders alongside SECURE_PROXY_SSL_HEADER above: with that header
# set correctly this shouldn't be needed for same-origin admin/API POSTs, but
# it's what Django actually asks for when trusting an origin behind a proxy,
# and it's required if this app is ever served from more than one hostname.
_csrf_origins = os.environ.get('CSRF_TRUSTED_ORIGINS', '')
CSRF_TRUSTED_ORIGINS = [o.strip() for o in _csrf_origins.split(',') if o.strip()]

# ── initial manager seed ──────────────────────────────────────────────────────
INITIAL_MANAGER_EMAIL = os.environ.get('INITIAL_MANAGER_EMAIL', '')

# ── noid: scene packages ──────────────────────────────────────────────────────
def _resolve_noid_path(env_var: str, default_name: str) -> str:
    """Relative paths in noid env vars are anchored at noid/ (as before the move)."""
    raw = os.environ.get(env_var, '')
    if raw:
        p = Path(raw)
        return str(p if p.is_absolute() else (NOID_ROOT / p).resolve())
    return str(NOID_ROOT / default_name)


SCENE_PACKAGES_DIR = _resolve_noid_path('SCENE_PACKAGES_DIR', 'scene_packages')

# ── noid: shared resource store ───────────────────────────────────────────────
SHARED_RESOURCES_DIR = _resolve_noid_path('SHARED_RESOURCES_DIR', 'shared_resources')

# ── noid: processing machine ──────────────────────────────────────────────────
PROCESSING_URL = os.environ.get('PROCESSING_URL', 'http://localhost:8001')
PROCESSING_API_KEY = os.environ.get('PROCESSING_API_KEY', 'dev-key')

# ── LLM gateway ───────────────────────────────────────────────────────────────
# Provider API keys are NOT read from settings or the database. The gateway
# (server/llm/) reads each key from a file — <PROVIDER>_API_KEY_FILE if set,
# else <LLM_SECRETS_DIR>/<provider>_api_key — falling back to the
# <PROVIDER>_API_KEY env var only for local dev. In Docker, ./secrets/ is
# mounted read-only at /run/secrets. See docs/llm-gateway.md.
LLM_SECRETS_DIR = os.environ.get(
    'LLM_SECRETS_DIR',
    '/run/secrets' if Path('/run/secrets').is_dir() else str(REPO_ROOT / 'secrets'),
)
LLM_DEFAULT_PROVIDER = os.environ.get('LLM_DEFAULT_PROVIDER', 'groq')
LLM_DEFAULT_MODEL = os.environ.get('LLM_DEFAULT_MODEL', '')
# Default model per provider (<PROVIDER>_MODEL); LLM_DEFAULT_MODEL fills in
# for the default provider. Model ids change often — list the valid ones
# with `python manage.py llm_check <provider> --list-models`.
LLM_PROVIDER_MODELS = {
    p: os.environ.get(f'{p.upper()}_MODEL', '') for p in ('groq', 'openrouter', 'mistral')
}
# Sent to OpenRouter as HTTP-Referer (optional app attribution).
LLM_APP_URL = os.environ.get('LLM_APP_URL', '')
LLM_MAX_TOKENS = int(os.environ.get('LLM_MAX_TOKENS', '2048'))
LLM_TIMEOUT_SECONDS = float(os.environ.get('LLM_TIMEOUT_SECONDS', '120'))
# Per-user ceiling on gateway calls, a guard against runaway loops or abuse
# spending the platform's provider credit. 0 disables the limit.
LLM_USER_CALLS_PER_HOUR = int(os.environ.get('LLM_USER_CALLS_PER_HOUR', '300'))
