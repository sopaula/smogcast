from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


# Bazowa klasa dla wszystkich modeli SQLAlchemy.
class Base(DeclarativeBase):
    pass


# Stacje pomiarowe GIOŚ.
class Station(Base):
    __tablename__ = "stations"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    name: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    city: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    latitude: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    longitude: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )


# Sensory znajdujące się na stacjach.
class Sensor(Base):
    __tablename__ = "sensors"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    station_id: Mapped[int] = mapped_column(
        ForeignKey("stations.id"),
        nullable=False,
    )

    param_code: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="active",
    )

    last_backfill_attempt: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


# Surowe pomiary PM10 i PM2.5.
class Measurement(Base):
    __tablename__ = "measurements"

    __table_args__ = (
        UniqueConstraint(
            "sensor_id",
            "timestamp",
            name="uq_measurements_sensor_timestamp",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    sensor_id: Mapped[int] = mapped_column(
        ForeignKey("sensors.id"),
        nullable=False,
    )

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    value: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )


# Dane pogodowe dla lokalizacji stacji.
class Weather(Base):
    __tablename__ = "weather"

    __table_args__ = (
        UniqueConstraint(
            "station_id",
            "timestamp",
            name="uq_weather_station_timestamp",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    station_id: Mapped[int] = mapped_column(
        ForeignKey("stations.id"),
        nullable=False,
    )

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    temp_c: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    wind_ms: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    humidity: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    pressure_hpa: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    precip_mm: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )


# Dobowe agregaty pomiarów PM.
class DailyMeasurement(Base):
    __tablename__ = "daily_measurements"

    station_id: Mapped[int] = mapped_column(
        ForeignKey("stations.id"),
        primary_key=True,
    )

    param_code: Mapped[str] = mapped_column(
        String,
        primary_key=True,
    )

    date: Mapped[date] = mapped_column(
        Date,
        primary_key=True,
    )

    mean_value: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    max_value: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    coverage: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )


# Prognozy wygenerowane przez model.
class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    station_id: Mapped[int] = mapped_column(
        ForeignKey("stations.id"),
        nullable=False,
    )

    param_code: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    target_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    predicted_value: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    model_version: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )


# Zapisuje ukończone etapy inicjalizacji bazy.
class InitializationState(Base):
    __tablename__ = "initialization_state"

    step: Mapped[str] = mapped_column(
        String,
        primary_key=True,
    )

    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
