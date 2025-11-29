from pydantic import BaseModel
from enum import Enum


class AlertLevel(str, Enum):
    MAJOR = "MAJOR"
    MINOR = "MINOR"
    ALERT = "ALERT"
    NORMAL = "NORMAL"
    NO_DATA = "NO_DATA"


class Location(BaseModel):
    lat: float
    lng: float


class RiverBasin(BaseModel):
    name: str
    code: str


class River(BaseModel):
    name: str
    river_basin_name: str
    location_names: list[str]


class GaugingStation(BaseModel):
    name: str
    river_name: str
    lat_lng: list[float]
    alert_level: float
    minor_flood_level: float
    major_flood_level: float


class WaterLevelReading(BaseModel):
    station_name: str
    river_name: str
    water_level: float | None
    previous_water_level: float | None
    alert_status: AlertLevel
    flood_score: float | None
    rising_or_falling: str | None
    rainfall_mm: float | None
    remarks: str | None
    timestamp: str


class StationWithLevel(BaseModel):
    station: GaugingStation
    latest_reading: WaterLevelReading | None


class AlertSummary(BaseModel):
    alert_level: AlertLevel
    count: int
    stations: list[str]
