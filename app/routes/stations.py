from fastapi import APIRouter, HTTPException
from app.services import github_data
from app.models.schemas import GaugingStation, StationWithLevel, WaterLevelReading

router = APIRouter()


@router.get("", response_model=list[GaugingStation])
async def list_stations():
    """Get all gauging stations with their metadata and threshold levels."""
    stations = await github_data.get_gauging_stations()
    return [
        GaugingStation(
            name=s["name"],
            river_name=s["river_name"],
            lat_lng=s["lat_lng"],
            alert_level=s["alert_level"],
            minor_flood_level=s["minor_flood_level"],
            major_flood_level=s["major_flood_level"],
        )
        for s in stations
    ]


@router.get("/{name}", response_model=StationWithLevel)
async def get_station(name: str):
    """Get a specific station by name with its latest water level reading."""
    station = await github_data.get_station_by_name(name)
    if not station:
        raise HTTPException(status_code=404, detail=f"Station '{name}' not found")

    levels = await github_data.get_latest_water_levels()
    latest_reading = None

    for level in levels:
        if level.get("gauging_station_name", "").lower() == name.lower():
            water_level = level.get("current_water_level")
            alert_status = github_data.calculate_alert_status(water_level, station)
            flood_score = github_data.calculate_flood_score(water_level, station)

            latest_reading = WaterLevelReading(
                station_name=name,
                river_name=station["river_name"],
                water_level=water_level,
                previous_water_level=level.get("previous_water_level"),
                alert_status=alert_status,
                flood_score=flood_score,
                rising_or_falling=level.get("rising_or_falling"),
                rainfall_mm=level.get("rainfall_mm"),
                remarks=level.get("remarks"),
                timestamp=level.get("time_str", ""),
            )
            break

    return StationWithLevel(
        station=GaugingStation(
            name=station["name"],
            river_name=station["river_name"],
            lat_lng=station["lat_lng"],
            alert_level=station["alert_level"],
            minor_flood_level=station["minor_flood_level"],
            major_flood_level=station["major_flood_level"],
        ),
        latest_reading=latest_reading,
    )
