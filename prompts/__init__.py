"""
Prompts module for GrowthAI agent system.

Contains all system prompts as Python template strings for better maintainability
and IDE support.
"""

from .agent_decision import AGENT_DECISION_PROMPT
from .garden_chat import GARDEN_CHAT_PROMPT
from .garden_advisor import GARDEN_ADVISOR_PROMPT
from .websocket_chat import WEBSOCKET_CHAT_PROMPT

__all__ = [
    "AGENT_DECISION_PROMPT",
    "GARDEN_CHAT_PROMPT",
    "GARDEN_ADVISOR_PROMPT",
    "WEBSOCKET_CHAT_PROMPT",
]
