import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from smogcast.storage.db import SessionLocal
from smogcast.storage.models import Measurement, Sensor
from smogcast.storage.upsert import upsert_daily_measurements


# Pobiera pomiary z bazy razem
# z informacją o stacji i parametrze
def get_measurements_for_daily_aggregation(
    db: Session,
) -> pd.DataFrame:
    stmt = select(
        Sensor.station_id,
        Sensor.param_code,
        Measurement.timestamp,
        Measurement.value,
    ).join(
        Sensor,
        Measurement.sensor_id == Sensor.id,
    )

    rows = db.execute(stmt).all()

    return pd.DataFrame(
        rows,
        columns=[
            "station_id",
            "param_code",
            "timestamp",
            "value",
        ],
    )


# Agreguje pomiary PM
# do wartości dobowych
#
# Wylicza:
# - średnią
# - maksimum
# - procent dostępnych pomiarów
def calculate_daily_measurements(
    df: pd.DataFrame,
) -> pd.DataFrame:
    data = df.copy()

    if data.empty:
        return pd.DataFrame(
            columns=[
                "station_id",
                "param_code",
                "date",
                "mean_value",
                "max_value",
                "coverage",
            ]
        )

    data["timestamp"] = pd.to_datetime(data["timestamp"])

    data["date"] = data["timestamp"].dt.date

    daily = data.groupby(
        [
            "station_id",
            "param_code",
            "date",
        ],
        as_index=False,
    ).agg(
        mean_value=("value", "mean"),
        max_value=("value", "max"),
        valid_hours=("value", "count"),
    )

    daily["coverage"] = daily["valid_hours"] / 24 * 100

    return daily[
        [
            "station_id",
            "param_code",
            "date",
            "mean_value",
            "max_value",
            "coverage",
        ]
    ]


# Wylicza agregaty dobowe
# dla wszystkich stacji
def aggregate_daily_measurements():
    db = SessionLocal()

    try:
        measurements = get_measurements_for_daily_aggregation(db)

        daily = calculate_daily_measurements(measurements)

        records = daily.to_dict(
            orient="records",
        )

        if records:
            upsert_daily_measurements(
                db,
                records,
            )

        print(f"Saved {len(records)} daily measurements")

    finally:
        db.close()


# Wylicza agregaty dobowe
# tylko dla wybranych sensorów
#
# Te sensory zostały wcześniej
# wybrane przez current.py
#
# Dzięki temu nie mieszamy danych
# z kilku sensorów tego samego parametru
def aggregate_daily_measurements_for_sensors(
    sensor_ids,
):
    db = SessionLocal()

    try:
        stmt = (
            select(
                Sensor.station_id,
                Sensor.param_code,
                Measurement.timestamp,
                Measurement.value,
            )
            .join(
                Sensor,
                Measurement.sensor_id == Sensor.id,
            )
            .where(Sensor.id.in_(sensor_ids))
        )

        rows = db.execute(stmt).all()

        measurements = pd.DataFrame(
            rows,
            columns=[
                "station_id",
                "param_code",
                "timestamp",
                "value",
            ],
        )

        if measurements.empty:
            return 0

        daily = calculate_daily_measurements(measurements)

        records = daily.to_dict(
            orient="records",
        )

        if records:
            upsert_daily_measurements(
                db,
                records,
            )

        return len(records)

    finally:
        db.close()


if __name__ == "__main__":
    aggregate_daily_measurements()
