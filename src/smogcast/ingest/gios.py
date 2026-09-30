import time
from datetime import datetime, timedelta
from threading import Lock

import httpx


STATIONS_URL = "https://api.gios.gov.pl/pjp-api/v1/rest/station/findAll"

SENSORS_URL = "https://api.gios.gov.pl/pjp-api/v1/rest/station/sensors"

SENSOR_ARCHIVAL_URL = (
    "https://api.gios.gov.pl/pjp-api/v1/rest/archivalData/getDataBySensor"
)

CURRENT_DATA_URL = "https://api.gios.gov.pl/pjp-api/v1/rest/data/getData"


METADATA_CACHE_TTL_SECONDS = 6 * 60 * 60

# Minimalny odstęp między zapytaniami archiwalnymi.
MIN_REQUEST_INTERVAL = 1.0


# Wspólny klient HTTP.
client = httpx.Client()


_stations_cache = {
    "data": None,
    "expires_at": 0.0,
}


_sensors_cache = {}


_http_metrics = {
    "total_requests": 0,
    "retries": 0,
    "rate_limit_retries": 0,
    "timeout_retries": 0,
    "current_requests": 0,
    "current_time": 0.0,
    "archive_requests": 0,
    "archive_time": 0.0,
    "metadata_requests": 0,
    "metadata_time": 0.0,
}


_request_lock = Lock()
_last_request_time = 0.0


# Zachowuje odstęp między zapytaniami archiwalnymi.
def wait_for_request_slot():
    global _last_request_time

    with _request_lock:
        now = time.monotonic()

        remaining = MIN_REQUEST_INTERVAL - (now - _last_request_time)

        if remaining > 0:
            time.sleep(remaining)

        _last_request_time = time.monotonic()


# Zeruje statystyki HTTP.
def reset_http_metrics():
    time_metrics = {
        "current_time",
        "archive_time",
        "metadata_time",
    }

    for key in _http_metrics:
        if key in time_metrics:
            _http_metrics[key] = 0.0
        else:
            _http_metrics[key] = 0


# Zwraca statystyki HTTP.
def get_http_metrics():
    return _http_metrics.copy()


# Wykonuje zapytanie i zapisuje jego czas.
def timed_get(
    url,
    category,
    **kwargs,
):
    if category == "archive":
        wait_for_request_slot()

    _http_metrics["total_requests"] += 1

    request_key = f"{category}_requests"

    time_key = f"{category}_time"

    _http_metrics[request_key] += 1

    start = time.perf_counter()

    try:
        return client.get(
            url,
            **kwargs,
        )

    finally:
        _http_metrics[time_key] += time.perf_counter() - start


# Wyciąga listę stacji z odpowiedzi API.
def parse_stations(
    data,
):
    return data["Lista stacji pomiarowych"]


# Pobiera wszystkie stacje GIOŚ.
def get_all_stations():
    now = time.monotonic()

    # Korzysta z cache, jeśli jest aktualny.
    if _stations_cache["data"] is not None and now < _stations_cache["expires_at"]:
        return _stations_cache["data"]

    stations = []

    response = timed_get(
        STATIONS_URL,
        category="metadata",
        params={
            "size": 100,
        },
        timeout=10.0,
    )

    response.raise_for_status()

    data = response.json()

    stations.extend(parse_stations(data))

    total_pages = data["totalPages"]

    # Pobiera kolejne strony.
    for page in range(
        1,
        total_pages,
    ):
        response = timed_get(
            STATIONS_URL,
            category="metadata",
            params={
                "page": page,
                "size": 100,
            },
            timeout=10.0,
        )

        response.raise_for_status()

        page_data = response.json()

        stations.extend(parse_stations(page_data))

    # Zapisuje wynik w cache.
    _stations_cache["data"] = stations

    _stations_cache["expires_at"] = time.monotonic() + METADATA_CACHE_TTL_SECONDS

    return stations


# Pobiera sensory dla jednej stacji.
def get_station_sensors(
    station_id,
):
    now = time.monotonic()

    cached = _sensors_cache.get(station_id)

    # Korzysta z cache, jeśli jest aktualny.
    if cached is not None and now < cached["expires_at"]:
        return cached["data"]

    response = timed_get(
        f"{SENSORS_URL}/{station_id}",
        category="metadata",
        timeout=10.0,
    )

    response.raise_for_status()

    data = response.json()

    sensors = data["Lista stanowisk pomiarowych dla podanej stacji"]

    # Zapisuje sensory w cache.
    _sensors_cache[station_id] = {
        "data": sensors,
        "expires_at": (time.monotonic() + METADATA_CACHE_TTL_SECONDS),
    }

    return sensors


# DANE ARCHIWALNE


# Dzieli okres na mniejsze zakresy.
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


# Wyciąga archiwalne pomiary z odpowiedzi API.
def parse_archival_measurements(
    data,
):
    return data["Lista archiwalnych wyników pomiarów"]


# Pobiera jeden zakres dla sensora.
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
            if attempt > 0:
                _http_metrics["retries"] += 1

            try:
                response = timed_get(
                    f"{SENSOR_ARCHIVAL_URL}/{sensor_id}",
                    category="archive",
                    params={
                        "dateFrom": date_from,
                        "dateTo": date_to,
                        "page": page,
                        "size": 500,
                    },
                    timeout=30.0,
                )

                if response.status_code == 429:
                    _http_metrics["rate_limit_retries"] += 1

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
                _http_metrics["timeout_retries"] += 1

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
            return None

        if page >= total_pages - 1:
            break

        page += 1

        time.sleep(0.3)

    return all_measurements


# Pobiera cały okres dla sensora.
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

        time.sleep(0.5)

    return (
        all_measurements,
        failed_ranges,
    )


# Pobiera dane dla wielu sensorów.
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
            f"\n{i}/"
            f"{len(sensor_records)} | "
            f"{voivodeship} | "
            f"{city} | "
            f"{parameter} | "
            f"sensor {sensor_id}"
        )

        (
            measurements,
            sensor_failed_ranges,
        ) = get_sensor_data_for_period(
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

        time.sleep(0.5)

    return (
        all_measurements,
        failed_ranges,
    )


# DANE BIEŻĄCE


# Wyciąga bieżące pomiary z odpowiedzi API.
def parse_current_measurements(
    data,
):
    return data.get(
        "Lista danych pomiarowych",
        [],
    )


# Pobiera bieżące dane dla jednego sensora.
def get_current_sensor_data(
    sensor_id,
    timeout=30.0,
    max_retries=3,
):
    for attempt in range(max_retries):
        if attempt > 0:
            _http_metrics["retries"] += 1

        try:
            response = timed_get(
                f"{CURRENT_DATA_URL}/{sensor_id}",
                category="current",
                params={
                    "size": 100,
                },
                timeout=timeout,
            )

            if response.status_code == 429:
                _http_metrics["rate_limit_retries"] += 1

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
            _http_metrics["timeout_retries"] += 1

            print(
                "Timeout dla bieżących danych "
                f"sensora {sensor_id}. "
                f"Próba "
                f"{attempt + 1}/"
                f"{max_retries}"
            )

            time.sleep(5)

    return None
