FROM python:3.11-slim

WORKDIR /app

# Install shared runner package first (build context is noid/)
COPY runner/ runner/
RUN pip install --no-cache-dir -e runner/

# Install authoring dependencies
COPY authoring/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy authoring source
COPY authoring/ authoring/

WORKDIR /app/authoring

ENV DJANGO_SETTINGS_MODULE=config.settings
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2"]
