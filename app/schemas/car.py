from pydantic import BaseModel, Field
from typing import Optional


class CarQuery(BaseModel):
    """Input schema for the car agent endpoint."""
    query: str = Field(
        ...,
        description="Car description to search for, e.g. 'Fiat Panda 2019 1.2'",
        min_length=2,
        max_length=100,
    )


class CarInfo(BaseModel):
    """Structured car information returned by the AI agent.
    This is the output_type for the PydanticAI agent.
    """
    make: str = Field(description="Car manufacturer, e.g. 'Fiat'")
    model: str = Field(description="Car model name, e.g. 'Panda'")
    year: int = Field(description="Model year, e.g. 2019")
    trim: Optional[str] = Field(default=None, description="Trim level or variant, e.g. 'Pop' or 'Lounge'")
    fuel_type: Optional[str] = Field(default=None, description="Fuel type: 'Gasoline', 'Diesel', 'Hybrid', 'Electric', 'GPL', 'Methane'")
    engine: Optional[str] = Field(default=None, description="Engine specification, e.g. '1.2 69hp' or '1.0 FireFly 70hp'")
    consumption_l_100km: Optional[float] = Field(default=None, description="Average fuel consumption in liters per 100km")
    consumption_mpg: Optional[float] = Field(default=None, description="Average fuel consumption in miles per gallon")


class CarResponse(BaseModel):
    """API response wrapping car info with metadata."""
    car: CarInfo
    source: str = Field(description="Where the data came from: 'database' or 'agent'")
