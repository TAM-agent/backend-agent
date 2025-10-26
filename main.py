import os
import logging
import asyncio
import json
import re
import random
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional, Set, Dict

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from prompts import (
    AGENT_DECISION_PROMPT,
    GARDEN_CHAT_PROMPT,
    GARDEN_ADVISOR_PROMPT,
    WEBSOCKET_CHAT_PROMPT,
)

# Configure logging for Cloud Run
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    task = asyncio.create_task(monitor_system())
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
    TOOLS_AVAILABLE = True
    logger.info("Irrigation agent tools loaded successfully")
except Exception as e:
    TOOLS_AVAILABLE = False
    logger.warning(f"Could not load irrigation agent tools: {e}")
    logger.info("API will run in limited mode without irrigation tools")

# Audio configuration constants
DEFAULT_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"
DEFAULT_TTS_MODEL = "eleven_multilingual_v2"
DEFAULT_AUDIO_FORMAT = "mp3_44100_128"


class IrrigationRequest(BaseModel):
    plant: str
    duration: int = 30


class NotificationRequest(BaseModel):
    message: str
    priority: str = "medium"


class ChatRequest(BaseModel):
    message: str
    history: Optional[list] = None
    session_id: Optional[str] = None


    


class CropQuery(BaseModel):
    commodity: str
    year: int
    state: Optional[str] = None


class AdvisorRequest(BaseModel):
    """Request body for garden-level advisor using USDA context."""
    commodity: str
    state: Optional[str] = None
    year: Optional[int] = None
    user_message: Optional[str] = None


class SeedGardenRequest(BaseModel):
    name: str = "Demo Garden"
    personality: str = "neutral"
    latitude: float = 0.0
    longitude: float = 0.0
    plant_count: int = 0
    base_moisture: int = 50
    # Optional sensor history payload to attach at garden level
    history: Optional[list] = None


class TTSRequest(BaseModel):
    text: str
    voice_id: Optional[str] = None
    model_id: Optional[str] = None
    output_format: Optional[str] = None


# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.device_connections: Dict[str, Set[WebSocket]] = {}
        self.websocket_devices: Dict[WebSocket, str] = {}

    async def connect(self, websocket: WebSocket, device_id: str):
        await websocket.accept()
        self.active_connections.add(websocket)
        self.device_connections.setdefault(device_id, set()).add(websocket)
        self.websocket_devices[websocket] = device_id
        logger.info(f"New WebSocket connection. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        did = self.websocket_devices.pop(websocket, None)
        if did and did in self.device_connections:
            conns = self.device_connections.get(did)
            if conns is not None:
                conns.discard(websocket)
                if not conns:
                    self.device_connections.pop(did, None)
        logger.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Send message to all connected clients."""
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error sending to WebSocket: {e}")
                disconnected.add(connection)

        # Clean up disconnected clients
        for connection in disconnected:
            self.disconnect(connection)

    async def send_personal(self, message: dict, websocket: WebSocket):
        """Send message to specific client."""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
            self.disconnect(websocket)

    async def send_to_device(self, device_id: str, message: dict):
        """Send a message to all sockets associated with a device_id."""
        conns = self.device_connections.get(device_id, set())
        disconnected = set()
        for ws in list(conns):
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.error(f"Error sending to device {device_id}: {e}")
                disconnected.add(ws)
        for ws in disconnected:
            self.disconnect(ws)


manager = ConnectionManager()


# Agent decision-making function
async def agent_analyze_and_act(condition: str, data: dict) -> dict:
    """
    Use the agent to analyze a condition and decide what action to take.

    Args:
        condition: Description of the alert condition (e.g., "high temperature", "low moisture")
        data: Relevant sensor data

    Returns:
        Dictionary with agent's decision, explanation, and actions taken
    """
    if not TOOLS_AVAILABLE:
        return {
            "decision": "no_action",
            "explanation": "Agent tools not available",
            "actions": []
        }

    try:
        from irrigation_agent.utils.genai_utils import get_genai_client, extract_text, extract_json_object

        client = get_genai_client()

        # Extract garden personality from data
        personality = data.get("personality", "professional")
        garden_name = data.get("garden_name", "el jardin")

        # Build personality-based communication style
        personality_styles = {
            "friendly": "Usa un tono amigable, carinoso y cercano. Habla como un amigo que cuida sus plantas con amor.",
            "professional": "Usa un tono profesional, tecnico y preciso. Proporciona datos y recomendaciones basadas en mejores practicas.",
            "playful": "Usa un tono divertido, creativo y alegre. Haz que el cuidado de plantas sea entretenido.",
            "caring": "Usa un tono compasivo y maternal. Muestra preocupacion genuina por el bienestar de las plantas.",
            "neutral": "Usa un tono informativo y objetivo. Proporciona hechos sin agregar emociones."
        }
        style_instruction = personality_styles.get(personality, personality_styles["neutral"])

        prompt = AGENT_DECISION_PROMPT.format(
            garden_name=garden_name,
            personality=personality,
            style_instruction=style_instruction,
            condition=condition,
            data=data
        )

        response = client.models.generate_content(
            model=config.worker_model,
            contents=prompt
        )

        # Extract response text
        response_text = extract_text(response)

        # Try to parse JSON from response
        decision_obj, raw_text = extract_json_object(response_text)
        if decision_obj is None:
            decision = {
                "decision": "alerta",
                "explanation": raw_text,
                "priority": "medium"
            }
        else:
            decision = decision_obj

        # Execute actions based on decision
        actions_taken = []
        if decision.get("decision") == "regar" and decision.get("plant_id"):
            try:
                duration = decision.get("action_params", {}).get("duration", 30)
                result = trigger_irrigation(decision["plant_id"], duration)
                actions_taken.append({
                    "type": "irrigation",
                    "plant": decision["plant_id"],
                    "duration": duration,
                    "result": result
                })
            except Exception as e:
                logger.error(f"Error executing irrigation: {e}")
                actions_taken.append({
                    "type": "irrigation",
                    "error": str(e)
                })

        decision["actions_taken"] = actions_taken
        decision["timestamp"] = datetime.now().isoformat()

        # Send Telegram notification for agent decisions
        try:
            from irrigation_agent.service.telegram_service import send_agent_decision_notification
            send_agent_decision_notification(
                garden_name=garden_name,
                plant_name=data.get("plant_name", decision.get("plant_id", "Unknown")),
                decision=decision.get("decision", "unknown"),
                explanation=decision.get("explanation", ""),
                moisture=data.get("moisture", 0),
                priority=decision.get("priority", "medium")
            )
        except Exception as telegram_err:
            logger.warning(f"Failed to send Telegram notification: {telegram_err}")

        return decision

    except Exception as e:
        logger.error(f"Error in agent analysis: {e}")
        return {
            "decision": "error",
            "explanation": f"Error al analizar: {str(e)}",
            "actions": [],
            "timestamp": datetime.now().isoformat()
        }


async def process_garden_monitoring(garden_id: str, garden_data: dict, collect_results: bool = False):
    """Process monitoring for a single garden. Returns alerts and decisions if collect_results=True."""
    if garden_data.get("status") != "success":
        return [], []

    garden_name = garden_data.get("garden_name", garden_id)
    personality = garden_data.get("personality", "neutral")
    alerts = []
    decisions = []

    for plant_id, plant_data in garden_data.get("plant_status", {}).items():
        moisture = plant_data.get("moisture")
        if moisture is None:
            continue

        if moisture < 30:
            alert = {
                "type": "low_moisture",
                "severity": "critical",
                "garden_id": garden_id,
                "garden_name": garden_name,
                "plant_id": plant_id,
                "plant_name": plant_data.get("name", plant_id),
                "moisture": moisture,
                "message": f"[{garden_name}] Humedad critica en {plant_id}: {moisture}%"
            }
            if collect_results:
                alerts.append(alert)

            decision = await agent_analyze_and_act(
                f"Humedad critica detectada en planta {plant_id} del jardin {garden_name}",
                {
                    "garden_id": garden_id,
                    "garden_name": garden_name,
                    "personality": personality,
                    "plant_id": plant_id,
                    "plant_name": plant_data.get("name", plant_id),
                    "moisture": moisture,
                    "threshold": 30,
                    "last_irrigation": plant_data.get("last_irrigation")
                }
            )
            if collect_results:
                decisions.append(decision)

            await manager.broadcast({
                "type": "agent_decision",
                "garden_id": garden_id,
                "garden_name": garden_name,
                "personality": personality,
                "alert": alert,
                "decision": decision,
                "timestamp": datetime.now().isoformat()
            })

        elif moisture < 45:
            alert = {
                "type": "low_moisture",
                "severity": "warning",
                "garden_id": garden_id,
                "garden_name": garden_name,
                "plant_id": plant_id,
                "plant_name": plant_data.get("name", plant_id),
                "moisture": moisture,
                "message": f"[{garden_name}] Humedad baja en {plant_id}: {moisture}%"
            }
            if collect_results:
                alerts.append(alert)

            # Send Telegram alert for low moisture warnings
            try:
                from irrigation_agent.service.telegram_service import send_moisture_alert
                send_moisture_alert(
                    garden_name=garden_name,
                    plant_name=plant_data.get("name", plant_id),
                    moisture=moisture,
                    severity="warning"
                )
            except Exception as telegram_err:
                logger.warning(f"Failed to send Telegram moisture alert: {telegram_err}")

            await manager.broadcast({
                "type": "alert",
                "garden_id": garden_id,
                "garden_name": garden_name,
                "personality": personality,
                "alert": alert,
                "timestamp": datetime.now().isoformat()
            })

    return alerts, decisions


# Background monitoring task
async def monitor_system():
    """
    Continuously monitor ALL gardens and their plants.
    Triggers agent decisions based on garden context and personality.
    Runs as a background task when the application starts.
    """
    logger.info("Starting garden monitoring task")

    while True:
        try:
            if not TOOLS_AVAILABLE:
                await asyncio.sleep(60)
                continue

            # Import garden functions
            from irrigation_agent.tools import get_all_gardens_status

            # Get status for all gardens
            gardens_status = get_all_gardens_status()

            if gardens_status.get("status") != "success":
                logger.error(f"Error getting gardens status: {gardens_status.get('error')}")
                await asyncio.sleep(60)
                continue

            for garden_id, garden_data in gardens_status.get("gardens", {}).items():
                await process_garden_monitoring(garden_id, garden_data, collect_results=False)

            # Sleep for monitoring interval
            monitoring_interval = int(os.getenv('MONITORING_INTERVAL_SECONDS', '30'))
            await asyncio.sleep(monitoring_interval)

        except Exception as e:
            logger.error(f"Error in monitoring task: {e}")
            await asyncio.sleep(60)


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
    if not TOOLS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Irrigation tools not available")
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
    if not TOOLS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Irrigation tools not available")
    try:
        history = get_sensor_history(plant_name, hours)
        return history
    except Exception as e:
        logger.error(f"Error getting history for {plant_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/plant/{plant_name}/health")
async def api_plant_health(plant_name: str):
    """Get plant health assessment."""
    if not TOOLS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Irrigation tools not available")
    try:
        health = analyze_plant_health(plant_name)
        return health
    except Exception as e:
        logger.error(f"Error analyzing health for {plant_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tank")
async def api_tank_level():
    """Get water tank level."""
    if not TOOLS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Irrigation tools not available")
    try:
        tank = check_water_tank_level()
        return tank
    except Exception as e:
        logger.error(f"Error checking tank level: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/weather")
async def api_weather(days: int = Query(default=3, ge=1, le=7)):
    """Get weather forecast."""
    if not TOOLS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Irrigation tools not available")
    try:
        weather = get_weather_forecast(days)
        return weather
    except Exception as e:
        logger.error(f"Error getting weather: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/irrigate")
async def api_irrigate(request: IrrigationRequest):
    """Trigger irrigation for a plant."""
    if not TOOLS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Irrigation tools not available")
    try:
        result = trigger_irrigation(request.plant, request.duration)
        return result
    except Exception as e:
        logger.error(f"Error triggering irrigation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/notify")
async def api_notify(request: NotificationRequest):
    """Send notification."""
    if not TOOLS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Irrigation tools not available")
    try:
        result = send_notification(request.message, request.priority)
        return result
    except Exception as e:
        logger.error(f"Error sending notification: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/monitor/trigger")
async def api_trigger_monitoring():
    """Manually trigger the monitoring system to check all gardens immediately."""
    if not TOOLS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Agent tools not available")

    try:
        logger.info("Manual monitoring trigger requested")

        # Import garden functions
        from irrigation_agent.tools import get_all_gardens_status

        # Get status for all gardens
        gardens_status = get_all_gardens_status()

        if gardens_status.get("status") != "success":
            raise HTTPException(status_code=500, detail=gardens_status.get("error"))

        alerts = []
        decisions = []

        for garden_id, garden_data in gardens_status.get("gardens", {}).items():
            garden_alerts, garden_decisions = await process_garden_monitoring(garden_id, garden_data, collect_results=True)
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
# GARDEN ENDPOINTS (New Architecture)
# ============================================================================

@app.get("/api/gardens")
async def api_get_all_gardens():
    """Get all gardens with their metadata."""
    if not TOOLS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Agent tools not available")

    try:
        from irrigation_agent.tools import get_all_gardens
        result = get_all_gardens()
        return result
    except Exception as e:
        logger.error(f"Error getting all gardens: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/gardens/status")
async def api_get_all_gardens_status():
    """Get status for ALL gardens and their plants."""
    if not TOOLS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Agent tools not available")

    try:
        from irrigation_agent.tools import get_all_gardens_status
        result = get_all_gardens_status()
        return result
    except Exception as e:
        logger.error(f"Error getting gardens status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/gardens/{garden_id}")
async def api_get_garden_status(garden_id: str):
    """Get status for a specific garden and all its plants."""
    if not TOOLS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Agent tools not available")

    try:
        from irrigation_agent.tools import get_garden_status
        result = get_garden_status(garden_id)

        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("error"))

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting garden {garden_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/gardens/{garden_id}/plants/{plant_id}")
async def api_get_plant_in_garden(garden_id: str, plant_id: str):
    """Get detailed status for a specific plant in a garden."""
    if not TOOLS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Agent tools not available")

    try:
        from irrigation_agent.tools import get_plant_in_garden
        result = get_plant_in_garden(garden_id, plant_id)

        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("error"))

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting plant {plant_id} in garden {garden_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/gardens/{garden_id}/plants/{plant_id}/chat")
async def api_chat_with_plant(garden_id: str, plant_id: str, request: ChatRequest):
    """Deprecated: garden has one sensor; chat is garden-scoped."""
    raise HTTPException(status_code=410, detail="El chat por planta ya no esta disponible. Usa POST /api/gardens/{garden_id}/chat")


@app.get("/api/gardens/{garden_id}/weather")
async def api_get_garden_weather(garden_id: str):
    """Get weather forecast for a garden location using Google Weather API."""
    if not TOOLS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Agent tools not available")

    try:
        from irrigation_agent.tools import get_garden_weather
        result = get_garden_weather(garden_id)

        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("error"))

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting weather for garden {garden_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/gardens/{garden_id}/plants/{plant_id}/recommendation")
async def api_get_irrigation_recommendation(garden_id: str, plant_id: str):
    """Get irrigation recommendation with weather analysis for a specific plant."""
    if not TOOLS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Agent tools not available")

    try:
        from irrigation_agent.tools import get_irrigation_recommendation_with_weather
        result = get_irrigation_recommendation_with_weather(garden_id, plant_id)

        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("error"))

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting recommendation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# AGRICULTURE DATA (USDA Quick Stats)
# ============================================================================


@app.get("/api/agriculture/yield")
async def api_agri_yield(
    commodity: str = Query(..., description="Commodity, e.g., CORN, WHEAT"),
    year: int = Query(..., ge=1900, le=2100),
    state: Optional[str] = Query(None, description="State alpha code, e.g., IA"),
):
    """Get crop yield statistics from USDA Quick Stats."""
    try:
        from irrigation_agent.service.agriculture_service import get_crop_yield
        result = get_crop_yield(commodity, year, state)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting crop yield: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/agriculture/area_planted")
async def api_agri_area_planted(
    commodity: str = Query(..., description="Commodity, e.g., CORN, WHEAT"),
    year: int = Query(..., ge=1900, le=2100),
    state: Optional[str] = Query(None, description="State alpha code, e.g., IA"),
):
    """Get area planted statistics from USDA Quick Stats."""
    try:
        from irrigation_agent.service.agriculture_service import get_area_planted
        result = get_area_planted(commodity, year, state)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting area planted: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/agriculture/search")
async def api_agri_search(
    commodity: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
    state: Optional[str] = Query(None),
    statistic: Optional[str] = Query(None, description="statisticcat_desc, e.g., YIELD, AREA PLANTED"),
    unit: Optional[str] = Query(None, description="unit_desc"),
    desc: Optional[str] = Query(None, description="short_desc"),
):
    """Generic USDA Quick Stats search with common filters."""
    try:
        from irrigation_agent.service.agriculture_service import search_quickstats
        result = search_quickstats(
            commodity_desc=commodity,
            year=year,
            state_alpha=state,
            statisticcat_desc=statistic,
            unit_desc=unit,
            short_desc=desc,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in Quick Stats search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/gardens/{garden_id}/advisor")
async def api_garden_advisor(garden_id: str, req: AdvisorRequest):
    """Agent advisor for a garden combining local context with USDA Quick Stats.

    Returns a JSON-structured recommendation at garden level (no per-plant chat).
    """
    if not TOOLS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Agent tools not available")

    try:
        from irrigation_agent.tools import get_garden_status, get_garden_weather
        from irrigation_agent.service.agriculture_service import get_crop_yield, get_area_planted
        from irrigation_agent.utils.genai_utils import get_genai_client, extract_text, extract_json_object

        client = get_genai_client()

        # Garden context
        garden_data = get_garden_status(garden_id)
        if garden_data.get("status") != "success":
            raise HTTPException(status_code=404, detail=garden_data.get("error", "Garden not found"))

        # USDA context (optional fields)
        year = req.year or datetime.now().year
        usda_yield = get_crop_yield(req.commodity, year, req.state)
        usda_area = get_area_planted(req.commodity, year, req.state)

        # Weather context for the garden (optional if API not configured)
        weather = get_garden_weather(garden_id)

        personality = garden_data.get("personality", "neutral")
        garden_name = garden_data.get("garden_name", garden_id)

        context_prompt = GARDEN_ADVISOR_PROMPT.format(
            garden_name=garden_name,
            personality=personality,
            garden_data=garden_data,
            commodity=req.commodity,
            year=year,
            state=req.state or '-',
            usda_yield=usda_yield,
            usda_area=usda_area,
            weather=weather,
            user_message=req.user_message or '',
            weather_available=str(weather.get('status') == 'success').lower()
        )

        response = client.models.generate_content(
            model=config.worker_model,
            contents=context_prompt
        )

        response_text = extract_text(response)
        try:
            data, raw = extract_json_object(response_text)
            if data is None:
                raise json.JSONDecodeError("not json", raw, 0)
            return {
                "garden_id": garden_id,
                "garden_name": garden_name,
                "advisor": data,
                "timestamp": datetime.now().isoformat()
            }
        except json.JSONDecodeError:
            return {
                "garden_id": garden_id,
                "garden_name": garden_name,
                "advisor": {
                    "message": response_text.strip(),
                    "irrigation_action": "monitor",
                    "params": {},
                    "considered": {
                        "usda": {"commodity": req.commodity, "year": year, "state": req.state or ''}
                    },
                    "priority": "info"
                },
                "timestamp": datetime.now().isoformat()
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in garden advisor: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/gardens/{garden_id}/seed")
async def api_seed_garden(garden_id: str, req: SeedGardenRequest):
    """Seed or update a garden with plants in simulation/Firestore for testing."""
    try:
        from irrigation_agent.service.firebase_service import seed_garden
        result = seed_garden(
            garden_id=garden_id,
            name=req.name,
            personality=req.personality,
            latitude=req.latitude,
            longitude=req.longitude,
            plant_count=req.plant_count,
            base_moisture=req.base_moisture,
            history=req.history,
        )
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Seed failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error seeding garden {garden_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# AUDIO: TTS/STT
# ============================================================================


@app.post("/api/audio/tts")
async def api_audio_tts(req: TTSRequest):
    """Text-to-Speech using ElevenLabs. Returns base64 audio data."""
    try:
        # Prefer SDK service from fabian branch if available
        try:
            from irrigation_agent.service.tts_service import convert_text_to_speech
            audio_b64 = convert_text_to_speech(
                req.text,
                voice_id=req.voice_id or DEFAULT_VOICE_ID,
                model_id=req.model_id or DEFAULT_TTS_MODEL,
                output_format=req.output_format or DEFAULT_AUDIO_FORMAT,
            )
            if not audio_b64:
                raise ValueError("TTS conversion failed")
            return {
                "status": "success",
                "audio_base64": audio_b64,
                "voice_id": req.voice_id or DEFAULT_VOICE_ID,
                "model_id": req.model_id or DEFAULT_TTS_MODEL,
                "format": req.output_format or DEFAULT_AUDIO_FORMAT,
                "timestamp": datetime.now().isoformat(),
            }
        except (ImportError, AttributeError, ValueError):
            from irrigation_agent.service.audio_service import tts_elevenlabs
            result = tts_elevenlabs(
                text=req.text,
                voice_id=req.voice_id or DEFAULT_VOICE_ID,
                model_id=req.model_id or DEFAULT_TTS_MODEL,
                output_format=req.output_format or DEFAULT_AUDIO_FORMAT,
            )
            if result.get("status") == "error":
                raise HTTPException(status_code=400, detail=result.get("error"))
            return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in TTS: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/audio/stt")
async def api_audio_stt(file: UploadFile = File(...)):
    """Speech-to-Text using ElevenLabs STT (best-effort)."""
    try:
        file_bytes = await file.read()
        # Prefer SDK service if available
        try:
            from irrigation_agent.service.stt_service import convert_audio_to_text
            text = convert_audio_to_text(file_bytes)
            if not text:
                raise ValueError("STT failed")
            return {
                "status": "success",
                "text": text,
                "timestamp": datetime.now().isoformat(),
            }
        except (ImportError, AttributeError, ValueError):
            from irrigation_agent.service.audio_service import stt_elevenlabs
            result = stt_elevenlabs(file_bytes)
            if result.get("status") == "error":
                raise HTTPException(status_code=400, detail=result.get("error"))
            return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in STT: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/voice/gardens/{garden_id}/talk")
async def api_voice_garden_talk(
    garden_id: str,
    request: Request,
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
    tts: Optional[bool] = Form(True),
    voice_id: Optional[str] = Form(None),
    model_id: Optional[str] = Form(None),
    output_format: Optional[str] = Form(None),
):
    """Unified voice endpoint: STT (if audio) -> garden chat -> TTS (optional).

    Accepts either:
    - multipart/form-data with `file` (audio) and optional form fields, or
    - application/json with { text, history?, tts?, voice_id?, model_id?, output_format? }.
    """
    try:
        # Resolve inputs from multipart or JSON
        input_text: Optional[str] = None
        history = None
        modality = ""

        if file is not None:
            # Audio path: STT first
            modality = "audio"
            audio_bytes = await file.read()
            from irrigation_agent.service.stt_service import convert_audio_to_text

            transcript = convert_audio_to_text(audio_bytes)
            if not transcript:
                raise HTTPException(status_code=400, detail="STT failed or empty transcript")
            input_text = transcript
        elif text:
            modality = "text"
            input_text = text
        else:
            # Try JSON body
            try:
                payload = await request.json()
                modality = payload.get("modality", "text")
                input_text = payload.get("text")
                history = payload.get("history")
                if "tts" in payload:
                    tts = bool(payload.get("tts"))
                voice_id = payload.get("voice_id", voice_id)
                model_id = payload.get("model_id", model_id)
                output_format = payload.get("output_format", output_format)
            except Exception:
                pass

        if not input_text:
            raise HTTPException(status_code=400, detail="Provide audio file or text")

        # Run garden chat using existing endpoint logic
        chat_req = ChatRequest(message=input_text, history=history)
        chat_result = await api_garden_chat(garden_id, chat_req)

        if not isinstance(chat_result, dict) or not chat_result.get("garden_id"):
            raise HTTPException(status_code=500, detail="Chat processing failed")

        response_text = str(chat_result.get("message", "")).strip()

        out = {
            "status": "success",
            "garden_id": garden_id,
            "modality": modality or ("audio" if file else "text"),
            "input_text": input_text,
            "chat": chat_result,
            "timestamp": datetime.now().isoformat(),
        }

        # Optional TTS of the agent response
        if (tts is None or bool(tts)) and response_text:
            try:
                from irrigation_agent.service.tts_service import convert_text_to_speech
                audio_b64 = convert_text_to_speech(
                    response_text,
                    voice_id=voice_id or DEFAULT_VOICE_ID,
                    model_id=model_id or DEFAULT_TTS_MODEL,
                    output_format=output_format or DEFAULT_AUDIO_FORMAT,
                )
                if audio_b64:
                    out.update({
                        "audio_base64": audio_b64,
                        "voice_id": voice_id or DEFAULT_VOICE_ID,
                        "format": output_format or DEFAULT_AUDIO_FORMAT,
                    })
            except Exception as tts_err:
                logger.warning(f"TTS step failed: {tts_err}")

        return out
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in unified voice talk: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/gardens/{garden_id}/images/analyze")
async def api_garden_image_analyze(garden_id: str, file: UploadFile = File(...)):
    """Upload an image and return plant health analysis (disease, causes, cures)."""
    try:
        data = await file.read()
        content_type = file.content_type or "image/jpeg"
        from irrigation_agent.service.image_service import analyze_plant_image, store_image_record

        analysis = analyze_plant_image(data, content_type)
        if analysis.get("status") != "success":
            raise HTTPException(status_code=400, detail=analysis.get("error", "analysis failed"))

        store = store_image_record(garden_id, data, content_type, analysis.get("analysis", {}))
        if store.get("status") != "success":
            logger.warning(f"Image stored locally or failed: {store}")

        return {
            "status": "success",
            "garden_id": garden_id,
            "doc_id": store.get("doc_id"),
            "analysis": analysis.get("analysis"),
            "timestamp": datetime.now().isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing image: {e}")
        raise HTTPException(status_code=500, detail=str(e))
@app.post("/api/gardens/{garden_id}/chat")
async def api_garden_chat(garden_id: str, request: ChatRequest):
    """Chat del asistente a nivel de jardin (incluye info de plantas como contexto)."""
    if not TOOLS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Agent tools not available")

    try:
        from irrigation_agent.utils.genai_utils import get_genai_client, extract_text, extract_json_object
        from irrigation_agent.tools import get_garden_status

        client = get_genai_client()
        garden_data = get_garden_status(garden_id)
        if garden_data.get("status") != "success":
            raise HTTPException(status_code=404, detail=garden_data.get("error", "Garden not found"))
        personality = garden_data.get("personality", "neutral")
        garden_name = garden_data.get("garden_name", garden_id)

        # Simulate a small data tick on each chat in simulation mode
        _maybe_simulate_garden(garden_id)

        # Build garden type and recent history text (last 10)
        garden_type = garden_data.get("garden_type") or garden_data.get("plant_type", "unknown")
        history_text = ""
        try:
            if request.history:
                flat: list[str] = []
                for h in request.history:
                    if isinstance(h, str):
                        flat.append(h)
                    elif isinstance(h, dict) and "content" in h:
                        flat.append(str(h.get("content")))
                    else:
                        flat.append(str(h))
                recent = flat[-10:]
                if recent:
                    history_text = "\n".join(f"- {item}" for item in recent)
        except Exception as _hist_err:
            logger.warning(f"Failed to process chat history: {_hist_err}")

        context_prompt = GARDEN_CHAT_PROMPT.format(
            garden_type=garden_type,
            garden_name=garden_name,
            personality=personality,
            garden_data=garden_data,
            history_text=history_text or 'N/A',
            message=request.message
        )

        # Determine session_id (reuse if provided)
        import uuid as _uuid
        session_id = request.session_id or str(_uuid.uuid4())

        # Log user turn into sessions (best-effort)
        try:
            from irrigation_agent.service.firebase_service import add_session_message
            add_session_message(garden_id, "user", str(request.message), {"garden_name": garden_name}, session_id=session_id)
        except Exception:
            pass

        response = client.models.generate_content(
            model=config.worker_model,
            contents=context_prompt
        )

        # Extract and parse response
        response_text = extract_text(response)

        try:
            response_data, raw_text = extract_json_object(response_text)
            if response_data is None:
                raise json.JSONDecodeError("not json", raw_text, 0)
            _msg = str(response_data.get("message", response_text)).strip()
            try:
                from irrigation_agent.service.firebase_service import add_session_message
                add_session_message(garden_id, "assistant", _msg, {"garden_name": garden_name}, session_id=session_id)
            except Exception:
                pass
            return {
                "garden_id": garden_id,
                "garden_name": garden_name,
                "session_id": session_id,
                "message": _msg,
                "plants_summary": response_data.get("plants_summary", []),
                "data": response_data.get("data", {}),
                "suggestions": response_data.get("suggestions", []),
                "priority": response_data.get("priority", "info"),
                "timestamp": datetime.now().isoformat()
            }
        except json.JSONDecodeError:
            _fallback_msg = response_text.strip()
            try:
                from irrigation_agent.service.firebase_service import add_session_message
                add_session_message(garden_id, "assistant", _fallback_msg, {"garden_name": garden_name}, session_id=session_id)
            except Exception:
                pass
            return {
                "garden_id": garden_id,
                "garden_name": garden_name,
                "session_id": session_id,
                "message": _fallback_msg,
                "plants_summary": [],
                "data": {},
                "suggestions": [],
                "priority": "info",
                "timestamp": datetime.now().isoformat()
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in garden chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _maybe_simulate_garden(garden_id: str) -> None:
    """If in simulation mode, vary plant moisture slightly to simulate updates."""
    try:
        if os.getenv('USE_SIMULATION', 'false').lower() != 'true':
            return
        from irrigation_agent.service.firebase_service import simulator
        plants = simulator.get_garden_plants(garden_id)
        for pid, pdata in plants.items():
            current = pdata.get('current_moisture') or 50
            new = max(0, min(100, int(current) + random.randint(-3, 3)))
            simulator.update_garden_plant_moisture(garden_id, pid, new)
    except Exception as e:
        logger.warning(f"Simulation update failed for garden {garden_id}: {e}")


@app.post("/api/chat")
async def api_chat(request: ChatRequest):
    """Deprecated: use garden-scoped chat endpoint."""
    raise HTTPException(status_code=400, detail="El chat es por jardin. Usa POST /api/gardens/{garden_id}/chat")


@app.websocket("/ws/{device_id}")
async def websocket_endpoint(websocket: WebSocket, device_id: str):
    """
    WebSocket endpoint for real-time notifications and agent communications.

    The client connects to this endpoint to receive:
    - Real-time alerts (low moisture, low tank, high temperature)
    - Agent decisions and explanations
    - Irrigation actions taken automatically
    - System status updates

    Messages sent to clients have this format:
    {
        "type": "alert" | "agent_decision" | "system_update" | "chat_response",
        "data": {...},
        "timestamp": "ISO timestamp"
    }
    """
    await manager.connect(websocket, device_id)

    try:
        # Send welcome message
        await manager.send_personal({
            "type": "connection",
            "message": "Conectado a GrowthAI - Sistema de Irrigacion Inteligente",
            "device_id": device_id,
            "timestamp": datetime.now().isoformat()
        }, websocket)

        # Listen for incoming messages from client
        while True:
            data = await websocket.receive_json()

            message_type = data.get("type")

            # Relay device-originated events as normalized notifications
            relay_types = {"alert", "agent_decision", "system_update", "event"}
            if message_type in relay_types:
                payload = {
                    "type": message_type,
                    "device_id": device_id,
                    "garden_id": data.get("garden_id"),
                    "data": data.get("data", data),
                    "timestamp": datetime.now().isoformat(),
                }
                await manager.broadcast(payload)
                continue

            if message_type == "ping":
                await manager.send_personal({
                    "type": "pong",
                    "device_id": device_id,
                    "timestamp": datetime.now().isoformat()
                }, websocket)
                continue

            if message_type == "chat":
                # Garden-scoped chat: require garden_id and include plants info as context
                user_message = data.get("message", "")
                garden_id = data.get("garden_id")

                if not TOOLS_AVAILABLE:
                    await manager.send_personal({
                        "type": "chat_response",
                        "response": "Lo siento, el agente no esta disponible en este momento.",
                        "timestamp": datetime.now().isoformat()
                    }, websocket)
                    continue

                if not garden_id:
                    await manager.send_personal({
                        "type": "error",
                        "message": "El chat es por jardin. Incluye 'garden_id' en el mensaje.",
                        "timestamp": datetime.now().isoformat()
                    }, websocket)
                    continue

                try:
                    from irrigation_agent.utils.genai_utils import get_genai_client, extract_text, extract_json_object
                    from irrigation_agent.tools import get_garden_status

                    client = get_genai_client()
                    garden_data = get_garden_status(garden_id)
                    if garden_data.get("status") != "success":
                        await manager.send_personal({
                            "type": "error",
                            "message": f"Jardin '{garden_id}' no encontrado o sin datos",
                            "timestamp": datetime.now().isoformat()
                        }, websocket)
                        continue

                    personality = garden_data.get("personality", "neutral")
                    garden_name = garden_data.get("garden_name", garden_id)

                    context_prompt = WEBSOCKET_CHAT_PROMPT.format(
                        garden_name=garden_name,
                        personality=personality,
                        garden_data=garden_data,
                        user_message=user_message
                    )

                    response = client.models.generate_content(
                        model=config.worker_model,
                        contents=context_prompt
                    )

                    response_text = extract_text(response)

                    try:
                        response_data, raw_text = extract_json_object(response_text)
                        if response_data is None:
                            raise json.JSONDecodeError("not json", raw_text, 0)

                        _ws_msg = str(response_data.get("message", "")).strip()
                        if garden_name and garden_name.lower() not in _ws_msg.lower():
                            _ws_msg = f"{garden_name}: {_ws_msg}"
                        await manager.send_personal({
                            "type": "chat_response",
                            "garden_id": garden_id,
                            "garden_name": garden_name,
                            "message": _ws_msg,
                            "plants_summary": response_data.get("plants_summary", []),
                            "data": response_data.get("data", {}),
                            "suggestions": response_data.get("suggestions", []),
                            "priority": response_data.get("priority", "info"),
                            "timestamp": datetime.now().isoformat()
                        }, websocket)

                    except (json.JSONDecodeError, AttributeError):
                        _ws_fallback = response_text.strip()
                        if garden_name and garden_name.lower() not in _ws_fallback.lower():
                            _ws_fallback = f"{garden_name}: {_ws_fallback}"
                        await manager.send_personal({
                            "type": "chat_response",
                            "garden_id": garden_id,
                            "garden_name": garden_name,
                            "message": _ws_fallback,
                            "plants_summary": [],
                            "data": {},
                            "suggestions": [],
                            "priority": "info",
                            "timestamp": datetime.now().isoformat()
                        }, websocket)

                except Exception as e:
                    logger.error(f"Error in WebSocket garden chat: {e}")
                    await manager.send_personal({
                        "type": "error",
                        "message": f"Error al procesar mensaje: {str(e)}",
                        "timestamp": datetime.now().isoformat()
                    }, websocket)

            elif message_type == "request_status":
                # Client requesting current system status
                try:
                    status = get_system_status()
                    await manager.send_personal({
                        "type": "system_status",
                        "data": status,
                        "timestamp": datetime.now().isoformat()
                    }, websocket)
                except Exception as e:
                    logger.error(f"Error getting status: {e}")
                    await manager.send_personal({
                        "type": "error",
                        "message": str(e),
                        "timestamp": datetime.now().isoformat()
                    }, websocket)

            elif message_type == "ping":
                # Keep-alive ping
                await manager.send_personal({
                    "type": "pong",
                    "timestamp": datetime.now().isoformat()
                }, websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn

    # Get port from environment (Cloud Run sets PORT)
    port = int(os.environ.get("PORT", 8080))

    # Start server
    logger.info(f"Starting Intelligent Irrigation Agent API on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)




# Chat session retrieval
@app.get("/api/chat/{session_id}")
async def api_get_chat_session(session_id: str):
    try:
        from irrigation_agent.service.firebase_service import get_session_messages
        return get_session_messages(session_id)
    except Exception as e:
        logger.error(f"Error retrieving session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
