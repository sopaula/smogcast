from time import perf_counter

import httpx
from sqlalchemy import select

from smogcast.ingest.current import (
    refresh_station_measurements,
)
from smogcast.processing.daily import (
    aggregate_daily_measurements_for_sensors,
)
from smogcast.storage.db import SessionLocal
from smogcast.storage.models import Measurement, Sensor


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


# Aktualizuje wszystkie stacje.
def refresh_all_stations():
    station_ids = get_station_ids()

    updated_sensor_ids = set()

    refreshed = 0
    failed = 0

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

        # Zbiera sensory z nowymi danymi.
        for param_result in result.values():
            if not isinstance(
                param_result,
                dict,
            ):
                continue

            sensor_id = param_result.get("sensor_id")

            new_records = param_result.get(
                "new_records",
                0,
            )

            if sensor_id is not None and new_records > 0:
                updated_sensor_ids.add(sensor_id)

        print(f"PM10: {result.get('PM10')}")

        print(f"PM2.5: {result.get('PM25')}")

    # Przelicza agregaty dla zmienionych sensorów.
    if updated_sensor_ids:
        print("\nPrzeliczanie danych dobowych...")

        daily_count = aggregate_daily_measurements_for_sensors(list(updated_sensor_ids))

        print(f"Zapisano {daily_count} agregatów dobowych.")

    else:
        print("\nBrak nowych danych do przeliczenia.")

    elapsed = perf_counter() - start

    print("\nGotowe.")

    print(f"Odświeżone stacje: {refreshed}")

    print(f"Błędy: {failed}")

    print(f"Czas: {elapsed:.2f} s")


if __name__ == "__main__":
    refresh_all_stations()
