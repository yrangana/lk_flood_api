from fastapi import APIRouter, HTTPException
from app.services import github_data
from app.models.schemas import River, GaugingStation

router = APIRouter()


@router.get("", response_model=list[River])
async def list_rivers():
    """Get all rivers with their basin assignments."""
    rivers = await github_data.get_rivers()
    return [
        River(
            name=r["name"],
            river_basin_name=r["river_basin_name"],
            location_names=r.get("location_names", []),
        )
        for r in rivers
    ]


@router.get("/{name}", response_model=River)
async def get_river(name: str):
    """Get a specific river by name."""
    river = await github_data.get_river_by_name(name)
    if not river:
        raise HTTPException(status_code=404, detail=f"River '{name}' not found")

    return River(
        name=river["name"],
        river_basin_name=river["river_basin_name"],
        location_names=river.get("location_names", []),
    )


@router.get("/{name}/stations", response_model=list[GaugingStation])
async def get_river_stations(name: str):
    """Get all gauging stations on a specific river."""
    river = await github_data.get_river_by_name(name)
    if not river:
        raise HTTPException(status_code=404, detail=f"River '{name}' not found")

    stations = await github_data.get_gauging_stations()
    river_stations = [
        GaugingStation(
            name=s["name"],
            river_name=s["river_name"],
            lat_lng=s["lat_lng"],
            alert_level=s["alert_level"],
            minor_flood_level=s["minor_flood_level"],
            major_flood_level=s["major_flood_level"],
        )
        for s in stations
        if s["river_name"].lower() == name.lower()
    ]

    return river_stations
