from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.routes import stations, rivers, basins, levels, alerts

app = FastAPI(
    title="Sri Lanka Flood Data API",
    description="REST API for Sri Lanka river water level and flood monitoring data. "
                "Data sourced from the Disaster Management Center (DMC) via nuuuwan/lk_dmc_vis.",
    version="1.0.0",
    contact={
        "name": "GitHub Repository",
        "url": "https://github.com/nuuuwan/lk_dmc_vis",
    },
    license_info={
        "name": "MIT",
    },
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stations.router, prefix="/stations", tags=["Stations"])
app.include_router(rivers.router, prefix="/rivers", tags=["Rivers"])
app.include_router(basins.router, prefix="/basins", tags=["Basins"])
app.include_router(levels.router, prefix="/levels", tags=["Water Levels"])
app.include_router(alerts.router, prefix="/alerts", tags=["Alerts"])


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": "lk-flood-api",
        "data_source": "https://github.com/nuuuwan/lk_dmc_vis",
    }
