import os
import logging
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Configure logging for Cloud Run
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Intelligent Irrigation Agent API",
    description="Multi-agent irrigation system using Google Gemini ADK",
    version="0.1.0"
)

# Try to import irrigation_agent modules, but don't fail if they're not available
try:
    from irrigation_agent.tools import (
        get_system_status,
        check_soil_moisture,
        check_water_tank_level,
        get_sensor_history,
        trigger_irrigation,
        get_weather_forecast,
        analyze_plant_health,
        send_notification
    )
    from irrigation_agent.config import config
    from irrigation_agent.agent import intelligent_irrigation_agent
    TOOLS_AVAILABLE = True
    AGENT_AVAILABLE = True
    logger.info("Irrigation agent tools loaded successfully")
except Exception as e:
    TOOLS_AVAILABLE = False
    AGENT_AVAILABLE = False
    logger.warning(f"Could not load irrigation agent tools: {e}")
    logger.info("API will run in limited mode without irrigation tools")



class IrrigationRequest(BaseModel):
    plant: str
    duration: int = 30


class NotificationRequest(BaseModel):
    message: str
    priority: str = "medium"


class ChatRequest(BaseModel):
    message: str
    history: Optional[list] = None




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


@app.get("/api/plant/{plant_name}/moisture")
async def api_soil_moisture(plant_name: str):
    """Get soil moisture for specific plant."""
    try:
        moisture = check_soil_moisture(plant_name)
        return moisture
    except Exception as e:
        logger.error(f"Error checking moisture for {plant_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/plant/{plant_name}/history")
async def api_sensor_history(
    plant_name: str,
    hours: int = Query(default=24, ge=1, le=168)
):
    """Get historical sensor data for plant."""
    try:
        history = get_sensor_history(plant_name, hours)
        return history
    except Exception as e:
        logger.error(f"Error getting history for {plant_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/plant/{plant_name}/health")
async def api_plant_health(plant_name: str):
    """Get plant health assessment."""
    try:
        health = analyze_plant_health(plant_name)
        return health
    except Exception as e:
        logger.error(f"Error analyzing health for {plant_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tank")
async def api_tank_level():
    """Get water tank level."""
    try:
        tank = check_water_tank_level()
        return tank
    except Exception as e:
        logger.error(f"Error checking tank level: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/weather")
async def api_weather(days: int = Query(default=3, ge=1, le=7)):
    """Get weather forecast."""
    try:
        weather = get_weather_forecast(days)
        return weather
    except Exception as e:
        logger.error(f"Error getting weather: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/irrigate")
async def api_irrigate(request: IrrigationRequest):
    """Trigger irrigation for a plant."""
    try:
        result = trigger_irrigation(request.plant, request.duration)
        return result
    except Exception as e:
        logger.error(f"Error triggering irrigation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/notify")
async def api_notify(request: NotificationRequest):
    """Send notification."""
    try:
        result = send_notification(request.message, request.priority)
        return result
    except Exception as e:
        logger.error(f"Error sending notification: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat")
async def api_chat(request: ChatRequest):
    """Chat with the intelligent irrigation agent."""
    if not AGENT_AVAILABLE:
        raise HTTPException(status_code=503, detail="Agent not available")

    try:
        response = intelligent_irrigation_agent.send_message(
            message=request.message,
            history=request.history or []
        )

        return {
            "response": response.text,
            "timestamp": datetime.now().isoformat(),
            "status": "success"
        }
    except Exception as e:
        logger.error(f"Error in chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    # Get port from environment (Cloud Run sets PORT)
    port = int(os.environ.get("PORT", 8080))

    # Start server
    logger.info(f"Starting Intelligent Irrigation Agent API on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
