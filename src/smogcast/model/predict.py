from datetime import date, timedelta
from pathlib import Path

import joblib
import pandas as pd
from sqlalchemy import select

from smogcast.ingest.weather import get_tomorrow_weather
from smogcast.processing.seasons import is_heating_season
from smogcast.storage.db import SessionLocal
from smogcast.storage.models import DailyMeasurement, Station


MODEL_PATH = Path("models/model_v2.joblib")


ALARM_THRESHOLDS = {
    "PM10": 50.0,
    "PM25": 25.0,
}


# Zamienia parametr używany w API na kod zapisany w bazie
# W API używamy PM25, a w bazie parametr jest zapisany jako PM2.5
def map_param(param):
    if param == "PM25":
        return "PM2.5"

    return param


# Pobiera z bazy informacje o jednej stacji
def get_station(db, station_id):
    return db.get(Station, station_id)


# Pobiera 7 ostatnich dobowych pomiarów PM
# Są potrzebne do policzenia lagów i średnich kroczących
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


# Buduje jeden rekord cech dla prognozy na jutro
# Cechy mają dokładnie taki sam układ jak podczas treningu modelu
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
        "pm_mean_3d": sum(values[:3]) / 3,
        "pm_mean_7d": sum(values[:7]) / 7,
        "month": tomorrow.month,
        "day_of_week": tomorrow.weekday(),
        "is_weekend": int(tomorrow.weekday() >= 5),
        "is_heating_season": int(is_heating_season(tomorrow)),
        "temp_c": weather["temp_c"],
        "wind_ms": weather["wind_ms"],
        "humidity": weather["humidity"],
    }

    return features


# Wczytuje zapisany model i wykonuje prognozę na jutro
# Pobiera historię PM z bazy oraz prognozę pogody z Open-Meteo
# Sprawdza, czy prognozowana wartość przekracza ustalony próg i ustawia flagę alarmu dla odpowiedzi API
def predict_tomorrow(
    station_id,
    param,
):
    param_code = map_param(param)

    model_bundle = joblib.load(MODEL_PATH)

    model = model_bundle["model"]

    feature_columns = model_bundle["feature_columns"]

    with SessionLocal() as db:
        station = get_station(
            db,
            station_id,
        )

        if station is None:
            raise ValueError("Station not found")

        measurements = get_recent_measurements(
            db,
            station_id,
            param_code,
        )

        if len(measurements) < 7:
            raise ValueError("Not enough historical data")

        weather = get_tomorrow_weather(
            station.latitude,
            station.longitude,
        )

        if weather is None:
            raise ValueError("Weather forecast unavailable")

    features = build_forecast_features(
        measurements,
        weather,
    )

    X = pd.DataFrame([features])[feature_columns]

    prediction = float(model.predict(X)[0])

    threshold = ALARM_THRESHOLDS[param]

    alarm = prediction > threshold

    return {
        "station_id": station_id,
        "param": param,
        "forecast_date": weather["date"],
        "forecast_value": round(
            prediction,
            2,
        ),
        "threshold": threshold,
        "alarm": alarm,
    }
