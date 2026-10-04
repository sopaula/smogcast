from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from sqlalchemy import text

from smogcast.api.routes import router
from smogcast.model.predict import load_model_bundle
from smogcast.storage.db import SessionLocal


# Ładuje model przy starcie API.
@asynccontextmanager
async def lifespan(app):
    load_model_bundle()

    yield


app = FastAPI(
    title="Smogcast API",
    version="0.1.0",
    lifespan=lifespan,
)


# Sprawdza, czy API działa.
@app.get("/health")
def health():
    return {
        "status": "ok",
    }


# Sprawdza gotowość modelu i bazy.
@app.get("/ready")
def ready():
    try:
        load_model_bundle()

        with SessionLocal() as db:
            db.execute(text("SELECT 1"))

        return {
            "status": "ready",
            "model": "ok",
            "database": "ok",
        }

    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail="API is not ready",
        ) from error


app.include_router(router)
