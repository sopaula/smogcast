from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from smogcast.storage.models import (
    DailyMeasurement,
    Measurement,
    Sensor,
    Station,
    Weather,
)


# Wstawia lub aktualizuje stację
def upsert_station(
    db: Session,
    station_data: dict,
):
    stmt = insert(Station).values(
        id=station_data["id"],
        name=station_data["name"],
        city=station_data["city"],
        latitude=station_data["latitude"],
        longitude=station_data["longitude"],
    )

    stmt = stmt.on_conflict_do_update(
        index_elements=["id"],
        set_={
            "name": stmt.excluded.name,
            "city": stmt.excluded.city,
            "latitude": stmt.excluded.latitude,
            "longitude": stmt.excluded.longitude,
        },
    )

    db.execute(stmt)


# Wstawia lub aktualizuje sensor
def upsert_sensor(
    db: Session,
    sensor_data: dict,
):
    stmt = insert(Sensor).values(
        id=sensor_data["id"],
        station_id=sensor_data["station_id"],
        param_code=sensor_data["param_code"],
    )

    stmt = stmt.on_conflict_do_update(
        index_elements=["id"],
        set_={
            "station_id": stmt.excluded.station_id,
            "param_code": stmt.excluded.param_code,
        },
    )

    db.execute(stmt)


# Zapisuje wiele stacji i sensorów w jednej transakcji
def upsert_metadata(
    db: Session,
    stations: list[dict],
    sensors: list[dict],
):
    for station in stations:
        upsert_station(db, station)

    for sensor in sensors:
        upsert_sensor(db, sensor)

    db.commit()


# Zamienia rekord stacji GIOŚ na format tabeli stations.
def map_station_from_gios(station: dict) -> dict:
    return {
        "id": station["Identyfikator stacji"],
        "name": station["Nazwa stacji"],
        "city": station["Nazwa miasta"],
        "latitude": float(station["WGS84 φ N"]),
        "longitude": float(station["WGS84 λ E"]),
    }


# Zamienia rekord sensora GIOŚ na format tabeli sensors.
def map_sensor_from_gios(
    sensor: dict,
    station_id: int,
) -> dict | None:
    param_code = sensor["Wskaźnik - kod"]

    if param_code not in {"PM10", "PM2.5"}:
        return None

    return {
        "id": sensor["Identyfikator stanowiska"],
        "station_id": station_id,
        "param_code": param_code,
    }


# Zapisuje pomiary do bazy.
# Jeśli pomiar dla danego sensora i czasu już istnieje, aktualizuje jego wartość.
def upsert_measurements(
    db: Session,
    measurements: list[dict],
):
    stmt = insert(Measurement)

    stmt = stmt.on_conflict_do_update(
        index_elements=["sensor_id", "timestamp"],
        set_={
            "value": stmt.excluded.value,
        },
    )

    db.execute(stmt, measurements)
    db.commit()


# Zapisuje dane pogodowe do bazy.
# Jeśli rekord dla danej stacji i czasu już istnieje, aktualizuje jego wartości.
def upsert_weather(
    db: Session,
    weather_records: list[dict],
):
    stmt = insert(Weather)

    stmt = stmt.on_conflict_do_update(
        index_elements=["station_id", "timestamp"],
        set_={
            "temp_c": stmt.excluded.temp_c,
            "wind_ms": stmt.excluded.wind_ms,
            "humidity": stmt.excluded.humidity,
            "pressure_hpa": stmt.excluded.pressure_hpa,
            "precip_mm": stmt.excluded.precip_mm,
        },
    )

    db.execute(stmt, weather_records)
    db.commit()


# Zapisuje dobowe agregaty pomiarów do bazy.
# Jeśli rekord dla tej samej stacji, parametru i daty już istnieje,
# aktualizuje jego wartości zamiast tworzyć duplikat.
def upsert_daily_measurements(
    db: Session,
    daily_records: list[dict],
):
    stmt = insert(DailyMeasurement)

    stmt = stmt.on_conflict_do_update(
        index_elements=[
            "station_id",
            "param_code",
            "date",
        ],
        set_={
            "mean_value": stmt.excluded.mean_value,
            "max_value": stmt.excluded.max_value,
            "coverage": stmt.excluded.coverage,
        },
    )

    db.execute(stmt, daily_records)
    db.commit()
