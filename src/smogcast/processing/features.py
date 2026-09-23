import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from smogcast.processing.seasons import is_heating_season
from smogcast.storage.db import SessionLocal
from smogcast.storage.models import DailyMeasurement, Weather


# Pobiera agregaty dobowe PM z bazy danych
def get_daily_measurements(
    db: Session,
) -> pd.DataFrame:
    stmt = select(
        DailyMeasurement.station_id,
        DailyMeasurement.param_code,
        DailyMeasurement.date,
        DailyMeasurement.mean_value,
        DailyMeasurement.max_value,
        DailyMeasurement.coverage,
    )

    rows = db.execute(stmt).all()

    return pd.DataFrame(
        rows,
        columns=[
            "station_id",
            "param_code",
            "date",
            "mean_value",
            "max_value",
            "coverage",
        ],
    )


# Pobiera godzinowe dane pogodowe z bazy danych
def get_weather(
    db: Session,
) -> pd.DataFrame:
    stmt = select(
        Weather.station_id,
        Weather.timestamp,
        Weather.temp_c,
        Weather.wind_ms,
        Weather.humidity,
        Weather.pressure_hpa,
        Weather.precip_mm,
    )

    rows = db.execute(stmt).all()

    return pd.DataFrame(
        rows,
        columns=[
            "station_id",
            "timestamp",
            "temp_c",
            "wind_ms",
            "humidity",
            "pressure_hpa",
            "precip_mm",
        ],
    )


# Agreguje godzinowe dane pogodowe do jednego rekordu na stację i dzień
def aggregate_daily_weather(
    weather: pd.DataFrame,
) -> pd.DataFrame:
    data = weather.copy()

    data["timestamp"] = pd.to_datetime(data["timestamp"])
    data["date"] = data["timestamp"].dt.date

    daily_weather = data.groupby(
        ["station_id", "date"],
        as_index=False,
    ).agg(
        temp_c=("temp_c", "mean"),
        wind_ms=("wind_ms", "mean"),
        humidity=("humidity", "mean"),
        pressure_hpa=("pressure_hpa", "mean"),
        precip_mm=("precip_mm", "sum"),
    )

    return daily_weather


# Buduje cechy modelowe na podstawie agregatów PM i pogody
def build_features(
    daily_measurements: pd.DataFrame,
    daily_weather: pd.DataFrame,
) -> pd.DataFrame:
    data = daily_measurements.copy()

    data["date"] = pd.to_datetime(data["date"])

    data = data.sort_values(["station_id", "param_code", "date"]).reset_index(drop=True)

    groups = data.groupby(["station_id", "param_code"])["mean_value"]

    coverage_groups = data.groupby(["station_id", "param_code"])["coverage"]

    # PM z poprzedniego dnia.
    data["pm_lag_1d"] = groups.shift(1)

    # Średnia z 3 poprzednich dni.
    data["pm_mean_3d"] = groups.transform(
        lambda values: values.shift(1).rolling(3).mean()
    )

    # Średnia z 7 poprzednich dni.
    data["pm_mean_7d"] = groups.transform(
        lambda values: values.shift(1).rolling(7).mean()
    )

    # Pokrycie danych z poprzedniego dnia.
    data["coverage_lag_1d"] = coverage_groups.shift(1)

    # Średnie pokrycie z 3 poprzednich dni.
    data["coverage_mean_3d"] = coverage_groups.transform(
        lambda values: values.shift(1).rolling(3).mean()
    )

    # Średnie pokrycie z 7 poprzednich dni.
    data["coverage_mean_7d"] = coverage_groups.transform(
        lambda values: values.shift(1).rolling(7).mean()
    )

    # Cechy kalendarzowe dnia, który chcemy przewidzieć.
    data["month"] = data["date"].dt.month
    data["day_of_week"] = data["date"].dt.dayofweek
    data["is_weekend"] = data["day_of_week"] >= 5

    data["is_heating_season"] = data["month"].apply(is_heating_season)

    # Wartość, którą model będzie przewidywał.
    data["target_value"] = data["mean_value"]

    weather = daily_weather.copy()
    weather["date"] = pd.to_datetime(weather["date"])

    # Dodaje pogodę dla dnia docelowego.
    features = data.merge(
        weather,
        on=["station_id", "date"],
        how="left",
    )

    return features


# Pobiera dane z bazy i buduje gotową tabelę cech
def build_features_from_db() -> pd.DataFrame:
    db = SessionLocal()

    try:
        daily_measurements = get_daily_measurements(db)
        weather = get_weather(db)

        daily_weather = aggregate_daily_weather(weather)

        features = build_features(
            daily_measurements,
            daily_weather,
        )

        return features

    finally:
        db.close()


if __name__ == "__main__":
    features = build_features_from_db()

    print(features.head())
    print()
    print(f"Features created: {len(features)}")
