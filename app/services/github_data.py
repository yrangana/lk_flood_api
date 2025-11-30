import httpx
from cachetools import TTLCache
from functools import wraps
from typing import Any

BASE_URL = "https://raw.githubusercontent.com/nuuuwan/lk_dmc_vis/main"

# Cache data for 15 minutes (900 seconds) - matches pipeline update frequency
cache = TTLCache(maxsize=100, ttl=900)


def cached(key_func):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            key = key_func(*args, **kwargs)
            if key in cache:
                return cache[key]
            result = await func(*args, **kwargs)
            cache[key] = result
            return result
        return wrapper
    return decorator


async def fetch_json(path: str) -> dict | list | None:
    url = f"{BASE_URL}/{path}"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError:
            return None


@cached(lambda: "gauging_stations")
async def get_gauging_stations() -> list[dict]:
    data = await fetch_json("data/static/gauging_stations.json")
    return data if data else []


@cached(lambda: "rivers")
async def get_rivers() -> list[dict]:
    data = await fetch_json("data/static/rivers.json")
    return data if data else []


@cached(lambda: "river_basins")
async def get_river_basins() -> list[dict]:
    data = await fetch_json("data/static/river_basins.json")
    return data if data else []


@cached(lambda: "locations")
async def get_locations() -> list[dict]:
    data = await fetch_json("data/static/locations.json")
    return data if data else []


@cached(lambda: "docs_index")
async def get_docs_index() -> list[dict]:
    url = f"{BASE_URL}/data/docs_last100.tsv"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=30.0)
            response.raise_for_status()
            lines = response.text.strip().split("\n")
            docs = []
            # Skip header row, doc_id is in column 1
            for line in lines[1:]:
                parts = line.split("\t")
                if len(parts) >= 2:
                    docs.append({"id": parts[1], "url": parts[5] if len(parts) > 5 else ""})
            return docs
        except httpx.HTTPError:
            return []


async def get_water_level_data(doc_id: str) -> dict | None:
    cache_key = f"water_level_{doc_id}"
    if cache_key in cache:
        return cache[cache_key]

    data = await fetch_json(f"data/jsons/{doc_id}.json")
    if data:
        cache[cache_key] = data
    return data


async def get_latest_water_levels() -> list[dict]:
    docs = await get_docs_index()
    if not docs:
        return []

    # Get most recent water-level document (skip flood warnings which don't have JSON files)
    latest_doc = None
    for doc in docs:
        if "water-level" in doc["id"]:
            latest_doc = doc
            break

    if not latest_doc:
        return []

    data = await get_water_level_data(latest_doc["id"])

    if not data or "d_list" not in data:
        return []

    return data["d_list"]


async def get_station_by_name(name: str) -> dict | None:
    stations = await get_gauging_stations()
    for station in stations:
        if station.get("name", "").lower() == name.lower():
            return station
    return None


async def get_river_by_name(name: str) -> dict | None:
    rivers = await get_rivers()
    for river in rivers:
        if river.get("name", "").lower() == name.lower():
            return river
    return None


async def get_basin_by_name(name: str) -> dict | None:
    basins = await get_river_basins()
    for basin in basins:
        if basin.get("name", "").lower() == name.lower():
            return basin
    return None


def calculate_alert_status(water_level: float | None, station: dict) -> str:
    if water_level is None:
        return "NO_DATA"

    major = station.get("major_flood_level", float("inf"))
    minor = station.get("minor_flood_level", float("inf"))
    alert = station.get("alert_level", float("inf"))

    if water_level >= major:
        return "MAJOR"
    elif water_level >= minor:
        return "MINOR"
    elif water_level >= alert:
        return "ALERT"
    else:
        return "NORMAL"


def calculate_flood_score(water_level: float | None, station: dict) -> float | None:
    if water_level is None:
        return None

    alert = station.get("alert_level", 0)
    major = station.get("major_flood_level", 0)

    if major <= alert:
        return None

    # Normalized score: 0 = at alert level, 1 = at major flood level
    return (water_level - alert) / (major - alert)
