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


# Ostatnie dni próbujemy pobierać
# z bieżącego endpointu GIOŚ
CURRENT_DATA_DAYS = 3

# Dane do 2 dni uznajemy za świeże
FRESH_DATA_DAYS = 2


# Zamienia parametr używany w API
# na kod zapisany w bazie
#
# W API używamy PM25,
# a w bazie zapisujemy PM2.5
def map_param(param):
    if param == "PM25":
        return "PM2.5"

    return param


# Pobiera wszystkie sensory
# dla wybranej stacji i parametru
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


# Pobiera najnowszy timestamp
# zapisany dla konkretnego sensora
def get_latest_measurement_timestamp(
    db,
    sensor_id,
):
    stmt = (
        select(Measurement.timestamp)
        .where(Measurement.sensor_id == sensor_id)
        .order_by(Measurement.timestamp.desc())
        .limit(1)
    )

    return db.scalar(stmt)


# Zamienia rekordy zwrócone przez GIOŚ
# na format używany w naszej bazie
#
# Timestamp GIOŚ traktujemy jako CET
# i zapisujemy jako UTC bez timezone
def prepare_measurements_for_database(
    sensor_id,
    measurements,
):
    prepared = []

    cet = timezone(timedelta(hours=1))

    for measurement in measurements:
        timestamp_text = measurement.get("Data")

        # Jeśli rekord nie ma daty,
        # pomijamy go
        if timestamp_text is None:
            continue

        timestamp = datetime.fromisoformat(timestamp_text)

        timestamp_cet = timestamp.replace(tzinfo=cet)

        timestamp_utc = timestamp_cet.astimezone(timezone.utc)

        prepared.append(
            {
                "sensor_id": sensor_id,
                "timestamp": (timestamp_utc.replace(tzinfo=None)),
                "value": measurement.get("Wartość"),
            }
        )

    return prepared


# Próbuje pobrać bieżące dane
# dla jednego sensora
#
# Nie wszystkie sensory są obsługiwane
# przez current API GIOŚ
#
# Jeśli endpoint zwróci 400,
# traktujemy to jako brak current data
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


# Zwraca timestamp najnowszego
# rekordu pobranego z current API
def get_latest_current_timestamp(
    measurements,
):
    timestamps = []

    for measurement in measurements:
        timestamp_text = measurement.get("Data")

        if timestamp_text is None:
            continue

        timestamp = datetime.fromisoformat(timestamp_text)

        timestamps.append(timestamp)

    if not timestamps:
        return None

    return max(timestamps)


# Sprawdza wszystkie sensory
# i wybiera sensor mający
# najświeższe bieżące dane
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


# Jeśli żaden sensor nie ma current data,
# wybiera sensor z najświeższymi
# danymi zapisanymi w naszej bazie
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


# Uzupełnia starszą część luki
# za pomocą archiwalnego endpointu GIOŚ
def refresh_archive_part(
    db,
    sensor_id,
    date_from,
    date_to,
):
    measurements, failed_ranges = get_sensor_data_for_period(
        sensor_id=sensor_id,
        date_from=date_from.strftime("%Y-%m-%d 00:00"),
        date_to=date_to.strftime("%Y-%m-%d 23:00"),
        days_per_range=30,
    )

    # Jeśli nie udało się pobrać
    # któregoś zakresu, zgłaszamy błąd
    if failed_ranges:
        raise RuntimeError(f"Failed archival ranges: {failed_ranges}")

    # Jeśli archiwum niczego nie zwróciło,
    # przechodzimy dalej
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


# Zapisuje bieżące pomiary
# pobrane z current API
def save_current_measurements(
    db,
    sensor_id,
    measurements,
):
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


# Określa status świeżości danych
#
# Dane do 2 dni uznajemy za świeże.
# Starsze dane nadal mogą zostać użyte
# do forecastu, ale zwracamy ostrzeżenie.
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


# Aktualizuje dane PM
# dla wybranej stacji i parametru
def refresh_recent_measurements(
    station_id,
    param,
):
    param_code = map_param(param)

    with SessionLocal() as db:
        sensors = get_sensors_for_station(
            db,
            station_id,
            param_code,
        )

        if not sensors:
            raise ValueError("No sensor found for station and parameter")

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

        if latest_date < archive_end_date:
            archive_start_date = latest_date + timedelta(days=1)

            refresh_archive_part(
                db=db,
                sensor_id=sensor.id,
                date_from=archive_start_date,
                date_to=archive_end_date,
            )

        save_current_measurements(
            db=db,
            sensor_id=sensor.id,
            measurements=current_measurements,
        )

        refreshed_timestamp = get_latest_measurement_timestamp(
            db,
            sensor.id,
        )

        if refreshed_timestamp is None:
            raise RuntimeError("No measurements available after refresh")

        refreshed_date = refreshed_timestamp.date()

        freshness = get_data_freshness(refreshed_date)

        return {
            "sensor_id": sensor.id,
            "data_date": freshness["data_date"],
            "data_age_days": freshness["data_age_days"],
            "data_status": freshness["data_status"],
            "warning": freshness["warning"],
        }


# Aktualizuje PM10 i PM2.5
# dla jednej wybranej stacji
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
