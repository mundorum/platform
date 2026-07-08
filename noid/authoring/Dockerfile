FROM python:3.11-slim

RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install shared runner package first (build context is noid/)
COPY runner/ runner/
RUN pip install --no-cache-dir -e runner/

# Install authoring dependencies
COPY authoring/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy authoring source
COPY authoring/ authoring/

# Shared collections config (read by both authoring and processing)
COPY collections.yaml .

WORKDIR /app/authoring

ENV DJANGO_SETTINGS_MODULE=config.settings
ENV PYTHONUNBUFFERED=1

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
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "3700"]
