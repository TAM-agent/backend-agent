"""Modern garden endpoints (garden-level operations with personality)."""
import os
import logging
import json
import random
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, UploadFile, File

from api.models import ChatRequest, AdvisorRequest, SeedGardenRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/gardens", tags=["Gardens"])


# Audio configuration constants
DEFAULT_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"
DEFAULT_TTS_MODEL = "eleven_multilingual_v2"
DEFAULT_AUDIO_FORMAT = "mp3_44100_128"


def check_tools_available(tools_available: bool):
    """Helper to check if tools are available."""
    if not tools_available:
        raise HTTPException(status_code=503, detail="Agent tools not available")


@router.get("")
async def get_all_gardens(tools_available: bool = True):
    """Get all gardens with their metadata."""
    check_tools_available(tools_available)
    try:
        from irrigation_agent.tools import get_all_gardens
        result = get_all_gardens()
        return result
    except Exception as e:
        logger.error(f"Error getting all gardens: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_all_gardens_status(tools_available: bool = True):
    """Get status for ALL gardens and their plants."""
    check_tools_available(tools_available)
    try:
        from irrigation_agent.tools import get_all_gardens_status
        result = get_all_gardens_status()
        return result
    except Exception as e:
        logger.error(f"Error getting gardens status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{garden_id}")
async def get_garden_status(garden_id: str, tools_available: bool = True):
    """Get status for a specific garden and all its plants."""
    check_tools_available(tools_available)
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


@router.get("/{garden_id}/plants/{plant_id}")
async def get_plant_in_garden(garden_id: str, plant_id: str, tools_available: bool = True):
    """Get detailed status for a specific plant in a garden."""
    check_tools_available(tools_available)
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


@router.post("/{garden_id}/plants/{plant_id}/chat")
async def chat_with_plant(garden_id: str, plant_id: str, request: ChatRequest):
    """Deprecated: garden has one sensor; chat is garden-scoped."""
    raise HTTPException(
        status_code=410,
        detail="El chat por planta ya no esta disponible. Usa POST /api/gardens/{garden_id}/chat"
    )


@router.get("/{garden_id}/weather")
async def get_garden_weather(garden_id: str, tools_available: bool = True):
    """Get weather forecast for a garden location using Google Weather API."""
    check_tools_available(tools_available)
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


@router.get("/{garden_id}/plants/{plant_id}/recommendation")
async def get_irrigation_recommendation(garden_id: str, plant_id: str, tools_available: bool = True):
    """Get irrigation recommendation with weather analysis for a specific plant."""
    check_tools_available(tools_available)
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


@router.post("/{garden_id}/advisor")
async def garden_advisor(garden_id: str, req: AdvisorRequest, tools_available: bool = True, config=None):
    """Agent advisor for a garden combining local context with USDA Quick Stats."""
    check_tools_available(tools_available)
    try:
        from irrigation_agent.tools import get_garden_status, get_garden_weather
        from irrigation_agent.service.agriculture_service import get_crop_yield, get_area_planted
        from irrigation_agent.utils.genai_utils import get_genai_client, extract_text, extract_json_object
        from irrigation_agent.config import config as app_config
        from prompts import GARDEN_ADVISOR_PROMPT

        if config is None:
            config = app_config

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


@router.post("/{garden_id}/seed")
async def seed_garden(garden_id: str, req: SeedGardenRequest):
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


@router.post("/{garden_id}/chat")
async def garden_chat(garden_id: str, request: ChatRequest, tools_available: bool = True, config=None):
    """Chat del asistente a nivel de jardin (incluye info de plantas como contexto)."""
    check_tools_available(tools_available)
    try:
        from irrigation_agent.utils.genai_utils import get_genai_client, extract_text, extract_json_object
        from irrigation_agent.tools import get_garden_status
        from irrigation_agent.config import config as app_config
        from prompts import GARDEN_CHAT_PROMPT

        if config is None:
            config = app_config

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
        session_id = request.session_id or str(uuid.uuid4())

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
            result = {
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
            # Optional TTS of assistant reply
            try:
                if bool(request.include_audio) and _msg:
                    from irrigation_agent.service.tts_service import convert_text_to_speech
                    audio_b64 = convert_text_to_speech(
                        _msg,
                        voice_id=DEFAULT_VOICE_ID,
                        model_id=DEFAULT_TTS_MODEL,
                        output_format=DEFAULT_AUDIO_FORMAT,
                    )
                    if audio_b64:
                        result["audio_base64"] = audio_b64
            except Exception as _tts_err:
                logger.warning(f"TTS (chat) failed: {_tts_err}")
            return result
        except json.JSONDecodeError:
            _fallback_msg = response_text.strip()
            try:
                from irrigation_agent.service.firebase_service import add_session_message
                add_session_message(garden_id, "assistant", _fallback_msg, {"garden_name": garden_name}, session_id=session_id)
            except Exception:
                pass
            result = {
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
            # Optional TTS of assistant reply
            try:
                if bool(request.include_audio) and _fallback_msg:
                    from irrigation_agent.service.tts_service import convert_text_to_speech
                    audio_b64 = convert_text_to_speech(
                        _fallback_msg,
                        voice_id=DEFAULT_VOICE_ID,
                        model_id=DEFAULT_TTS_MODEL,
                        output_format=DEFAULT_AUDIO_FORMAT,
                    )
                    if audio_b64:
                        result["audio_base64"] = audio_b64
            except Exception as _tts_err:
                logger.warning(f"TTS (chat-fallback) failed: {_tts_err}")
            return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in garden chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{garden_id}/images/analyze")
async def garden_image_analyze(garden_id: str, file: UploadFile = File(...)):
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
