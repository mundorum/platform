# Docker Deployment

This guide covers deploying the noid platform on any machine using Docker Compose.
The stack starts three services in a single command: PostgreSQL, Authoring (Django), and Processing (FastAPI).

For local development without Docker see [dev-setup.md](dev-setup.md).

---

## Prerequisites

- [Docker Engine](https://docs.docker.com/engine/install/) 24+
- [Docker Compose plugin](https://docs.docker.com/compose/install/) (bundled with Docker Desktop; on Linux install the `docker-compose-plugin` package)
- Git

Verify the installation:

```bash
docker --version
docker compose version
```

---

## 1. Clone the repository

```bash
git clone <platform-repo-url>
cd platform/noid
```

---

## 2. Configure environment variables

Copy the example file and edit it:

```bash
cp .env.example .env
```

Open `.env` and set at minimum:

```dotenv
# Django secret key — generate with: python -c "import secrets; print(secrets.token_urlsafe(50))"
SECRET_KEY=<strong-random-value>

# API key shared between Authoring and Processing
PROCESSING_API_KEY=<strong-random-value>

# Postgres credentials (must match across all three variables below)
POSTGRES_USER=noid
POSTGRES_PASSWORD=<strong-random-value>
POSTGRES_DB=noid
DATABASE_URL=postgresql://noid:<strong-random-value>@db:5432/noid

# First manager account — seeded on first deploy
INITIAL_MANAGER_EMAIL=your-admin@example.com

# Google OAuth (required for login)
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com

# Comma-separated list of allowed frontend origins
CORS_ALLOWED_ORIGINS=http://localhost:8000
```

> **Note:** `DATABASE_URL` must match `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB`.
> If you keep all three at their defaults (`noid`/`noid`/`noid`) you can omit `DATABASE_URL` entirely
> and the compose default will be used.

---

## 3. Build the Docker images

```bash
docker compose build
```

This builds two images (`authoring` and `processing`) from the local source.
The `db` service uses the official `postgres:16` image and requires no build step.

To force a full rebuild without cache (e.g. after a base-image security update):

```bash
docker compose build --no-cache
```

---

## 4. Start the services

```bash
docker compose up -d
```

Docker Compose starts the services in dependency order:

1. `db` — PostgreSQL (waits for the healthcheck to pass)
2. `processing` — FastAPI scene execution engine
3. `authoring` — Django authoring UI (waits for both `db` and `processing`)

Check that all three are running:

```bash
docker compose ps
```

---

## 5. First-run: apply migrations and seed the initial manager

Run these once after the first `up`:

```bash
# Apply Django database migrations
docker compose exec authoring python manage.py migrate

# Create the initial manager account (email set in INITIAL_MANAGER_EMAIL)
docker compose exec authoring python manage.py seed_initial_manager
```

---

## 6. Verify the deployment

| Service | URL |
|---------|-----|
| Authoring UI | http://localhost:8000 |
| Processing API | http://localhost:8001 |
| Processing API docs | http://localhost:8001/docs |

Quick health checks:

```bash
curl http://localhost:8000/api/health/
curl http://localhost:8001/health
```

---

## Day-to-day operations

### View logs

```bash
# All services
docker compose logs -f

# Single service
docker compose logs -f authoring
docker compose logs -f processing
docker compose logs -f db
```

### Stop and restart

```bash
# Stop all services (data volumes are preserved)
docker compose down

# Start again
docker compose up -d
```

### Rebuild after a code change

```bash
# Rebuild and restart a single service
docker compose up -d --build authoring
docker compose up -d --build processing
```

### Run Django management commands

```bash
docker compose exec authoring python manage.py <command>

# Examples
docker compose exec authoring python manage.py createsuperuser
docker compose exec authoring python manage.py shell
```

### Update collections.yaml

Edit the root-level `collections.yaml`, then restart the affected services:

```bash
docker compose restart authoring processing
```

---

## Data persistence

Named Docker volumes survive `docker compose down` and image rebuilds.

| Volume | Contents |
|--------|----------|
| `noid_db` | PostgreSQL database files |
| `noid_storage` | Scene packages and shared resources |

To remove all data (irreversible):

```bash
docker compose down -v
```

To back up the database:

```bash
docker compose exec db pg_dump -U noid noid > noid_backup_$(date +%Y%m%d).sql
```

To restore:

```bash
cat noid_backup_YYYYMMDD.sql | docker compose exec -T db psql -U noid noid
```
