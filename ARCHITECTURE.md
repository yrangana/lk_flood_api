# Architecture

## Overview

This is a stateless FastAPI REST API that wraps flood monitoring data from Sri Lanka's Disaster Management Center (DMC). It fetches and caches data from the [nuuuwan/lk_dmc_vis](https://github.com/nuuuwan/lk_dmc_vis) GitHub repository.

## System Architecture

```mermaid
flowchart TB
    subgraph External["External Data Source"]
        DMC["Sri Lanka DMC
        dmc.gov.lk"] -->|PDF Reports| Pipeline
        Pipeline["nuuuwan/lk_dmc_vis
        (GitHub Actions)"]
        Pipeline -->|Every 15 min| GH[("GitHub Repository
        raw.githubusercontent.com")]
    end

    subgraph API["This API (FastAPI)"]
        GH -->|HTTPS| Service["github_data.py
        Data Service"]
        Service --> Cache[("TTLCache
        15 min TTL")]
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

The upstream [nuuuwan/lk_dmc_vis](https://github.com/nuuuwan/lk_dmc_vis) repository provides:

```mermaid
flowchart LR
    subgraph Static["Static Data"]
        GS["gauging_stations.json
        (39 stations)"]
        RV["rivers.json
        (26 rivers)"]
        RB["river_basins.json
        (18 basins)"]
    end

    subgraph Dynamic["Dynamic Data (Updated Every 15 min)"]
        IDX["docs_last100.tsv
        (Report Index)"]
        JSON["jsons/*.json
        (Water Level Data)"]
    end

    subgraph Images["Generated Images"]
        MAP["map.png
        (Flood Map)"]
        CHARTS["stations/*.png
        (Station Charts)"]
    end
```

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
│   │   ├── levels.py        # GET /levels/latest, /levels/history, /levels/map, /levels/chart
│   │   └── alerts.py        # GET /alerts, /alerts/summary
│   ├── services/
│   │   └── github_data.py   # Data fetching, caching, calculations
│   └── static/
│       └── dashboard.html   # Interactive map dashboard (Leaflet.js)
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

## Demo Dashboard

The `/demo/stations` endpoint serves a single-page application that visualizes station data:

```mermaid
flowchart LR
    Browser["Browser"] -->|GET /demo/stations| Server["FastAPI"]
    Server -->|dashboard.html| Browser
    Browser -->|Fetch /stations, /levels/latest, /alerts/summary| Server
    Server -->|JSON| Browser
    Browser -->|Render| Map["Leaflet Map + Station List"]
```

**Features:**
- Interactive map with color-coded station markers
- Sidebar with filterable station list (MAJOR first)
- Filter buttons by alert level
- Auto-refresh every 5 minutes
- Mobile responsive design
- Dark theme using CartoDB tiles

## Design Decisions

1. **Stateless Architecture**: No database. Data fetched on-demand from GitHub keeps the API always in sync with the source.

2. **15-minute Cache**: Matches the upstream update frequency. Reduces GitHub API load while keeping data fresh.

3. **Async Throughout**: Uses `httpx` and async functions for non-blocking I/O, enabling high concurrency.

4. **API-level Alert Calculations**: Computed on each request rather than relying on pre-computed values, ensuring consistency.

5. **Image Proxying**: Serves map and chart images through the API with cache headers, enabling CORS access from web apps.

## Data Source Acknowledgment

This API relies entirely on data from:

- **[nuuuwan/lk_dmc_vis](https://github.com/nuuuwan/lk_dmc_vis)** - Open-source data pipeline by [@nuuuwan](https://github.com/nuuuwan)
- **[Sri Lanka Disaster Management Center](https://www.dmc.gov.lk)** - Original source of flood monitoring data
