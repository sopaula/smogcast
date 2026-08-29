from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class StationResponse(BaseModel):
    id: int
    name: str
    city: str
    latitude: float
    longitude: float

    model_config = {
        "from_attributes": True,
    }
