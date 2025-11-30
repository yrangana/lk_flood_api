from fastapi import APIRouter
from app.services import github_data
from app.models.schemas import WaterLevelReading, AlertSummary, AlertLevel

router = APIRouter()


@router.get("", response_model=list[WaterLevelReading])
async def get_active_alerts():
    """Get all stations currently in ALERT, MINOR, or MAJOR status."""
    levels = await github_data.get_latest_water_levels()
    alerts = []

    for level in levels:
        alert_status = level.get("alert_status", "NO_DATA")

        if alert_status in ["ALERT", "MINOR", "MAJOR"]:
            alerts.append(
                WaterLevelReading(
                    station_name=level["station_name"],
                    river_name=level["river_name"],
                    water_level=level.get("water_level"),
                    previous_water_level=level.get("previous_water_level"),
                    alert_status=alert_status,
                    flood_score=level.get("flood_score"),
                    rising_or_falling=level.get("rising_or_falling"),
                    rainfall_mm=level.get("rainfall_mm"),
                    remarks=level.get("remarks"),
                    timestamp=level.get("timestamp", ""),
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

    counts: dict[str, list[str]] = {
        "MAJOR": [],
        "MINOR": [],
        "ALERT": [],
        "NORMAL": [],
        "NO_DATA": [],
    }

    for level in levels:
        alert_status = level.get("alert_status", "NO_DATA")
        station_name = level.get("station_name", "")
        if alert_status in counts:
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
