import time
from datetime import datetime, timezone
from time import perf_counter

import httpx
from sqlalchemy import select

from smogcast.ingest.current import (
    refresh_station_measurements,
)
from smogcast.ingest.gios import (
    get_http_metrics,
    reset_http_metrics,
)
from smogcast.ingest.weather import (
    get_forecast_weather,
    get_tomorrow_date,
)
from smogcast.processing.daily import (
    aggregate_daily_measurements_for_sensors,
)
from smogcast.storage.db import SessionLocal, create_tables
from smogcast.storage.models import (
    InitializationState,
    Measurement,
    Sensor,
    Station,
    WeatherForecast,
)


# Pobiera stacje używane w SmogCast.
def get_station_ids():
    with SessionLocal() as db:
        stmt = (
            select(
                Sensor.station_id,
            )
            .join(
                Measurement,
                Measurement.sensor_id == Sensor.id,
            )
            .distinct()
        )

        return list(db.scalars(stmt))


# Pobiera dane stacji potrzebne do prognozy pogody.
def get_forecast_stations(
    station_ids,
):
    with SessionLocal() as db:
        stmt = (
            select(Station)
            .where(
                Station.id.in_(station_ids),
            )
            .order_by(Station.id)
        )

        stations = db.scalars(stmt).all()

        return [
            {
                "station_id": station.id,
                "latitude": station.latitude,
                "longitude": station.longitude,
            }
            for station in stations
        ]


# Sprawdza, czy prognoza na dany dzień jest już w bazie.
def weather_forecast_exists(
    station_id,
    target_date,
):
    with SessionLocal() as db:
        stmt = select(WeatherForecast.station_id).where(
            WeatherForecast.station_id == station_id,
            WeatherForecast.target_date == target_date,
        )

        return db.scalar(stmt) is not None


# Zapisuje prognozę pogody dla stacji.
def save_weather_forecast(
    station_id,
    weather,
):
    with SessionLocal() as db:
        forecast = WeatherForecast(
            station_id=station_id,
            target_date=weather["date"],
            temp_c=weather["temp_c"],
            wind_ms=weather["wind_ms"],
            humidity=weather["humidity"],
            fetched_at=datetime.now(timezone.utc),
        )

        db.merge(forecast)
        db.commit()


# Pobiera i zapisuje prognozy pogody na jutro.
def refresh_weather_forecasts(
    station_ids,
):
    target_date = get_tomorrow_date()

    stations = get_forecast_stations(
        station_ids,
    )

    refreshed = 0
    skipped = 0
    failed = 0

    print(f"\nPobieranie prognozy pogody na {target_date}...")

    for index, station in enumerate(
        stations,
        start=1,
    ):
        station_id = station["station_id"]

        print(f"{index}/{len(stations)} | prognoza pogody | stacja {station_id}")

        if weather_forecast_exists(
            station_id,
            target_date,
        ):
            skipped += 1

            print("Prognoza już istnieje - pominięto.")

            continue

        weather = get_forecast_weather(
            station["latitude"],
            station["longitude"],
            target_date,
        )

        if weather is None:
            failed += 1

            print(f"Nie udało się pobrać prognozy dla stacji {station_id}.")

        else:
            save_weather_forecast(
                station_id,
                weather,
            )

            refreshed += 1

        # Ogranicza tempo zapytań do Open-Meteo.
        if index < len(stations):
            time.sleep(1)

    print(f"Nowe prognozy pogody: {refreshed}")

    print(f"Pominięte prognozy: {skipped}")

    print(f"Błędy prognozy pogody: {failed}")

    return refreshed, skipped, failed


# Zapisuje czas ostatniego udanego odświeżenia.
def save_last_successful_refresh():
    with SessionLocal() as db:
        state = InitializationState(
            step="last_successful_refresh",
            completed_at=datetime.now(timezone.utc),
        )

        db.merge(state)
        db.commit()


# Aktualizuje wszystkie stacje.
def refresh_all_stations():
    create_tables()

    reset_http_metrics()

    station_ids = get_station_ids()

    updated_sensor_ids = set()

    refreshed = 0
    failed = 0

    total_gios_time = 0.0
    total_db_write_time = 0.0

    total_fetched_records = 0
    total_new_records = 0

    total_current_calls = 0
    total_archive_uses = 0

    start = perf_counter()

    print(f"Odświeżanie {len(station_ids)} stacji...")

    for index, station_id in enumerate(
        station_ids,
        start=1,
    ):
        print(f"\n{index}/{len(station_ids)} | stacja {station_id}")

        try:
            result = refresh_station_measurements(station_id)

        except (
            httpx.HTTPError,
            RuntimeError,
        ) as error:
            failed += 1

            print(f"Błąd: {error}")

            continue

        refreshed += 1

        # Zbiera statystyki odświeżania.
        for param_result in result.values():
            if not isinstance(
                param_result,
                dict,
            ):
                continue

            if param_result.get("available") is False:
                continue

            sensor_id = param_result.get("sensor_id")

            new_records = param_result.get(
                "new_records",
                0,
            )

            if sensor_id is not None and new_records > 0:
                updated_sensor_ids.add(sensor_id)

            total_gios_time += param_result.get(
                "gios_time",
                0.0,
            )

            total_db_write_time += param_result.get(
                "db_write_time",
                0.0,
            )

            total_fetched_records += param_result.get(
                "fetched_records",
                0,
            )

            total_new_records += new_records

            total_current_calls += param_result.get(
                "current_calls",
                0,
            )

            if param_result.get(
                "archive_used",
                False,
            ):
                total_archive_uses += 1

        print(f"PM10: {result.get('PM10')}")

        print(f"PM2.5: {result.get('PM25')}")

    daily_time = 0.0
    daily_count = 0

    # Przelicza agregaty dla zmienionych sensorów.
    if updated_sensor_ids:
        print("\nPrzeliczanie danych dobowych...")

        daily_start = perf_counter()

        daily_count = aggregate_daily_measurements_for_sensors(list(updated_sensor_ids))

        daily_time = perf_counter() - daily_start

        print(f"Zapisano {daily_count} agregatów dobowych.")

    else:
        print("\nBrak nowych danych do przeliczenia.")

    # Pobiera pogodę na jutro i zapisuje ją do bazy.
    weather_start = perf_counter()

    (
        weather_refreshed,
        weather_skipped,
        weather_failed,
    ) = refresh_weather_forecasts(
        station_ids,
    )

    weather_time = perf_counter() - weather_start

    elapsed = perf_counter() - start

    http_metrics = get_http_metrics()

    other_time = (
        elapsed - total_gios_time - total_db_write_time - daily_time - weather_time
    )

    print("\n==============================")

    print("PODSUMOWANIE ODŚWIEŻANIA")

    print("==============================")

    print(f"Stacje: {len(station_ids)}")

    print(f"Odświeżone stacje: {refreshed}")

    print(f"Błędy GIOŚ: {failed}")

    print()

    print(f"Nowe prognozy pogody: {weather_refreshed}")

    print(f"Pominięte prognozy pogody: {weather_skipped}")

    print(f"Błędy prognozy pogody: {weather_failed}")

    print()

    print(f"Zapytania HTTP: {http_metrics['total_requests']}")

    print(f"Ponowienia: {http_metrics['retries']}")

    print(f"Ponowienia po 429: {http_metrics['rate_limit_retries']}")

    print(f"Ponowienia po timeout: {http_metrics['timeout_retries']}")

    print()

    print(f"Zapytania bieżące: {http_metrics['current_requests']}")

    print(f"Zapytania archiwalne: {http_metrics['archive_requests']}")

    print(f"Wywołania bieżących danych: {total_current_calls}")

    print(f"Użycia archiwum: {total_archive_uses}")

    print()

    print(f"Pobrane rekordy: {total_fetched_records}")

    print(f"Nowe rekordy: {total_new_records}")

    print(f"Agregaty dobowe: {daily_count}")

    print()

    print(f"Czas danych bieżących: {http_metrics['current_time']:.2f} s")

    print(f"Czas danych archiwalnych: {http_metrics['archive_time']:.2f} s")

    print(f"Czas GIOŚ łącznie: {total_gios_time:.2f} s")

    print(f"Czas zapisu do bazy: {total_db_write_time:.2f} s")

    print(f"Czas agregacji: {daily_time:.2f} s")

    print(f"Czas prognozy pogody: {weather_time:.2f} s")

    print(f"Pozostały czas: {max(other_time, 0):.2f} s")

    print()

    print(f"CZAS CAŁKOWITY: {elapsed:.2f} s")

    print("==============================")

    if failed > 0:
        raise RuntimeError(f"Nie udało się odświeżyć {failed} stacji GIOŚ.")

    if weather_failed > 0:
        raise RuntimeError(f"Nie udało się pobrać {weather_failed} prognoz pogody.")

    save_last_successful_refresh()

    print("Zapisano czas ostatniego udanego odświeżenia.")


if __name__ == "__main__":
    refresh_all_stations()
