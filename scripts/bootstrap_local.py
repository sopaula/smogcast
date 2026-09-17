from pathlib import Path

from smogcast.ingest.metadata import ingest_metadata
from smogcast.ingest.timeseries import ingest_timeseries
from smogcast.processing.daily import aggregate_daily_measurements
from smogcast.storage.db import create_tables


DATABASE_PATH = Path("smogcast.db")


def main():
    # Jeśli baza już istnieje,
    # nie budujemy jej ponownie.
    if DATABASE_PATH.exists():
        print("Database already exists.")
        print("Skipping database bootstrap.")
        return

    print("Creating database tables...")
    create_tables()

    print("Ingesting station and sensor metadata...")
    ingest_metadata()

    print("Ingesting historical measurements and weather...")
    ingest_timeseries()

    print("Calculating daily measurements...")
    aggregate_daily_measurements()

    print("Database bootstrap finished.")


if __name__ == "__main__":
    main()
