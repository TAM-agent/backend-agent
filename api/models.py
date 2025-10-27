"""Pydantic models for API requests and responses."""
from typing import Optional
from pydantic import BaseModel


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
    # Optional TTS of assistant reply
    include_audio: Optional[bool] = False


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
