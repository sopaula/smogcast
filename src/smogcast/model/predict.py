from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

import joblib
import pandas as pd
from sqlalchemy import select

from smogcast.ingest.current import get_data_freshness
from smogcast.ingest.weather import get_tomorrow_weather
from smogcast.processing.seasons import is_heating_season
from smogcast.storage.db import SessionLocal
from smogcast.storage.models import (
    DailyMeasurement,
    Measurement,
    Sensor,
    Station,
)


MODEL_PATH = Path("models/model_v2.joblib")


ALARM_THRESHOLDS = {
    "PM10": 50.0,
    "PM25": 25.0,
}


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


# Określa jakość danych na podstawie coverage.
def get_coverage_quality(
    measurements,
):
    coverages = [measurement.coverage for measurement in measurements[:7]]

    coverage_7d = sum(coverages) / len(coverages)

    if coverage_7d >= 75:
        return {
            "coverage_7d": round(coverage_7d, 2),
            "coverage_status": "good",
            "coverage_warning": None,
        }

    if coverage_7d >= 50:
        return {
            "coverage_7d": round(coverage_7d, 2),
            "coverage_status": "warning",
            "coverage_warning": (
                "Prognoza została przygotowana na podstawie "
                "niepełnych danych z ostatnich dni."
            ),
        }

    return {
        "coverage_7d": round(coverage_7d, 2),
        "coverage_status": "critical",
        "coverage_warning": (
            "Prognoza została przygotowana na podstawie bardzo "
            "ograniczonej liczby pomiarów i może być mniej wiarygodna."
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

    tomorrow = date.today() + timedelta(days=1)

    return {
        "pm_lag_1d": values[0],
        "pm_mean_3d": sum(values[:3]) / 3,
        "pm_mean_7d": sum(values[:7]) / 7,
        "coverage_lag_1d": coverages[0],
        "coverage_mean_3d": sum(coverages[:3]) / 3,
        "coverage_mean_7d": sum(coverages[:7]) / 7,
        "month": tomorrow.month,
        "day_of_week": tomorrow.weekday(),
        "is_weekend": int(tomorrow.weekday() >= 5),
        "is_heating_season": int(is_heating_season(tomorrow)),
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

    coverage_quality = get_coverage_quality(
        measurements,
    )

    # Ustawia kolejność cech zgodną z modelem.
    X = pd.DataFrame([features])[feature_columns]

    prediction = float(model.predict(X)[0])

    threshold = ALARM_THRESHOLDS[param]

    return {
        "sensor_id": freshness["sensor_id"],
        "forecast_value": round(
            prediction,
            2,
        ),
        "threshold": threshold,
        "alarm": prediction > threshold,
        "data_date": freshness["data_date"],
        "data_age_days": freshness["data_age_days"],
        "data_status": freshness["data_status"],
        "warning": freshness["warning"],
        "coverage_7d": coverage_quality["coverage_7d"],
        "coverage_status": coverage_quality["coverage_status"],
        "coverage_warning": coverage_quality["coverage_warning"],
    }


# Tworzy prognozę dla jednej stacji.
def predict_station_tomorrow(
    station_id,
):
    # Wczytuje model.
    model_bundle = load_model_bundle()

    model = model_bundle["model"]

    feature_columns = model_bundle["feature_columns"]

    with SessionLocal() as db:
        # Pobiera stację.
        station = get_station(
            db,
            station_id,
        )

        if station is None:
            raise ValueError("Station not found")

        # Pobiera najnowsze dane PM10.
        pm10_freshness = get_latest_sensor_data(
            db,
            station_id,
            "PM10",
        )

        # Pobiera najnowsze dane PM2.5.
        pm25_freshness = get_latest_sensor_data(
            db,
            station_id,
            "PM25",
        )

        # Pobiera historię dobową PM10.
        pm10_measurements = get_recent_measurements(
            db,
            station_id,
            "PM10",
        )

        # Pobiera historię dobową PM2.5.
        pm25_measurements = get_recent_measurements(
            db,
            station_id,
            "PM2.5",
        )

        if len(pm10_measurements) < 7:
            raise ValueError("Not enough historical PM10 data")

        if len(pm25_measurements) < 7:
            raise ValueError("Not enough historical PM2.5 data")

        # Pobiera pogodę na jutro.
        weather = get_tomorrow_weather(
            station.latitude,
            station.longitude,
        )

        if weather is None:
            raise ValueError("Weather forecast unavailable")

    # Liczy prognozę PM10.
    pm10_forecast = predict_pollutant(
        model=model,
        feature_columns=feature_columns,
        measurements=pm10_measurements,
        weather=weather,
        param="PM10",
        freshness=pm10_freshness,
    )

    # Liczy prognozę PM2.5.
    pm25_forecast = predict_pollutant(
        model=model,
        feature_columns=feature_columns,
        measurements=pm25_measurements,
        weather=weather,
        param="PM25",
        freshness=pm25_freshness,
    )

    return {
        "station_id": station_id,
        "forecast_date": weather["date"],
        "pm10": pm10_forecast,
        "pm25": pm25_forecast,
    }
