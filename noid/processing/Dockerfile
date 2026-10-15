FROM python:3.11-slim

RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Build context is the repository root (platform/); the image layout
# under /app is unchanged from when the context was noid/.
# Install shared runner package first
COPY noid/runner/ runner/
RUN pip install --no-cache-dir -e runner/

# Install processing dependencies
COPY noid/processing/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy processing source
COPY noid/processing/ processing/

# Shared collections config (read by both authoring and processing)
COPY noid/collections.yaml .

ENV PYTHONUNBUFFERED=1

EXPOSE 8001

CMD ["uvicorn", "processing.main:app", "--host", "0.0.0.0", "--port", "8001"]
