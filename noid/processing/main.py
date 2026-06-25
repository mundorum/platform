from contextlib import asynccontextmanager

from fastapi import FastAPI

from processing.app.routes import deploy, health, run
from processing.app.worker import pool as worker_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield  # server is running
    worker_pool.shutdown()  # graceful shutdown: stop all warm worker processes


app = FastAPI(
    title="noid Processing Machine",
    version="0.1.0",
    description="Scene execution API for the noid platform.",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(deploy.router)
app.include_router(run.router)
