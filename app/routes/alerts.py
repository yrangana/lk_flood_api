from fastapi import APIRouter
from app.services import github_data
from app.models.schemas import WaterLevelReading, AlertSummary, AlertLevel

router = APIRouter()


@router.get("", response_model=list[WaterLevelReading])
async def get_active_alerts():
    """Get all stations currently in ALERT, MINOR, or MAJOR status."""
    levels = await github_data.get_latest_water_levels()
    stations = await github_data.get_gauging_stations()

    station_map = {s["name"].lower(): s for s in stations}
    alerts = []

    for level in levels:
        station_name = level.get("gauging_station_name", "")
        station = station_map.get(station_name.lower())

        if station:
            water_level = level.get("current_water_level")
            alert_status = github_data.calculate_alert_status(water_level, station)

            if alert_status in ["ALERT", "MINOR", "MAJOR"]:
                flood_score = github_data.calculate_flood_score(water_level, station)
                alerts.append(
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

    # Sort by severity: MAJOR > MINOR > ALERT
    severity_order = {"MAJOR": 0, "MINOR": 1, "ALERT": 2}
    alerts.sort(key=lambda x: severity_order.get(x.alert_status, 99))

    return alerts


@router.get("/summary", response_model=list[AlertSummary])
async def get_alert_summary():
    """Get a summary count of stations by alert level."""
    levels = await github_data.get_latest_water_levels()
    stations = await github_data.get_gauging_stations()

    station_map = {s["name"].lower(): s for s in stations}
    counts: dict[str, list[str]] = {
        "MAJOR": [],
        "MINOR": [],
        "ALERT": [],
        "NORMAL": [],
        "NO_DATA": [],
    }

    for level in levels:
        station_name = level.get("gauging_station_name", "")
        station = station_map.get(station_name.lower())

        if station:
            water_level = level.get("current_water_level")
            alert_status = github_data.calculate_alert_status(water_level, station)
            counts[alert_status].append(station_name)

    return [
        AlertSummary(
            alert_level=AlertLevel(level),
            count=len(station_list),
            stations=station_list,
        )
        for level, station_list in counts.items()
        if len(station_list) > 0
    ]
