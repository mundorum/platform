# Docker Deployment

This guide covers deploying the Mundorum platform on any machine with Docker
Compose. One command starts three services:

| Service | What it runs |
|---------|--------------|
| `db` | PostgreSQL 16, one database shared by every subproject |
| `server` | The shared Django server: portal (`/`), noid (`/noid/`), VP Studio (`/vp/`), plus `/auth/` and `/admin/` |
| `noid-processing` | noid's FastAPI scene execution engine (internal only) |

For local development without Docker, see [dev-setup.md](dev-setup.md).

---

## Prerequisites

- [Docker Engine](https://docs.docker.com/engine/install/) 24+
- [Docker Compose plugin](https://docs.docker.com/compose/install/) v2 (bundled with Docker Desktop; on Linux install the `docker-compose-plugin` package)
- Git

```bash
docker --version
docker compose version
```

---

## 1. Clone the repository

```bash
git clone https://github.com/mundorum/platform.git
cd platform
```

Every command below runs from the repository root. That is also the Docker
build context for every image.

---

## 2. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and set at minimum:

```dotenv
# Django secret key: python -c "import secrets; print(secrets.token_urlsafe(50))"
SECRET_KEY=<strong-random-value>

# Shared secret between the server and noid-processing
PROCESSING_API_KEY=<strong-random-value>

# Postgres credentials (must match DATABASE_URL). Use a hex password:
# python -c "import secrets; print(secrets.token_hex(12))"
POSTGRES_USER=noid
POSTGRES_PASSWORD=<hex-value>
POSTGRES_DB=noid
DATABASE_URL=postgresql://noid:<hex-value>@db:5432/noid

# First manager account, seeded on first deploy
INITIAL_MANAGER_EMAIL=your-admin@example.com

# Google OAuth (shared sign-in, required for login)
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com

CORS_ALLOWED_ORIGINS=http://localhost:8000
```

> `DATABASE_URL` must match `POSTGRES_USER`, `POSTGRES_PASSWORD` and
> `POSTGRES_DB`. Avoid `#`, `@`, `:` and `/` in the password: they break URL
> parsing silently.

### LLM provider keys

VP Studio calls LLMs through the server's [LLM gateway](llm-gateway.md).
Provider keys are **files** in `secrets/`, not variables in `.env`:

```bash
umask 077
printf '%s' '<your-groq-key>' > secrets/groq_api_key
# optional: secrets/openrouter_api_key, secrets/mistral_api_key
```

Then choose the default provider and model in `.env`:

```dotenv
LLM_DEFAULT_PROVIDER=groq
GROQ_MODEL=<model id>
```

---

## 3. Create the data volumes (once)

The volumes are declared `external` in `docker-compose.yml`. Compose refuses to
start without them instead of silently creating empty ones, and
`docker compose down -v` cannot delete them.

```bash
docker volume create mundorum_db
docker volume create mundorum_noid_storage
```

---

## 4. Build and start

```bash
docker compose build
docker compose up -d
docker compose ps
```

Startup order: `db` (waits for its healthcheck), `noid-processing`, then
`server`.

To force a full rebuild (e.g. after a base-image security update):

```bash
docker compose build --no-cache
```

---

## 5. First run: migrations and initial manager

```bash
docker compose exec server python manage.py migrate
docker compose exec server python manage.py seed_initial_manager
```

---

## 6. Verify

| What | URL |
|------|-----|
| Portal | http://localhost:8000/ |
| noid editor | http://localhost:8000/noid/ |
| VP Studio | http://localhost:8000/vp/ |
| noid processing API docs | http://localhost:8001/docs |

```bash
curl -o /dev/null -s -w "%{http_code}\n" http://localhost:8000/
curl http://localhost:8000/auth/config/
curl -H "Authorization: Bearer ${PROCESSING_API_KEY}" http://localhost:8001/health

# Which LLM providers have a key (keys are never printed)
docker compose exec server python manage.py llm_check
# Send a test prompt / list model ids
docker compose exec server python manage.py llm_check groq
docker compose exec server python manage.py llm_check groq --list-models
```

> If `ALLOWED_HOSTS` is restricted to a specific domain, requests to
> `localhost` get `400 Bad Request` whatever the path. Django rejects them on
> the `Host` header. Send it explicitly:
> `curl -H "Host: <your-domain>" http://localhost:8000/auth/config/`

---

## Production deployment behind a reverse proxy

Only the **server** should be reachable from the internet. `noid-processing`
is called by the server over the Docker network
(`PROCESSING_URL=http://noid-processing:8001`), and every route on it requires
a bearer token. Don't create a public proxy entry for it.

### Environment for production

```dotenv
DEBUG=false
ALLOWED_HOSTS=<your-domain>
CORS_ALLOWED_ORIGINS=https://<your-domain>
CSRF_TRUSTED_ORIGINS=https://<your-domain>
SERVER_PORT=<free-host-port>
```

`CSRF_TRUSTED_ORIGINS` (with scheme) is required behind a reverse proxy that
terminates TLS. Without it, and without `SECURE_PROXY_SSL_HEADER` (already set
unconditionally in `server/config/settings.py`), Django's CSRF check rejects
every POST, including the `/admin/` login, with a 403.

`SERVER_PORT` / `PROCESSING_PORT` choose the published host ports (default
`8000` / `8001`). `AUTHORING_PORT` is still accepted as the old name of
`SERVER_PORT`.

For Google sign-in, register `https://<your-domain>` as an authorized
JavaScript origin and `https://<your-domain>/auth/google/callback/` as an
authorized redirect URI. There is one callback for every subproject: the
frontend adds `?next=noid` or `?next=vp`, and the server sends the user back
to that app.

### Reverse proxy configuration

Point the proxy (nginx, Nginx Proxy Manager, Caddy, Traefik, ...) at the
server's published port, with TLS terminated at the proxy:

```
https://<your-domain>  →  http://<docker-host-address>:<SERVER_PORT>
```

One location (`/`) is enough. Django routes `/`, `/noid/`, `/vp/`, `/auth/`,
`/admin/` and `/static/` itself, so no path-based proxy rules are needed.

If the proxy runs in a container (common with Nginx Proxy Manager), it
usually can't reach the target through `127.0.0.1`. Use the Docker bridge
gateway address instead (`ip addr show docker0`).

---

## Day-to-day operations

### Logs

```bash
docker compose logs -f
docker compose logs -f server
docker compose logs -f noid-processing
```

### Stop and restart

```bash
docker compose down        # volumes are external: never touched
docker compose up -d
```

### Deploy an update

```bash
git pull
docker compose up -d --build
docker compose exec server python manage.py migrate   # if there are new migrations
```

### Management commands

```bash
docker compose exec server python manage.py <command>
docker compose exec -it server python manage.py createsuperuser
docker compose exec server python manage.py shell
```

### Update noid's collections.yaml

If you are only enabling or disabling collections that are already
installed, edit `noid/collections.yaml` and restart:

```bash
docker compose restart server noid-processing
```

If a **new** collection needs a package that isn't in the images yet, add it
to both `noid/authoring/requirements.txt` and
`noid/processing/requirements.txt`, then rebuild:

```bash
docker compose up -d --build
```

---

## Data persistence

| Volume | Contents |
|--------|----------|
| `mundorum_db` | PostgreSQL database files (every subproject) |
| `mundorum_noid_storage` | noid scene packages and shared resources |

Backup and restore:

```bash
docker compose exec -T db pg_dump -U noid -Fc noid > mundorum_$(date +%Y%m%d).dump
docker compose exec -T db pg_restore -U noid -d noid --clean < mundorum_YYYYMMDD.dump
```

Removing data is deliberately manual: `docker volume rm mundorum_db
mundorum_noid_storage` (irreversible).

---

## Upgrading from the noid-only deployment

Before the server was shared, the stack lived in `noid/docker-compose.yml`.
Its volumes were named after that folder (`noid_noid_db`,
`noid_noid_storage`). The new compose file uses `mundorum_*` volumes, so the
data has to be copied once. Docker can't rename volumes.

```bash
# 0. Note the current commit (for rollback) and confirm the old volume names
git rev-parse HEAD
docker volume ls | grep noid

# 1. Logical backup as a safety net
cd noid
docker compose exec -T db pg_dump -U noid -Fc noid > ~/noid-$(date +%F).dump

# 2. Stop the old stack. Do NOT pass -v
docker compose down
cd ..

# 3. Copy the data into the new volumes (stopped containers = consistent copy)
docker volume create mundorum_db
docker volume create mundorum_noid_storage
docker run --rm -v noid_noid_db:/from:ro      -v mundorum_db:/to           alpine sh -c 'cp -a /from/. /to/'
docker run --rm -v noid_noid_storage:/from:ro -v mundorum_noid_storage:/to alpine sh -c 'cp -a /from/. /to/'

# 4. Move noid/.env to the root and start the new stack
git pull
mv noid/.env .env
docker compose up -d --build
docker compose exec server python manage.py migrate
```

Keep the old `noid_noid_*` volumes until you have used the new deployment for
a while. To roll back: `docker compose down`, `git checkout <noted commit>`,
`mv .env noid/.env`, and `cd noid && docker compose up -d`.
