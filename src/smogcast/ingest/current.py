from datetime import date, datetime, timedelta, timezone

import httpx
from sqlalchemy import select

from smogcast.ingest.gios import (
    get_current_sensor_data,
    get_sensor_data_for_period,
)
from smogcast.storage.db import SessionLocal
from smogcast.storage.models import Measurement, Sensor
from smogcast.storage.upsert import upsert_measurements


CURRENT_DATA_DAYS = 3

FRESH_DATA_DAYS = 2


# Zamienia nazwę parametru na format z bazy.
def map_param(
    param,
):
    if param == "PM25":
        return "PM2.5"

    return param


# Pobiera sensory stacji z bazy.
def get_sensors_for_station(
    db,
    station_id,
    param_code,
):
    stmt = select(Sensor).where(
        Sensor.station_id == station_id,
        Sensor.param_code == param_code,
    )

    return list(db.scalars(stmt))


# Pobiera timestamp ostatniego pomiaru sensora.
def get_latest_measurement_timestamp(
    db,
    sensor_id,
):
    stmt = (
        select(Measurement.timestamp)
        .where(
            Measurement.sensor_id == sensor_id,
            Measurement.value.is_not(None),
        )
        .order_by(Measurement.timestamp.desc())
        .limit(1)
    )

    return db.scalar(stmt)


# Przygotowuje pomiary do zapisu.
def prepare_measurements_for_database(
    sensor_id,
    measurements,
):
    prepared = []

    cet = timezone(timedelta(hours=1))

    for measurement in measurements:
        timestamp_text = measurement.get("Data")

        value = measurement.get("Wartość")

        if timestamp_text is None:
            continue

        if value is None:
            continue

        timestamp = datetime.fromisoformat(timestamp_text)

        timestamp_cet = timestamp.replace(tzinfo=cet)

        timestamp_utc = timestamp_cet.astimezone(timezone.utc)

        prepared.append(
            {
                "sensor_id": sensor_id,
                "timestamp": timestamp_utc.replace(tzinfo=None),
                "value": value,
            }
        )

    return prepared


# Pobiera bieżące dane sensora.
def try_get_current_sensor_data(
    sensor_id,
):
    try:
        measurements = get_current_sensor_data(sensor_id=sensor_id)

    except httpx.HTTPStatusError as error:
        if error.response.status_code == 400:
            return []

        raise

    if measurements is None:
        return []

    return measurements


# Pobiera timestamp najnowszego poprawnego rekordu.
def get_latest_current_timestamp(
    measurements,
):
    timestamps = []

    for measurement in measurements:
        timestamp_text = measurement.get("Data")

        value = measurement.get("Wartość")

        if timestamp_text is None:
            continue

        if value is None:
            continue

        timestamps.append(datetime.fromisoformat(timestamp_text))

    if not timestamps:
        return None

    return max(timestamps)


# Wybiera sensor z najświeższymi bieżącymi danymi.
def find_best_current_sensor(
    sensors,
):
    best_sensor = None
    best_measurements = []
    best_timestamp = None

    for sensor in sensors:
        measurements = try_get_current_sensor_data(sensor.id)

        if not measurements:
            continue

        latest_timestamp = get_latest_current_timestamp(measurements)

        if latest_timestamp is None:
            continue

        if best_timestamp is None or latest_timestamp > best_timestamp:
            best_sensor = sensor
            best_measurements = measurements
            best_timestamp = latest_timestamp

    return (
        best_sensor,
        best_measurements,
    )


# Wybiera sensor z najświeższymi danymi w bazie.
def find_best_historical_sensor(
    db,
    sensors,
):
    best_sensor = None
    best_timestamp = None

    for sensor in sensors:
        latest_timestamp = get_latest_measurement_timestamp(
            db,
            sensor.id,
        )

        if latest_timestamp is None:
            continue

        if best_timestamp is None or latest_timestamp > best_timestamp:
            best_sensor = sensor
            best_timestamp = latest_timestamp

    return best_sensor


# Uzupełnia starszą lukę z archiwum GIOŚ.
def refresh_archive_part(
    db,
    sensor_id,
    date_from,
    date_to,
):
    (
        measurements,
        failed_ranges,
    ) = get_sensor_data_for_period(
        sensor_id=sensor_id,
        date_from=date_from.strftime("%Y-%m-%d 00:00"),
        date_to=date_to.strftime("%Y-%m-%d 23:00"),
        days_per_range=30,
    )

    if failed_ranges:
        raise RuntimeError(f"Failed archival ranges: {failed_ranges}")

    if not measurements:
        return

    prepared = prepare_measurements_for_database(
        sensor_id=sensor_id,
        measurements=measurements,
    )

    if not prepared:
        return

    upsert_measurements(
        db,
        prepared,
    )


# Zapisuje tylko nowe bieżące pomiary.
def save_current_measurements(
    db,
    sensor_id,
    measurements,
    latest_timestamp,
):
    if not measurements:
        return 0

    prepared = prepare_measurements_for_database(
        sensor_id=sensor_id,
        measurements=measurements,
    )

    if latest_timestamp is not None:
        prepared = [
            measurement
            for measurement in prepared
            if measurement["timestamp"] > latest_timestamp
        ]

    if not prepared:
        return 0

    upsert_measurements(
        db,
        prepared,
    )

    return len(prepared)


# Określa świeżość danych.
def get_data_freshness(
    latest_date,
):
    data_age_days = (date.today() - latest_date).days

    if data_age_days <= FRESH_DATA_DAYS:
        return {
            "data_date": latest_date,
            "data_age_days": data_age_days,
            "data_status": "fresh",
            "warning": None,
        }

    return {
        "data_date": latest_date,
        "data_age_days": data_age_days,
        "data_status": "stale",
        "warning": (
            "Forecast is based on older PM data. "
            f"Latest available measurement is from "
            f"{latest_date}."
        ),
    }


# Aktualizuje jeden parametr dla stacji.
def refresh_recent_measurements(
    station_id,
    param,
):
    param_code = map_param(param)

    with SessionLocal() as db:
        # Pobiera sensory zapisane w bazie.
        sensors = get_sensors_for_station(
            db,
            station_id,
            param_code,
        )

        if not sensors:
            raise ValueError("No sensor found for station and parameter")

        # Szuka sensora z najświeższymi danymi.
        (
            current_sensor,
            current_measurements,
        ) = find_best_current_sensor(sensors)

        if current_sensor is not None:
            sensor = current_sensor

        else:
            sensor = find_best_historical_sensor(
                db,
                sensors,
            )

            current_measurements = []

        if sensor is None:
            raise ValueError("No measurements available for station and parameter")

        latest_timestamp = get_latest_measurement_timestamp(
            db,
            sensor.id,
        )

        if latest_timestamp is None:
            raise ValueError("No historical measurements available")

        latest_date = latest_timestamp.date()

        expected_latest_date = date.today() - timedelta(days=1)

        current_start_date = expected_latest_date - timedelta(
            days=CURRENT_DATA_DAYS - 1
        )

        archive_end_date = current_start_date - timedelta(days=1)

        # Uzupełnia starszą lukę.
        if latest_date < archive_end_date:
            archive_start_date = latest_date + timedelta(days=1)

            refresh_archive_part(
                db=db,
                sensor_id=sensor.id,
                date_from=archive_start_date,
                date_to=archive_end_date,
            )

        # Sprawdza timestamp po uzupełnieniu archiwum.
        latest_timestamp = get_latest_measurement_timestamp(
            db,
            sensor.id,
        )

        # Dopisuje tylko nowsze rekordy.
        new_records = save_current_measurements(
            db=db,
            sensor_id=sensor.id,
            measurements=current_measurements,
            latest_timestamp=latest_timestamp,
        )

        refreshed_timestamp = get_latest_measurement_timestamp(
            db,
            sensor.id,
        )

        if refreshed_timestamp is None:
            raise RuntimeError("No measurements available after refresh")

        freshness = get_data_freshness(refreshed_timestamp.date())

        return {
            "sensor_id": sensor.id,
            "new_records": new_records,
            "data_date": freshness["data_date"],
            "data_age_days": freshness["data_age_days"],
            "data_status": freshness["data_status"],
            "warning": freshness["warning"],
        }


# Aktualizuje PM10 i PM2.5 dla stacji.
def refresh_station_measurements(
    station_id,
):
    results = {}

    for param in [
        "PM10",
        "PM25",
    ]:
        try:
            results[param] = refresh_recent_measurements(
                station_id,
                param,
            )

        except ValueError as error:
            results[param] = {
                "available": False,
                "error": str(error),
            }

    return results
