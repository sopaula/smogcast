from datetime import date, timedelta
from pathlib import Path

import joblib
import pandas as pd
from sqlalchemy import select

from smogcast.ingest.current import (
    refresh_recent_measurements,
)
from smogcast.ingest.weather import (
    get_tomorrow_weather,
)
from smogcast.processing.daily import (
    aggregate_daily_measurements_for_sensors,
)
from smogcast.processing.seasons import (
    is_heating_season,
)
from smogcast.storage.db import SessionLocal
from smogcast.storage.models import (
    DailyMeasurement,
    Station,
)


MODEL_PATH = Path("models/model_v2.joblib")


# Progi używane do ustawienia
# flagi alarmu dla prognozy
ALARM_THRESHOLDS = {
    "PM10": 50.0,
    "PM25": 25.0,
}


# Zamienia parametr używany w API
# na kod zapisany w bazie
#
# W API używamy PM25,
# a w bazie parametr jest zapisany
# jako PM2.5
def map_param(
    param,
):
    if param == "PM25":
        return "PM2.5"

    return param


# Pobiera z bazy informacje
# o jednej stacji
def get_station(
    db,
    station_id,
):
    return db.get(
        Station,
        station_id,
    )


# Pobiera 7 ostatnich
# dobowych pomiarów PM
#
# Są potrzebne do policzenia:
# - lag 1 dzień
# - średniej 3-dniowej
# - średniej 7-dniowej
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
        )
        .order_by(DailyMeasurement.date.desc())
        .limit(7)
    )

    measurements = list(db.scalars(stmt))

    return measurements


# Buduje jeden rekord cech
# dla prognozy na jutro
#
# Cechy mają dokładnie taki sam
# układ jak podczas treningu modelu
def build_forecast_features(
    measurements,
    weather,
):
    if len(measurements) < 7:
        raise ValueError("Not enough historical measurements")

    values = [measurement.mean_value for measurement in measurements]

    tomorrow = date.today() + timedelta(days=1)

    features = {
        "pm_lag_1d": values[0],
        "pm_mean_3d": (sum(values[:3]) / 3),
        "pm_mean_7d": (sum(values[:7]) / 7),
        "month": tomorrow.month,
        "day_of_week": (tomorrow.weekday()),
        "is_weekend": int(tomorrow.weekday() >= 5),
        "is_heating_season": int(is_heating_season(tomorrow)),
        "temp_c": weather["temp_c"],
        "wind_ms": weather["wind_ms"],
        "humidity": weather["humidity"],
    }

    return features


# Wykonuje prognozę
# dla jednego parametru
#
# Model jest ten sam,
# ale historia PM jest osobna
# dla PM10 i PM2.5
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

    X = pd.DataFrame([features])[feature_columns]

    prediction = float(model.predict(X)[0])

    threshold = ALARM_THRESHOLDS[param]

    alarm = prediction > threshold

    return {
        "forecast_value": round(
            prediction,
            2,
        ),
        "threshold": threshold,
        "alarm": alarm,
        "data_date": freshness["data_date"],
        "data_age_days": freshness["data_age_days"],
        "data_status": freshness["data_status"],
        "warning": freshness["warning"],
    }


# Wykonuje prognozę jakości
# powietrza dla jednej stacji
#
# Zwraca jednocześnie:
# - forecast PM10
# - forecast PM2.5
# - flagę alarmu dla obu
# - informację o świeżości danych
#
# Pogoda na jutro jest używana
# tylko jako wejście modelu
def predict_station_tomorrow(
    station_id,
):
    # Wczytuje zapisany model
    model_bundle = joblib.load(MODEL_PATH)

    model = model_bundle["model"]

    feature_columns = model_bundle["feature_columns"]

    # Aktualizuje PM10
    # i wybiera najlepszy sensor PM10
    pm10_freshness = refresh_recent_measurements(
        station_id,
        "PM10",
    )

    # Aktualizuje PM2.5
    # i wybiera najlepszy sensor PM2.5
    pm25_freshness = refresh_recent_measurements(
        station_id,
        "PM25",
    )

    # Pobiera ID sensorów,
    # które zostały wybrane
    pm10_sensor_id = pm10_freshness["sensor_id"]

    pm25_sensor_id = pm25_freshness["sensor_id"]

    # Przelicza daily_measurements
    # tylko dla wybranych sensorów
    aggregate_daily_measurements_for_sensors(
        [
            pm10_sensor_id,
            pm25_sensor_id,
        ]
    )

    with SessionLocal() as db:
        station = get_station(
            db,
            station_id,
        )

        if station is None:
            raise ValueError("Station not found")

        # Pobiera historię PM10
        pm10_measurements = get_recent_measurements(
            db,
            station_id,
            "PM10",
        )

        # Pobiera historię PM2.5
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
        # Pogoda jest używana tylko
        # jako wejście do modelu.
        weather = get_tomorrow_weather(
            station.latitude,
            station.longitude,
        )

        if weather is None:
            raise ValueError("Weather forecast unavailable")

    # Prognoza PM10
    pm10_forecast = predict_pollutant(
        model=model,
        feature_columns=feature_columns,
        measurements=pm10_measurements,
        weather=weather,
        param="PM10",
        freshness=pm10_freshness,
    )

    # Prognoza PM2.5
    pm25_forecast = predict_pollutant(
        model=model,
        feature_columns=feature_columns,
        measurements=pm25_measurements,
        weather=weather,
        param="PM25",
        freshness=pm25_freshness,
    )

    # Użytkownik dostaje
    # obie prognozy w jednej odpowiedzi.
    # Pogody nie zwracamy w API.
    return {
        "station_id": station_id,
        "forecast_date": weather["date"],
        "pm10": pm10_forecast,
        "pm25": pm25_forecast,
    }
