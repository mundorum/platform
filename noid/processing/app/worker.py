"""
Warm worker pool for deployed noid scenes.

Each deployed scene gets one dedicated worker process (ProcessPoolExecutor with
max_workers=1). Its initializer pre-imports the scene's component modules once,
so subsequent blocking runs skip the per-run import overhead (~300–700 ms).

Architecture
────────────
  SceneWorkerPool (singleton ``pool``)
    └─ {scene_id: SceneWorker}
         └─ ProcessPoolExecutor(max_workers=1)
              worker process: component modules already in sys.modules
                 → NoidPlayer created fresh per run (no state leakage)

Streaming runs still use the existing subprocess approach in runner.py because
capturing line-by-line output from a ProcessPoolExecutor requires additional IPC.

Usage
─────
  # Deploy: warm up the worker
  await asyncio.to_thread(pool.register, scene_id, scene_dir, imports)

  # Run (blocking): use warm worker, fall back to cold runner on miss
  result = await asyncio.to_thread(pool.run, scene_id, timeout)

  # Evict: shut down the worker process
  pool.evict(scene_id)

  # App shutdown: clean up all workers
  pool.shutdown()
"""
import concurrent.futures
import importlib
import multiprocessing as mp
import threading
from pathlib import Path
from typing import Dict, List, Optional


# ── worker-process functions ──────────────────────────────────────────────────
# These must live at module level so they are picklable.


def _worker_init(imports: List[str]) -> None:
    """
    Initializer for the warm worker process.

    Runs once when the process starts (before any task). Importing modules here
    populates sys.modules so all subsequent _run_scene calls skip re-importing.
    Import errors are silenced — they surface as "component not found" errors at
    run time, matching the existing cold-start behaviour.
    """
    for module_path in imports:
        try:
            importlib.import_module(module_path)
        except Exception:
            pass


def _noop() -> None:
    """Submitted once to trigger the initializer eagerly during warm-up."""


def _run_scene(scene_dir_str: str, timeout: int) -> dict:
    """
    Run a scene inside the warm worker process.

    Component modules are already imported (done by _worker_init).
    NoidPlayer is created fresh each call so there is no cross-run state leakage.
    stdout and stderr are captured and returned in the result dict.
    """
    import asyncio
    import contextlib
    import io
    from pathlib import Path as _Path

    from noid.core.player import NoidPlayer

    player = NoidPlayer()
    out_buf = io.StringIO()
    err_buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(out_buf), contextlib.redirect_stderr(err_buf):
            player.load(_Path(scene_dir_str))
            asyncio.run(player.run(timeout=timeout))
        return {
            "stdout": out_buf.getvalue(),
            "stderr": err_buf.getvalue(),
            "returncode": 0,
        }
    except Exception as exc:
        return {
            "stdout": out_buf.getvalue(),
            "stderr": f"{type(exc).__name__}: {exc}",
            "returncode": 1,
        }


# ── SceneWorker ───────────────────────────────────────────────────────────────


class SceneWorker:
    """
    Warm worker for one deployed scene.

    Wraps a ProcessPoolExecutor(max_workers=1) whose single worker process has
    pre-imported the scene's component modules. Each run() submits _run_scene()
    to that process; module loading is skipped because sys.modules is already
    populated.

    On timeout the worker process is killed and the executor is reset so the
    next run() transparently starts a new worker.
    """

    def __init__(self, scene_id: str, scene_dir: Path, imports: List[str]) -> None:
        self.scene_id = scene_id
        self.scene_dir = scene_dir
        self._imports = imports
        self._executor: Optional[concurrent.futures.ProcessPoolExecutor] = None
        self._lock = threading.Lock()

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def warm_up(self) -> None:
        """
        Start the worker process and block until its initializer completes.

        Idempotent — safe to call multiple times; only the first call creates
        the executor. Raises RuntimeError if the worker fails to start in 60 s.
        """
        with self._lock:
            if self._executor is not None:
                return
            executor = concurrent.futures.ProcessPoolExecutor(
                max_workers=1,
                mp_context=mp.get_context("spawn"),
                initializer=_worker_init,
                initargs=(self._imports,),
            )
            self._executor = executor

        try:
            # Submit a no-op to trigger the initializer and block until ready.
            executor.submit(_noop).result(timeout=60)
        except Exception as exc:
            self._shutdown()
            raise RuntimeError(f"Worker warm-up failed for scene {self.scene_id!r}: {exc}") from exc

    def stop(self) -> None:
        """Shut down the worker process, discarding any queued tasks."""
        self._shutdown()

    def _shutdown(self) -> None:
        with self._lock:
            executor, self._executor = self._executor, None
        if executor is not None:
            executor.shutdown(wait=False, cancel_futures=True)

    # ── run ───────────────────────────────────────────────────────────────────

    def run(self, timeout: int = 60) -> dict:
        """
        Run the scene in the warm worker, blocking until complete.

        Restarts the worker automatically if it died between calls.
        Kills and resets the worker on timeout so the next call gets a fresh one.
        """
        # Auto-start if not yet running (e.g. after a previous timeout reset)
        self.warm_up()

        with self._lock:
            executor = self._executor

        if executor is None:
            return {"stdout": "", "stderr": "Worker failed to start.", "returncode": -1}

        try:
            future = executor.submit(_run_scene, str(self.scene_dir), timeout)
            return future.result(timeout=timeout + 15)
        except concurrent.futures.TimeoutError:
            self._shutdown()
            return {"stdout": "", "stderr": f"Timed out after {timeout}s.", "returncode": -1}
        except Exception as exc:
            self._shutdown()
            return {"stdout": "", "stderr": str(exc), "returncode": -1}


# ── SceneWorkerPool ───────────────────────────────────────────────────────────


class SceneWorkerPool:
    """
    Manages warm workers for all deployed scenes.

    Import the module-level ``pool`` singleton rather than instantiating directly.
    """

    def __init__(self) -> None:
        self._workers: Dict[str, SceneWorker] = {}
        self._lock = threading.Lock()

    def register(self, scene_id: str, scene_dir: Path, imports: List[str]) -> SceneWorker:
        """
        Create (or replace) the warm worker for a scene and start warming it.

        Blocks until the worker process has started and pre-imported all
        component modules. Intended to be called from a thread (asyncio.to_thread)
        at deploy time.
        """
        worker = SceneWorker(scene_id, scene_dir, imports)
        with self._lock:
            old = self._workers.pop(scene_id, None)
            self._workers[scene_id] = worker
        if old is not None:
            old.stop()
        worker.warm_up()
        return worker

    def evict(self, scene_id: str) -> None:
        """Shut down and remove the warm worker for an evicted scene."""
        with self._lock:
            worker = self._workers.pop(scene_id, None)
        if worker is not None:
            worker.stop()

    def get(self, scene_id: str) -> Optional[SceneWorker]:
        """Return the warm worker for a scene, or None if not registered."""
        return self._workers.get(scene_id)

    def run(self, scene_id: str, timeout: int = 60) -> Optional[dict]:
        """
        Run a scene via its warm worker.

        Returns None if no worker is registered (caller should fall back to
        runner.run_scene).
        """
        worker = self.get(scene_id)
        return worker.run(timeout) if worker is not None else None

    def shutdown(self) -> None:
        """Stop all workers — call at application shutdown."""
        with self._lock:
            workers, self._workers = list(self._workers.values()), {}
        for w in workers:
            w.stop()


# ── module-level singleton ────────────────────────────────────────────────────

pool = SceneWorkerPool()
