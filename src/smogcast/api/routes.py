from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from smogcast.api.schemas import (
    ForecastResponse,
    HealthResponse,
    MeasurementResponse,
    StationResponse,
)
from smogcast.model.predict import (
    predict_station_tomorrow,
)
from smogcast.storage.db import SessionLocal
from smogcast.storage.models import (
    Measurement,
    Sensor,
    Station,
)


router = APIRouter()


# Zamienia nazwę parametru na format z bazy.
def map_param(
    param,
):
    if param == "PM25":
        return "PM2.5"

    return param


# Sprawdza działanie API.
@router.get(
    "/health",
    response_model=HealthResponse,
)
def health():
    return {
        "status": "ok",
    }


# Zwraca stacje dostępne w Smogcast.
@router.get(
    "/stations",
    response_model=list[StationResponse],
)
def get_stations():
    with SessionLocal() as db:
        stmt = (
            select(
                Station,
            )
            .join(
                Sensor,
                Sensor.station_id == Station.id,
            )
            .join(
                Measurement,
                Measurement.sensor_id == Sensor.id,
            )
            .distinct()
            .order_by(
                Station.city,
                Station.name,
            )
        )

        return list(db.scalars(stmt))


# Zwraca pomiary dla stacji i parametru.
@router.get(
    "/stations/{station_id}/measurements",
    response_model=list[MeasurementResponse],
)
def get_measurements(
    station_id: int,
    param: Literal[
        "PM10",
        "PM25",
    ],
    date_from: datetime | None = None,
    date_to: datetime | None = None,
):
    param_code = map_param(param)

    with SessionLocal() as db:
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
                Measurement,
                Sensor,
            )
            .join(
                Sensor,
                Measurement.sensor_id == Sensor.id,
            )
            .where(
                Sensor.station_id == station_id,
                Sensor.param_code == param_code,
            )
        )

        # Ogranicza zakres dat.
        if date_from is not None:
            stmt = stmt.where(Measurement.timestamp >= date_from)

        if date_to is not None:
            stmt = stmt.where(Measurement.timestamp <= date_to)

        stmt = stmt.order_by(Measurement.timestamp)

        rows = db.execute(stmt).all()

        return [
            {
                "sensor_id": sensor.id,
                "param": param,
                "timestamp": measurement.timestamp,
                "value": measurement.value,
            }
            for measurement, sensor in rows
        ]


# Zwraca najnowsze pomiary PM10 i PM2.5.
@router.get(
    "/stations/{station_id}/latest",
    response_model=list[MeasurementResponse],
)
def get_latest_measurements(
    station_id: int,
):
    results = []

    with SessionLocal() as db:
        station = db.get(
            Station,
            station_id,
        )

        if station is None:
            raise HTTPException(
                status_code=404,
                detail="Station not found",
            )

        for api_param, db_param in [
            (
                "PM10",
                "PM10",
            ),
            (
                "PM25",
                "PM2.5",
            ),
        ]:
            # Pobiera najnowszy poprawny pomiar.
            stmt = (
                select(
                    Measurement,
                    Sensor,
                )
                .join(
                    Sensor,
                    Measurement.sensor_id == Sensor.id,
                )
                .where(
                    Sensor.station_id == station_id,
                    Sensor.param_code == db_param,
                    Measurement.value.is_not(None),
                )
                .order_by(Measurement.timestamp.desc())
                .limit(1)
            )

            row = db.execute(stmt).first()

            if row is None:
                continue

            measurement, sensor = row

            results.append(
                {
                    "sensor_id": sensor.id,
                    "param": api_param,
                    "timestamp": measurement.timestamp,
                    "value": measurement.value,
                }
            )

    return results


# Zwraca prognozę PM10 i PM2.5 na jutro.
@router.get(
    "/stations/{station_id}/forecast",
    response_model=ForecastResponse,
)
def get_forecast(
    station_id: int,
):
    try:
        return predict_station_tomorrow(station_id)

    except ValueError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error

    except RuntimeError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error
