import os
import sys
import json
from pathlib import Path

# Ensure repo root is on sys.path so `import main` works when running this file directly
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Force simulation + Firestore for this smoke test
os.environ.setdefault("USE_SIMULATION", "true")
os.environ.setdefault("USE_FIRESTORE", "true")

from fastapi.testclient import TestClient

import main


def pretty(obj):
    try:
        return json.dumps(obj, indent=2)
    except Exception:
        return str(obj)


def run():
    client = TestClient(main.app)

    garden_id = os.getenv("TEST_GARDEN_ID", "demo-garden-fs")

    print("Seeding garden...", garden_id)
    seed_body = {
        "name": "Demo Garden (FS)",
        "personality": "neutral",
        "latitude": -33.45,
        "longitude": -70.65,
        "plant_count": 3,
        "base_moisture": 55,
    }
    r = client.post(f"/api/gardens/{garden_id}/seed", json=seed_body)
    print("/seed:", r.status_code)
    print(pretty(r.json()))

    print("\nGet garden status...")
    r = client.get(f"/api/gardens/{garden_id}")
    print("/garden:", r.status_code)
    print(pretty(r.json())[:600])

    print("\nPlant in garden (plant1)...")
    r = client.get(f"/api/gardens/{garden_id}/plants/plant1")
    print("/plant1:", r.status_code)
    print(pretty(r.json()))

    print("\nGarden chat (may require GenAI credentials)...")
    r = client.post(f"/api/gardens/{garden_id}/chat", json={"message": "¿Cómo están las plantas hoy?"})
    print("/chat:", r.status_code)
    try:
        print(pretty(r.json())[:800])
    except Exception:
        print(r.text)


if __name__ == "__main__":
    run()
