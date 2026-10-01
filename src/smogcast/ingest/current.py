from datetime import date, datetime, timedelta, timezone
from time import perf_counter
from zoneinfo import ZoneInfo

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

BACKFILL_RETRY_HOURS = 24


# Ujednolica czas do UTC.
def to_utc(dt):
    if dt is None:
        return None

    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc)


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

    return to_utc(db.scalar(stmt))


# Przygotowuje pomiary do zapisu.
def prepare_measurements_for_database(
    sensor_id,
    measurements,
):
    prepared = []
    warsaw = ZoneInfo("Europe/Warsaw")

    for measurement in measurements:
        timestamp_text = measurement.get("Data")
        value = measurement.get("Wartość")

        if timestamp_text is None:
            continue

        if value is None:
            continue

        timestamp = datetime.fromisoformat(timestamp_text)
        timestamp_local = timestamp.replace(tzinfo=warsaw)
        timestamp_utc = timestamp_local.astimezone(timezone.utc)

        prepared.append(
            {
                "sensor_id": sensor_id,
                "timestamp": timestamp_utc,
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

    gios_time = 0.0
    current_calls = 0
    fetched_records = 0

    for sensor in sensors:
        start = perf_counter()

        measurements = try_get_current_sensor_data(sensor.id)

        gios_time += perf_counter() - start

        current_calls += 1
        fetched_records += len(measurements)

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
        {
            "gios_time": gios_time,
            "current_calls": current_calls,
            "fetched_records": fetched_records,
        },
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


# Sprawdza, czy można ponowić próbę backfillu.
def can_retry_backfill(sensor):
    if sensor.next_retry_at is None:
        return True

    now = datetime.now(timezone.utc)
    next_retry_at = to_utc(sensor.next_retry_at)

    return now >= next_retry_at


# Uzupełnia starszą lukę z archiwum GIOŚ.
def refresh_archive_part(
    db,
    sensor_id,
    date_from,
    date_to,
):
    start = perf_counter()

    (
        measurements,
        failed_ranges,
    ) = get_sensor_data_for_period(
        sensor_id=sensor_id,
        date_from=date_from.strftime("%Y-%m-%d 00:00"),
        date_to=date_to.strftime("%Y-%m-%d 23:00"),
        days_per_range=30,
    )

    gios_time = perf_counter() - start

    if failed_ranges:
        raise RuntimeError(
            f"Nie udało się pobrać zakresów archiwalnych: {failed_ranges}"
        )

    if not measurements:
        return {
            "gios_time": gios_time,
            "db_write_time": 0.0,
            "fetched_records": 0,
            "new_records": 0,
            "archive_used": True,
        }

    prepared = prepare_measurements_for_database(
        sensor_id=sensor_id,
        measurements=measurements,
    )

    if not prepared:
        return {
            "gios_time": gios_time,
            "db_write_time": 0.0,
            "fetched_records": len(measurements),
            "new_records": 0,
            "archive_used": True,
        }

    write_start = perf_counter()

    upsert_measurements(
        db,
        prepared,
    )

    db_write_time = perf_counter() - write_start

    return {
        "gios_time": gios_time,
        "db_write_time": db_write_time,
        "fetched_records": len(measurements),
        "new_records": len(prepared),
        "archive_used": True,
    }


# Zapisuje tylko nowe bieżące pomiary.
def save_current_measurements(
    db,
    sensor_id,
    measurements,
    latest_timestamp,
):
    if not measurements:
        return {
            "new_records": 0,
            "db_write_time": 0.0,
        }

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
        return {
            "new_records": 0,
            "db_write_time": 0.0,
        }

    start = perf_counter()

    upsert_measurements(
        db,
        prepared,
    )

    db_write_time = perf_counter() - start

    return {
        "new_records": len(prepared),
        "db_write_time": db_write_time,
    }


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
            "Prognoza jest oparta na starszych danych PM. "
            "Najnowszy dostępny pomiar pochodzi z "
            f"{latest_date.strftime('%d.%m.%Y')}."
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
            raise ValueError("Nie znaleziono sensora dla wybranej stacji i parametru")

        # Szuka sensora z najświeższymi danymi.
        (
            current_sensor,
            current_measurements,
            current_metrics,
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
            raise ValueError("Brak dostępnych pomiarów dla wybranej stacji i parametru")

        latest_timestamp = get_latest_measurement_timestamp(
            db,
            sensor.id,
        )

        if latest_timestamp is None:
            raise ValueError("Brak historycznych pomiarów dla wybranego sensora")

        latest_date = latest_timestamp.date()

        expected_latest_date = date.today() - timedelta(days=1)

        current_start_date = expected_latest_date - timedelta(
            days=CURRENT_DATA_DAYS - 1
        )

        archive_end_date = current_start_date - timedelta(days=1)

        archive_metrics = {
            "gios_time": 0.0,
            "db_write_time": 0.0,
            "fetched_records": 0,
            "new_records": 0,
            "archive_used": False,
        }

        # Uzupełnia starszą lukę.
        if latest_date < archive_end_date and can_retry_backfill(sensor):
            archive_start_date = latest_date + timedelta(days=1)

            archive_metrics = refresh_archive_part(
                db=db,
                sensor_id=sensor.id,
                date_from=archive_start_date,
                date_to=archive_end_date,
            )

            attempt_time = datetime.now(timezone.utc)

            sensor.last_backfill_attempt = attempt_time

            latest_after_backfill = get_latest_measurement_timestamp(
                db,
                sensor.id,
            )

            if (
                latest_after_backfill is None
                or latest_after_backfill.date() < archive_end_date
            ):
                sensor.status = "stale"

                sensor.next_retry_at = attempt_time + timedelta(
                    hours=BACKFILL_RETRY_HOURS
                )

            else:
                sensor.status = "active"
                sensor.next_retry_at = None

            db.commit()

        # Sprawdza timestamp po uzupełnieniu archiwum.
        latest_timestamp = get_latest_measurement_timestamp(
            db,
            sensor.id,
        )

        # Dopisuje tylko nowsze rekordy.
        current_save = save_current_measurements(
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
            raise RuntimeError("Brak pomiarów po zakończeniu odświeżania danych")

        freshness = get_data_freshness(refreshed_timestamp.date())

        if freshness["data_status"] == "fresh":
            sensor.status = "active"
            sensor.next_retry_at = None

        else:
            sensor.status = "stale"

        db.commit()

        total_new_records = archive_metrics["new_records"] + current_save["new_records"]

        total_fetched_records = (
            current_metrics["fetched_records"] + archive_metrics["fetched_records"]
        )

        total_gios_time = current_metrics["gios_time"] + archive_metrics["gios_time"]

        total_db_write_time = (
            archive_metrics["db_write_time"] + current_save["db_write_time"]
        )

        return {
            "sensor_id": sensor.id,
            "new_records": total_new_records,
            "fetched_records": total_fetched_records,
            "current_calls": current_metrics["current_calls"],
            "archive_used": archive_metrics["archive_used"],
            "gios_time": total_gios_time,
            "db_write_time": total_db_write_time,
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
