from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from app.services import github_data
from app.models.schemas import WaterLevelReading
import httpx

router = APIRouter()


@router.get("/latest", response_model=list[WaterLevelReading])
async def get_latest_levels():
    """Get the latest water level readings for all stations."""
    levels = await github_data.get_latest_water_levels()

    # Data is already in the correct format from github_data
    readings = [
        WaterLevelReading(
            station_name=level["station_name"],
            river_name=level["river_name"],
            water_level=level.get("water_level"),
            previous_water_level=level.get("previous_water_level"),
            alert_status=level["alert_status"],
            flood_score=level.get("flood_score"),
            rising_or_falling=level.get("rising_or_falling"),
            rainfall_mm=level.get("rainfall_mm"),
            remarks=level.get("remarks"),
            timestamp=level.get("timestamp", ""),
        )
        for level in levels
    ]

    return readings


@router.get("/history/{station_name}")
async def get_station_history(station_name: str, limit: int = 200):
    """Get historical water level readings for a specific station.

    Returns up to 8 days of historical data with readings every ~1 hour.
    Data is sorted oldest to newest for charting purposes.
    """
    # Get history from irrigation data
    history = await github_data.get_station_history(station_name, limit=limit)

    if not history:
        # Try to find station to give better error message
        station = await github_data.get_station_by_name(station_name)
        if not station:
            raise HTTPException(status_code=404, detail=f"Station '{station_name}' not found")
        # Station exists but no history available
        return []

    return history


@router.get("/chart-data/{station_name}")
async def get_chart_data(station_name: str):
    """Get chart data for a station including history and thresholds.

    Returns data formatted for Chart.js rendering.
    """
    # Get station info for thresholds
    station = await github_data.get_station_by_name(station_name)
    if not station:
        raise HTTPException(status_code=404, detail=f"Station '{station_name}' not found")

    # Get history
    history = await github_data.get_station_history(station_name, limit=200)

    # Get latest reading for current status
    levels = await github_data.get_latest_water_levels()
    current = None
    for level in levels:
        if level.get("station_name", "").lower() == station_name.lower():
            current = level
            break

    return {
        "station_name": station["name"],
        "river_name": station.get("river_name", ""),
        "alert_level": station.get("alert_level", 0),
        "minor_flood_level": station.get("minor_flood_level", 0),
        "major_flood_level": station.get("major_flood_level", 0),
        "current": {
            "water_level": current.get("water_level") if current else None,
            "alert_status": current.get("alert_status") if current else "NO_DATA",
            "timestamp": current.get("timestamp") if current else "",
        },
        "history": history,
    }


@router.get("/map")
async def get_flood_map():
    """Get the current flood map image."""
    # Map is still in lk_dmc_vis repo
    url = "https://raw.githubusercontent.com/nuuuwan/lk_dmc_vis/main/images/map.png"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=30.0)
            response.raise_for_status()
            return Response(
                content=response.content,
                media_type="image/png",
                headers={"Cache-Control": "public, max-age=900"},
            )
        except httpx.HTTPError:
            raise HTTPException(status_code=503, detail="Could not fetch flood map")


@router.get("/chart/{station_name}")
async def get_station_chart(station_name: str):
    """Get the chart image for a specific station."""
    station = await github_data.get_station_by_name(station_name)
    if not station:
        raise HTTPException(status_code=404, detail=f"Station '{station_name}' not found")

    # Charts are still in lk_dmc_vis repo
    # Image filenames are lowercase with hyphens (e.g., "nagalagam-street.png")
    image_name = station["name"].lower().replace(" ", "-")
    url = f"https://raw.githubusercontent.com/nuuuwan/lk_dmc_vis/main/images/stations/{image_name}.png"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=30.0)
            response.raise_for_status()
            return Response(
                content=response.content,
                media_type="image/png",
                headers={"Cache-Control": "public, max-age=900"},
            )
        except httpx.HTTPError:
            raise HTTPException(status_code=404, detail=f"Chart for '{station_name}' not found")
