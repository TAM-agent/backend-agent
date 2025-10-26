import os
import logging
import asyncio
import json
import re
from datetime import datetime
from typing import Optional, Set

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddlewares
from pydantic import BaseModel

from irrigation_agent.stt_service import convert_audio_to_text

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

# Configure CORS (parametrized by env)
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



class IrrigationRequest(BaseModel):
    plant: str
    duration: int = 30


class NotificationRequest(BaseModel):
    message: str
    priority: str = "medium"


class ChatRequest(BaseModel):
    message: str
    history: Optional[list] = None


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


class TTSRequest(BaseModel):
    text: str
    voice_id: Optional[str] = None
    model_id: Optional[str] = None
    output_format: Optional[str] = None


# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"New WebSocket connection. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
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
        from irrigation_agent.genai_utils import get_genai_client, extract_text, extract_json_object

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

        # Build context prompt for the agent
        prompt = f"""Eres GrowthAI, un agente inteligente de irrigacion para el jardin '{garden_name}'.

PERSONALIDAD DEL JARDIN: {personality}
ESTILO DE COMUNICACION: {style_instruction}

SITUACION ACTUAL:
{condition}

DATOS DEL SISTEMA:
{data}

Analiza la situacion y decide:
1. ¿Que accion inmediata se debe tomar? (regar, no hacer nada, ajustar configuracion, etc.)
2. ¿Por que es necesaria esta accion?
3. ¿Cuales son los parametros especificos? (duracion del riego, cantidad de agua, etc.)

IMPORTANTE: Tu explanation debe reflejar la personalidad '{personality}' del jardin.

Responde en formato JSON con esta estructura:
{{
    "decision": "regar|esperar|alerta|ajustar",
    "plant_id": "ID de la planta afectada",
    "garden_id": "ID del jardin",
    "action_params": {{"duration": 30, "reason": "..."}},
    "explanation": "Explicacion clara y concisa para el usuario en tono {personality}",
    "priority": "critical|high|medium|low"
}}"""

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

        return decision

    except Exception as e:
        logger.error(f"Error in agent analysis: {e}")
        return {
            "decision": "error",
            "explanation": f"Error al analizar: {str(e)}",
            "actions": [],
            "timestamp": datetime.now().isoformat()
        }


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

            # Monitor each garden
            for garden_id, garden_data in gardens_status.get("gardens", {}).items():
                if garden_data.get("status") != "success":
                    continue

                garden_name = garden_data.get("garden_name", garden_id)
                personality = garden_data.get("personality", "neutral")

                # Check each plant in this garden
                for plant_id, plant_data in garden_data.get("plant_status", {}).items():
                    moisture = plant_data.get("moisture", 0)

                    # Critical: Very low moisture
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

                        # Let agent decide and act with garden context
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

                        # Broadcast to all connected clients with garden context
                        await manager.broadcast({
                            "type": "agent_decision",
                            "garden_id": garden_id,
                            "garden_name": garden_name,
                            "personality": personality,
                            "alert": alert,
                            "decision": decision,
                            "timestamp": datetime.now().isoformat()
                        })

                    # Warning: Low moisture
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

                        await manager.broadcast({
                            "type": "alert",
                            "garden_id": garden_id,
                            "garden_name": garden_name,
                            "personality": personality,
                            "alert": alert,
                            "timestamp": datetime.now().isoformat()
                        })

            # Sleep for monitoring interval
            monitoring_interval = int(os.getenv('MONITORING_INTERVAL_SECONDS', '30'))
            await asyncio.sleep(monitoring_interval)

        except Exception as e:
            logger.error(f"Error in monitoring task: {e}")
            await asyncio.sleep(60)


@app.on_event("startup")
async def startup_event():
    """Start background monitoring task when application starts."""
    asyncio.create_task(monitor_system())
    logger.info("Background monitoring task started")


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

        # Monitor each garden
        for garden_id, garden_data in gardens_status.get("gardens", {}).items():
            if garden_data.get("status") != "success":
                continue

            garden_name = garden_data.get("garden_name", garden_id)
            personality = garden_data.get("personality", "neutral")

            # Check each plant in this garden
            for plant_id, plant_data in garden_data.get("plant_status", {}).items():
                moisture = plant_data.get("moisture", 0)

                # Critical: Very low moisture
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
                    alerts.append(alert)

                    # Let agent decide and act with garden context
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
                    decisions.append(decision)

                    # Broadcast to all connected clients with garden context
                    await manager.broadcast({
                        "type": "agent_decision",
                        "garden_id": garden_id,
                        "garden_name": garden_name,
                        "personality": personality,
                        "alert": alert,
                        "decision": decision,
                        "timestamp": datetime.now().isoformat()
                    })

                # Warning: Low moisture
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
                    alerts.append(alert)

                    await manager.broadcast({
                        "type": "alert",
                        "garden_id": garden_id,
                        "garden_name": garden_name,
                        "personality": personality,
                        "alert": alert,
                        "timestamp": datetime.now().isoformat()
                    })

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
        from irrigation_agent.agriculture_service import get_crop_yield
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
        from irrigation_agent.agriculture_service import get_area_planted
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
        from irrigation_agent.agriculture_service import search_quickstats
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
        from irrigation_agent.agriculture_service import get_crop_yield, get_area_planted
        from irrigation_agent.genai_utils import get_genai_client, extract_text, extract_json_object

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

        context_prompt = f"""Eres GrowthAI, asesor inteligente de riego para el jardin '{garden_name}'.

PERSONALIDAD: {personality}

ESTADO DEL JARDIN (incluye plantas):
{garden_data}

ESTADISTICAS AGRICOLAS (USDA Quick Stats):
- Commodity: {req.commodity}  Year: {year}  State: {req.state or '-'}
- YIELD: {usda_yield}
- AREA PLANTED: {usda_area}

CLIMA (si disponible):
{weather}

MENSAJE DEL USUARIO (opcional):
{req.user_message or ''}

IMPORTANTE: Responde SIEMPRE en formato JSON con esta estructura:
{{
  "message": "Recomendacion en texto natural",
  "irrigation_action": "irrigate_now|irrigate_soon|monitor|skip",
  "params": {{"duration": 0}},
  "considered": {{
     "usda": {{"commodity": "{req.commodity}", "year": {year}, "state": "{req.state or ''}"}},
     "garden": {{"plants": "resumen"}},
     "weather": {{"available": {str(weather.get('status') == 'success').lower()} }}
  }},
  "priority": "info|warning|alert"
}}

Reglas:
- No converses con plantas individuales. Habla a nivel de jardin.
- Explica brevemente como las estadisticas USDA y el clima influyen en la recomendacion (tendencias macro, etapa del cultivo, lluvia/temperatura). 
- Responde en español.
"""

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


# ============================================================================
# AUDIO: TTS/STT
# ============================================================================


@app.post("/api/audio/tts")
async def api_audio_tts(req: TTSRequest):
    """Text-to-Speech using ElevenLabs. Returns base64 audio data."""
    try:
        # Prefer SDK service from fabian branch if available
        try:
            from irrigation_agent.tts_service import convert_text_to_speech
            audio_b64 = convert_text_to_speech(
                req.text,
                voice_id=req.voice_id or "JBFqnCBsd6RMkjVDRZzb",
                model_id=req.model_id or "eleven_multilingual_v2",
                output_format=req.output_format or "mp3_44100_128",
            )
            if not audio_b64:
                raise ValueError("TTS conversion failed")
            return {
                "status": "success",
                "audio_base64": audio_b64,
                "voice_id": req.voice_id or "JBFqnCBsd6RMkjVDRZzb",
                "model_id": req.model_id or "eleven_multilingual_v2",
                "format": req.output_format or "mp3_44100_128",
                "timestamp": datetime.now().isoformat(),
            }
        except Exception:
            from irrigation_agent.audio_service import tts_elevenlabs
            result = tts_elevenlabs(
                text=req.text,
                voice_id=req.voice_id or "JBFqnCBsd6RMkjVDRZzb",
                model_id=req.model_id or "eleven_multilingual_v2",
                output_format=req.output_format or "mp3_44100_128",
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
            from irrigation_agent.stt_service import convert_audio_to_text
            text = convert_audio_to_text(file_bytes)
            if not text:
                raise ValueError("STT failed")
            return {
                "status": "success",
                "text": text,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception:
            from irrigation_agent.audio_service import stt_elevenlabs
            result = stt_elevenlabs(file_bytes)
            if result.get("status") == "error":
                raise HTTPException(status_code=400, detail=result.get("error"))
            return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in STT: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/gardens/{garden_id}/chat")
async def api_garden_chat(garden_id: str, request: ChatRequest):
    """Chat del asistente a nivel de jardin (incluye info de plantas como contexto)."""
    if not TOOLS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Agent tools not available")

    try:
        from irrigation_agent.genai_utils import get_genai_client, extract_text, extract_json_object
        from irrigation_agent.tools import get_garden_status

        client = get_genai_client()

        garden_data = get_garden_status(garden_id)
        if garden_data.get("status") != "success":
            raise HTTPException(status_code=404, detail=garden_data.get("error", "Garden not found"))

        personality = garden_data.get("personality", "neutral")
        garden_name = garden_data.get("garden_name", garden_id)

        context_prompt = f"""Eres GrowthAI, asistente de riego para el jardin '{garden_name}'.

PERSONALIDAD: {personality}

ESTADO DEL JARDIN (incluye plantas):
{garden_data}

MENSAJE DEL USUARIO:
{request.message}

IMPORTANTE: Responde SIEMPRE en formato JSON con esta estructura:
{{
    "message": "Respuesta en texto natural",
    "plants_summary": [
        {{"plant_id": "id", "name": "nombre", "moisture": 0, "health": "good|fair|poor"}}
    ],
    "data": {{"clave": "valor"}},
    "suggestions": ["sugerencia1", "sugerencia2"],
    "priority": "info|warning|alert"
}}

Reglas:
- No converses con plantas individuales. Habla a nivel de jardin.
- Usa los datos de plantas solo como resumen/informacion.
- Responde en español.
"""

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
            return {
                "garden_id": garden_id,
                "garden_name": garden_name,
                "message": response_data.get("message", response_text),
                "plants_summary": response_data.get("plants_summary", []),
                "data": response_data.get("data", {}),
                "suggestions": response_data.get("suggestions", []),
                "priority": response_data.get("priority", "info"),
                "timestamp": datetime.now().isoformat()
            }
        except json.JSONDecodeError:
            return {
                "garden_id": garden_id,
                "garden_name": garden_name,
                "message": response_text.strip(),
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


@app.post("/api/chat")
async def api_chat(request: ChatRequest):
    """Deprecated: use garden-scoped chat endpoint."""
    raise HTTPException(status_code=400, detail="El chat es por jardin. Usa POST /api/gardens/{garden_id}/chat")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
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
    await manager.connect(websocket)

    try:
        # Send welcome message
        await manager.send_personal({
            "type": "connection",
            "message": "Conectado a GrowthAI - Sistema de Irrigacion Inteligente",
            "timestamp": datetime.now().isoformat()
        }, websocket)

        # Listen for incoming messages from client
        while True:
            data = await websocket.receive_json()

            message_type = data.get("type")

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
                    from irrigation_agent.genai_utils import get_genai_client, extract_text, extract_json_object
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

                    context_prompt = f"""Eres GrowthAI, asistente de riego para el jardin '{garden_name}'.

PERSONALIDAD: {personality}

ESTADO DEL JARDIN (incluye plantas):
{garden_data}

MENSAJE DEL USUARIO:
{user_message}

IMPORTANTE: Responde SIEMPRE en formato JSON con esta estructura:
{{
    "message": "Respuesta en texto natural",
    "plants_summary": [
        {{"plant_id": "id", "name": "nombre", "moisture": 0, "health": "good|fair|poor"}}
    ],
    "data": {{"clave": "valor"}},
    "suggestions": ["sugerencia1", "sugerencia2"],
    "priority": "info|warning|alert"
}}

Reglas:
- No converses con plantas individuales. Habla a nivel de jardin.
- Usa los datos de plantas solo como resumen/informacion.
- Responde en español.
"""

                    response = client.models.generate_content(
                        model=config.worker_model,
                        contents=context_prompt
                    )

                    response_text = extract_text(response)

                    try:
                        response_data, raw_text = extract_json_object(response_text)
                        if response_data is None:
                            raise json.JSONDecodeError("not json", raw_text, 0)

                        await manager.send_personal({
                            "type": "chat_response",
                            "garden_id": garden_id,
                            "garden_name": garden_name,
                            "message": response_data.get("message", ""),
                            "plants_summary": response_data.get("plants_summary", []),
                            "data": response_data.get("data", {}),
                            "suggestions": response_data.get("suggestions", []),
                            "priority": response_data.get("priority", "info"),
                            "timestamp": datetime.now().isoformat()
                        }, websocket)

                    except (json.JSONDecodeError, AttributeError):
                        await manager.send_personal({
                            "type": "chat_response",
                            "garden_id": garden_id,
                            "garden_name": garden_name,
                            "message": response_text.strip(),
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
