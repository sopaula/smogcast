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
from smogcast.processing.daily import (
    aggregate_daily_measurements_for_sensors,
)
from smogcast.storage.db import SessionLocal
from smogcast.storage.models import (
    InitializationState,
    Measurement,
    Sensor,
)


# Pobiera stacje używane w Smogcast.
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

    elapsed = perf_counter() - start

    http_metrics = get_http_metrics()

    other_time = elapsed - total_gios_time - total_db_write_time - daily_time

    print("\n==============================")

    print("PODSUMOWANIE ODŚWIEŻANIA")

    print("==============================")

    print(f"Stacje: {len(station_ids)}")

    print(f"Odświeżone stacje: {refreshed}")

    print(f"Błędy: {failed}")

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

    print(f"Pozostały czas: {max(other_time, 0):.2f} s")

    print()

    print(f"CZAS CAŁKOWITY: {elapsed:.2f} s")

    print("==============================")

    if failed > 0:
        raise RuntimeError(f"Nie udało się odświeżyć {failed} stacji.")

    save_last_successful_refresh()

    print("Zapisano czas ostatniego udanego odświeżenia.")


if __name__ == "__main__":
    refresh_all_stations()
