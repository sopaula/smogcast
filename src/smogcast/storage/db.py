from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from smogcast.storage.models import Base


DATABASE_URL = "sqlite:///smogcast.db"


# Tworzy silnik odpowiedzialny za połączenie z bazą danych.
engine = create_engine(
    DATABASE_URL,
)


# Fabryka sesji używanych do komunikacji z bazą danych.
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


# Tworzy wszystkie tabele zdefiniowane w models.py.
def create_tables():
    Base.metadata.create_all(engine)
