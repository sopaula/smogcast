import time

import httpx


OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


# Zamienia odpowiedź Open-Meteo na listę godzinowych pomiarów pogody
# Do każdego pomiaru dopisuje informacje o stacji
def parse_weather_data(
    data,
    station_id,
    station_name,
    city,
    voivodeship,
    latitude,
    longitude,
):
    hourly = data["hourly"]

    measurements = []

    for i, timestamp in enumerate(hourly["time"]):
        measurements.append(
            {
                "station_id": station_id,
                "station_name": station_name,
                "city": city,
                "voivodeship": voivodeship,
                "latitude": latitude,
                "longitude": longitude,
                "timestamp_utc": timestamp,
                "temperature_2m": hourly["temperature_2m"][i],
                "relative_humidity_2m": hourly["relative_humidity_2m"][i],
                "wind_speed_10m": hourly["wind_speed_10m"][i],
            }
        )

    return measurements


# Pobiera historyczne dane pogodowe dla jednej stacji
# Dane są pobierane godzinowo i od razu w strefie UTC
# W przypadku timeoutu lub kodu 429 funkcja ponawia zapytanie
def get_weather_for_location(
    station_id,
    station_name,
    city,
    voivodeship,
    latitude,
    longitude,
    start_date,
    end_date,
    max_retries=3,
):
    for attempt in range(max_retries):
        try:
            response = httpx.get(
                OPEN_METEO_ARCHIVE_URL,
                params={
                    "latitude": latitude,
                    "longitude": longitude,
                    "start_date": start_date,
                    "end_date": end_date,
                    "hourly": ("temperature_2m,relative_humidity_2m,wind_speed_10m"),
                    "timezone": "UTC",
                },
                timeout=30.0,
            )

            if response.status_code == 429:
                print("Za dużo zapytań do Open-Meteo. Czekam 10 sekund...")
                time.sleep(10)
                continue

            response.raise_for_status()

            data = response.json()

            return parse_weather_data(
                data,
                station_id,
                station_name,
                city,
                voivodeship,
                latitude,
                longitude,
            )

        except (httpx.ReadTimeout, httpx.ConnectTimeout):
            print(f"Timeout dla stacji {station_id}. Próba {attempt + 1}/{max_retries}")

            time.sleep(5)

    return None


# Pobiera pogodę historyczną dla wszystkich wybranych stacji
# Łączy pomiary w jedną listę i zapisuje stacje,
# których nie udało się pobrać
def get_weather_for_stations(
    station_records,
    start_date,
    end_date,
):
    all_weather = []
    failed_stations = []

    for i, station in enumerate(station_records, start=1):
        station_id = station["station_id"]
        station_name = station["station_name"]
        city = station["city"]
        voivodeship = station["voivodeship"]
        latitude = station["latitude"]
        longitude = station["longitude"]

        print(
            f"{i}/{len(station_records)} | {voivodeship} | {city} | stacja {station_id}"
        )

        measurements = get_weather_for_location(
            station_id,
            station_name,
            city,
            voivodeship,
            latitude,
            longitude,
            start_date,
            end_date,
        )

        if measurements is None:
            failed_stations.append(station_id)
            continue

        all_weather.extend(measurements)

        time.sleep(0.5)

    return all_weather, failed_stations
