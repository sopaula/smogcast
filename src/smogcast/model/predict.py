from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from time import perf_counter

import httpx
import joblib
import pandas as pd
from sqlalchemy import select

from smogcast.ingest.current import get_data_freshness
from smogcast.ingest.weather import (
    get_forecast_weather,
    get_tomorrow_date,
)
from smogcast.processing.seasons import is_heating_season
from smogcast.storage.db import SessionLocal
from smogcast.storage.models import (
    DailyMeasurement,
    Measurement,
    Sensor,
    Station,
    WeatherForecast,
)


MODEL_PATH = Path("models/model_v2.joblib")


# Zamienia nazwę parametru na format z bazy.
def map_param(
    param,
):
    if param == "PM25":
        return "PM2.5"

    return param


# Wczytuje konkretną wersję modelu.
@lru_cache(maxsize=1)
def _load_model_bundle(
    model_path,
    modified_time,
):
    return joblib.load(model_path)


# Wczytuje najnowszą wersję modelu.
def load_model_bundle():
    modified_time = MODEL_PATH.stat().st_mtime_ns

    return _load_model_bundle(
        str(MODEL_PATH),
        modified_time,
    )


# Pobiera stację z bazy.
def get_station(
    db,
    station_id,
):
    return db.get(
        Station,
        station_id,
    )


# Pobiera najnowszy sensor i datę pomiaru.
def get_latest_sensor_data(
    db,
    station_id,
    param,
):
    param_code = map_param(param)

    # Wybiera najnowszy poprawny pomiar.
    stmt = (
        select(
            Sensor.id,
            Measurement.timestamp,
        )
        .join(
            Measurement,
            Measurement.sensor_id == Sensor.id,
        )
        .where(
            Sensor.station_id == station_id,
            Sensor.param_code == param_code,
            Measurement.value.is_not(None),
        )
        .order_by(Measurement.timestamp.desc())
        .limit(1)
    )

    row = db.execute(stmt).first()

    if row is None:
        raise ValueError(f"No {param} measurements available")

    sensor_id, timestamp = row

    # Sprawdza świeżość danych.
    freshness = get_data_freshness(timestamp.date())

    return {
        "sensor_id": sensor_id,
        "data_date": freshness["data_date"],
        "data_age_days": freshness["data_age_days"],
        "data_status": freshness["data_status"],
        "warning": freshness["warning"],
    }


# Pobiera 7 ostatnich poprawnych wartości dobowych.
def get_recent_measurements(
    db,
    station_id,
    param_code,
):
    stmt = (
        select(DailyMeasurement)
        .where(
            DailyMeasurement.station_id == station_id,
            DailyMeasurement.param_code == param_code,
            DailyMeasurement.mean_value.is_not(None),
        )
        .order_by(DailyMeasurement.date.desc())
        .limit(7)
    )

    return list(db.scalars(stmt))


# Pobiera zapisaną prognozę pogody dla konkretnego dnia.
def get_saved_weather_forecast(
    db,
    station_id,
    target_date,
):
    stmt = select(WeatherForecast).where(
        WeatherForecast.station_id == station_id,
        WeatherForecast.target_date == target_date,
    )

    forecast = db.scalar(stmt)

    if forecast is None:
        return None

    return {
        "date": forecast.target_date,
        "temp_c": forecast.temp_c,
        "wind_ms": forecast.wind_ms,
        "humidity": forecast.humidity,
    }


# Zapisuje prognozę pogody pobraną awaryjnie.
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


# Pobiera pogodę z bazy lub awaryjnie z Open-Meteo.
def get_weather_for_prediction(
    station_id,
    latitude,
    longitude,
):
    target_date = get_tomorrow_date()

    # Najpierw sprawdza prognozę zapisaną w bazie.
    with SessionLocal() as db:
        weather = get_saved_weather_forecast(
            db,
            station_id,
            target_date,
        )

    if weather is not None:
        return weather, "database"

    print(
        f"[forecast-weather] "
        f"station={station_id} "
        f"target_date={target_date} "
        f"source=open-meteo-fallback"
    )

    # Brak prognozy na właściwe jutro - pobiera ją na żywo.
    weather = get_forecast_weather(
        latitude,
        longitude,
        target_date,
    )

    if weather is None:
        raise RuntimeError(
            "Weather forecast unavailable "
            f"for station {station_id} "
            f"and date {target_date}"
        )

    # Zapisuje fallback, żeby kolejne żądania korzystały już z bazy.
    save_weather_forecast(
        station_id,
        weather,
    )

    return weather, "open-meteo"


# Określa jakość danych na podstawie coverage.
def get_coverage_quality(
    measurements,
):
    coverages = [measurement.coverage for measurement in measurements[:7]]

    coverage_7d = sum(coverages) / len(coverages)

    if coverage_7d >= 75:
        return {
            "coverage_7d": round(
                coverage_7d,
                2,
            ),
            "coverage_status": "good",
            "coverage_warning": None,
        }

    if coverage_7d >= 50:
        return {
            "coverage_7d": round(
                coverage_7d,
                2,
            ),
            "coverage_status": "warning",
            "coverage_warning": (
                "Prognoza została przygotowana "
                "na podstawie niepełnych danych "
                "z ostatnich dni."
            ),
        }

    return {
        "coverage_7d": round(
            coverage_7d,
            2,
        ),
        "coverage_status": "critical",
        "coverage_warning": (
            "Prognoza została przygotowana "
            "na podstawie bardzo ograniczonej "
            "liczby pomiarów i może być "
            "mniej wiarygodna."
        ),
    }


# Buduje cechy dla prognozy.
def build_forecast_features(
    measurements,
    weather,
):
    valid_measurements = [
        measurement
        for measurement in measurements
        if measurement.mean_value is not None
    ]

    if len(valid_measurements) < 7:
        raise ValueError("Not enough valid historical measurements")

    values = [measurement.mean_value for measurement in valid_measurements]

    coverages = [measurement.coverage for measurement in valid_measurements]

    target_date = weather["date"]

    return {
        "pm_lag_1d": values[0],
        "pm_mean_3d": (sum(values[:3]) / 3),
        "pm_mean_7d": (sum(values[:7]) / 7),
        "coverage_lag_1d": coverages[0],
        "coverage_mean_3d": (sum(coverages[:3]) / 3),
        "coverage_mean_7d": (sum(coverages[:7]) / 7),
        "month": target_date.month,
        "day_of_week": (target_date.weekday()),
        "is_weekend": int(target_date.weekday() >= 5),
        "is_heating_season": int(is_heating_season(target_date)),
        "temp_c": weather["temp_c"],
        "wind_ms": weather["wind_ms"],
        "humidity": weather["humidity"],
    }


# Liczy prognozę dla jednego parametru.
def predict_pollutant(
    model,
    feature_columns,
    measurements,
    weather,
    param,
    freshness,
):
    features = build_forecast_features(
        measurements,
        weather,
    )

    missing_features = [
        feature for feature in feature_columns if feature not in features
    ]

    if missing_features:
        raise ValueError(
            "Missing required model features: " + ", ".join(missing_features)
        )

    coverage_quality = get_coverage_quality(measurements)

    # Ustawia kolejność cech zgodną z modelem.
    X = pd.DataFrame([features])[feature_columns]

    prediction = float(model.predict(X)[0])

    return {
        "sensor_id": freshness["sensor_id"],
        "forecast_value": round(
            prediction,
            2,
        ),
        "data_date": freshness["data_date"],
        "data_age_days": freshness["data_age_days"],
        "data_status": freshness["data_status"],
        "warning": freshness["warning"],
        "coverage_7d": (coverage_quality["coverage_7d"]),
        "coverage_status": (coverage_quality["coverage_status"]),
        "coverage_warning": (coverage_quality["coverage_warning"]),
    }


# Tworzy prognozę dla jednej stacji.
def predict_station_tomorrow(
    station_id,
):
    total_start = perf_counter()

    try:
        # Wczytuje model.
        model_start = perf_counter()

        model_bundle = load_model_bundle()

        model_time = perf_counter() - model_start

        model = model_bundle["model"]

        feature_columns = model_bundle["feature_columns"]

        # Pobiera dane z bazy.
        db_start = perf_counter()

        with SessionLocal() as db:
            station = get_station(
                db,
                station_id,
            )

            if station is None:
                raise ValueError("Station not found")

            pm10_freshness = get_latest_sensor_data(
                db,
                station_id,
                "PM10",
            )

            pm25_freshness = get_latest_sensor_data(
                db,
                station_id,
                "PM25",
            )

            pm10_measurements = get_recent_measurements(
                db,
                station_id,
                "PM10",
            )

            pm25_measurements = get_recent_measurements(
                db,
                station_id,
                "PM2.5",
            )

            if len(pm10_measurements) < 7:
                raise ValueError("Not enough historical PM10 data")

            if len(pm25_measurements) < 7:
                raise ValueError("Not enough historical PM2.5 data")

            latitude = station.latitude

            longitude = station.longitude

        db_time = perf_counter() - db_start

        # Pobiera pogodę z bazy lub awaryjnie z Open-Meteo.
        weather_start = perf_counter()

        weather, weather_source = get_weather_for_prediction(
            station_id,
            latitude,
            longitude,
        )

        weather_time = perf_counter() - weather_start

        # Liczy prognozy.
        prediction_start = perf_counter()

        pm10_forecast = predict_pollutant(
            model=model,
            feature_columns=feature_columns,
            measurements=pm10_measurements,
            weather=weather,
            param="PM10",
            freshness=pm10_freshness,
        )

        pm25_forecast = predict_pollutant(
            model=model,
            feature_columns=feature_columns,
            measurements=pm25_measurements,
            weather=weather,
            param="PM25",
            freshness=pm25_freshness,
        )

        prediction_time = perf_counter() - prediction_start

        total_time = perf_counter() - total_start

        print(
            f"[forecast] "
            f"station={station_id} "
            f"model={model_time:.2f}s "
            f"db={db_time:.2f}s "
            f"weather={weather_time:.2f}s "
            f"weather_source={weather_source} "
            f"prediction={prediction_time:.2f}s "
            f"total={total_time:.2f}s"
        )

        return {
            "station_id": station_id,
            "forecast_date": (weather["date"]),
            "pm10": pm10_forecast,
            "pm25": pm25_forecast,
        }

    except httpx.HTTPStatusError as error:
        print(
            f"[forecast-error] "
            f"station={station_id} "
            f"type={type(error).__name__} "
            f"status="
            f"{error.response.status_code}"
        )

        raise

    except httpx.HTTPError as error:
        print(
            f"[forecast-error] "
            f"station={station_id} "
            f"type={type(error).__name__} "
            "status=None"
        )

        raise

    except Exception as error:
        print(
            f"[forecast-error] "
            f"station={station_id} "
            f"type={type(error).__name__} "
            "status=None"
        )

        raise
