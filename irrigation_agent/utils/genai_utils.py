import json
import re
import threading
from typing import Any, Optional, Tuple

from ..config import config

_client_lock = threading.Lock()
_client_instance = None


def get_genai_client():
    """Return a singleton google.genai Client configured for Vertex AI if enabled."""
    global _client_instance
    if _client_instance is not None:
        return _client_instance
    with _client_lock:
        if _client_instance is None:
            # Lazy import to avoid hard dependency at import time
            from google import genai  # type: ignore
            _client_instance = genai.Client(vertexai=True)
    return _client_instance


def extract_text(response: Any) -> str:
    """Extract text from google.genai response across common shapes."""
    if response is None:
        return ""
    if hasattr(response, "text") and isinstance(response.text, str):
        return response.text
    text = ""
    try:
        candidates = getattr(response, "candidates", []) or []
        for cand in candidates:
            content = getattr(cand, "content", None)
            if content and hasattr(content, "parts"):
                for part in content.parts:
                    t = getattr(part, "text", None)
                    if isinstance(t, str):
                        text += t
    except Exception:
        pass
    return text


def extract_json_object(text: str) -> Tuple[Optional[dict], str]:
    """Try to parse a JSON object from text, handling code fences.

    Returns (obj, raw_text). obj is None if parsing fails.
    """
    if not text:
        return None, ""

    # Strip markdown code block if present
    match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text, re.DOTALL)
    if match:
        text = match.group(1)

    cleaned = text.strip()
    try:
        obj = json.loads(cleaned)
        if isinstance(obj, dict):
            return obj, cleaned
    except json.JSONDecodeError:
        pass
    return None, cleaned
