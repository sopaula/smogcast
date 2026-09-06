from datetime import timedelta, timezone

import pandas as pd

from smogcast.storage.db import SessionLocal
from smogcast.storage.upsert import upsert_measurements, upsert_weather


CET = timezone(timedelta(hours=1))

GIOS_PATH = "data/raw/gios_pm_measurements_3y.parquet"
WEATHER_PATH = "data/raw/open_meteo_weather_3y.parquet"


# Wczytuje pomiary GIOŚ z pliku parquet i przygotowuje je do zapisu w bazie.
def load_measurements():
    df = pd.read_parquet(GIOS_PATH)

    timestamps = pd.to_datetime(df["Data"])
    timestamps_cet = timestamps.dt.tz_localize(CET)
    timestamps_utc = timestamps_cet.dt.tz_convert("UTC")

    records = []

    for sensor_id, timestamp, value in zip(
        df["sensor_id"],
        timestamps_utc,
        df["Wartość"],
        strict=True,
    ):
        records.append(
            {
                "sensor_id": int(sensor_id),
                "timestamp": timestamp.to_pydatetime(),
                "value": None if pd.isna(value) else float(value),
            }
        )

    return records


# Wczytuje dane pogodowe Open-Meteo z pliku parquet
# i przygotowuje je do zapisu w bazie.
def load_weather():
    df = pd.read_parquet(WEATHER_PATH)

    timestamps = pd.to_datetime(
        df["timestamp_utc"],
        utc=True,
    )

    records = []

    for i, row in df.iterrows():
        records.append(
            {
                "station_id": int(row["station_id"]),
                "timestamp": timestamps.iloc[i].to_pydatetime(),
                "temp_c": (
                    None
                    if pd.isna(row["temperature_2m"])
                    else float(row["temperature_2m"])
                ),
                "wind_ms": (
                    None
                    if pd.isna(row["wind_speed_10m"])
                    else float(row["wind_speed_10m"]) / 3.6  # km/h -> m/s
                ),
                "humidity": (
                    None
                    if pd.isna(row["relative_humidity_2m"])
                    else float(row["relative_humidity_2m"])
                ),
                "pressure_hpa": None,
                "precip_mm": None,
            }
        )

    return records


# Zapisuje przygotowane pomiary i dane pogodowe do bazy danych.
def ingest_timeseries():
    print("Preparing measurements...")
    measurements = load_measurements()
    print(f"Measurements prepared: {len(measurements)}")

    print("Preparing weather...")
    weather = load_weather()
    print(f"Weather records prepared: {len(weather)}")

    db = SessionLocal()

    try:
        print("Saving measurements...")
        upsert_measurements(db, measurements)

        print("Saving weather...")
        upsert_weather(db, weather)

    finally:
        db.close()

    print("Timeseries ingest finished.")


if __name__ == "__main__":
    ingest_timeseries()
