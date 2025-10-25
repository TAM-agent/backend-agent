"""ElevenLabs Agents integration (simulate-conversations).

Lightweight helper to call the ElevenLabs Agents HTTP API for text-based
conversation simulation. Designed to be optional and not affect the rest
of the system when the API key is missing.
"""

from __future__ import annotations

import os
import logging
from typing import Dict, Any, List, Optional

import requests

logger = logging.getLogger(__name__)


def _base_url() -> str:
    return os.getenv("ELEVENLABS_AGENTS_BASE_URL", "https://api.elevenlabs.io/v1")


def _api_key() -> Optional[str]:
    return os.getenv("ELEVENLABS_API_KEY")


def _default_agent_id() -> Optional[str]:
    return os.getenv("ELEVENLABS_AGENT_ID")


def simulate_conversation(
    text: str,
    history: Optional[List[Dict[str, Any]]] = None,
    agent_id: Optional[str] = None,
    timeout: int = 15,
) -> Dict[str, Any]:
    """Call ElevenLabs Agents simulate-conversations endpoint.

    Args:
        text: current user message.
        history: optional list like [{"role": "user|assistant", "content": "..."}]
        agent_id: optional agent id; defaults to ELEVENLABS_AGENT_ID.
        timeout: request timeout seconds.
    Returns:
        Dict with keys: status, text, raw, agent_id, usage? depending on API.
    """
    key = _api_key()
    if not key:
        return {"status": "error", "error": "ELEVENLABS_API_KEY not configured"}

    agent = agent_id or _default_agent_id()
    if not agent:
        return {"status": "error", "error": "ELEVENLABS_AGENT_ID not configured"}

    # Build messages payload: include provided history + current user turn
    messages: List[Dict[str, Any]] = []
    if history and isinstance(history, list):
        for m in history:
            role = m.get("role") if isinstance(m, dict) else None
            content = m.get("content") if isinstance(m, dict) else None
            if role and content:
                messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": text})

    url = f"{_base_url()}/agents/simulate-conversations"
    headers = {
        "xi-api-key": key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {
        "agent_id": agent,
        "messages": messages,
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()

        # The response shape may vary; try common fields gracefully.
        assistant_text = None
        if isinstance(data, dict):
            # Many APIs return messages or output; try typical candidates
            if "text" in data and isinstance(data["text"], str):
                assistant_text = data["text"]
            elif "output" in data and isinstance(data["output"], dict):
                assistant_text = data["output"].get("text")
            elif "messages" in data and isinstance(data["messages"], list):
                # find last assistant message
                for m in reversed(data["messages"]):
                    if m.get("role") == "assistant":
                        assistant_text = m.get("content")
                        break

        if not assistant_text:
            assistant_text = ""

        return {
            "status": "success",
            "text": assistant_text,
            "agent_id": agent,
            "raw": data,
        }
    except requests.RequestException as e:
        logger.error(f"ElevenLabs simulate-conversations error: {e}")
        return {"status": "error", "error": str(e)}

