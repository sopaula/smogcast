import pandas as pd

from smogcast.processing.daily import calculate_daily_measurements


# Sprawdza poprawność średniej, maksimum i coverage
# na małym ręcznie policzonym przykładzie.
def test_calculate_daily_measurements():
    df = pd.DataFrame(
        [
            {
                "station_id": 1,
                "param_code": "PM10",
                "timestamp": "2026-01-10 00:00",
                "value": 10.0,
            },
            {
                "station_id": 1,
                "param_code": "PM10",
                "timestamp": "2026-01-10 01:00",
                "value": 20.0,
            },
            {
                "station_id": 1,
                "param_code": "PM10",
                "timestamp": "2026-01-10 02:00",
                "value": None,
            },
            {
                "station_id": 1,
                "param_code": "PM10",
                "timestamp": "2026-01-10 03:00",
                "value": 30.0,
            },
        ]
    )

    result = calculate_daily_measurements(df)

    row = result.iloc[0]

    assert row["mean_value"] == 20.0
    assert row["max_value"] == 30.0
    assert row["coverage"] == 12.5
