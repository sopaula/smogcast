from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from smogcast.api.schemas import HealthResponse, StationResponse
from smogcast.storage.db import SessionLocal
from smogcast.storage.models import Station


router = APIRouter()


# Tworzy sesję bazy danych dla pojedynczego requestu.
def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


@router.get(
    "/health",
    response_model=HealthResponse,
)
def health():
    return {
        "status": "ok",
    }


@router.get(
    "/stations",
    response_model=list[StationResponse],
)
def get_stations(
    db: Session = Depends(get_db),
):
    stations = db.query(Station).all()

    return stations
