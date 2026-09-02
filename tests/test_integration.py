from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from smogcast.storage.models import Base, Measurement, Sensor, Station
from smogcast.storage.upsert import (
    upsert_measurements,
    upsert_metadata,
)


# Sprawdza cały przepływ: zapis metadanych, zapis pomiarów,
# odczyt danych oraz brak duplikatów po ponownym ingestcie.
def test_backend_integration():
    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(bind=engine)

    Base.metadata.create_all(engine)

    db = TestingSessionLocal()

    stations = [
        {
            "id": 1,
            "name": "Test Station",
            "city": "Test City",
            "latitude": 50.0,
            "longitude": 19.0,
        }
    ]

    sensors = [
        {
            "id": 10,
            "station_id": 1,
            "param_code": "PM10",
        }
    ]

    timestamp = datetime(
        2026,
        1,
        10,
        12,
        0,
        tzinfo=timezone.utc,
    )

    measurements = [
        {
            "sensor_id": 10,
            "timestamp": timestamp,
            "value": 25.0,
        }
    ]

    # Pierwszy ingest.
    upsert_metadata(
        db,
        stations,
        sensors,
    )

    upsert_measurements(
        db,
        measurements,
    )

    # Odczyt zapisanych danych.
    stmt = (
        select(
            Station.id,
            Sensor.param_code,
            Measurement.timestamp,
            Measurement.value,
        )
        .join(
            Sensor,
            Sensor.station_id == Station.id,
        )
        .join(
            Measurement,
            Measurement.sensor_id == Sensor.id,
        )
    )

    row = db.execute(stmt).first()

    assert row is not None
    assert row.id == 1
    assert row.param_code == "PM10"
    assert row.value == 25.0

    # Ten sam ingest uruchomiony drugi raz.
    upsert_metadata(
        db,
        stations,
        sensors,
    )

    upsert_measurements(
        db,
        measurements,
    )

    # Liczba rekordów nie powinna się zwiększyć.
    assert db.query(Station).count() == 1
    assert db.query(Sensor).count() == 1
    assert db.query(Measurement).count() == 1

    db.close()
