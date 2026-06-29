"""
Execute a noid scene JSON via NoidPlayer in an isolated subprocess.
The subprocess uses the same Python interpreter, so all pip-installed
collections are available.  The scene's imports list is auto-populated
with the modules that registered the component types used in the scene.
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Callable, Generator, Optional


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


def _subprocess_env(extra: Optional[dict] = None) -> dict:
    """Build a subprocess environment, forwarding NOID_NAMESPACES if set."""
    env = os.environ.copy()
    if extra:
        env.update(extra)
    return env


def run_scene(
    scene: dict,
    catalog: list[dict],
    timeout: Optional[int] = 30,
    scene_dir: Optional[Path] = None,
) -> dict:
    """
    Run *scene* via NoidPlayer. Returns {stdout, stderr, returncode}.

    *scene_dir* should be the on-disk scene package directory when available.
    The temp scene file is written there (so relative imports and data paths
    resolve correctly) and the subprocess CWD is set to that directory.
    """
    runnable = dict(scene)
    runnable['imports'] = _build_imports(scene, catalog)

    # Write the temp file inside scene_dir so _scene_dir resolves correctly
    tmp_parent = scene_dir if scene_dir is not None else None
    with tempfile.NamedTemporaryFile(
        mode='w', suffix='.json', delete=False, encoding='utf-8',
        dir=tmp_parent,
    ) as fh:
        json.dump(runnable, fh, indent=2)
        scene_path = fh.name

    timeout_arg = 'None' if timeout is None else repr(timeout)
    script = (
        "from noid.core.player import NoidPlayer; "
        f"NoidPlayer.play(r'{scene_path}', timeout={timeout_arg})"
    )
    proc_timeout = None if timeout is None else timeout + 10
    try:
        proc = subprocess.run(
            [sys.executable, '-c', script],
            capture_output=True,
            text=True,
            timeout=proc_timeout,
            cwd=str(scene_dir) if scene_dir is not None else None,
            env=_subprocess_env(),
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
    timeout: Optional[int] = 60,
    verbose: bool = False,
    scene_dir: Optional[Path] = None,
    on_start: Optional[Callable[[subprocess.Popen], None]] = None,
) -> Generator[str, None, None]:
    """
    Yield output lines from the scene as they are produced.

    stderr is merged into stdout so the caller sees one ordered stream.
    Python is started with -u (unbuffered) so lines arrive immediately.
    A background timer kills the process after *timeout* seconds.

    *scene_dir* sets the subprocess CWD and the temp file location so that
    relative imports and data paths inside the scene resolve correctly.
    """
    runnable = dict(scene)
    runnable['imports'] = _build_imports(scene, catalog)

    tmp_parent = scene_dir if scene_dir is not None else None
    with tempfile.NamedTemporaryFile(
        mode='w', suffix='.json', delete=False, encoding='utf-8',
        dir=tmp_parent,
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
    timeout_arg = 'None' if timeout is None else repr(timeout)
    script = (
        f"{log_init}"
        "from noid.core.player import NoidPlayer; "
        f"NoidPlayer.play(r'{scene_path}', timeout={timeout_arg})"
    )
    proc = subprocess.Popen(
        [sys.executable, '-u', '-c', script],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=str(scene_dir) if scene_dir is not None else None,
        env=_subprocess_env(),
    )
    if on_start is not None:
        on_start(proc)
    timer = threading.Timer(timeout + 5, proc.kill) if timeout is not None else None
    if timer is not None:
        timer.start()
    try:
        for line in proc.stdout:
            yield line
        proc.wait()
        yield f'\n▶ exited with code {proc.returncode}\n'
    finally:
        if timer is not None:
            timer.cancel()
        Path(scene_path).unlink(missing_ok=True)
