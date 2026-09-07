from datetime import datetime, date

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


# Określa strukturę odpowiedzi endpointu prognozy
class ForecastResponse(BaseModel):
    station_id: int
    param: str
    forecast_date: date
    forecast_value: float
    threshold: float
    alarm: bool
