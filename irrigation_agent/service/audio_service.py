"""Audio services: Text-to-Speech and Speech-to-Text.

Brings in ElevenLabs TTS (as seen in branch 'fabian') and adds a simple
STT wrapper using ElevenLabs HTTP API.
"""

import base64
import io
import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional

import requests

logger = logging.getLogger(__name__)


def _eleven_key() -> Optional[str]:
    return os.getenv("ELEVENLABS_API_KEY")


def tts_elevenlabs(
    text: str,
    voice_id: str = "JBFqnCBsd6RMkjVDRZzb",
    model_id: str = "eleven_multilingual_v2",
    output_format: str = "mp3_44100_128",
) -> Dict[str, Any]:
    """Convert text to speech using ElevenLabs.

    Returns base64-encoded audio data and metadata.
    """
    api_key = _eleven_key()
    if not api_key:
        return {
            "status": "error",
            "error": "ELEVENLABS_API_KEY not configured",
            "timestamp": datetime.now().isoformat(),
        }

    try:
        # HTTP endpoint documented by ElevenLabs for TTS streaming
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {
            "xi-api-key": api_key,
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
        }
        payload = {
            "text": text,
            "model_id": model_id,
            "voice_settings": {"stability": 0.4, "similarity_boost": 0.8},
            "output_format": output_format,
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        audio_bytes = resp.content
        audio_b64 = base64.b64encode(audio_bytes).decode("ascii")

        return {
            "status": "success",
            "format": output_format,
            "voice_id": voice_id,
            "model_id": model_id,
            "audio_base64": audio_b64,
            "timestamp": datetime.now().isoformat(),
        }
    except requests.RequestException as e:
        logger.error(f"ElevenLabs TTS error: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


def stt_elevenlabs(file_bytes: bytes, model: Optional[str] = None) -> Dict[str, Any]:
    """Transcribe speech to text via ElevenLabs STT HTTP API.

    Tries the documented SDK-equivalent HTTP shapes and returns richer errors
    so callers can see why requests fail (e.g., missing model_id).
    """
    api_key = _eleven_key()
    if not api_key:
        return {
            "status": "error",
            "error": "ELEVENLABS_API_KEY not configured",
            "timestamp": datetime.now().isoformat(),
        }

    # Default to the same model used by the SDK wrapper if none provided
    model_id = model or "eleven_multilingual_v2"

    # Build common request parts
    headers = {
        "xi-api-key": api_key,
        "Accept": "application/json",
    }
    files = {
        # Many vendors expect the field name "audio" rather than "file"
        "audio": ("audio.mp3", io.BytesIO(file_bytes), "audio/mpeg"),
    }
    data = {"model_id": model_id}

    # Try primary endpoint, then a fallback path used by some clients
    endpoints = [
        "https://api.elevenlabs.io/v1/speech-to-text",
        "https://api.elevenlabs.io/v1/speech-to-text/convert",
    ]

    last_error: Optional[Dict[str, Any]] = None
    for url in endpoints:
        try:
            resp = requests.post(url, headers=headers, files=files, data=data, timeout=60)
            if resp.status_code >= 400:
                # Preserve vendor error for debugging
                err_text = None
                err_json = None
                try:
                    err_json = resp.json()
                except Exception:
                    err_text = resp.text
                last_error = {
                    "status": "error",
                    "http_status": resp.status_code,
                    "endpoint": url,
                    "error": (err_json or err_text or "Unknown error"),
                }
                continue

            data_json = resp.json()
            transcript = data_json.get("text") or data_json.get("transcript") or ""
            return {
                "status": "success",
                "text": transcript,
                "raw": data_json,
                "timestamp": datetime.now().isoformat(),
            }
        except requests.RequestException as e:
            # Network/transport error; capture and try next endpoint
            last_error = {
                "status": "error",
                "endpoint": url,
                "error": str(e),
            }
            continue

    # If we reach here, all attempts failed
    logger.error(f"ElevenLabs STT error: {last_error}")
    return {
        "status": "error",
        **(last_error or {"error": "Unknown STT error"}),
        "timestamp": datetime.now().isoformat(),
    }
