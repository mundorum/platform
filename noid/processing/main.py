from fastapi import FastAPI

from processing.app.routes import deploy, health, run

app = FastAPI(
    title="noid Processing Machine",
    version="0.1.0",
    description="Scene execution API for the noid platform.",
)

app.include_router(health.router)
app.include_router(deploy.router)
app.include_router(run.router)
