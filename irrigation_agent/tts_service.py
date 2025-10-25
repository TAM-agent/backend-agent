from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
import os
import base64

load_dotenv()

elevenlabs = ElevenLabs(
  api_key=os.getenv("ELEVENLABS_API_KEY"),
)


def convert_text_to_speech(text: str) -> str | None:
  """Convert text to speech using ElevenLabs API and return as base64 string."""
    audio = elevenlabs.text_to_speech.convert(
        text=text,
        voice_id="JBFqnCBsd6RMkjVDRZzb",
        model_id="eleven_multilingual_v2",
        stream=False,
    )
    audio_base64 = base64.b64encode(audio).decode('utf-8')
    return audio_base64

