from datetime import datetime

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from smogcast.storage.models import Base, Measurement, Sensor, Station
from smogcast.storage.upsert import upsert_measurements


def create_test_database(tmp_path):
    database_path = tmp_path / "test_resume.db"

    engine = create_engine(f"sqlite:///{database_path}")

    Base.metadata.create_all(engine)

    session_factory = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )

    return session_factory


def add_test_sensor(db):
    station = Station(
        id=1,
        name="Test station",
        city="Test city",
        latitude=50.0,
        longitude=19.0,
    )

    sensor = Sensor(
        id=100,
        station_id=1,
        param_code="PM10",
    )

    db.add(station)
    db.add(sensor)
    db.commit()


def get_measurement_count(db):
    stmt = select(func.count(Measurement.id))

    return db.scalar(stmt)


# Sprawdza rollback po przerwaniu przed commit.
def test_resume_after_interruption_before_commit(
    tmp_path,
    monkeypatch,
):
    SessionLocal = create_test_database(tmp_path)

    with SessionLocal() as db:
        add_test_sensor(db)

        measurements = [
            {
                "sensor_id": 100,
                "timestamp": datetime(
                    2026,
                    9,
                    20,
                    10,
                    0,
                ),
                "value": 20.0,
            },
            {
                "sensor_id": 100,
                "timestamp": datetime(
                    2026,
                    9,
                    20,
                    11,
                    0,
                ),
                "value": 21.0,
            },
        ]

        def interrupted_commit():
            raise RuntimeError("Symulowane przerwanie zapisu")

        monkeypatch.setattr(
            db,
            "commit",
            interrupted_commit,
        )

        try:
            upsert_measurements(
                db,
                measurements,
            )
        except RuntimeError:
            pass

    # Zamknięcie sesji cofa niezakończoną transakcję.
    with SessionLocal() as db:
        assert get_measurement_count(db) == 0


# Sprawdza ponowne wykonanie po zapisie bez duplikatów.
def test_resume_after_commit_before_step_mark(
    tmp_path,
):
    SessionLocal = create_test_database(tmp_path)

    measurements = [
        {
            "sensor_id": 100,
            "timestamp": datetime(
                2026,
                9,
                20,
                10,
                0,
            ),
            "value": 20.0,
        },
        {
            "sensor_id": 100,
            "timestamp": datetime(
                2026,
                9,
                20,
                11,
                0,
            ),
            "value": 21.0,
        },
    ]

    with SessionLocal() as db:
        add_test_sensor(db)

        # Pierwszy zapis zakończył się,
        # ale etap nie został oznaczony jako ukończony.
        upsert_measurements(
            db,
            measurements,
        )

    with SessionLocal() as db:
        assert get_measurement_count(db) == 2

        # Symuluje ponowne uruchomienie tego samego etapu.
        upsert_measurements(
            db,
            measurements,
        )

    with SessionLocal() as db:
        assert get_measurement_count(db) == 2
