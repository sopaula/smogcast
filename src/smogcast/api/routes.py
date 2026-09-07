from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from smogcast.api.schemas import (
    HealthResponse,
    MeasurementResponse,
    StationResponse,
    ForecastResponse,
)

from smogcast.storage.db import SessionLocal
from smogcast.storage.models import Measurement, Sensor, Station

from smogcast.model.predict import predict_tomorrow


router = APIRouter()


# Otwiera połączenie z bazą danych na czas obsługi zapytania.
def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


# Sprawdza, czy API działa.
@router.get(
    "/health",
    response_model=HealthResponse,
)
def health():
    return {"status": "ok"}


# Zwraca listę wszystkich stacji zapisanych w bazie.
@router.get(
    "/stations",
    response_model=list[StationResponse],
)
def get_stations(
    db: Session = Depends(get_db),
):
    stations = db.query(Station).all()

    return stations


# Zwraca pomiary wybranego parametru dla stacji
# w podanym zakresie czasu.
@router.get(
    "/stations/{station_id}/measurements",
    response_model=list[MeasurementResponse],
)
def get_station_measurements(
    station_id: int,
    param: Literal["PM10", "PM25"],
    date_from: datetime = Query(alias="from"),
    date_to: datetime = Query(alias="to"),
    db: Session = Depends(get_db),
):
    station = db.get(
        Station,
        station_id,
    )

    if station is None:
        raise HTTPException(
            status_code=404,
            detail="Station not found",
        )

    param_code = "PM2.5" if param == "PM25" else param

    stmt = (
        select(
            Measurement.sensor_id,
            Sensor.param_code,
            Measurement.timestamp,
            Measurement.value,
        )
        .join(
            Sensor,
            Measurement.sensor_id == Sensor.id,
        )
        .where(
            Sensor.station_id == station_id,
            Sensor.param_code == param_code,
            Measurement.timestamp >= date_from,
            Measurement.timestamp <= date_to,
        )
        .order_by(
            Measurement.timestamp,
        )
    )

    rows = db.execute(stmt).all()

    return [
        {
            "sensor_id": row.sensor_id,
            "param": param,
            "timestamp": row.timestamp,
            "value": row.value,
        }
        for row in rows
    ]


# Zwraca najnowszy dostępny pomiar dla wybranej stacji.
@router.get(
    "/stations/{station_id}/latest",
    response_model=MeasurementResponse,
)
def get_latest_measurement(
    station_id: int,
    db: Session = Depends(get_db),
):
    station = db.get(
        Station,
        station_id,
    )

    if station is None:
        raise HTTPException(
            status_code=404,
            detail="Station not found",
        )

    stmt = (
        select(
            Measurement.sensor_id,
            Sensor.param_code,
            Measurement.timestamp,
            Measurement.value,
        )
        .join(
            Sensor,
            Measurement.sensor_id == Sensor.id,
        )
        .where(
            Sensor.station_id == station_id,
        )
        .order_by(
            Measurement.timestamp.desc(),
        )
        .limit(1)
    )

    row = db.execute(stmt).first()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="No measurements found for this station",
        )

    param = "PM25" if row.param_code == "PM2.5" else row.param_code

    return {
        "sensor_id": row.sensor_id,
        "param": param,
        "timestamp": row.timestamp,
        "value": row.value,
    }


# Zwraca prognozę PM na jutro dla wybranej stacji i parametru
# Odpowiedź zawiera również próg oraz flagę alarmu
@router.get(
    "/stations/{station_id}/forecast",
    response_model=ForecastResponse,
)
def get_forecast(
    station_id: int,
    param: Literal["PM10", "PM25"],
):
    try:
        return predict_tomorrow(
            station_id=station_id,
            param=param,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error
