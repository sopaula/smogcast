from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from smogcast.storage.models import Base, Measurement, Sensor, Station
from smogcast.storage.upsert import upsert_measurements, upsert_metadata


# Sprawdza, czy ponowny zapis tych samych stacji i sensorów
# nie tworzy duplikatów w bazie danych
def test_upsert_metadata_is_idempotent():
    engine = create_engine(
        "sqlite:///:memory:",
    )

    TestingSessionLocal = sessionmaker(
        bind=engine,
    )

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

    upsert_metadata(
        db,
        stations,
        sensors,
    )

    station_count_first = db.query(Station).count()
    sensor_count_first = db.query(Sensor).count()

    upsert_metadata(
        db,
        stations,
        sensors,
    )

    station_count_second = db.query(Station).count()
    sensor_count_second = db.query(Sensor).count()

    assert station_count_first == 1
    assert sensor_count_first == 1

    assert station_count_second == 1
    assert sensor_count_second == 1

    db.close()


# Sprawdza, czy ponowny zapis pomiaru dla tego samego sensora i czasu
# nie tworzy duplikatu i aktualizuje wartość pomiaru
def test_measurement_upsert_is_idempotent():
    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(bind=engine)

    Base.metadata.create_all(engine)

    db = TestingSessionLocal()

    station = Station(
        id=1,
        name="Test Station",
        city="Test City",
        latitude=50.0,
        longitude=19.0,
    )

    sensor = Sensor(
        id=10,
        station_id=1,
        param_code="PM10",
    )

    db.add(station)
    db.add(sensor)
    db.commit()

    timestamp = datetime(
        2026,
        1,
        10,
        12,
        0,
        tzinfo=timezone.utc,
    )

    first_measurement = [
        {
            "sensor_id": 10,
            "timestamp": timestamp,
            "value": 20.0,
        }
    ]

    upsert_measurements(db, first_measurement)

    assert db.query(Measurement).count() == 1

    second_measurement = [
        {
            "sensor_id": 10,
            "timestamp": timestamp,
            "value": 25.0,
        }
    ]

    upsert_measurements(db, second_measurement)

    assert db.query(Measurement).count() == 1

    measurement = db.query(Measurement).first()

    assert measurement.value == 25.0

    db.close()
