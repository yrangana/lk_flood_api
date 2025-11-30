# Sri Lanka Flood Data API

REST API for Sri Lanka river water level and flood monitoring data.

**Live API:** https://lk-flood-api.vercel.app

| Documentation | URL |
|--------------|-----|
| Swagger UI | https://lk-flood-api.vercel.app/docs |
| ReDoc | https://lk-flood-api.vercel.app/redoc |
| OpenAPI Spec | https://lk-flood-api.vercel.app/openapi.json |

## Features

- Real-time water level data for 39 gauging stations
- Alert status classification (MAJOR, MINOR, ALERT, NORMAL)
- Historical water level readings
- River and basin information
- Flood map and station chart images

## API Documentation

### Swagger UI
![Swagger UI](docs/api-swagger.png)

### ReDoc
![ReDoc](docs/api-redoc.png)

## Data Flow

```mermaid
flowchart LR
    DMC[("Sri Lanka DMC
    (PDF Reports)")] --> Pipeline
    Pipeline["nuuuwan/lk_dmc_vis
    (Data Pipeline)"] --> GitHub[("GitHub
    Raw Files")]
    GitHub --> API["This API
    (FastAPI)"]
    API --> Apps["Web Apps
    Mobile Apps
    Alert Systems"]
```

## API Endpoints

### Health
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | API health check |

### Stations
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/stations` | List all gauging stations |
| GET | `/stations/{name}` | Get station with latest reading |

### Rivers
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/rivers` | List all rivers |
| GET | `/rivers/{name}` | Get river details |
| GET | `/rivers/{name}/stations` | Get stations on a river |

### Basins
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/basins` | List all river basins |
| GET | `/basins/{name}` | Get basin details |
| GET | `/basins/{name}/rivers` | Get rivers in a basin |

### Water Levels
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/levels/latest` | Latest readings for all stations |
| GET | `/levels/history/{station}?limit=50` | Historical readings for a station |
| GET | `/levels/map` | Current flood map (PNG) |
| GET | `/levels/chart/{station}` | Station chart (PNG) |

### Alerts
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/alerts` | Stations in ALERT/MINOR/MAJOR status |
| GET | `/alerts/summary` | Count of stations by alert level |

### Dashboard
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/demo/stations` | Interactive map showing station locations and alert status |

## Local Development

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn app.main:app --reload
```

Visit http://localhost:8000/docs for interactive API documentation (Swagger UI).

## Data Source & Acknowledgments

This API consumes data from [**nuuuwan/lk_dmc_vis**](https://github.com/nuuuwan/lk_dmc_vis), an open-source data pipeline by [@nuuuwan](https://github.com/nuuuwan) that:

1. Fetches PDF flood reports from the [Sri Lanka Disaster Management Center (DMC)](https://www.dmc.gov.lk)
2. Parses and extracts water level data using OCR/PDF processing
3. Publishes structured JSON data to GitHub every 15 minutes

### Original Data Source

**Sri Lanka Disaster Management Center (DMC)**
- Website: [https://www.dmc.gov.lk](https://www.dmc.gov.lk)
- Reports: [River Water Level & Flood Warnings](https://www.dmc.gov.lk/index.php?option=com_dmcreports&view=reports&Itemid=277&report_type_id=6&lang=en)

The DMC is the official government agency responsible for disaster management in Sri Lanka, operating under the Ministry of Defence.

## License

MIT
