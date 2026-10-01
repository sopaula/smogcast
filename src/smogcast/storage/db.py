import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from smogcast.storage.models import Base


load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///smogcast.db",
)


# Tworzy silnik odpowiedzialny za połączenie z bazą danych.
engine = create_engine(
    DATABASE_URL,
)


# Ustawia stabilniejszą pracę SQLite przy wielu procesach.
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if engine.dialect.name != "sqlite":
        return

    cursor = dbapi_connection.cursor()

    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA busy_timeout=5000;")

    cursor.close()


# Fabryka sesji używanych do komunikacji z bazą danych.
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


# Tworzy wszystkie tabele zdefiniowane w models.py.
def create_tables():
    Base.metadata.create_all(engine)
