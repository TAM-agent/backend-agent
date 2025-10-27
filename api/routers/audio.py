"""Audio endpoints for Text-to-Speech and Speech-to-Text."""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Request

from api.models import TTSRequest, ChatRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Audio"])


# Audio configuration constants
DEFAULT_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"
DEFAULT_TTS_MODEL = "eleven_multilingual_v2"
DEFAULT_AUDIO_FORMAT = "mp3_44100_128"


@router.post("/audio/tts")
async def text_to_speech(req: TTSRequest):
    """Text-to-Speech using ElevenLabs. Returns base64 audio data."""
    try:
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


@router.post("/audio/stt")
async def speech_to_text(file: UploadFile = File(...)):
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


@router.post("/voice/gardens/{garden_id}/talk")
async def voice_garden_talk(
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
        # Import garden chat endpoint
        from api.routers.gardens import garden_chat

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
        chat_result = await garden_chat(garden_id, chat_req)

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


@router.get("/chat/{session_id}")
async def get_chat_session(session_id: str):
    """Retrieve chat session history."""
    try:
        from irrigation_agent.service.firebase_service import get_session_messages
        return get_session_messages(session_id)
    except Exception as e:
        logger.error(f"Error retrieving session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat")
async def deprecated_chat(request: ChatRequest):
    """Deprecated: use garden-scoped chat endpoint."""
    raise HTTPException(
        status_code=400,
        detail="El chat es por jardin. Usa POST /api/gardens/{garden_id}/chat"
    )
