"""Legacy plant endpoints (flat model, single plant operations)."""
import logging
from fastapi import APIRouter, HTTPException, Query

from api.models import IrrigationRequest, NotificationRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Plants (Legacy)"])


def check_tools_available(tools_available: bool):
    """Helper to check if tools are available."""
    if not tools_available:
        raise HTTPException(status_code=503, detail="Irrigation tools not available")


@router.get("/plant/{plant_name}/moisture")
async def get_soil_moisture(plant_name: str, tools_available: bool):
    """Get soil moisture for specific plant."""
    check_tools_available(tools_available)
    try:
        from irrigation_agent.tools import check_soil_moisture
        moisture = check_soil_moisture(plant_name)
        return moisture
    except Exception as e:
        logger.error(f"Error checking moisture for {plant_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/plant/{plant_name}/history")
async def get_sensor_history(
    plant_name: str,
    hours: int = Query(default=24, ge=1, le=168),
    tools_available: bool = True
):
    """Get historical sensor data for plant."""
    check_tools_available(tools_available)
    try:
        from irrigation_agent.tools import get_sensor_history as get_history
        history = get_history(plant_name, hours)
        return history
    except Exception as e:
        logger.error(f"Error getting history for {plant_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/plant/{plant_name}/health")
async def get_plant_health(plant_name: str, tools_available: bool = True):
    """Get plant health assessment."""
    check_tools_available(tools_available)
    try:
        from irrigation_agent.tools import analyze_plant_health
        health = analyze_plant_health(plant_name)
        return health
    except Exception as e:
        logger.error(f"Error analyzing health for {plant_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tank")
async def get_tank_level(tools_available: bool = True):
    """Get water tank level."""
    check_tools_available(tools_available)
    try:
        from irrigation_agent.tools import check_water_tank_level
        tank = check_water_tank_level()
        return tank
    except Exception as e:
        logger.error(f"Error checking tank level: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/weather")
async def get_weather(days: int = Query(default=3, ge=1, le=7), tools_available: bool = True):
    """Get weather forecast."""
    check_tools_available(tools_available)
    try:
        from irrigation_agent.tools import get_weather_forecast
        weather = get_weather_forecast(days)
        return weather
    except Exception as e:
        logger.error(f"Error getting weather: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/irrigate")
async def trigger_irrigation_endpoint(request: IrrigationRequest, tools_available: bool = True):
    """Trigger irrigation for a plant."""
    check_tools_available(tools_available)
    try:
        from irrigation_agent.tools import trigger_irrigation
        result = trigger_irrigation(request.plant, request.duration)
        return result
    except Exception as e:
        logger.error(f"Error triggering irrigation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/notify")
async def send_notification_endpoint(request: NotificationRequest, tools_available: bool = True):
    """Send notification."""
    check_tools_available(tools_available)
    try:
        from irrigation_agent.tools import send_notification
        result = send_notification(request.message, request.priority)
        return result
    except Exception as e:
        logger.error(f"Error sending notification: {e}")
        raise HTTPException(status_code=500, detail=str(e))
