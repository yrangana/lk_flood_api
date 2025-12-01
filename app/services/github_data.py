import httpx
from cachetools import TTLCache
from functools import wraps
from datetime import datetime

BASE_URL = "https://raw.githubusercontent.com/nuuuwan/lk_dmc_vis/main"
GITHUB_API_URL = "https://api.github.com/repos/nuuuwan/lk_dmc_vis/contents"

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


@cached(lambda: "latest_water_level_file")
async def get_latest_water_level_filename() -> str | None:
    """Get the most recent water level file by listing the directory."""
    url = f"{GITHUB_API_URL}/data/jsons"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=30.0)
            response.raise_for_status()
            files = response.json()
            # Filter for water-level JSON files and sort by name (YYYY-MM-DD-HH-MM format)
            json_files = [f["name"] for f in files if f["name"].endswith("-water-level.json")]
            if not json_files:
                return None
            # Sort and get the latest
            json_files.sort(reverse=True)
            return json_files[0]
        except httpx.HTTPError:
            return None


@cached(lambda: "gauging_stations")
async def get_gauging_stations() -> list[dict]:
    """Get station metadata. Uses water level data for accurate names."""
    # Get latest water levels which have accurate station names
    levels = await get_latest_water_levels()
    if not levels:
        return []

    # Build stations from water level data (has all the info we need)
    stations = []
    seen = set()
    for level in levels:
        name = level.get("station_name")
        if name and name not in seen:
            seen.add(name)
            stations.append({
                "name": name,
                "river_name": level.get("river_name", ""),
                "river_basin_name": level.get("river_basin_name", ""),
                "lat_lng": level.get("lat_lng", [0, 0]),
                "alert_level": level.get("alert_level", 0),
                "minor_flood_level": level.get("minor_flood_level", 0),
                "major_flood_level": level.get("major_flood_level", 0),
            })
    return stations


@cached(lambda: "stations_static")
async def get_stations_static() -> list[dict]:
    """Get static station data with coordinates and thresholds."""
    data = await fetch_json("data/static/gauging_stations.json")
    return data if data else []


# Mapping from water level station names to static station names
# (water level data uses different spellings than stations.json)
STATION_NAME_MAP = {
    "Nagalagam Street": "N' Street",
    "Kithulgala": "Kitulgala",
    "Rathnapura": "Ratnapura",
    "Thawalama": "Tawalama",
    "Thanamalwila": "Tanamalwila",
    "Thaldena": "Taldena",
    "Horowpothana": "Horowpatana",
    "Yaka Wewa": "Yakawewa",
    "Thanthirimale": "Tantirimale",
    "Padiyathalawa": "Padiyatalawa",
    "Manampitiya": "Manampitiya (HMIS)",
    "Weraganthota": "Weragantota",
}


def normalize_station_name(name: str) -> str:
    """Normalize station name for matching with static data."""
    # First check if there's a known mapping
    mapped_name = STATION_NAME_MAP.get(name, name)
    return mapped_name.lower().replace("'", "").replace(" ", "").replace("(", "").replace(")", "")


@cached(lambda: "rivers")
async def get_rivers() -> list[dict]:
    """Extract unique rivers from water level data."""
    levels = await get_latest_water_levels()
    if not levels:
        return []

    rivers = {}
    for level in levels:
        river_name = level.get("river_name", "")
        if river_name and river_name not in rivers:
            rivers[river_name] = {
                "name": river_name,
                "river_basin_name": level.get("river_basin_name", ""),
            }
    return list(rivers.values())


@cached(lambda: "river_basins")
async def get_river_basins() -> list[dict]:
    """Extract unique river basins from water level data."""
    levels = await get_latest_water_levels()
    if not levels:
        return []

    basins = {}
    for level in levels:
        basin_name = level.get("river_basin_name", "")
        if basin_name and basin_name not in basins:
            # Extract basin code from name like "Kelani Ganga (RB 01)"
            code = ""
            if "(RB " in basin_name:
                code = basin_name.split("(RB ")[1].rstrip(")")
            basins[basin_name] = {
                "name": basin_name,
                "code": code,
            }
    return list(basins.values())


def parse_timestamp_from_filename(filename: str) -> str:
    """Extract timestamp from filename like '2025-12-01-12-30-water-level.json'."""
    # Remove the '-water-level.json' suffix
    date_part = filename.replace("-water-level.json", "")
    # Parse: 2025-12-01-12-30 -> 2025-12-01 12:30:00
    parts = date_part.split("-")
    if len(parts) >= 5:
        return f"{parts[0]}-{parts[1]}-{parts[2]} {parts[3]}:{parts[4]}:00"
    return ""


async def get_latest_water_levels() -> list[dict]:
    """Get the latest water level readings for all stations."""
    cache_key = "latest_water_levels"
    if cache_key in cache:
        return cache[cache_key]

    filename = await get_latest_water_level_filename()
    if not filename:
        return []

    data = await fetch_json(f"data/jsons/{filename}")
    if not data:
        return []

    # Extract timestamp from filename (more reliable than time_str in data)
    file_timestamp = parse_timestamp_from_filename(filename)

    # lk_dmc_vis format: {"d_list": [...]}
    d_list = data.get("d_list", []) if isinstance(data, dict) else data

    # Get static station data for coordinates and thresholds
    static_stations = await get_stations_static()
    station_data = {}
    for s in static_stations:
        normalized = normalize_station_name(s.get("name", ""))
        station_data[normalized] = {
            "lat_lng": s.get("lat_lng", [0, 0]),
            "river_name": s.get("river_name", ""),
            "alert_level": s.get("alert_level", 0),
            "minor_flood_level": s.get("minor_flood_level", 0),
            "major_flood_level": s.get("major_flood_level", 0),
        }

    # Transform to our API format
    results = []
    for item in d_list:
        station_name = item.get("gauging_station_name", "")
        water_level = item.get("current_water_level")
        prev_water_level = item.get("previous_water_level")

        # Get static data for this station
        normalized_name = normalize_station_name(station_name)
        static = station_data.get(normalized_name, {})
        lat_lng = static.get("lat_lng", [0, 0])
        river_name = static.get("river_name", "")

        # Get alert thresholds from static data
        alert_level = static.get("alert_level", 0)
        minor_flood_level = static.get("minor_flood_level", 0)
        major_flood_level = static.get("major_flood_level", 0)

        # Calculate alert status from thresholds or derive from remarks
        remarks = item.get("remarks", "")
        if water_level is not None and alert_level > 0:
            alert_status = calculate_alert_status(water_level, {
                "alert_level": alert_level,
                "minor_flood_level": minor_flood_level,
                "major_flood_level": major_flood_level,
            })
        elif "Major Flood" in remarks:
            alert_status = "MAJOR"
        elif "Minor Flood" in remarks:
            alert_status = "MINOR"
        elif "Alert" in remarks:
            alert_status = "ALERT"
        elif water_level is not None:
            alert_status = "NORMAL"
        else:
            alert_status = "NO_DATA"

        # Calculate flood score if we have thresholds
        flood_score = calculate_flood_score(water_level, {
            "alert_level": alert_level,
            "major_flood_level": major_flood_level,
        }) if alert_level > 0 else None

        # Use filename timestamp (more reliable than time_str which can be buggy)
        timestamp = file_timestamp

        # Get rising/falling status
        rising_or_falling = item.get("rising_or_falling", "")

        results.append({
            "station_name": station_name,
            "river_name": river_name,
            "river_basin_name": "",  # Not available in this format
            "lat_lng": lat_lng,
            "water_level": water_level,
            "previous_water_level": prev_water_level,
            "alert_level": alert_level,
            "minor_flood_level": minor_flood_level,
            "major_flood_level": major_flood_level,
            "alert_status": alert_status,
            "flood_score": flood_score,
            "rising_or_falling": rising_or_falling,
            "rainfall_mm": item.get("rainfall_mm", 0),
            "remarks": remarks,
            "timestamp": timestamp,
        })

    cache[cache_key] = results
    return results


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
