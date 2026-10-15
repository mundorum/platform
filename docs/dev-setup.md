# Development Setup

How to run the shared server (portal, noid, VP Studio) and noid's
processing server locally, without Docker. To run the full stack in
containers, see [deployment.md](deployment.md).

## Prerequisites

- Python 3.11+
- Docker, for the dev PostgreSQL container (or a local PostgreSQL 16+)
- Git

## First-time setup

```bash
cd platform

# Dev PostgreSQL (container "mundorum-dbms"). dbms/docker-compose.yml is
# gitignored: copy the example and set the data path inside it first.
cp dbms/docker-compose-example.yml dbms/docker-compose.yml
docker compose -f dbms/docker-compose.yml up -d

# One virtualenv for the shared server and noid's processing server.
# It lives in noid/ for historical reasons; the commands below assume that.
python -m venv noid/.venv
source noid/.venv/bin/activate

pip install -e noid/runner/
pip install -r server/requirements.txt          # also pulls noid's and vp's app deps
pip install -r noid/processing/requirements.txt

cp .env.example .env
# Edit .env and set at minimum:
#   DATABASE_URL=postgres://noid:noid@localhost:5432/noid
#   PROCESSING_URL=http://localhost:8001
#   PROCESSING_API_KEY=dev-key
#   GOOGLE_CLIENT_ID=<dev OAuth client>   (redirect URI http://localhost:8000/auth/google/callback/)
#   INITIAL_MANAGER_EMAIL=<your Google account>

cd server
python manage.py migrate
python manage.py seed_initial_manager
```

> The server reads the root `.env`, falling back to `noid/.env` for values
> the root file doesn't set. Relative noid paths (`COLLECTIONS_FILE`,
> `SCENE_PACKAGES_DIR`, `SHARED_RESOURCES_DIR`) are resolved against `noid/`.

### VP Studio content

Without a content pack, VP Studio uses neutral placeholder scripts and
prompts. To work with real content, load a pack
(see [content packs](../vp/docs/content-packs.md)):

```bash
python server/manage.py load_vp_content <path/to/pack.json>
```

### LLM keys (for VP Studio)

```bash
umask 077
printf '%s' '<key>' > secrets/groq_api_key     # from the repository root
python server/manage.py llm_check              # shows which providers have a key
python server/manage.py llm_check groq --list-models
```

Then set `GROQ_MODEL=<model id>` in `.env`. See [llm-gateway.md](llm-gateway.md).

## Running

```bash
# Terminal 1: shared server
source noid/.venv/bin/activate
python server/manage.py runserver 8000

# Terminal 2: noid processing server (reads noid/.env)
cd noid && source .venv/bin/activate
uvicorn processing.main:app --reload --port 8001
```

| URL | What |
|-----|------|
| http://localhost:8000/ | portal |
| http://localhost:8000/noid/ | noid editor |
| http://localhost:8000/vp/ | VP Studio |
| http://localhost:8000/admin/ | Django admin |
| http://localhost:8001/docs | noid processing API docs |

## Tests

```bash
cd server && pytest                # every app on the shared server (server/, noid/authoring/, vp/server/)
cd noid && pytest runner/          # noid_runner (no DB)
cd noid && pytest authoring/       # just noid's Django apps
cd noid && pytest processing/      # noid's FastAPI server
node --test vp/web/tests/*.test.mjs   # VP Studio's browser-side rules (Node 22+, from the repo root)
```

Django tests use a real PostgreSQL test database (created and dropped by
`pytest-django`); no database mocking.

## Docs site

```bash
pip install "mkdocs>=1.6,<2" "mkdocs-material>=9.5,<10"
tools/stage-docs.sh && mkdocs serve -f build/docs-site/mkdocs.yml
```
