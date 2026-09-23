from smogcast.ingest.metadata import ingest_metadata
from smogcast.ingest.timeseries import ingest_timeseries
from smogcast.processing.daily import aggregate_daily_measurements
from smogcast.storage.db import create_tables


# Przygotowuje bazę przy pierwszym uruchomieniu.
def init_database():
    print("Tworzenie tabel...")
    create_tables()

    print("\nPobieranie metadanych...")
    ingest_metadata()

    print("\nImport danych historycznych...")
    ingest_timeseries()

    print("\nTworzenie agregatów dobowych...")
    aggregate_daily_measurements()

    print("\nInicjalizacja bazy zakończona.")


if __name__ == "__main__":
    init_database()
