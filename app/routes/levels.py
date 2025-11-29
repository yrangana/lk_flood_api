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
    stations = await github_data.get_gauging_stations()

    station_map = {s["name"].lower(): s for s in stations}
    readings = []

    for level in levels:
        station_name = level.get("gauging_station_name", "")
        station = station_map.get(station_name.lower())

        if station:
            water_level = level.get("current_water_level")
            alert_status = github_data.calculate_alert_status(water_level, station)
            flood_score = github_data.calculate_flood_score(water_level, station)

            readings.append(
                WaterLevelReading(
                    station_name=station_name,
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
            )

    return readings


@router.get("/history/{station_name}", response_model=list[WaterLevelReading])
async def get_station_history(station_name: str, limit: int = 50):
    """Get historical water level readings for a specific station."""
    station = await github_data.get_station_by_name(station_name)
    if not station:
        raise HTTPException(status_code=404, detail=f"Station '{station_name}' not found")

    docs = await github_data.get_docs_index()
    readings = []

    for doc in docs[:limit]:
        data = await github_data.get_water_level_data(doc["id"])
        if not data or "d_list" not in data:
            continue

        for level in data["d_list"]:
            if level.get("gauging_station_name", "").lower() == station_name.lower():
                water_level = level.get("current_water_level")
                alert_status = github_data.calculate_alert_status(water_level, station)
                flood_score = github_data.calculate_flood_score(water_level, station)

                readings.append(
                    WaterLevelReading(
                        station_name=station_name,
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
                )
                break

    return readings


@router.get("/map")
async def get_flood_map():
    """Get the current flood map image."""
    url = f"{github_data.BASE_URL}/images/map.png"
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

    # Image filenames are lowercase with hyphens (e.g., "nagalagam-street.png")
    image_name = station["name"].lower().replace(" ", "-")
    url = f"{github_data.BASE_URL}/images/stations/{image_name}.png"
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
