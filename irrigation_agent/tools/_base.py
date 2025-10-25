import os
import logging

from irrigation_agent.config import iot_config, weather_config, notification_config


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

USE_SIMULATION = os.getenv("USE_SIMULATION", "false").lower() == "true"

if USE_SIMULATION:
    from irrigation_agent.service.firebase_service import simulator  # type: ignore
else:
    simulator = None  # type: ignore

__all__ = [
    "logger",
    "USE_SIMULATION",
    "simulator",
    "iot_config",
    "weather_config",
    "notification_config",
]

