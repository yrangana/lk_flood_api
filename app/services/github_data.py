import httpx
from cachetools import TTLCache
from functools import wraps
from datetime import datetime, timezone, timedelta

# Sri Lanka timezone (UTC+5:30)
LK_TZ = timezone(timedelta(hours=5, minutes=30))

BASE_URL = "https://raw.githubusercontent.com/nuuuwan/lk_dmc_vis/main"
GITHUB_API_URL = "https://api.github.com/repos/nuuuwan/lk_dmc_vis/contents"
IRRIGATION_BASE_URL = "https://raw.githubusercontent.com/nuuuwan/lk_irrigation/main"

# Cache data for 5 minutes (300 seconds) - irrigation data updates more frequently
cache = TTLCache(maxsize=100, ttl=300)


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


async def fetch_irrigation_json(path: str) -> dict | list | None:
    """Fetch JSON from lk_irrigation repo."""
    url = f"{IRRIGATION_BASE_URL}/{path}"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError:
            return None


@cached(lambda: "irrigation_stations_static")
async def get_irrigation_stations_static() -> list[dict]:
    """Get static station data from lk_irrigation (has thresholds and coords)."""
    data = await fetch_irrigation_json("data/static/stations.json")
    return data if data else []


@cached(lambda: "irrigation_latest_levels")
async def get_irrigation_latest_levels() -> dict:
    """Get latest water levels from lk_irrigation (fresher data).
    Returns dict mapping station_name -> {water_level, timestamp}
    """
    data = await fetch_irrigation_json("data/latest-100.json")
    if not data:
        return {}

    # Build dict of latest level per station
    latest = {}
    for rec in data:
        station = rec.get("station_name", "")
        time_ut = rec.get("time_ut", 0)
        water_level = rec.get("water_level_m")

        if station and (station not in latest or time_ut > latest[station]["time_ut"]):
            latest[station] = {
                "water_level": water_level,
                "time_ut": time_ut,
                "timestamp": datetime.fromtimestamp(time_ut, tz=LK_TZ).strftime("%Y-%m-%d %H:%M:%S") if time_ut else "",
            }
    return latest


@cached(lambda: "irrigation_all_history")
async def get_irrigation_all_history() -> list[dict]:
    """Get all historical water level data from lk_irrigation."""
    data = await fetch_irrigation_json("data/all.json")
    return data if data else []


async def get_station_history(station_name: str, limit: int = 200) -> list[dict]:
    """Get historical water level readings for a specific station.

    Returns list of {timestamp, water_level} sorted by time (oldest first).
    """
    all_data = await get_irrigation_all_history()
    if not all_data:
        return []

    # Filter for this station (case-insensitive match)
    station_lower = station_name.lower()
    station_records = [
        r for r in all_data
        if r.get("station_name", "").lower() == station_lower
    ]

    # Sort by timestamp (oldest first for charting)
    station_records.sort(key=lambda x: x.get("time_ut", 0))

    # Limit records if needed
    if limit and len(station_records) > limit:
        station_records = station_records[-limit:]

    # Transform to API format
    return [
        {
            "timestamp": datetime.fromtimestamp(r["time_ut"], tz=LK_TZ).strftime("%Y-%m-%d %H:%M:%S") if r.get("time_ut") else "",
            "time_ut": r.get("time_ut", 0),
            "water_level": r.get("water_level_m"),
        }
        for r in station_records
    ]


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
    """Get the latest water level readings for all stations.

    Merges data from two sources:
    - lk_irrigation: fresher water level readings (updates every few minutes)
    - lk_dmc_vis: metadata like remarks, rising/falling, rainfall (updates every 3 hours)

    Uses irrigation data for water levels when available and fresher.
    """
    cache_key = "latest_water_levels"
    if cache_key in cache:
        return cache[cache_key]

    filename = await get_latest_water_level_filename()
    if not filename:
        return []

    data = await fetch_json(f"data/jsons/{filename}")
    if not data:
        return []

    # Extract timestamp from DMC filename
    dmc_timestamp = parse_timestamp_from_filename(filename)

    # Get fresher water levels from irrigation data
    irrigation_levels = await get_irrigation_latest_levels()

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

    # Also get irrigation static data (has better thresholds)
    irrigation_static = await get_irrigation_stations_static()
    irrigation_station_data = {}
    for s in irrigation_static:
        name = s.get("name", "")
        irrigation_station_data[name] = {
            "lat_lng": s.get("lat_lng", [0, 0]),
            "river_name": s.get("river_name", ""),
            "alert_level": s.get("alert_level_m", 0),
            "minor_flood_level": s.get("minor_flood_level_m", 0),
            "major_flood_level": s.get("major_flood_level_m", 0),
        }

    # Transform to our API format
    results = []
    seen_stations = set()

    for item in d_list:
        station_name = item.get("gauging_station_name", "")
        seen_stations.add(station_name)

        dmc_water_level = item.get("current_water_level")
        prev_water_level = item.get("previous_water_level")

        # Check if irrigation has fresher data for this station
        irr_data = irrigation_levels.get(station_name)
        if irr_data and irr_data.get("water_level") is not None:
            water_level = irr_data["water_level"]
            timestamp = irr_data["timestamp"]
        else:
            water_level = dmc_water_level
            timestamp = dmc_timestamp

        # Get static data - prefer irrigation static (better thresholds)
        irr_static = irrigation_station_data.get(station_name, {})
        normalized_name = normalize_station_name(station_name)
        dmc_static = station_data.get(normalized_name, {})

        # Use irrigation static if available, else DMC static
        if irr_static:
            lat_lng = irr_static.get("lat_lng", [0, 0])
            river_name = irr_static.get("river_name", "") or dmc_static.get("river_name", "")
            alert_level = irr_static.get("alert_level", 0)
            minor_flood_level = irr_static.get("minor_flood_level", 0)
            major_flood_level = irr_static.get("major_flood_level", 0)
        else:
            lat_lng = dmc_static.get("lat_lng", [0, 0])
            river_name = dmc_static.get("river_name", "")
            alert_level = dmc_static.get("alert_level", 0)
            minor_flood_level = dmc_static.get("minor_flood_level", 0)
            major_flood_level = dmc_static.get("major_flood_level", 0)

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

        # Get rising/falling status from DMC
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
