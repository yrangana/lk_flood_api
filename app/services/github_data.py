import httpx
from cachetools import TTLCache
from functools import wraps
from datetime import datetime

BASE_URL = "https://raw.githubusercontent.com/nuuuwan/dmc_gov_lk_2024/main"
GITHUB_API_URL = "https://api.github.com/repos/nuuuwan/dmc_gov_lk_2024/contents"

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
    url = f"{GITHUB_API_URL}/data-parsed/river-water-level-and-flood-warnings"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=30.0)
            response.raise_for_status()
            files = response.json()
            # Filter for JSON files and sort by name (YYYYMMDD.HHMMSS.json format)
            json_files = [f["name"] for f in files if f["name"].endswith(".json")]
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
    """Get static station data with coordinates."""
    data = await fetch_json("data-static/stations.json")
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


async def get_latest_water_levels() -> list[dict]:
    """Get the latest water level readings for all stations."""
    cache_key = "latest_water_levels"
    if cache_key in cache:
        return cache[cache_key]

    filename = await get_latest_water_level_filename()
    if not filename:
        return []

    data = await fetch_json(f"data-parsed/river-water-level-and-flood-warnings/{filename}")
    if not data:
        return []

    # Get static station data for coordinates
    static_stations = await get_stations_static()
    station_coords = {}
    for s in static_stations:
        normalized = normalize_station_name(s.get("name", ""))
        station_coords[normalized] = s.get("latLng", [0, 0])

    # Transform to our API format
    results = []
    for item in data:
        station_name = item.get("station", "")
        water_level = item.get("water_level_2")  # Latest reading
        prev_water_level = item.get("water_level_1")  # Previous reading

        # Get coordinates
        normalized_name = normalize_station_name(station_name)
        lat_lng = station_coords.get(normalized_name, [0, 0])

        # Calculate alert status
        alert_level = item.get("alert_level", 0)
        minor_flood_level = item.get("minor_flood_level", 0)
        major_flood_level = item.get("major_flood_level", 0)

        alert_status = calculate_alert_status(water_level, {
            "alert_level": alert_level,
            "minor_flood_level": minor_flood_level,
            "major_flood_level": major_flood_level,
        })

        flood_score = calculate_flood_score(water_level, {
            "alert_level": alert_level,
            "major_flood_level": major_flood_level,
        })

        # Convert unix timestamp to datetime string
        ut = item.get("ut_water_level_2") or item.get("ut")
        timestamp = ""
        if ut:
            timestamp = datetime.fromtimestamp(ut).strftime("%Y-%m-%d %H:%M:%S")

        # Determine rising/falling from remarks or calculate
        rising_or_falling = item.get("remarks_rising", "")
        if not rising_or_falling and water_level and prev_water_level:
            if water_level > prev_water_level:
                rising_or_falling = "Rising"
            elif water_level < prev_water_level:
                rising_or_falling = "Falling"

        results.append({
            "station_name": station_name,
            "river_name": item.get("river", ""),
            "river_basin_name": item.get("river_basin", ""),
            "lat_lng": lat_lng,
            "water_level": water_level,
            "previous_water_level": prev_water_level,
            "alert_level": alert_level,
            "minor_flood_level": minor_flood_level,
            "major_flood_level": major_flood_level,
            "alert_status": alert_status,
            "flood_score": flood_score,
            "rising_or_falling": rising_or_falling,
            "rainfall_mm": item.get("rainfall", 0),
            "remarks": item.get("remarks", ""),
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
