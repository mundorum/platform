# noid Development Tasks

Setting up the environment (virtualenv, database, `.env`, running the shared
server and the processing server, tests) is covered by the platform guide:
[Development setup](../../docs/dev-setup.md). This page lists noid-specific
tasks.

noid's authoring API is served by the shared server under `/noid/api/`
(port 8000 in development). The processing server runs on port 8001.

Every endpoint except the public `catalog/` needs the shared sign-in token:
`-H "Authorization: Token <token>"`. Take it from the browser's
`localStorage.mundorum_token` after signing in at http://localhost:8000/noid/.

---

## Add a component collection

1. Add the Python module path to `noid/collections.yaml` under the appropriate label.
2. If the module comes from a new package, add the package to **both**
   `noid/authoring/requirements.txt` and `noid/processing/requirements.txt`.
3. Restart both servers (or on Processing, `DELETE /deploy/{id}` + `POST /deploy/{id}`
   to reload the registry for an affected scene).

## Add a scene-specific component

1. Create a `.py` file decorated with `@Noid.component(spec)` in
   `scene_packages/{scene_id}/components/`.
2. Upload it via `POST /scenes/{id}/components/` or include it in a ZIP import.
3. SceneRegistry will reload the component automatically when the file mtime changes.

## Upload a full scene package

```bash
zip -r my_scene.zip scene.json components/ data/
curl -X POST http://localhost:8000/noid/api/scenes/import/ \
     -H "Authorization: Token $TOKEN" \
     -F "file=@my_scene.zip"
```

## Download a scene package

```bash
curl -H "Authorization: Token $TOKEN" \
     http://localhost:8000/noid/api/scenes/{id}/export/ -o my_scene.zip
```

## Run a scene via the authoring API (proxies to Processing)

```bash
# Blocking: returns {stdout, stderr, returncode, run_id}
curl -X POST -H "Authorization: Token $TOKEN" http://localhost:8000/noid/api/scenes/{id}/run/

# Streaming: output lines arrive as they are produced
curl -N -X POST -H "Authorization: Token $TOKEN" http://localhost:8000/noid/api/scenes/{id}/run/stream/
```

## Run a scene directly via the scratch endpoint (no DB record)

```bash
curl -X POST http://localhost:8000/noid/api/play/ \
     -H "Authorization: Token $TOKEN" -H "Content-Type: application/json" \
     -d @scene.json

curl -N -X POST http://localhost:8000/noid/api/play/stream/ \
     -H "Authorization: Token $TOKEN" -H "Content-Type: application/json" \
     -d @scene.json
```

## Secrets and scene subprocesses

Scene components are user-authored code and run as subprocesses of the
server. `noid_runner.runner._subprocess_env()` drops secret-looking variables
(`SECRET_KEY`, `DATABASE_URL`, and any name containing `API_KEY`, `SECRET`,
`PASSWORD`, `TOKEN` or `POSTGRES_`) from their environment. If a component
legitimately needs one (e.g. `HF_TOKEN` to download gated models), list it in
`NOID_SUBPROCESS_ENV_PASSTHROUGH` (comma-separated).
