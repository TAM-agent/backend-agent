from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
import os
import base64

load_dotenv()

_client = ElevenLabs(
    api_key=os.getenv("ELEVENLABS_API_KEY"),
)


def convert_text_to_speech(
    text: str,
    voice_id: str = "JBFqnCBsd6RMkjVDRZzb",
    model_id: str = "eleven_multilingual_v2",
    output_format: str = "mp3_44100_128",
) -> str | None:
    """Convert text to speech using ElevenLabs API and return as base64 string."""
    if not text:
        return None
    if not _client.api_key:
        return None
    audio: bytes = _client.text_to_speech.convert(
        text=text,
        voice_id=voice_id,
        model_id=model_id,
        output_format=output_format,
        stream=False,
    )
    audio_base64 = base64.b64encode(audio).decode("utf-8")
    return audio_base64

