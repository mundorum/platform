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

# --timeout 0 disables gunicorn's worker-timeout kill. Scenes have their own
# timeout/cancel machinery (editor/views.py _resolve_timeout, runner.py's
# subprocess timer, RunCancelView) and are allowed to run for minutes to
# hours by design (timeout presets up to 3600s, or unlimited when unset) —
# gunicorn's default 30s kill fired mid-stream on a legitimate long-running
# run rather than a hung one, since sync workers can't distinguish the two
# for a single in-progress streaming response.
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "0"]
