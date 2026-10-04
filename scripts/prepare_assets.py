from pathlib import Path

import hashlib
import json

import httpx
import pandas as pd

from smogcast.ingest.gios import (
    get_all_stations,
    get_data_for_sensor_records,
    get_station_sensors,
)
from smogcast.ingest.weather import get_weather_for_stations


GIOS_PATH = Path("data/raw/gios_pm_measurements_3y.parquet")
WEATHER_PATH = Path("data/raw/open_meteo_weather_3y.parquet")
METADATA_PATH = Path("data/dataset_metadata.json")

DATE_FROM = "2023-08-20 00:00"
DATE_TO = "2026-08-20 23:00"

WEATHER_DATE_FROM = "2023-08-20"
WEATHER_DATE_TO = "2026-08-20"

DATASET_VERSION = "data-v1"

RELEASE_BASE_URL = (
    f"https://github.com/sopaula/smogcast/releases/download/{DATASET_VERSION}"
)


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


# Oblicza sumę SHA256 pliku.
def calculate_sha256(path):
    sha256 = hashlib.sha256()

    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            sha256.update(chunk)

    return sha256.hexdigest()


# Wczytuje metadata datasetu.
def load_dataset_metadata():
    if not METADATA_PATH.exists():
        return None

    with open(METADATA_PATH, encoding="utf-8") as file:
        return json.load(file)


# Sprawdza integralność pliku.
def verify_asset(path, metadata):
    file_metadata = metadata["files"].get(path.name)

    if not file_metadata:
        print(f"Brak checksumy dla {path.name}.")
        return False

    expected = file_metadata["sha256"]
    actual = calculate_sha256(path)

    if actual != expected:
        print(f"Nieprawidłowa suma SHA256: {path.name}")
        return False

    print(f"SHA256 poprawne: {path.name}")
    return True


# Pobiera plik z GitHub Release.
def download_release_asset(filename, target_path):
    url = f"{RELEASE_BASE_URL}/{filename}"
    temp_path = target_path.with_suffix(target_path.suffix + ".part")

    target_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(f"Pobieranie {filename} z GitHub Release {DATASET_VERSION}...")

    try:
        with httpx.stream(
            "GET",
            url,
            follow_redirects=True,
            timeout=60.0,
        ) as response:
            response.raise_for_status()

            with open(temp_path, "wb") as file:
                for chunk in response.iter_bytes():
                    file.write(chunk)

        temp_path.replace(target_path)

        print(f"Pobrano: {target_path}")
        return True

    except httpx.HTTPError as error:
        print(f"Nie udało się pobrać {filename} z GitHub Release: {error}")

        if temp_path.exists():
            temp_path.unlink()

        return False


# Pobiera gotowy dataset i sprawdza checksumy.
def download_prepared_assets():
    if not METADATA_PATH.exists():
        downloaded = download_release_asset(
            "dataset_metadata.json",
            METADATA_PATH,
        )

        if not downloaded:
            return False

    metadata = load_dataset_metadata()

    if metadata is None:
        return False

    assets = [
        (
            "gios_pm_measurements_3y.parquet",
            GIOS_PATH,
        ),
        (
            "open_meteo_weather_3y.parquet",
            WEATHER_PATH,
        ),
    ]

    for filename, path in assets:
        if not path.exists():
            downloaded = download_release_asset(
                filename,
                path,
            )

            if not downloaded:
                return False

        if not verify_asset(path, metadata):
            print(f"Usuwanie uszkodzonego pliku: {path}")
            path.unlink()
            return False

    return True


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


# Przygotowuje historyczne dane projektu.
def prepare_assets():
    if GIOS_PATH.exists() and WEATHER_PATH.exists():
        metadata = load_dataset_metadata()

        if metadata:
            gios_ok = verify_asset(GIOS_PATH, metadata)
            weather_ok = verify_asset(WEATHER_PATH, metadata)

            if gios_ok and weather_ok:
                print("Historyczne dane są już przygotowane.")
                return

        else:
            print("Historyczne dane są już przygotowane.")
            return

    print("Przygotowywanie danych SmogCast...")

    release_ready = download_prepared_assets()

    if release_ready and GIOS_PATH.exists() and WEATHER_PATH.exists():
        print("\nGotowe dane pobrano z GitHub Release.")
        return

    print("\nGotowy dataset jest niedostępny. Przechodzę do pełnej odbudowy danych.")

    stations = get_selected_stations()

    print(f"Wybrane stacje: {len(stations)}")

    prepare_gios(stations)
    prepare_weather(stations)

    print("\nPrzygotowanie danych zakończone.")


if __name__ == "__main__":
    prepare_assets()
