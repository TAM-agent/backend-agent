import os
import base64
import logging
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode('utf-8')


def analyze_plant_image(image_bytes: bytes, content_type: str = "image/jpeg") -> Dict[str, Any]:
    """Analyze a plant image using the configured GenAI client.

    Returns a dict with fields: status, analysis { disease, causes, cures, severity, confidence, summary }.
    """
    try:
        from irrigation_agent.utils.genai_utils import get_genai_client, extract_text, extract_json_object
        client = get_genai_client()

        prompt = (
            "Eres un agrónomo. Analiza la imagen de una planta y responde en JSON con: "
            "{\"disease\": string|\"none\", \"causes\": [..], \"cures\": [..], \"severity\": \"low|medium|high\", "
            "\"confidence\": 0-1, \"summary\": string}. Si no puedes determinar, usa disease=none y confidence baja."
        )

        # Inline image via base64 if supported by client
        b64 = _b64(image_bytes)
        contents = [
            {"role": "user", "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": content_type, "data": b64}},
            ]}
        ]

        response = client.models.generate_content(
            model=os.getenv("AI_MODEL", "gemini-2.5-pro"),
            contents=contents,
        )
        text = extract_text(response)
        data, raw = extract_json_object(text)
        if not data:
            data = {"summary": text.strip()}
        return {"status": "success", "analysis": data, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"Image analysis failed: {e}")
        return {"status": "error", "error": str(e), "timestamp": datetime.now().isoformat()}


def store_image_record(
    garden_id: str,
    image_bytes: bytes,
    content_type: str,
    analysis: Dict[str, Any],
) -> Dict[str, Any]:
    """Store image (best effort) and its analysis. Prefer Firestore doc with base64 to keep it simple.

    Returns { status, doc_id }.
    """
    try:
        from irrigation_agent.service.firebase_service import simulator
        from google.cloud import firestore  # type: ignore
        ts = datetime.now()
        doc_id = ts.strftime('%Y-%m-%dT%H%M%S')

        payload = {
            'garden_id': garden_id,
            'content_type': content_type,
            'image_base64': _b64(image_bytes),
            'analysis': analysis,
            'created_at': ts,
        }
        if simulator and simulator.use_firestore and simulator.db:
            simulator.db.collection('gardens').document(garden_id)\
                .collection('images').document(doc_id).set(payload)
            return {"status": "success", "doc_id": doc_id}
    except Exception as e:
        logger.warning(f"Firestore image store failed, falling back to local: {e}")

    # Local fallback in simulation JSON
    try:
        from irrigation_agent.service.firebase_service import simulator as _sim
        data = _sim._load_local_data()
        data.setdefault('garden_images', {})
        items = data['garden_images'].get(garden_id, [])
        record = {
            'id': datetime.now().isoformat(),
            'garden_id': garden_id,
            'content_type': content_type,
            'image_base64': _b64(image_bytes),
            'analysis': analysis,
        }
        items.append(record)
        data['garden_images'][garden_id] = items
        with open(_sim.local_data_file, 'w') as f:
            import json
            json.dump(data, f, indent=2)
        return {"status": "success", "doc_id": record['id']}
    except Exception as le:
        logger.error(f"Local image store failed: {le}")
        return {"status": "error", "error": str(le)}

