import pandas as pd

from smogcast.processing.features import build_features


# Sprawdza poprawność lagów i średnich kroczących
# oraz upewnia się, że cechy nie korzystają z przyszłych wartości PM.
def test_build_features_uses_only_past_pm_values():
    daily_measurements = pd.DataFrame(
        [
            {
                "station_id": 1,
                "param_code": "PM10",
                "date": "2026-01-01",
                "mean_value": 10.0,
                "max_value": 12.0,
                "coverage": 100.0,
            },
            {
                "station_id": 1,
                "param_code": "PM10",
                "date": "2026-01-02",
                "mean_value": 20.0,
                "max_value": 22.0,
                "coverage": 100.0,
            },
            {
                "station_id": 1,
                "param_code": "PM10",
                "date": "2026-01-03",
                "mean_value": 30.0,
                "max_value": 32.0,
                "coverage": 100.0,
            },
            {
                "station_id": 1,
                "param_code": "PM10",
                "date": "2026-01-04",
                "mean_value": 100.0,
                "max_value": 105.0,
                "coverage": 100.0,
            },
        ]
    )

    daily_weather = pd.DataFrame(
        [
            {
                "station_id": 1,
                "date": "2026-01-04",
                "temp_c": 2.0,
                "wind_ms": 3.0,
                "humidity": 80.0,
                "pressure_hpa": None,
                "precip_mm": None,
            }
        ]
    )

    result = build_features(
        daily_measurements,
        daily_weather,
    )

    row = result[result["date"] == pd.Timestamp("2026-01-04")].iloc[0]

    assert row["pm_lag_1d"] == 30.0

    assert row["pm_mean_3d"] == 20.0

    assert row["target_value"] == 100.0

    assert row["month"] == 1
    assert row["day_of_week"] == 6
    assert bool(row["is_weekend"]) is True
    assert bool(row["is_heating_season"]) is True

    assert row["temp_c"] == 2.0
