# Architecture

## Overview

This is a stateless FastAPI REST API that wraps flood monitoring data from Sri Lanka's Disaster Management Center (DMC). It fetches and caches data from two GitHub repositories:
- [nuuuwan/lk_irrigation](https://github.com/nuuuwan/lk_irrigation) - Fresh water levels and historical data
- [nuuuwan/lk_dmc_vis](https://github.com/nuuuwan/lk_dmc_vis) - Metadata (remarks, trend) and images

## System Architecture

```mermaid
flowchart TB
    subgraph External["External Data Sources"]
        DMC["Sri Lanka DMC
        dmc.gov.lk"] -->|PDF Reports| Pipeline1
        DMC -->|PDF Reports| Pipeline2
        Pipeline1["nuuuwan/lk_irrigation
        (Water Levels)"]
        Pipeline2["nuuuwan/lk_dmc_vis
        (Metadata, Images)"]
        Pipeline1 -->|Every ~10 min| GH[("GitHub Repository
        raw.githubusercontent.com")]
        Pipeline2 -->|Every ~3 hours| GH
    end

    subgraph API["This API (FastAPI)"]
        GH -->|HTTPS| Service["github_data.py
        Data Service"]
        Service --> Cache[("TTLCache
        5 min TTL")]
        Cache --> Routes

        subgraph Routes["Route Handlers"]
            R1["/stations"]
            R2["/rivers"]
            R3["/basins"]
            R4["/levels"]
            R5["/alerts"]
            R6["/demo/stations"]
        end

        subgraph Static["Static Files"]
            Dashboard["dashboard.html
            (Leaflet Map)"]
        end
    end

    subgraph Consumers["API Consumers"]
        Routes --> Web["Web Dashboards"]
        Routes --> Mobile["Mobile Apps"]
        Routes --> Alerts["Alert Systems"]
        Routes --> Analysis["Data Analysis"]
        Dashboard --> Routes
    end
```

## Data Files Structure

Data is sourced from two upstream repositories:

```mermaid
flowchart LR
    subgraph Irrigation["lk_irrigation (Fresh Data)"]
        LATEST["latest-100.json
        (Current water levels)"]
        ALL["all.json
        (8 days history)"]
        STATIC_IRR["static/stations.json
        (Thresholds)"]
    end

    subgraph DMC["lk_dmc_vis (Metadata & Images)"]
        GS["gauging_stations.json
        (Station coords)"]
        JSON["jsons/*.json
        (Remarks, trend, rainfall)"]
        MAP["images/map.png
        (Flood Map)"]
        CHARTS["images/stations/*.png
        (Station Charts)"]
    end
```

| Source | File | Purpose | Update Frequency |
|--------|------|---------|------------------|
| lk_irrigation | `latest-100.json` | Current water levels | ~10 min |
| lk_irrigation | `all.json` | Historical data (~8 days) | ~10 min |
| lk_irrigation | `static/stations.json` | Station thresholds | Static |
| lk_dmc_vis | `jsons/*.json` | Remarks, rising/falling, rainfall | ~3 hours |
| lk_dmc_vis | `gauging_stations.json` | Station coordinates | Static |
| lk_dmc_vis | `images/map.png` | Flood map image | ~3 hours |
| lk_dmc_vis | `images/stations/*.png` | Pre-rendered charts | ~3 hours |

## Project Structure

```
lk_flood_api/
├── app/
│   ├── main.py              # FastAPI app, CORS, router registration
│   ├── models/
│   │   └── schemas.py       # Pydantic models
│   ├── routes/
│   │   ├── stations.py      # GET /stations, /stations/{name}
│   │   ├── rivers.py        # GET /rivers, /rivers/{name}, /rivers/{name}/stations
│   │   ├── basins.py        # GET /basins, /basins/{name}, /basins/{name}/rivers
│   │   ├── levels.py        # GET /levels/latest, /levels/history, /levels/chart-data, /levels/map, /levels/chart
│   │   └── alerts.py        # GET /alerts, /alerts/summary
│   ├── services/
│   │   └── github_data.py   # Data fetching, caching, calculations
│   └── static/
│       └── dashboard.html   # Interactive map dashboard (Leaflet.js + Chart.js)
├── requirements.txt
├── vercel.json
└── README.md
```

## Alert Level Calculation

```mermaid
flowchart TD
    WL["Water Level Reading"] --> Check1{">= Major
    Flood Level?"}
    Check1 -->|Yes| MAJOR["MAJOR"]
    Check1 -->|No| Check2{">= Minor
    Flood Level?"}
    Check2 -->|Yes| MINOR["MINOR"]
    Check2 -->|No| Check3{">= Alert
    Level?"}
    Check3 -->|Yes| ALERT["ALERT"]
    Check3 -->|No| Check4{"Has Data?"}
    Check4 -->|Yes| NORMAL["NORMAL"]
    Check4 -->|No| NODATA["NO_DATA"]

    style MAJOR fill:#d32f2f,color:#fff
    style MINOR fill:#f57c00,color:#fff
    style ALERT fill:#fbc02d,color:#000
    style NORMAL fill:#388e3c,color:#fff
    style NODATA fill:#9e9e9e,color:#fff
```

## Flood Score Calculation

The `flood_score` is a normalized value indicating flood severity:

```
flood_score = (water_level - alert_level) / (major_flood_level - alert_level)
```

| Score | Meaning |
|-------|---------|
| < 0 | Below alert level |
| 0 | At alert level |
| 0.5 | Halfway between alert and major |
| 1.0 | At major flood level |
| > 1 | Above major flood level |

## Data Models

```mermaid
classDiagram
    class GaugingStation {
        +string name
        +string river_name
        +float[] lat_lng
        +float alert_level
        +float minor_flood_level
        +float major_flood_level
    }

    class WaterLevelReading {
        +string station_name
        +string river_name
        +float water_level
        +AlertLevel alert_status
        +float flood_score
        +string timestamp
    }

    class River {
        +string name
        +string river_basin_name
        +string[] location_names
    }

    class RiverBasin {
        +string name
        +string code
    }

    class AlertLevel {
        <<enumeration>>
        MAJOR
        MINOR
        ALERT
        NORMAL
        NO_DATA
    }

    GaugingStation --> WaterLevelReading : has readings
    River --> RiverBasin : belongs to
    WaterLevelReading --> AlertLevel : has status
```

## Request Flow

```mermaid
sequenceDiagram
    participant Client
    participant FastAPI
    participant Cache
    participant GitHub

    Client->>FastAPI: GET /levels/latest
    FastAPI->>Cache: Check cache

    alt Cache Hit
        Cache-->>FastAPI: Return cached data
    else Cache Miss
        FastAPI->>GitHub: Fetch docs_last100.tsv
        GitHub-->>FastAPI: TSV data
        FastAPI->>GitHub: Fetch latest JSON
        GitHub-->>FastAPI: Water level data
        FastAPI->>Cache: Store (15 min TTL)
    end

    FastAPI->>FastAPI: Calculate alert status
    FastAPI-->>Client: JSON response
```

## Dependencies

| Package | Purpose |
|---------|---------|
| [FastAPI](https://fastapi.tiangolo.com/) | Web framework |
| [Uvicorn](https://www.uvicorn.org/) | ASGI server |
| [httpx](https://www.python-httpx.org/) | Async HTTP client |
| [Pydantic](https://docs.pydantic.dev/) | Data validation |
| [cachetools](https://cachetools.readthedocs.io/) | TTL-based caching |
| [Leaflet.js](https://leafletjs.com/) | Interactive map (dashboard) |
| [Chart.js](https://www.chartjs.org/) | Water level trend charts (dashboard) |

## Demo Dashboard

The `/demo/stations` endpoint serves a single-page application that visualizes station data:

```mermaid
flowchart LR
    Browser["Browser"] -->|GET /demo/stations| Server["FastAPI"]
    Server -->|dashboard.html| Browser
    Browser -->|Fetch /levels/latest, /alerts/summary| Server
    Server -->|JSON| Browser
    Browser -->|Render| Map["Leaflet Map + Station List"]
    Browser -->|Click View Chart| ChartModal["Chart.js Modal"]
    ChartModal -->|Fetch /levels/chart-data/{station}| Server
```

**Features:**
- Interactive map with color-coded station markers
- Sidebar with filterable station list (MAJOR first)
- Filter buttons by alert level
- Chart.js water level trend charts (~8 days history)
- Threshold lines (Alert, Minor Flood, Major Flood) on charts
- All timestamps displayed in Sri Lanka timezone (UTC+5:30)
- Auto-refresh every 5 minutes
- Mobile responsive design
- Dark theme using CartoDB tiles

## Design Decisions

1. **Stateless Architecture**: No database. Data fetched on-demand from GitHub keeps the API always in sync with the source.

2. **5-minute Cache**: More aggressive caching since lk_irrigation updates frequently (~10 min). Reduces GitHub API load while keeping data fresh.

3. **Async Throughout**: Uses `httpx` and async functions for non-blocking I/O, enabling high concurrency.

4. **API-level Alert Calculations**: Computed on each request rather than relying on pre-computed values, ensuring consistency.

5. **Image Proxying**: Serves map and chart images through the API with cache headers, enabling CORS access from web apps.

6. **Dual Data Source Merging**: Combines fresher water levels from lk_irrigation with metadata (remarks, trend, rainfall) from lk_dmc_vis for the best of both sources.

7. **Sri Lanka Timezone**: All timestamps are generated in Sri Lanka timezone (UTC+5:30) regardless of server location.

## Data Source Acknowledgment

This API relies entirely on data from:

- **[nuuuwan/lk_irrigation](https://github.com/nuuuwan/lk_irrigation)** - Open-source data pipeline by [@nuuuwan](https://github.com/nuuuwan) (fresh water levels)
- **[nuuuwan/lk_dmc_vis](https://github.com/nuuuwan/lk_dmc_vis)** - Open-source data pipeline by [@nuuuwan](https://github.com/nuuuwan) (metadata, images)
- **[Sri Lanka Disaster Management Center](https://www.dmc.gov.lk)** - Original source of flood monitoring data
