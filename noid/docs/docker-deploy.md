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

## Production deployment behind a reverse proxy

In production, only **Authoring** should be reachable from the internet. Processing
is called server-side by Authoring over the Docker network
(`PROCESSING_URL=http://processing:8001`) and every one of its routes requires a
bearer token — it has no reason to be exposed publicly, and doing so only adds
attack surface. Don't create a public proxy entry for it.

### Environment for production

In `.env`, beyond the values from step 2, set:

```dotenv
DEBUG=false
ALLOWED_HOSTS=<your-domain>
CORS_ALLOWED_ORIGINS=https://<your-domain>
```

`docker-compose.yml` also reads `AUTHORING_PORT` / `PROCESSING_PORT` to control which
host ports get published (default `8000`/`8001`). On a shared host running other
Dockerized services, pick free ports for these:

```dotenv
AUTHORING_PORT=<free-host-port>
```

If you're using Google OAuth login, register `https://<your-domain>` as an
authorized JavaScript origin and `https://<your-domain>/auth/google/callback/` as
an authorized redirect URI on the OAuth client — the frontend derives the
callback URL from `window.location.origin`, so no code change is needed, just the
OAuth client configuration.

### Reverse proxy configuration

Point your reverse proxy (nginx, Nginx Proxy Manager, Caddy, Traefik, etc.) at the
Authoring container's published port, with SSL/TLS terminated at the proxy:

```
https://<your-domain>  →  http://<docker-host-address>:<AUTHORING_PORT>
```

A single location (`/`) is enough — Authoring serves the UI, `/api/`, and `/auth/`
from one Django app on one port, so no path-based routing is required.

If your proxy itself runs in a container (common with Nginx Proxy Manager), it
generally can't reach the target container via `127.0.0.1` — it needs the Docker
bridge gateway address instead. Find it with:

```bash
ip addr show docker0   # or: docker network inspect bridge
```

Do not publish or proxy the Processing port publicly. If you want to keep it
reachable for local debugging on the host, restrict it at the firewall rather
than routing it through the reverse proxy.

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
