FROM python:3.11-slim

RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

# Build context is the repository root (platform/). The image keeps the
# repository's relative layout under /app, which server/config/settings.py
# relies on to find each subproject's apps (noid/authoring, vp/server).
WORKDIR /app

# noid's shared runner package first
COPY noid/runner/ noid/runner/
RUN pip install --no-cache-dir -e noid/runner/

# Dependencies: server/requirements.txt pulls in each subproject's own file
COPY server/requirements.txt server/requirements.txt
COPY noid/authoring/requirements.txt noid/authoring/requirements.txt
COPY vp/server/requirements.txt vp/server/requirements.txt
RUN pip install --no-cache-dir -r server/requirements.txt

# Subproject sources
COPY noid/collections.yaml noid/collections.yaml
COPY noid/authoring/ noid/authoring/
COPY vp/server/ vp/server/
COPY vp/web/ vp/web/

# Shared server (Django project, accounts, portal, llm)
COPY server/ server/

WORKDIR /app/server

ENV DJANGO_SETTINGS_MODULE=config.settings
ENV PYTHONUNBUFFERED=1

# Builds the whitenoise-served static manifest (admin CSS/JS, etc.) into
# STATIC_ROOT. Doesn't touch the database, so it's safe to run at build time
# with no real env vars present — settings.py's defaults are enough.
RUN python manage.py collectstatic --noinput

EXPOSE 8000

# Scenes have their own timeout/cancel machinery (editor/views.py
# _resolve_timeout, runner.py's subprocess timer, RunCancelView) and are
# allowed to run for minutes to hours by design (timeout presets up to
# 3600s, or unlimited when unset) — gunicorn's default 30s kill fired
# mid-stream on a legitimate long-running run rather than a hung one, since
# sync workers can't distinguish the two for a single in-progress streaming
# response. We tried --timeout 0 (disabled) to fix that, but a scene with a
# real app-level bug (bad notice wiring — never published 'player/done')
# hung forever with no ceiling at all, and with only 2 sync workers two such
# requests were enough to exhaust every worker and take the whole service
# down — not just the one broken request. --timeout 3700 keeps slightly more
# headroom than the app's own longest preset (3600s) while still giving
# gunicorn a last-resort way to reclaim a worker from a genuinely stuck
# request. If you need scenes to legitimately run longer than that, raise
# this value and consider raising --workers too, rather than disabling the
# timeout again.
# Note: this ceiling only exists for *sync* workers. With gthread/async
# workers, --timeout only tracks the worker process's heartbeat, not the
# length of a request, so a stuck request is never reclaimed. Keep that in
# mind before switching worker class to get more concurrency for vp.
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "3700"]
