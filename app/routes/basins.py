from fastapi import APIRouter, HTTPException
from app.services import github_data
from app.models.schemas import RiverBasin, River

router = APIRouter()


@router.get("", response_model=list[RiverBasin])
async def list_basins():
    """Get all river basins."""
    basins = await github_data.get_river_basins()
    return [
        RiverBasin(name=b["name"], code=b["code"])
        for b in basins
    ]


@router.get("/{name}", response_model=RiverBasin)
async def get_basin(name: str):
    """Get a specific river basin by name."""
    basin = await github_data.get_basin_by_name(name)
    if not basin:
        raise HTTPException(status_code=404, detail=f"Basin '{name}' not found")

    return RiverBasin(name=basin["name"], code=basin["code"])


@router.get("/{name}/rivers", response_model=list[River])
async def get_basin_rivers(name: str):
    """Get all rivers in a specific basin."""
    basin = await github_data.get_basin_by_name(name)
    if not basin:
        raise HTTPException(status_code=404, detail=f"Basin '{name}' not found")

    rivers = await github_data.get_rivers()
    basin_rivers = [
        River(
            name=r["name"],
            river_basin_name=r["river_basin_name"],
            location_names=r.get("location_names", []),
        )
        for r in rivers
        if r["river_basin_name"].lower() == name.lower()
    ]

    return basin_rivers
