from pathlib import Path

import pandas as pd

from smogcast.ingest.gios import (
    get_all_stations,
    get_data_for_sensor_records,
    get_station_sensors,
)
from smogcast.ingest.weather import get_weather_for_stations


GIOS_PATH = Path("data/raw/gios_pm_measurements_3y.parquet")
WEATHER_PATH = Path("data/raw/open_meteo_weather_3y.parquet")

DATE_FROM = "2023-08-20 00:00"
DATE_TO = "2026-08-20 23:00"

WEATHER_DATE_FROM = "2023-08-20"
WEATHER_DATE_TO = "2026-08-20"


SELECTED_STATION_IDS = [
    117,
    156,
    258,
    361,
    295,
    400,
    530,
    590,
    671,
    609,
    729,
    814,
    11195,
    861,
    944,
    986,
]


# Pobiera dane wybranych stacji.
def get_selected_stations():
    stations = get_all_stations()

    selected = [
        station
        for station in stations
        if station["Identyfikator stacji"] in SELECTED_STATION_IDS
    ]

    found_ids = {station["Identyfikator stacji"] for station in selected}

    missing_ids = set(SELECTED_STATION_IDS) - found_ids

    if missing_ids:
        raise RuntimeError(f"Nie znaleziono stacji GIOŚ: {sorted(missing_ids)}")

    return selected


# Przygotowuje listę sensorów PM10 i PM2.5.
def build_sensor_records(stations):
    sensor_records = []

    for station in stations:
        station_id = station["Identyfikator stacji"]

        sensors = get_station_sensors(station_id)

        for sensor in sensors:
            parameter = sensor["Wskaźnik - kod"]

            if parameter not in {"PM10", "PM2.5"}:
                continue

            sensor_records.append(
                {
                    "station_id": station_id,
                    "station_name": station["Nazwa stacji"],
                    "city": station["Nazwa miasta"],
                    "voivodeship": station["Województwo"],
                    "sensor_id": sensor["Identyfikator stanowiska"],
                    "parameter": parameter,
                }
            )

    return sensor_records


# Przygotowuje listę stacji dla Open-Meteo.
def build_weather_records(stations):
    records = []

    for station in stations:
        records.append(
            {
                "station_id": station["Identyfikator stacji"],
                "station_name": station["Nazwa stacji"],
                "city": station["Nazwa miasta"],
                "voivodeship": station["Województwo"],
                "latitude": float(station["WGS84 φ N"]),
                "longitude": float(station["WGS84 λ E"]),
            }
        )

    return records


# Tworzy historyczny plik pomiarów GIOŚ.
def prepare_gios(stations):
    if GIOS_PATH.exists():
        print(f"GIOŚ: {GIOS_PATH} już istnieje.")
        return

    print("\nPobieranie historycznych danych GIOŚ...")

    sensor_records = build_sensor_records(stations)

    print(f"Wybrane sensory PM: {len(sensor_records)}")

    measurements, failed_ranges = get_data_for_sensor_records(
        sensor_records,
        DATE_FROM,
        DATE_TO,
        days_per_range=30,
    )

    if failed_ranges:
        raise RuntimeError(f"Nie udało się pobrać części danych GIOŚ: {failed_ranges}")

    df = pd.DataFrame(measurements)

    columns = [
        "Nazwa stacji",
        "Kod stanowiska",
        "Data",
        "Wartość",
        "station_id",
        "sensor_id",
        "station_name",
        "city",
        "voivodeship",
        "Parametr",
    ]

    df = df[columns]

    GIOS_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    df.to_parquet(
        GIOS_PATH,
        index=False,
    )

    print(f"Zapisano: {GIOS_PATH}")
    print(f"Rekordy: {len(df)}")


# Tworzy historyczny plik pogody.
def prepare_weather(stations):
    if WEATHER_PATH.exists():
        print(f"Open-Meteo: {WEATHER_PATH} już istnieje.")
        return

    print("\nPobieranie historycznych danych pogodowych...")

    station_records = build_weather_records(stations)

    weather, failed_stations = get_weather_for_stations(
        station_records,
        WEATHER_DATE_FROM,
        WEATHER_DATE_TO,
    )

    if failed_stations:
        raise RuntimeError(f"Nie udało się pobrać pogody dla stacji: {failed_stations}")

    df = pd.DataFrame(weather)

    WEATHER_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    df.to_parquet(
        WEATHER_PATH,
        index=False,
    )

    print(f"Zapisano: {WEATHER_PATH}")
    print(f"Rekordy: {len(df)}")


def prepare_assets():
    if GIOS_PATH.exists() and WEATHER_PATH.exists():
        print("Historyczne dane są już przygotowane.")
        return

    print("Przygotowywanie danych SmogCast...")

    stations = get_selected_stations()

    print(f"Wybrane stacje: {len(stations)}")

    prepare_gios(stations)
    prepare_weather(stations)

    print("\nPrzygotowanie danych zakończone.")


if __name__ == "__main__":
    prepare_assets()
