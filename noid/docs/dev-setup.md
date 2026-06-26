# Development Setup

---

## Prerequisites

- Python 3.11+
- PostgreSQL 16+ (or start it via Docker — see below)
- Git
- (Optional) NVIDIA GPU + drivers if you need GPU workloads on the Processing server

---

## First-time setup

```bash
cd platform/noid

# Create the shared virtualenv (used by both servers in development)
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# Install the shared noid_runner package in editable mode
pip install -e runner/

# Install dependencies for both servers
pip install -r authoring/requirements.txt
pip install -r processing/requirements.txt

# Copy and configure environment variables
cp .env.example .env
# Edit .env and set at minimum:
#   DATABASE_URL=postgres://noid:noid@localhost:5432/noid
#   PROCESSING_URL=http://localhost:8001
#   PROCESSING_API_KEY=dev-key
#   COLLECTIONS_FILE=../collections.yaml
#   SCENE_PACKAGES_DIR=../scene_packages

# Create the authoring database schema
python authoring/manage.py migrate

# Add the first manager in the database
python manage.py seed_initial_manager
```

---

## Running the servers

```bash
# Terminal 1 — Authoring Machine (Django)
source .venv/bin/activate
python authoring/manage.py runserver 8000

# Terminal 2 — Processing Machine (FastAPI)
source .venv/bin/activate
uvicorn processing.main:app --reload --port 8001
```

| Server | URL |
|--------|-----|
| Authoring | http://localhost:8000 |
| Processing API | http://localhost:8001 |
| Processing docs | http://localhost:8001/docs |

---

## Running with Docker Compose

Docker Compose starts PostgreSQL, Authoring, and Processing in one command.
The build context is `noid/` so both Dockerfiles can access `runner/`.

```bash
# from noid/
cp .env.example .env   # edit if needed
docker compose up --build
```

To rebuild a single service after a code change:

```bash
docker compose up --build authoring
docker compose up --build processing
```

---

## Running tests

```bash
# noid_runner unit tests (no server or DB needed)
pytest runner/

# Authoring Django integration tests (requires a running PostgreSQL)
pytest authoring/

# Processing FastAPI tests
pytest processing/
```

Tests use a real PostgreSQL database — no mocking. The test database is created
and destroyed automatically by `pytest-django`.

---

## Common development tasks

### Add a component collection

1. Add the Python module path to `collections.yaml` under the appropriate label.
2. Restart both servers (or on Processing, `DELETE /deploy/{id}` + `POST /deploy/{id}`
   to reload the registry for an affected scene).

### Add a scene-specific component

1. Create a `.py` file decorated with `@Noid.component(spec)` in
   `scene_packages/{scene_id}/components/`.
2. Upload it via `POST /scenes/{id}/components/` or include it in a ZIP import.
3. SceneRegistry will reload the component automatically when the file mtime changes.

### Upload a full scene package

```bash
zip -r my_scene.zip scene.json components/ data/
curl -X POST http://localhost:8000/api/scenes/import/ \
     -F "file=@my_scene.zip"
```

### Download a scene package

```bash
curl http://localhost:8000/api/scenes/{id}/export/ -o my_scene.zip
```

### Run a scene via the Authoring Machine (proxies to Processing)

```bash
# Blocking — returns {stdout, stderr, returncode, run_id}
curl -X POST http://localhost:8000/api/scenes/{id}/run/

# Streaming — output lines arrive as they are produced
curl -N -X POST http://localhost:8000/api/scenes/{id}/run/stream/
```

### Run a scene directly via the scratch endpoint (no DB record)

```bash
# Quick run via the editor scratch endpoint
curl -X POST http://localhost:8000/api/play/ \
     -H "Content-Type: application/json" \
     -d @scene.json

# Stream output
curl -N -X POST http://localhost:8000/api/play/stream/ \
     -H "Content-Type: application/json" \
     -d @scene.json
```
