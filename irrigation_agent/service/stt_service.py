import os
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from typing import Optional

load_dotenv()

_api_key = os.getenv("ELEVENLABS_API_KEY")
_client = ElevenLabs(api_key=_api_key) if _api_key else None


def convert_audio_to_text(audio_bytes: bytes, model_id: str = "eleven_multilingual_v2") -> Optional[str]:
    """
    Takes audio bytes, sends them to the ElevenLabs STT API, and returns the transcribed text.
    """
    if not _client or not _api_key:
        return None
    if not audio_bytes:
        return None

    response = _client.speech_to_text.convert(
        audio=audio_bytes,
        model_id=model_id,
    )
    if response and getattr(response, "text", None):
        return response.text
    return None

