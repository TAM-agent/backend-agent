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

## Architecture

### System Architecture Diagram

<p align="center">
  <img src="docs/images/arch-gcp.svg" alt="GCP Architecture" width="800">
</p>

### Components Overview

**API Layer** (FastAPI)
- REST endpoints organized by domain (plants, gardens, agriculture, audio)
- WebSocket server for real-time notifications
- Background monitoring task (30-60s intervals)

**Agent Layer** (Google Gemini ADK)
- Multi-agent orchestration with 4 specialized sub-agents
- Sensor monitor, nutrient analyzer, alert manager, optimization agent
- Explainable AI decisions with reasoning

**Tools Layer** (Modular)
- Sensors: moisture, tank level, history
- Control: irrigation triggers
- Analysis: plant health assessment
- Gardens: garden-scoped operations
- API integrations: weather, USDA

**Services Layer**
- Firebase/Firestore simulator for data persistence
- Weather APIs (Google Weather, OpenWeatherMap)
- USDA Quick Stats for agriculture data
- ElevenLabs for TTS/STT
- Telegram for notifications
- Image analysis for plant health

**Infrastructure** (Google Cloud)
- Cloud Run for serverless deployment
- Vertex AI for Gemini models
- Firestore for data storage
- Secret Manager for API keys

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
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
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

# Telegram Notifications (optional)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id

# CORS (optional)
ALLOWED_ORIGINS=http://localhost:3000
ALLOW_CREDENTIALS=false
```

### Telegram Notifications Setup

To receive real-time notifications from the agent:

1. **Create a Telegram Bot:**
   - Open Telegram and chat with [@BotFather](https://t.me/BotFather)
   - Send `/newbot` and follow instructions
   - Save the API token (format: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz1234567890`)

2. **Get your Chat ID:**
   - Option A: Chat with [@userinfobot](https://t.me/userinfobot) and send `/start`
   - Option B: Send a message to your bot, then visit:
     ```
     https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
     ```
     Look for `"chat":{"id":123456789}` in the JSON response

3. **Configure Environment:**
   ```env
   TELEGRAM_BOT_TOKEN=your_bot_token_here
   TELEGRAM_CHAT_ID=your_chat_id_here
   ```

**Notification Triggers:**

The system automatically sends Telegram notifications when:
- **Critical moisture detected** (< 30%): Agent analyzes and decides irrigation action
- **Low moisture warning** (< 45%): Alert sent before becoming critical
- **Agent makes decisions**: Full explanation with moisture levels and reasoning

Notifications include:
- Visual moisture bar (🟥/🟨/🟩)
- Garden and plant names
- Current moisture percentage
- Agent's decision and explanation
- Timestamp

Example notification:
```
⚠️ DECISIÓN DEL AGENTE

🌱 Jardín: Mi Jardín
🪴 Planta: Tomate Cherry
💧 Decisión: REGAR

💧 Humedad Actual: 25%
🟥🟥🟥⬜⬜⬜⬜⬜⬜⬜ 25%

📝 Explicación:
Humedad crítica detectada. Se recomienda riego inmediato.

🕐 2025-10-26 15:30:45
```

**Priority Levels:**
- Only `high` and `critical` priority events trigger Telegram notifications by default
- This prevents notification spam while keeping you informed of important events
- You can modify priority thresholds in `irrigation_agent/tools/notifications.py`

**Service Implementation:**
- Rich formatting with emojis and visual bars in `irrigation_agent/service/telegram_service.py`
- Integrated into agent decision flow (`agent_analyze_and_act()`)
- Also works with monitoring loop (`process_garden_monitoring()`)

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

## Deployment

### Quick Deploy

```bash
# Option 1: Using Makefile (recommended)
cd deployment
make deploy

# Option 2: Direct gcloud command
gcloud run deploy intelligent-irrigation-agent \
  --source . \
  --region us-east1 \
  --project YOUR_PROJECT_ID \
  --allow-unauthenticated \
  --memory 512Mi --cpu 1 --timeout 300

# Option 3: Cloud Build (CI/CD)
cd deployment
make cloud-build
```

### Useful Commands

```bash
# View logs
cd deployment && make logs

# Health check
cd deployment && make health

# Service info
cd deployment && make info

# See all commands
cd deployment && make help
```

### Complete Documentation

📚 **See [deployment/README.md](deployment/README.md)** for:
- Complete deployment guide
- Secrets configuration
- Troubleshooting
- Version rollback
- Local Docker build

---

## Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally with hot reload
uvicorn main:app --reload --port 8080

# Run tests (if present)
pytest -q
```

Project structure
```
backend-agent/
├── main.py                    # FastAPI app (236 lines, refactored)
├── api/                       # API layer (organized by domain)
│   ├── models.py             # Pydantic request/response models
│   ├── websocket.py          # WebSocket connection manager
│   ├── routers/              # Endpoint routers
│   │   ├── plants.py         # Legacy plant endpoints
│   │   ├── gardens.py        # Modern garden endpoints
│   │   ├── agriculture.py    # USDA Quick Stats endpoints
│   │   └── audio.py          # TTS/STT endpoints
│   └── services/             # Business logic services
│       └── monitoring.py     # Background monitoring
├── irrigation_agent/         # Core agent logic
│   ├── tools/               # Function tools for agents
│   ├── service/             # External service integrations
│   ├── utils/               # Utilities (LLM client, helpers)
│   ├── sub_agents/          # Specialized sub-agents
│   └── config.py            # Configuration management
├── prompts/                  # LLM system prompts
├── docs/
│   └── images/              # Architecture diagrams (SVG)
├── deployment/              # Deployment files and guides
│   ├── Dockerfile
│   ├── cloudbuild.yaml
│   ├── Makefile
│   └── README.md
└── scripts/                  # Utility scripts
```

---

License: MIT (see LICENSE)
