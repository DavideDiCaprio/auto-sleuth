from pydantic import BaseModel
from typing import Optional, Dict


class FuelPrices(BaseModel):
    gasoline: float = 0.0
    diesel: float = 0.0
    gpl: float = 0.0
    methane: float = 0.0


class NearbyPricesResponse(BaseModel):
    gasoline: float
    diesel: float
    gpl: float
    methane: float
    station_count: int
    currency: str = "EUR"
    source: str


class RegionalAverageResponse(BaseModel):
    region: str
    station_count: int
    prices: FuelPrices


class NationalAverageResponse(BaseModel):
    country: str
    station_count: int
    prices: FuelPrices


class LocationInfo(BaseModel):
    city: str
    region: str
    regionName: str
    country: str
    countryCode: str
    lat: str
    lon: str


class FuelPriceResponse(BaseModel):
    location: LocationInfo
    fuel_price: NearbyPricesResponse
    price_data: Dict[str, Optional[NearbyPricesResponse | RegionalAverageResponse | NationalAverageResponse]]
