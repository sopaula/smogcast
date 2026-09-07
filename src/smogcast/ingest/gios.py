import time
from datetime import datetime, timedelta

import httpx


STATIONS_URL = "https://api.gios.gov.pl/pjp-api/v1/rest/station/findAll"

SENSORS_URL = "https://api.gios.gov.pl/pjp-api/v1/rest/station/sensors"

SENSOR_ARCHIVAL_URL = (
    "https://api.gios.gov.pl/pjp-api/v1/rest/archivalData/getDataBySensor"
)

CURRENT_DATA_URL = "https://api.gios.gov.pl/pjp-api/v1/rest/data/getData"


# Wyciąga listę stacji z odpowiedzi JSON zwróconej przez API
def parse_stations(data):
    return data["Lista stacji pomiarowych"]


# Pobiera wszystkie stacje pomiarowe GIOŚ ze wszystkich stron API
def get_all_stations():
    stations = []

    response = httpx.get(
        STATIONS_URL,
        timeout=10.0,
    )
    response.raise_for_status()

    data = response.json()

    stations.extend(parse_stations(data))

    total_pages = data["totalPages"]

    for page in range(1, total_pages):
        response = httpx.get(
            STATIONS_URL,
            params={
                "page": page,
                "size": 20,
            },
            timeout=10.0,
        )

        response.raise_for_status()

        page_data = response.json()

        stations.extend(parse_stations(page_data))

    return stations


# Pobiera sensory dla jednej stacji GIOŚ
def get_station_sensors(station_id):
    response = httpx.get(
        f"{SENSORS_URL}/{station_id}",
        timeout=10.0,
    )

    response.raise_for_status()

    data = response.json()

    return data["Lista stanowisk pomiarowych dla podanej stacji"]


# DANE ARCHIWALNE


# Dzieli okres na mniejsze, niepokrywające się zakresy dat
def generate_date_ranges(
    date_from,
    date_to,
    days_per_range=30,
):
    current = datetime.strptime(
        date_from,
        "%Y-%m-%d %H:%M",
    )

    end = datetime.strptime(
        date_to,
        "%Y-%m-%d %H:%M",
    )

    ranges = []

    while current <= end:
        range_end = min(
            current + timedelta(days=days_per_range) - timedelta(hours=1),
            end,
        )

        ranges.append(
            (
                current.strftime("%Y-%m-%d %H:%M"),
                range_end.strftime("%Y-%m-%d %H:%M"),
            )
        )

        current = range_end + timedelta(hours=1)

    return ranges


# Wyciąga listę archiwalnych pomiarów
# z odpowiedzi JSON API
def parse_archival_measurements(data):
    return data["Lista archiwalnych wyników pomiarów"]


# Pobiera jeden zakres dat dla jednego sensora
# Obsługuje wszystkie strony odpowiedzi, timeouty i kod 429
def get_archival_data_by_sensor(
    sensor_id,
    date_from,
    date_to,
    max_retries=3,
):
    all_measurements = []
    page = 0

    while True:
        for attempt in range(max_retries):
            try:
                response = httpx.get(
                    f"{SENSOR_ARCHIVAL_URL}/{sensor_id}",
                    params={
                        "dateFrom": date_from,
                        "dateTo": date_to,
                        "page": page,
                        "size": 500,
                    },
                    timeout=30.0,
                )

                if response.status_code == 429:
                    print("Za dużo zapytań. Czekam 10 sekund...")

                    time.sleep(10)
                    continue

                response.raise_for_status()

                data = response.json()

                measurements = parse_archival_measurements(data)

                all_measurements.extend(measurements)

                total_pages = data["totalPages"]

                break

            except (
                httpx.ReadTimeout,
                httpx.ConnectTimeout,
            ):
                print(
                    f"Timeout dla sensora "
                    f"{sensor_id}, "
                    f"strona {page}. "
                    f"Próba "
                    f"{attempt + 1}/"
                    f"{max_retries}"
                )

                time.sleep(5)

        else:
            # Wszystkie próby dla tej strony się nie udały
            return None

        # Jeśli właśnie pobraliśmy ostatnią stronę,
        # kończymy
        if page >= total_pages - 1:
            break

        page += 1

        # Krótka przerwa przed pobraniem
        # kolejnej strony
        time.sleep(0.3)

    return all_measurements


# Pobiera cały okres dla jednego sensora,
# dzieląc go na mniejsze zakresy dat
def get_sensor_data_for_period(
    sensor_id,
    date_from,
    date_to,
    days_per_range=30,
):
    ranges = generate_date_ranges(
        date_from,
        date_to,
        days_per_range,
    )

    all_measurements = []
    failed_ranges = []

    for range_from, range_to in ranges:
        print(f"Pobieram sensor {sensor_id}: {range_from} - {range_to}")

        measurements = get_archival_data_by_sensor(
            sensor_id,
            range_from,
            range_to,
        )

        if measurements is None:
            failed_ranges.append(
                (
                    sensor_id,
                    range_from,
                    range_to,
                )
            )

            continue

        all_measurements.extend(measurements)

        # Krótka przerwa przed kolejnym zakresem
        time.sleep(0.5)

    return (
        all_measurements,
        failed_ranges,
    )


# Pobiera dane dla wielu sensorów i dopisuje
# informacje o stacji oraz parametrze PM10/PM2.5
def get_data_for_sensor_records(
    sensor_records,
    date_from,
    date_to,
    days_per_range=30,
):
    all_measurements = []
    failed_ranges = []

    for i, sensor in enumerate(
        sensor_records,
        start=1,
    ):
        station_id = sensor["station_id"]

        station_name = sensor["station_name"]

        city = sensor["city"]

        voivodeship = sensor["voivodeship"]

        sensor_id = sensor["sensor_id"]

        parameter = sensor["parameter"]

        print(
            f"\n{i}/{len(sensor_records)} | "
            f"{voivodeship} | "
            f"{city} | "
            f"{parameter} | "
            f"sensor {sensor_id}"
        )

        measurements, sensor_failed_ranges = get_sensor_data_for_period(
            sensor_id,
            date_from,
            date_to,
            days_per_range,
        )

        for measurement in measurements:
            measurement["station_id"] = station_id

            measurement["sensor_id"] = sensor_id

            measurement["station_name"] = station_name

            measurement["city"] = city

            measurement["voivodeship"] = voivodeship

            measurement["Parametr"] = parameter

        all_measurements.extend(measurements)

        failed_ranges.extend(sensor_failed_ranges)

        # Krótka przerwa przed następnym sensorem
        time.sleep(0.5)

    return (
        all_measurements,
        failed_ranges,
    )


# DANE BIEŻĄCE


# Wyciąga listę bieżących pomiarów
# z odpowiedzi JSON GIOŚ
def parse_current_measurements(data):
    return data.get(
        "Lista danych pomiarowych",
        [],
    )


# Pobiera najnowsze pomiary dla jednego sensora
# Korzysta z bieżącego endpointu GIOŚ,
# a nie z endpointu archiwalnego
def get_current_sensor_data(
    sensor_id,
    timeout=30.0,
    max_retries=3,
):
    for attempt in range(max_retries):
        try:
            response = httpx.get(
                f"{CURRENT_DATA_URL}/{sensor_id}",
                timeout=timeout,
            )

            if response.status_code == 429:
                print("Za dużo zapytań do GIOŚ. Czekam 10 sekund...")

                time.sleep(10)
                continue

            response.raise_for_status()

            data = response.json()

            return parse_current_measurements(data)

        except (
            httpx.ReadTimeout,
            httpx.ConnectTimeout,
        ):
            print(
                f"Timeout dla bieżących danych "
                f"sensora {sensor_id}. "
                f"Próba "
                f"{attempt + 1}/"
                f"{max_retries}"
            )

            time.sleep(5)

    return None
