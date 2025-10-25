# Intelligent Irrigation Agent

Multi‑agent irrigation backend using Google Gemini ADK. Adds proactive monitoring, explainable decisions and API endpoints over an IoT irrigation setup (sensors + pumps).

---

## Table of Contents
- Project Overview
- Quick Start
- Architecture
- Installation
- Configuration
- API Endpoints
- Audio (TTS/STT)
- Agriculture (USDA Quick Stats)
- Deployment (Cloud Run)
- Development

---

## Project Overview

This service turns a traditional automated irrigation system into an intelligent assistant. It analyzes sensor history, weather, and crop context to recommend or trigger actions with clear reasons.

Key benefits
- Proactive: predicts issues 12–48 hours ahead
- Efficient: 15–25% water savings via optimization
- Explainable: every decision includes reasoning
- Context‑aware: integrates weather, soil and plant data
- Smart alerts: priority‑based notifications

---

## Quick Start

Prerequisites
- Python 3.10+
- pip

Setup
```bash
pip install -r requirements.txt
# Create .env and fill keys (see Configuration)

# Run locally
uvicorn main:app --reload --port 8080

# Health check
curl http://localhost:8080/health
```

---

## Architecture (brief)
- FastAPI REST + WebSocket for real‑time messages
- Tools layer (modular): sensors, control, analysis, gardens, API integrations
- Services: Firestore simulator, weather, audio, agriculture
- Utils: LLM client (singleton) + response parsing

---

## Installation
```bash
python -m venv venv
venv\Scripts\activate      # Windows
# or: source venv/bin/activate
pip install -r requirements.txt
```

---

## Configuration

Environment variables (examples)
```env
# Google Cloud
GOOGLE_CLOUD_PROJECT=tam-adk
GOOGLE_CLOUD_LOCATION=us-east1
GOOGLE_GENAI_USE_VERTEXAI=True

# Models
AI_MODEL=gemini-2.5-pro

# Simulation / data source
USE_SIMULATION=true
USE_FIRESTORE=true

# External APIs (optional)
OPENWEATHER_API_KEY=...
GOOGLE_WEATHER_API_KEY=...
USDA_QUICKSTATS_API_KEY=...
ELEVENLABS_API_KEY=...

# CORS (optional)
ALLOWED_ORIGINS=http://localhost:3000
ALLOW_CREDENTIALS=false
```

Notes
- With `USE_SIMULATION=true` and `USE_FIRESTORE=true`, the app reads/writes from Firestore collections (gardens, plants, system/water_tank).
- For local ADC: `gcloud auth application-default login`.

---

## API Endpoints (main)

Core
- GET `/health` – service health
- GET `/api/status` – overall system status

Plants (flat)
- GET `/api/plant/{plant_name}/moisture`
- GET `/api/plant/{plant_name}/history?hours=24`
- GET `/api/plant/{plant_name}/health`
- GET `/api/tank`
- GET `/api/weather` (OpenWeather; requires API key)
- POST `/api/irrigate` – body: `{ "plant": "tomato", "duration": 30 }`
- POST `/api/notify` – body: `{ "message": "...", "priority": "high" }`

Gardens (Firestore model)
- GET `/api/gardens`
- GET `/api/gardens/status`
- GET `/api/gardens/{garden_id}`
- GET `/api/gardens/{garden_id}/plants/{plant_id}`
- GET `/api/gardens/{garden_id}/weather` (Google Weather; needs lat/long on garden)
- GET `/api/gardens/{garden_id}/plants/{plant_id}/recommendation`
- POST `/api/gardens/{garden_id}/chat` – garden‑scoped chat (returns structured JSON)
- POST `/api/gardens/{garden_id}/advisor` – combines garden + USDA + weather context
- POST `/api/gardens/{garden_id}/seed` – seeds demo data (Firestore or local JSON)

Agriculture (USDA)
- GET `/api/agriculture/yield?commodity=CORN&year=2023&state=IA`
- GET `/api/agriculture/area_planted?commodity=CORN&year=2023&state=IA`
- GET `/api/agriculture/search?...`

WebSocket
- `/ws` – real‑time alerts, decisions, chat responses

---

## Audio (Speech‑to‑Text / Text‑to‑Speech)

ElevenLabs integration (SDK preferred; HTTP fallback).
- TTS: POST `/api/audio/tts`
  - body: `{ "text": "Hola jardín", "voice_id": "JBFqnCBsd6RMkjVDRZzb", "model_id": "eleven_multilingual_v2", "output_format": "mp3_44100_128" }`
- STT: POST `/api/audio/stt` (multipart, field `file`)

Set `ELEVENLABS_API_KEY` in environment. For production, prefer Secret Manager and `--set-secrets` in Cloud Run deploy.

---

## Agriculture Data (USDA Quick Stats)

Adds crop statistics (yield, area planted) for richer context.
- API: https://quickstats.nass.usda.gov/api
- Configure `USDA_QUICKSTATS_API_KEY`
- Advisor endpoint: `POST /api/gardens/{garden_id}/advisor` combines garden + USDA + (optional) weather.

---

## Deployment (Cloud Run)

Example deploy with separate env vars (non‑secrets):
```bash
gcloud run deploy intelligent-irrigation-agent \
  --source . \
  --region us-east1 \
  --project tam-adk \
  --allow-unauthenticated \
  --service-account tam-adk@tam-adk.iam.gserviceaccount.com \
  --memory 512Mi --cpu 1 --timeout 300 \
  --set-env-vars GOOGLE_CLOUD_PROJECT=tam-adk \
  --set-env-vars GOOGLE_CLOUD_LOCATION=us-east1 \
  --set-env-vars GOOGLE_GENAI_USE_VERTEXAI=true \
  --set-env-vars AI_MODEL=gemini-2.5-pro \
  --set-env-vars USE_SIMULATION=true \
  --set-env-vars USE_FIRESTORE=true
```

Recommended (secrets via Secret Manager):
```bash
--set-secrets USDA_QUICKSTATS_API_KEY=usda-quickstats:latest \
--set-secrets ELEVENLABS_API_KEY=elevenlabs:latest
```

Logs & URL
```bash
gcloud run services describe intelligent-irrigation-agent \
  --region us-east1 --project tam-adk \
  --format='value(status.url)'
gcloud run services logs read intelligent-irrigation-agent \
  --region us-east1 --project tam-adk --limit 100
```

---

## Development
```bash
make install-dev   # or: pip install -r requirements.txt
uvicorn main:app --reload --port 8080
# Tests (if present)
pytest -q
```

Project structure (simplified)
```
irrigation_agent/
  service/        # external services (weather, audio, firestore, agriculture)
  tools/          # sensors, control, notifications, analysis, gardens, api
  utils/          # llm client + helpers
  sub_agents/     # orchestrator + specialized sub-agents
main.py           # FastAPI app
```

---

License: MIT (see LICENSE)
