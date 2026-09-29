from datetime import datetime, timezone

from smogcast.ingest.metadata import ingest_metadata
from smogcast.ingest.timeseries import (
    ingest_measurements,
    ingest_weather,
)
from smogcast.processing.daily import aggregate_daily_measurements
from smogcast.storage.db import SessionLocal, create_tables
from smogcast.storage.models import InitializationState


# Sprawdza, czy etap inicjalizacji został ukończony.
def is_step_completed(step):
    with SessionLocal() as db:
        return db.get(InitializationState, step) is not None


# Zapisuje ukończony etap inicjalizacji.
def mark_step_completed(step):
    with SessionLocal() as db:
        db.add(
            InitializationState(
                step=step,
                completed_at=datetime.now(timezone.utc),
            )
        )

        db.commit()


# Uruchamia etap tylko wtedy, gdy nie został wcześniej ukończony.
def run_step(
    step,
    message,
    function,
):
    if is_step_completed(step):
        print(f"{message} - pominięto, etap już ukończony.")
        return

    print(message)

    function()

    mark_step_completed(step)

    print(f"Etap '{step}' zakończony.")


# Przygotowuje bazę przy pierwszym uruchomieniu.
def init_database():
    print("Tworzenie tabel...")
    create_tables()

    run_step(
        step="metadata",
        message="\nPobieranie metadanych...",
        function=ingest_metadata,
    )

    run_step(
        step="measurements",
        message="\nImport historycznych pomiarów PM...",
        function=ingest_measurements,
    )

    run_step(
        step="weather",
        message="\nImport historycznych danych pogodowych...",
        function=ingest_weather,
    )

    run_step(
        step="daily",
        message="\nTworzenie agregatów dobowych...",
        function=aggregate_daily_measurements,
    )

    print("\nInicjalizacja bazy zakończona.")


if __name__ == "__main__":
    init_database()
