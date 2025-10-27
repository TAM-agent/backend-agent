"""
Intelligent Irrigation Agent API - Main Application

"""
import os
import logging
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from functools import partial

from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware

# Configure logging for Cloud Run
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Try to import irrigation_agent modules, but don't fail if they're not available
try:
    from irrigation_agent.tools import get_system_status
    from irrigation_agent.config import config
    TOOLS_AVAILABLE = True
    logger.info("Irrigation agent tools loaded successfully")
except Exception as e:
    TOOLS_AVAILABLE = False
    config = None
    logger.warning(f"Could not load irrigation agent tools: {e}")
    logger.info("API will run in limited mode without irrigation tools")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    from api.services.monitoring import monitor_system

    task = asyncio.create_task(monitor_system(TOOLS_AVAILABLE))
    logger.info("Background monitoring task started")
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        logger.info("Background monitoring task stopped")


app = FastAPI(
    title="Intelligent Irrigation Agent API",
    description="Multi-agent irrigation system using Google Gemini ADK",
    version="0.1.0",
    lifespan=lifespan
)

# Configure CORS
allowed_origins_env = os.getenv("ALLOWED_ORIGINS")
if allowed_origins_env:
    allowed_origins = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]
else:
    allowed_origins = ["*"]

allow_credentials = os.getenv("ALLOW_CREDENTIALS", "false").lower() == "true"

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# ROOT AND HEALTH ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint - API information."""
    return {
        "service": "Intelligent Irrigation Agent",
        "status": "running",
        "version": "0.1.0",
        "timestamp": datetime.now().isoformat(),
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health")
async def health():
    """Health check endpoint for Cloud Run."""
    try:
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "tools_available": TOOLS_AVAILABLE
        }

        if TOOLS_AVAILABLE:
            # Verify configuration is loaded
            _ = config.worker_model
            health_status["config_loaded"] = True

        return health_status
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/api/status")
async def api_system_status():
    """Get comprehensive system status."""
    if not TOOLS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Irrigation tools not available")

    try:
        status = get_system_status()
        return status
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/monitor/trigger")
async def api_trigger_monitoring():
    """Manually trigger the monitoring system to check all gardens immediately."""
    if not TOOLS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Agent tools not available")

    try:
        logger.info("Manual monitoring trigger requested")

        from irrigation_agent.tools import get_all_gardens_status
        from api.services.monitoring import process_garden_monitoring
        from api.websocket import manager

        # Get status for all gardens
        gardens_status = get_all_gardens_status()

        if gardens_status.get("status") != "success":
            raise HTTPException(status_code=500, detail=gardens_status.get("error"))

        alerts = []
        decisions = []

        for garden_id, garden_data in gardens_status.get("gardens", {}).items():
            garden_alerts, garden_decisions = await process_garden_monitoring(
                garden_id,
                garden_data,
                manager,
                TOOLS_AVAILABLE,
                config,
                collect_results=True
            )
            alerts.extend(garden_alerts)
            decisions.extend(garden_decisions)

        return {
            "status": "success",
            "alerts_found": len(alerts),
            "decisions_made": len(decisions),
            "alerts": alerts,
            "decisions": decisions,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error in manual monitoring: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# WEBSOCKET ENDPOINT
# ============================================================================

@app.websocket("/ws/{device_id}")
async def websocket_route(websocket: WebSocket, device_id: str):
    """WebSocket endpoint for real-time notifications and agent communications."""
    from api.websocket import websocket_endpoint
    await websocket_endpoint(websocket, device_id, TOOLS_AVAILABLE, config)


# ============================================================================
# REGISTER ROUTERS
# ============================================================================

# Import routers
from api.routers import plants, gardens, agriculture, audio

# Create partial functions to inject dependencies into routers
# This allows routers to access TOOLS_AVAILABLE and config without global imports
def inject_dependencies(router_module):
    """Inject TOOLS_AVAILABLE and config into router endpoints."""
    for route in router_module.router.routes:
        if hasattr(route, 'endpoint'):
            # Add default values for tools_available and config parameters
            endpoint = route.endpoint
            if 'tools_available' in endpoint.__code__.co_varnames:
                # Use partial to inject TOOLS_AVAILABLE as default
                route.endpoint = partial(endpoint, tools_available=TOOLS_AVAILABLE)
            if 'config' in endpoint.__code__.co_varnames:
                # Use partial to inject config as default
                route.endpoint = partial(endpoint, config=config)

# Apply dependency injection
inject_dependencies(plants)
inject_dependencies(gardens)
inject_dependencies(agriculture)
inject_dependencies(audio)

# Register all routers
app.include_router(plants.router)
app.include_router(gardens.router)
app.include_router(agriculture.router)
app.include_router(audio.router)

logger.info("All routers registered successfully")


# ============================================================================
# APPLICATION ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    # Get port from environment (Cloud Run sets PORT)
    port = int(os.environ.get("PORT", 8080))

    # Start server
    logger.info(f"Starting Intelligent Irrigation Agent API on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
