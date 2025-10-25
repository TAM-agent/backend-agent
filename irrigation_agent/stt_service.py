import os
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

load_dotenv()

try:
    client = ElevenLabs()
    if not client.api_key:
        raise ValueError("ELEVEN_API_KEY not found in .env file")
except Exception as e:
    print(f"Error initializing ElevenLabs. Is ELEVEN_API_KEY missing from your .env file? Error: {e}")
    client = None

def convert_audio_to_text(audio_bytes: bytes) -> str | None:
    """
    Takes audio bytes, sends them to the ElevenLabs STT API, and returns the transcribed text.
    """
    if not client:
        print("The ElevenLabs STT client is not initialized.")
        return None

    if not audio_bytes:
        print("Received empty audio bytes.")
        return None

    print(f"Sending {len(audio_bytes)} bytes of audio for transcription to ElevenLabs...")

    try:
        # 1. Make the transcription request to ElevenLabs
        # The SDK will detect the format automatically (e.g., webm, mp3)
        response = client.speech_to_text.convert(
            audio=audio_bytes,
            model_id="eleven_multilingual_v2",  # Model that supports STT in Spanish
        )
        
        # 2. Extract the text
        if response and response.text:
            transcript = response.text
            print(f"Transcribed text: '{transcript}'")
            return transcript
        else:
            print("No transcription results received from ElevenLabs.")
            return None

    except Exception as e:
        print(f"Error during ElevenLabs STT transcription: {e}")
        return None