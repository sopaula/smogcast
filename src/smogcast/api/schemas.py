from datetime import date, datetime

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class StationResponse(BaseModel):
    id: int
    name: str
    city: str
    latitude: float
    longitude: float

    model_config = {"from_attributes": True}


# Pojedynczy pomiar zwracany przez API.
class MeasurementResponse(BaseModel):
    sensor_id: int
    param: str
    timestamp: datetime
    value: float | None


# Prognoza dla jednego parametru PM.
class PollutantForecastResponse(BaseModel):
    sensor_id: int
    forecast_value: float
    data_date: date
    data_age_days: int
    data_status: str
    warning: str | None
    coverage_7d: float
    coverage_status: str
    coverage_warning: str | None


# Odpowiedź endpointu prognozy dla jednej stacji.
class ForecastResponse(BaseModel):
    station_id: int
    forecast_date: date

    pm10: PollutantForecastResponse
    pm25: PollutantForecastResponse


# Odpowiedź endpointu statusu odświeżania danych.
class StatusResponse(BaseModel):
    last_successful_refresh: datetime | None
