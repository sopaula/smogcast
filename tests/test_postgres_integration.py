from datetime import UTC, date, datetime

from sqlalchemy import select

from smogcast.storage.db import SessionLocal, create_tables, engine
from smogcast.storage.models import InitializationState, Station, WeatherForecast


def test_postgres_connection_and_tables():
    assert engine.dialect.name == "postgresql"

    create_tables()

    with engine.connect() as connection:
        assert connection.closed is False


def test_initialization_state_roundtrip():
    create_tables()

    with SessionLocal() as db:
        state = InitializationState(
            step="integration_test",
            completed_at=datetime.now(UTC),
        )
        db.merge(state)
        db.commit()

    with SessionLocal() as db:
        saved = db.scalar(
            select(InitializationState).where(
                InitializationState.step == "integration_test"
            )
        )

        assert saved is not None
        assert saved.completed_at is not None


def test_weather_forecast_roundtrip():
    create_tables()

    target_date = date(2099, 1, 1)

    with SessionLocal() as db:
        station = Station(
            id=999999,
            name="Test Station",
            city="Test City",
            latitude=50.0,
            longitude=19.0,
        )
        db.merge(station)

        forecast = WeatherForecast(
            station_id=999999,
            target_date=target_date,
            temp_c=10.5,
            humidity=70.0,
            wind_ms=4.2,
            fetched_at=datetime.now(UTC),
        )
        db.merge(forecast)
        db.commit()

    with SessionLocal() as db:
        saved = db.scalar(
            select(WeatherForecast).where(
                WeatherForecast.station_id == 999999,
                WeatherForecast.target_date == target_date,
            )
        )

        assert saved is not None
        assert saved.temp_c == 10.5
        assert saved.humidity == 70.0
        assert saved.wind_ms == 4.2
        assert saved.fetched_at.tzinfo is not None
