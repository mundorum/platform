"""
Execute a noid scene JSON via NoidPlayer in an isolated subprocess.
The subprocess uses the same Python interpreter, so all pip-installed
collections are available.  The scene's imports list is auto-populated
with the modules that registered the component types used in the scene.
"""
import json
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Generator


def _build_imports(scene: dict, catalog: list[dict]) -> list[str]:
    """Return module paths needed to run the scene's component types."""
    type_to_module = {c['id']: c['module'] for c in catalog}
    modules: set[str] = set()
    for comp in scene.get('components', []):
        mod = type_to_module.get(comp.get('type', ''))
        if mod:
            modules.add(mod)
    existing = set(scene.get('imports', []))
    return list(existing | modules)


def run_scene(scene: dict, catalog: list[dict], timeout: int = 30) -> dict:
    """Run *scene* via NoidPlayer. Returns {stdout, stderr, returncode}."""
    runnable = dict(scene)
    runnable['imports'] = _build_imports(scene, catalog)

    with tempfile.NamedTemporaryFile(
        mode='w', suffix='.json', delete=False, encoding='utf-8'
    ) as fh:
        json.dump(runnable, fh, indent=2)
        scene_path = fh.name

    script = (
        "from noid.core.player import NoidPlayer; "
        f"NoidPlayer.play(r'{scene_path}', timeout={timeout})"
    )
    try:
        proc = subprocess.run(
            [sys.executable, '-c', script],
            capture_output=True,
            text=True,
            timeout=timeout + 10,
        )
        return {
            'stdout': proc.stdout,
            'stderr': proc.stderr,
            'returncode': proc.returncode,
        }
    except subprocess.TimeoutExpired:
        return {'stdout': '', 'stderr': f'Timed out after {timeout}s.', 'returncode': -1}
    except Exception as exc:
        return {'stdout': '', 'stderr': str(exc), 'returncode': -1}
    finally:
        Path(scene_path).unlink(missing_ok=True)


def stream_scene(
    scene: dict,
    catalog: list[dict],
    timeout: int = 60,
    verbose: bool = False,
) -> Generator[str, None, None]:
    """
    Yield output lines from the scene as they are produced.

    stderr is merged into stdout so the caller sees one ordered stream.
    Python is started with -u (unbuffered) so lines arrive immediately.
    A background timer kills the process after *timeout* seconds.
    """
    runnable = dict(scene)
    runnable['imports'] = _build_imports(scene, catalog)

    with tempfile.NamedTemporaryFile(
        mode='w', suffix='.json', delete=False, encoding='utf-8'
    ) as fh:
        json.dump(runnable, fh, indent=2)
        scene_path = fh.name

    log_init = (
        "import logging; "
        "logging.basicConfig("
        "level=logging.DEBUG, "
        "format='[%(levelname)s] %(name)s: %(message)s'"
        "); "
        if verbose else ""
    )
    script = (
        f"{log_init}"
        "from noid.core.player import NoidPlayer; "
        f"NoidPlayer.play(r'{scene_path}', timeout={timeout})"
    )
    proc = subprocess.Popen(
        [sys.executable, '-u', '-c', script],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,   # merge stderr into stdout
        text=True,
        bufsize=1,
    )
    timer = threading.Timer(timeout + 5, proc.kill)
    timer.start()
    try:
        for line in proc.stdout:
            yield line
        proc.wait()
        yield f'\n▶ exited with code {proc.returncode}\n'
    finally:
        timer.cancel()
        Path(scene_path).unlink(missing_ok=True)
