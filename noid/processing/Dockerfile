FROM python:3.11-slim

WORKDIR /app

# Install shared runner package first (build context is noid/)
COPY runner/ runner/
RUN pip install --no-cache-dir -e runner/

# Install processing dependencies
COPY processing/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy processing source
COPY processing/ processing/

ENV PYTHONUNBUFFERED=1

EXPOSE 8001

CMD ["uvicorn", "processing.main:app", "--host", "0.0.0.0", "--port", "8001"]
