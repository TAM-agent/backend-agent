"""Intelligent Irrigation Agent Package.

Multi-agent system for proactive plant care using Google Gemini ADK.
Coordinates specialized agents for sensor monitoring, plant health analysis,
alert management, and irrigation optimization.
"""

from .agent import (
    intelligent_irrigation_agent,
    irrigation_orchestrator,
    root_agent
)
from .config import config, iot_config, weather_config, notification_config

__all__ = [
    "intelligent_irrigation_agent",
    "irrigation_orchestrator",
    "root_agent",
    "config",
    "iot_config",
    "weather_config",
    "notification_config"
]

__version__ = "0.1.0"
