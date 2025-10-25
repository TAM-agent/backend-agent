# Intelligent Irrigation Agent

Multi-agent irrigation system using Google's Gemini ADK for proactive plant care management. This system extends automated irrigation with AI agent capabilities for monitoring, optimization, and intelligent decision-making.

---

## Table of Contents
- [Project Overview](#project-overview)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Agent System](#agent-system)
- [Tools & Functions](#tools--functions)
- [API Integration](#api-integration)
- [Deployment](#deployment)
- [Development](#development)
- [Troubleshooting](#troubleshooting)
- [Project Structure](#project-structure)

---

## Project Overview

This backend agent component transforms a traditional MERN-based automated irrigation system into an intelligent, proactive plant care assistant using Google's Gemini multi-agent framework.

**Hardware**: Raspberry Pi, NodeMCU ESP8266, capacitive soil moisture sensors, water pumps, relays
**Base Stack**: MongoDB, Express, React, Node.js
**AI Layer**: Python with Google Gemini ADK for agent orchestration

### What Makes This Different

**Traditional System** âŒ
```python
if soil_moisture < 30%:
    water_plant()
```

**Intelligent Agent System** âœ…
```python
Agent analyzes:
- Current moisture trends (declining 15%/day)
- Weather forecasts (rain tomorrow 80% probability)
- Plant growth stage (fruiting - higher water needs)
- Historical patterns (normal consumption rate)

Decision: "Skip irrigation - rain expected in 8 hours will provide
adequate water. Saves 15L. Will verify moisture post-rain."
```

### Key Benefits

- ðŸ§  **Proactive**: Predicts problems 12-48 hours before they occur
- ðŸ’§ **Efficient**: 15-25% water savings through optimization
- ðŸ“Š **Explainable**: Every decision includes reasoning
- ðŸŒ¤ï¸ **Context-Aware**: Integrates weather, soil, plant knowledge
- ðŸ”” **Smart Alerts**: Priority-based notifications with fatigue prevention

---

## Quick Start

### Prerequisites

- Python 3.10 or higher
- pip package manager
- Gemini API key ([Get one free](https://makersuite.google.com/app/apikey))
- OpenWeatherMap API key ([Free tier](https://openweathermap.org/api))

### 3-Step Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env-template .env
# Edit .env with your API keys

# 3. Test
python -c "from irrigation_agent.tools import get_system_status; import json; print(json.dumps(get_system_status(), indent=2))"
```

**Expected output:**
```
==================================================================
SYSTEM STATUS REPORT
==================================================================

âš¡ Overall Health: WARNING

ðŸ’§ Water Tank:
   Level: 28%
   Capacity: 100 liters
   Status: LOW

ðŸŒ¿ Plant Health:
   âœ… Tomato       - Moisture: 65% - Health: good
   âš ï¸  Basil        - Moisture: 38% - Health: fair
   âœ… Lettuce      - Moisture: 72% - Health: good
   âš ï¸  Pepper       - Moisture: 42% - Health: fair

â„¹ï¸  WARNINGS:
   â€¢ Water tank low (28%)
   â€¢ Basil moisture approaching threshold (38%)
```

---

## Architecture

### Multi-Agent Hierarchy

```
intelligent_irrigation_agent (Root)
â”œâ”€â”€ irrigation_orchestrator (Coordinator)
â”‚   â”œâ”€â”€ sensor_monitor_agent       [Monitors IoT sensors]
â”‚   â”œâ”€â”€ nutrient_analyzer_agent    [Analyzes plant health]
â”‚   â”œâ”€â”€ alert_manager_agent        [Manages notifications]
â”‚   â””â”€â”€ optimization_agent         [Optimizes schedules]
â””â”€â”€ automated_monitoring_workflow  [Sequential execution]
```

### Data Flow

```
IoT Sensors (Raspberry Pi)
    â†“ REST API
Sensor Monitor â†’ Reads data, detects anomalies
    â†“
Nutrient Analyzer â†’ Assesses health, diagnoses issues
    â†“
Optimization Agent â†’ Integrates weather, calculates needs
    â†“
Alert Manager â†’ Classifies priority, sends notifications
    â†“
User / System Actions
```

---

## Installation

### Step 1: Install Dependencies

```bash
# Create virtual environment (recommended)
python -m venv venv

# Activate
source venv/bin/activate  # Mac/Linux
venv\Scripts\activate     # Windows

# Install packages
pip install -r requirements.txt
```

**Installed packages:**
- `google-adk` - Agent Development Kit
- `google-genai` - Gemini models
- `requests` - API calls
- `python-dotenv` - Environment management
- `pydantic` - Data validation

### Step 2: Get API Keys

#### Gemini API Key (Required)

1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Sign in with Google account
3. Click "Create API Key"
4. Copy the key (starts with `AIza...`)

#### OpenWeather API Key (Recommended)

1. Sign up at [OpenWeatherMap](https://openweathermap.org/api)
2. Free tier: 1000 calls/day
3. Copy your API key

### Step 3: Configure Environment

```bash
# Create .env from template
cp .env-template .env
```

**Edit `.env` file:**
```env
# Google AI
GEMINI_API_KEY=AIza_your_actual_key_here

# Models
AI_MODEL=gemini-2.5-flash
CRITIC_MODEL=gemini-2.5-pro

# IoT Backend
RASPBERRY_PI_IP=192.168.1.100
BACKEND_PORT=3000

# Weather
OPENWEATHER_API_KEY=your_weather_key
WEATHER_LOCATION=Santiago,CL
```

### Step 4: Verify Installation

```bash
# Test system
python run_agent.py --status

# Or use make commands
make monitor
```

---

## Configuration

### Environment Variables

#### Required

```env
GEMINI_API_KEY=your_key          # From Google AI Studio
RASPBERRY_PI_IP=192.168.1.100   # Your Pi's IP address
```

#### Recommended

```env
OPENWEATHER_API_KEY=your_key     # For weather optimization
WEATHER_LOCATION=YourCity,CC     # City,CountryCode
```

#### Optional - Notifications

**Telegram:**
```env
TELEGRAM_BOT_TOKEN=123:ABC       # From @BotFather
TELEGRAM_CHAT_ID=123456          # From @userinfobot
```

**Email (Gmail example):**
```env
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your.email@gmail.com
SMTP_PASSWORD=app_specific_password
NOTIFICATION_EMAIL=recipient@example.com
```

#### System Configuration

```env
SENSOR_POLLING_INTERVAL=300      # Seconds between cycles (5 min)
ALERT_COOLDOWN_MINUTES=30        # Prevent notification spam
MAX_IRRIGATION_DURATION=1800     # Safety limit (30 min)
```

### Configuration Dataclasses

The system uses typed configuration:

```python
from irrigation_agent.config import config, iot_config, weather_config

# Agent configuration
config.worker_model              # gemini-2.5-flash
config.critic_model              # gemini-2.5-pro
config.sensor_polling_interval   # 300 seconds

# IoT configuration
iot_config.raspberry_pi_ip       # 192.168.1.100
iot_config.base_url              # http://192.168.1.100:3000
iot_config.max_irrigation_duration  # 1800 seconds

# Weather configuration
weather_config.location          # Santiago,CL
weather_config.forecast_days     # 3
```

---

## Usage

### Using the Tools Directly

#### Check System Status

```python
from irrigation_agent.tools import get_system_status
import json

status = get_system_status()
print(json.dumps(status, indent=2))
```

#### Check Individual Plant

```python
from irrigation_agent.tools import check_soil_moisture

moisture = check_soil_moisture("tomato")
print(f"Tomato moisture: {moisture['moisture_level']}%")
```

#### Trigger Irrigation

```python
from irrigation_agent.tools import trigger_irrigation

result = trigger_irrigation("basil", duration_seconds=30)
print(f"Irrigation status: {result['status']}")
```

#### Get Weather Forecast

```python
from irrigation_agent.tools import get_weather_forecast

weather = get_weather_forecast(days=3)
for forecast in weather['forecast'][:3]:
    print(f"{forecast['date']}: {forecast['temp_celsius']}Â°C, {forecast['description']}")
```

### Using the Agents

#### Interactive Query (Future)

```python
from irrigation_agent import intelligent_irrigation_agent

# Ask the agent a question
response = intelligent_irrigation_agent.query(
    "Why are my tomato leaves turning yellow?"
)
print(response)
```

#### Automated Monitoring (Future)

```python
from irrigation_agent import automated_monitoring_workflow
import time

# Run continuous monitoring
while True:
    result = automated_monitoring_workflow.execute()
    print(f"Monitoring complete: {result}")
    time.sleep(300)  # 5 minutes
```

### Make Commands

```bash
# Development
make install          # Install dependencies
make setup            # Complete development setup
make run              # Run the agent

# Monitoring
make monitor          # Check system status
make check-sensors    # Read all sensors
make check-weather    # Get weather forecast

# Testing
make test             # Run tests
make lint             # Check code quality

# Deployment
make setup-gcp        # Setup Google Cloud
make deploy           # Deploy to Cloud Run
make logs             # View logs

# Utilities
make clean            # Clean temporary files
make help             # Show all commands
```

---

## Agent System

### The Four Specialized Agents

#### 1. Sensor Monitor Agent ðŸ”

**Model**: `gemini-2.5-flash` (fast operations)

**Responsibilities:**
- Real-time IoT sensor monitoring
- Anomaly detection (stuck sensors, erratic readings)
- Historical pattern analysis
- Data quality assurance

**Tools:**
- `check_soil_moisture(plant_name)`
- `check_water_tank_level()`
- `get_sensor_history(plant, hours)`
- `get_system_status()`

**Example Output:**
```
Tomato sensor shows stable 65% moisture over 24h. All readings
within normal variance (<5%). Water tank at 45% declining at
expected rate of 8L/day. No anomalies detected.
```

#### 2. Nutrient Analyzer Agent ðŸŒ¿

**Model**: `gemini-2.5-pro` (complex analysis)

**Responsibilities:**
- Plant health assessment (2-4 scale)
- Nutrient deficiency diagnosis (N, P, K, Ca, Mg, Fe)
- Fertilizer recommendations with NPK ratios
- Growth pattern analysis

**Knowledge Base:**
- **Nitrogen**: Yellowing older leaves â†’ Fish emulsion (5-1-1)
- **Phosphorus**: Dark/purple leaves â†’ Bone meal
- **Potassium**: Brown leaf edges â†’ Potash
- **Calcium**: Blossom end rot â†’ Lime/gypsum
- **Magnesium**: Interveinal chlorosis â†’ Epsom salt
- **Iron**: Yellowing new leaves â†’ Iron chelate

**Example Output:**
```
Basil showing early nitrogen deficiency:
- Evidence: Yellowing lower leaves, slower water uptake (15%/day vs 20%)
- Cause: High nitrogen demand during rapid growth
- Recommendation: Fish emulsion (5-1-1) at half strength, every 2 weeks
- Expected outcome: Recovery in 10-14 days, darker green new growth
```

#### 3. Alert Manager Agent ðŸ“¢

**Model**: `gemini-2.5-flash` (fast decisions)

**Responsibilities:**
- Priority classification (CRITICAL/HIGH/MEDIUM/LOW)
- Alert fatigue prevention (cooldown periods)
- Context-aware messaging
- Multi-channel delivery

**Priority System:**

| Priority | When | Channels | Cooldown | Example |
|----------|------|----------|----------|---------|
| ðŸš¨ CRITICAL | Plant death risk, system failure | All | None | "Water tank at 3% - irrigation will fail in 2 hours" |
| âš ï¸ HIGH | Urgent attention needed | Telegram + Email | 2 hours | "Lettuce moisture at 18% - irrigation needed within 6h" |
| â„¹ï¸ MEDIUM | Important but not urgent | Telegram | 6 hours | "Tomato showing nitrogen deficiency - fertilizer recommended" |
| ðŸ’¡ LOW | Informational | Daily digest | 24 hours | "All plants healthy! Basil grew 15% this week" |

#### 4. Optimization Agent ðŸ“Š

**Model**: `gemini-2.5-pro` (complex optimization)

**Responsibilities:**
- Weather forecast integration
- Irrigation schedule optimization
- Resource efficiency (15-25% water savings)
- Precise duration calculations

**Optimization Strategies:**
- **Deep Watering**: 60-90s every 3-4 days (tomatoes, peppers)
- **Frequent Light**: 20-35s every 1-2 days (lettuce, basil)
- **Weather Integration**: Skip before rain, increase in heat
- **Time Optimization**: Early morning (6-9 AM) preferred

**Example Decision:**
```
Analysis:
- Tomato moisture: 45%
- Weather: 15mm rain in 8 hours (80% probability)
- Normal threshold: 50%

Decision: SKIP irrigation
Reasoning: Current 45% acceptable. Rain will bring to 70-75%.
Savings: 15L water, reduced pump wear
Next check: 12h post-rain to verify increase
```

---

## Tools & Functions

### Monitoring Tools

#### check_soil_moisture(plant_name: str)
Read current soil moisture level from IoT sensor.

**Parameters:**
- `plant_name`: Plant identifier ("tomato", "basil", "lettuce", "pepper")

**Returns:**
```python
{
    "plant": "tomato",
    "moisture_level": 65,
    "timestamp": "2025-10-24T10:30:00",
    "status": "success"
}
```

#### check_water_tank_level()
Retrieve current water tank level and capacity.

**Returns:**
```python
{
    "level_percentage": 75,
    "capacity_liters": 100,
    "timestamp": "2025-10-24T10:30:00",
    "status": "success"
}
```

#### get_sensor_history(plant_name: str, hours: int = 24)
Retrieve historical sensor data for pattern analysis.

**Returns:**
```python
{
    "plant": "tomato",
    "history": [
        {"moisture": 65, "timestamp": "2025-10-24T08:00:00"},
        {"moisture": 63, "timestamp": "2025-10-24T09:00:00"},
        ...
    ],
    "hours_analyzed": 24,
    "status": "success"
}
```

#### get_system_status()
Get comprehensive system status overview.

**Returns:**
```python
{
    "overall_health": "warning",
    "water_tank": {"level_percentage": 28, "status": "low"},
    "plant_status": {
        "tomato": {"moisture": 65, "health": "good"},
        "basil": {"moisture": 38, "health": "fair"}
    },
    "critical_issues": [],
    "warnings": ["Water tank low (28%)"],
    "status": "success"
}
```

### Control Tools

#### trigger_irrigation(plant_name: str, duration_seconds: int)
Activate irrigation pump for specified plant and duration.

**Parameters:**
- `plant_name`: Plant to irrigate
- `duration_seconds`: How long to run pump (max 1800s)

**Returns:**
```python
{
    "plant": "tomato",
    "duration_seconds": 45,
    "status": "success",
    "timestamp": "2025-10-24T10:30:00"
}
```

### Analysis Tools

#### analyze_plant_health(plant_name: str, image_path: Optional[str] = None)
Analyze plant health using sensor data and optional image.

**Returns:**
```python
{
    "plant": "tomato",
    "health_score": 3,  # 2=poor, 3=fair, 4=good
    "avg_moisture": 55.2,
    "issues": ["Slightly low moisture"],
    "recommendations": ["Monitor closely", "Consider irrigation"],
    "status": "success"
}
```

#### get_weather_forecast(days: int = 3)
Fetch weather forecast from OpenWeatherMap API.

**Returns:**
```python
{
    "forecast": [
        {
            "date": "2025-10-24",
            "temp_celsius": 22,
            "humidity": 65,
            "precipitation_prob": 0.1,
            "description": "partly cloudy"
        }
    ],
    "days": 3,
    "location": "Santiago,CL",
    "status": "success"
}
```

### Communication Tools

#### send_notification(message: str, priority: str = "medium")
Send notification to user with priority classification.

**Parameters:**
- `message`: Notification text
- `priority`: "critical", "high", "medium", or "low"

**Returns:**
```python
{
    "message": "Water tank at 28%",
    "priority": "medium",
    "sent": True,
    "channels": ["log", "telegram"],
    "status": "success"
}
```

---

## API Integration

The agent communicates with your Node.js backend via REST API:

### Sensor Data Endpoints

```http
# Get current sensor reading
GET http://{RASPI_IP}:3000/api/sensors/{plant_name}

Response:
{
    "plant": "tomato",
    "moisture": 65,
    "timestamp": "2025-10-24T10:30:00Z"
}
```

```http
# Get historical data
GET http://{RASPI_IP}:3000/api/sensors/{plant_name}/history?hours=24

Response:
{
    "history": [
        {"moisture": 65, "timestamp": "..."},
        {"moisture": 63, "timestamp": "..."}
    ]
}
```

### Control Endpoints

```http
# Trigger irrigation
POST http://{RASPI_IP}:3000/api/irrigate
Content-Type: application/json

{
    "plant": "tomato",
    "duration": 45
}

Response:
{
    "status": "success",
    "started_at": "2025-10-24T10:30:00Z"
}
```

### System Endpoints

```http
# Get water tank status
GET http://{RASPI_IP}:3000/api/water-tank

Response:
{
    "level": 75,
    "capacity_liters": 100
}
```

---

## Deployment

### Local Development

```python
# Test tools directly
from irrigation_agent.tools import get_system_status
print(get_system_status())
```

### Google Cloud Run Deployment

This project includes full support for deploying as a REST API on Google Cloud Run with automated CI/CD.

#### Prerequisites

**1. Google Cloud Account**
- Active Google Cloud account with billing enabled
- New users get $300 free credit

**2. Install Google Cloud CLI**

```bash
# Mac (Homebrew)
brew install --cask google-cloud-sdk

# Windows
# Download installer from: https://cloud.google.com/sdk/docs/install

# Linux
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
```

**3. Authenticate**

```bash
# Login to Google Cloud
gcloud auth login

# Set application default credentials for local testing
gcloud auth application-default login
```

**4. Create GCP Project**

```bash
# Create new project
gcloud projects create YOUR-PROJECT-ID --name="Intelligent Irrigation Agent"

# Set as active project
gcloud config set project YOUR-PROJECT-ID

# Enable billing (required for Cloud Run)
# Go to: https://console.cloud.google.com/billing
```

**5. Enable Required APIs**

```bash
# Enable all necessary Google Cloud APIs
gcloud services enable \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  containerregistry.googleapis.com \
  aiplatform.googleapis.com \
  generativelanguage.googleapis.com
```

#### Configuration

**1. Set Up Environment Variables**

Cloud Run requires environment variables to be configured. You have two options:

**Option A: Configure during deployment** (recommended for API keys)

```bash
# Deploy with environment variables
gcloud run deploy intelligent-irrigation-agent \
  --source . \
  --region us-east1 \
  --set-env-vars="GEMINI_API_KEY=AIza...,OPENWEATHER_API_KEY=abc123" \
  --set-env-vars="RASPBERRY_PI_IP=YOUR_PI_IP,BACKEND_PORT=3000" \
  --set-env-vars="WEATHER_LOCATION=Santiago,CL"
```

**Option B: Use Secret Manager** (most secure for production)

```bash
# Create secrets
echo -n "AIza_your_key" | gcloud secrets create gemini-api-key --data-file=-
echo -n "weather_key" | gcloud secrets create openweather-api-key --data-file=-

# Deploy with secrets
gcloud run deploy intelligent-irrigation-agent \
  --source . \
  --region us-east1 \
  --set-secrets="GEMINI_API_KEY=gemini-api-key:latest,OPENWEATHER_API_KEY=openweather-api-key:latest"
```

#### Deployment Methods

**Method 1: Using Cloud Build (Automated CI/CD)** â­ Recommended

This method uses the included `cloudbuild.yaml` for automated deployment.

```bash
# Submit build to Cloud Build
gcloud builds submit --config cloudbuild.yaml

# Or use the Makefile
make deploy
```

The Cloud Build pipeline will:
1. Build Docker image from `Dockerfile`
2. Push image to Google Container Registry (GCR)
3. Deploy to Cloud Run with configuration from `cloudbuild.yaml`
4. Auto-scaling: 0-10 instances, 512Mi RAM, 1 CPU

**Method 2: Direct Source Deployment**

Deploy directly from source code without Cloud Build:

```bash
gcloud run deploy intelligent-irrigation-agent \
  --source . \
  --region us-east1 \
  --platform managed \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --timeout 300 \
  --max-instances 10 \
  --min-instances 0 \
  --port 8080 \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=$(gcloud config get-value project)" \
  --set-env-vars="GEMINI_API_KEY=YOUR_KEY,OPENWEATHER_API_KEY=YOUR_KEY" \
  --set-env-vars="RASPBERRY_PI_IP=YOUR_IP,BACKEND_PORT=3000"
```

**Method 3: Pre-built Docker Image**

If you've built the Docker image locally:

```bash
# Build image locally
docker build -t gcr.io/YOUR-PROJECT-ID/intelligent-irrigation-agent:latest .

# Push to GCR
docker push gcr.io/YOUR-PROJECT-ID/intelligent-irrigation-agent:latest

# Deploy from GCR
gcloud run deploy intelligent-irrigation-agent \
  --image gcr.io/YOUR-PROJECT-ID/intelligent-irrigation-agent:latest \
  --region us-east1 \
  --platform managed
```

#### Post-Deployment

**1. Get Service URL**

```bash
# Get the deployed service URL
SERVICE_URL=$(gcloud run services describe intelligent-irrigation-agent \
  --region us-east1 \
  --format 'value(status.url)')

echo "Service deployed at: $SERVICE_URL"
```

**2. Test the Deployment**

```bash
# Test health endpoint
curl $SERVICE_URL/health

# Expected response:
# {"status": "healthy", "timestamp": "2025-10-24T10:30:00"}

# Test system status
curl $SERVICE_URL/api/status

# Get soil moisture
curl "$SERVICE_URL/api/plant/tomato/moisture"

# Get weather forecast
curl "$SERVICE_URL/api/weather?days=3"

# Trigger irrigation (POST)
curl -X POST "$SERVICE_URL/api/irrigate" \
  -H "Content-Type: application/json" \
  -d '{"plant_name": "tomato", "duration_seconds": 30}'
```

**3. Access API Documentation**

FastAPI automatically generates interactive API documentation:

```bash
# Open Swagger UI
open $SERVICE_URL/docs

# Open ReDoc
open $SERVICE_URL/redoc
```

#### Available API Endpoints

Once deployed, your Cloud Run service exposes these REST endpoints:

| Endpoint | Method | Description | Example |
|----------|--------|-------------|---------|
| `/health` | GET | Health check | `curl $URL/health` |
| `/api/status` | GET | Full system status | `curl $URL/api/status` |
| `/api/plant/{name}/moisture` | GET | Soil moisture reading | `curl $URL/api/plant/tomato/moisture` |
| `/api/plant/{name}/health` | GET | Plant health analysis | `curl $URL/api/plant/tomato/health` |
| `/api/tank` | GET | Water tank level | `curl $URL/api/tank` |
| `/api/weather` | GET | Weather forecast | `curl $URL/api/weather?days=3` |
| `/api/irrigate` | POST | Trigger irrigation | `curl -X POST $URL/api/irrigate -d '{"plant_name":"tomato","duration_seconds":30}'` |

#### Monitoring and Logging

**View Logs**

```bash
# Real-time logs
gcloud run services logs tail intelligent-irrigation-agent \
  --region us-east1

# Or use Makefile
make logs

# View logs in Console
# https://console.cloud.google.com/run
```

**Monitor Metrics**

```bash
# Open Cloud Run dashboard
gcloud run services describe intelligent-irrigation-agent \
  --region us-east1 \
  --format="value(status.url)"

# View in Console for detailed metrics:
# - Request count
# - Latency
# - Container CPU/Memory usage
# - Error rate
```

**Set Up Alerts**

```bash
# Example: Alert on high error rate
gcloud alpha monitoring policies create \
  --notification-channels=YOUR_CHANNEL_ID \
  --display-name="Irrigation Agent Errors" \
  --condition-display-name="Error rate > 5%" \
  --condition-threshold-value=0.05 \
  --condition-threshold-duration=60s
```

#### Continuous Deployment (CI/CD)

**Connect to GitHub**

```bash
# Install Cloud Build GitHub app
# https://github.com/apps/google-cloud-build

# Create trigger for automatic deployment on push
gcloud builds triggers create github \
  --repo-name=YOUR-REPO \
  --repo-owner=YOUR-USERNAME \
  --branch-pattern="^main$" \
  --build-config=cloudbuild.yaml
```

Now every push to `main` branch automatically deploys to Cloud Run!

#### Cost Estimation

Cloud Run pricing (as of 2024):

**Free Tier (Monthly):**
- 2 million requests
- 360,000 GB-seconds (memory)
- 180,000 vCPU-seconds

**Estimated Monthly Cost** (after free tier):
- Light usage (1000 requests/day): ~$0-5
- Medium usage (10,000 requests/day): ~$10-20
- Heavy usage (100,000 requests/day): ~$50-100

**Cost optimization tips:**
- Use `--min-instances=0` to scale to zero when idle
- Set appropriate `--max-instances` to control maximum spend
- Use regional deployment (cheaper than global)

#### Updating the Deployment

**Update Environment Variables**

```bash
# Update existing service
gcloud run services update intelligent-irrigation-agent \
  --region us-east1 \
  --set-env-vars="NEW_VAR=value"
```

**Deploy New Version**

```bash
# Simply deploy again with updated code
gcloud builds submit --config cloudbuild.yaml

# Or using Makefile
make deploy
```

Cloud Run automatically:
- Creates new revision
- Gradually shifts traffic to new version
- Keeps old revision for rollback

**Rollback to Previous Version**

```bash
# List revisions
gcloud run revisions list \
  --service intelligent-irrigation-agent \
  --region us-east1

# Rollback to specific revision
gcloud run services update-traffic intelligent-irrigation-agent \
  --region us-east1 \
  --to-revisions=REVISION_NAME=100
```

#### Security Best Practices

**1. Authentication** (if needed)

```bash
# Require authentication
gcloud run services update intelligent-irrigation-agent \
  --region us-east1 \
  --no-allow-unauthenticated

# Call authenticated endpoint
curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  $SERVICE_URL/api/status
```

**2. Use Secret Manager**

```bash
# Store sensitive data in Secret Manager
echo -n "your-secret" | gcloud secrets create my-secret --data-file=-

# Grant Cloud Run access
gcloud secrets add-iam-policy-binding my-secret \
  --member="serviceAccount:YOUR-PROJECT-NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Use in deployment
gcloud run services update intelligent-irrigation-agent \
  --set-secrets="MY_SECRET=my-secret:latest"
```

**3. VPC Connector** (for private Raspberry Pi access)

```bash
# Create VPC connector for private network access
gcloud compute networks vpc-access connectors create irrigation-connector \
  --region us-east1 \
  --range 10.8.0.0/28

# Deploy with VPC connector
gcloud run services update intelligent-irrigation-agent \
  --vpc-connector irrigation-connector \
  --vpc-egress all-traffic
```

#### Troubleshooting Deployment

**Problem: Build fails with "permission denied"**

```bash
# Grant Cloud Build permissions
gcloud projects add-iam-policy-binding YOUR-PROJECT-ID \
  --member="serviceAccount:YOUR-PROJECT-NUMBER@cloudbuild.gserviceaccount.com" \
  --role="roles/run.admin"
```

**Problem: Service crashes on startup**

```bash
# Check logs
gcloud run services logs read intelligent-irrigation-agent \
  --region us-east1 \
  --limit 50

# Common issues:
# - Missing environment variables
# - Invalid API keys
# - Port mismatch (must be 8080)
```

**Problem: Can't connect to Raspberry Pi**

```bash
# Option 1: Use Cloud Run VPC connector (see Security section)
# Option 2: Expose Raspberry Pi with Cloudflare Tunnel
# Option 3: Use VPN or Cloud VPN

# Test connectivity from Cloud Shell
gcloud cloud-shell ssh
curl http://YOUR-RASPI-IP:3000/api/water-tank
```

**Problem: High latency**

```bash
# Increase CPU/memory
gcloud run services update intelligent-irrigation-agent \
  --cpu 2 \
  --memory 1Gi

# Use minimum instances to avoid cold starts
gcloud run services update intelligent-irrigation-agent \
  --min-instances 1
```

#### Local Testing with Docker

Before deploying, test the Docker container locally:

```bash
# Build image
docker build -t irrigation-agent:local .

# Run locally
docker run -p 8080:8080 \
  -e GEMINI_API_KEY=your_key \
  -e OPENWEATHER_API_KEY=your_key \
  -e RASPBERRY_PI_IP=localhost \
  irrigation-agent:local

# Test in browser
open http://localhost:8080/docs
```

#### Makefile Commands

The included `Makefile` provides convenient deployment commands:

```bash
make setup-gcp        # Initial GCP setup
make deploy           # Deploy to Cloud Run
make logs             # View service logs
make status           # Check service status
make delete           # Delete Cloud Run service
```

---

## Development

### Project Structure

```
backend-agent/
â”œâ”€â”€ irrigation_agent/           # Main package
â”‚   â”œâ”€â”€ __init__.py            # Package exports
â”‚   â”œâ”€â”€ agent.py               # Agent orchestration
â”‚   â”œâ”€â”€ config.py              # Configuration management
â”‚   â”œâ”€â”€ tools.py               # Tool implementations
â”‚   â””â”€â”€ sub_agents/            # Specialized agents
â”‚       â”œâ”€â”€ __init__.py
â”‚       â”œâ”€â”€ sensor_monitor.py
â”‚       â”œâ”€â”€ nutrient_analyzer.py
â”‚       â”œâ”€â”€ alert_manager.py
â”‚       â””â”€â”€ optimization_agent.py
â”œâ”€â”€ .env-template              # Configuration template
â”œâ”€â”€ requirements.txt           # Dependencies
â”œâ”€â”€ Makefile                   # Development commands
â”œâ”€â”€ pyproject.toml            # Project metadata
â””â”€â”€ README.md                 # This file
```

### Adding a New Tool

```python
# In irrigation_agent/tools.py

def my_new_tool(param: str) -> Dict[str, Any]:
    """Tool description for the LLM.

    Args:
        param: Parameter description

    Returns:
        Dictionary with result and status
    """
    try:
        # Implementation
        result = perform_operation(param)

        return {
            "result": result,
            "status": "success",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error in my_new_tool: {e}")
        return {
            "result": None,
            "status": "error",
            "error": str(e)
        }
```

```python
# In agent definition (e.g., sensor_monitor.py)

from google.adk.tools import FunctionTool
from ..tools import my_new_tool

agent = Agent(
    name="my_agent",
    tools=[
        FunctionTool(my_new_tool),
        # ... other tools
    ]
)
```

### Customizing Plant List

Edit `tools.py` around line 550:

```python
def get_system_status() -> Dict[str, Any]:
    # Update this list with your plants
    plants = ["tomato", "basil", "lettuce", "pepper", "cucumber"]

    # Rest of the function...
```

### Testing

```bash
# Run tests
make test

# Or manually
pytest tests/ -v

# Test individual tools
python -c "from irrigation_agent.tools import get_system_status; print(get_system_status())"
```

---

## Troubleshooting

### Connection Errors

**Problem:** `Connection refused` when checking sensors

**Solutions:**
1. Verify backend is running: `curl http://{RASPI_IP}:3000/api/water-tank`
2. Check `RASPBERRY_PI_IP` in `.env`
3. Ensure port 3000 is open on firewall
4. Use mock backend for testing (see below)

### API Key Errors

**Problem:** `API key not configured` or `401 Unauthorized`

**Solutions:**
1. Verify `.env` file exists with keys
2. Check no quotes around keys in `.env`
3. Restart terminal after editing `.env`
4. Verify key is valid at [Google AI Studio](https://makersuite.google.com/app/apikey)

### Module Import Errors

**Problem:** `ModuleNotFoundError: No module named 'google.adk'`

**Solutions:**
```bash
# Ensure virtual environment is activated
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Reinstall dependencies
pip install -r requirements.txt

# Verify installation
pip list | grep google-adk
```

### Mock Backend for Testing

If you don't have hardware, create a mock backend:

```bash
# Install Flask
pip install flask

# Create and run mock backend
python << 'EOF'
from flask import Flask, jsonify, request
import random
from datetime import datetime

app = Flask(__name__)

@app.route('/api/sensors/<plant>')
def sensor(plant):
    return jsonify({
        'plant': plant,
        'moisture': random.randint(30, 80),
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/water-tank')
def tank():
    return jsonify({'level': random.randint(20, 90), 'capacity': 100})

@app.route('/api/sensors/<plant>/history')
def history(plant):
    return jsonify({
        'history': [{'moisture': random.randint(40, 70),
                     'timestamp': datetime.now().isoformat()}
                    for _ in range(24)]
    })

@app.route('/api/irrigate', methods=['POST'])
def irrigate():
    return jsonify({'status': 'success'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000)
EOF
```

Then in `.env`:
```env
RASPBERRY_PI_IP=localhost
```

---

## Contributing

This project was created for a hackathon demonstration of LLM agents in IoT environments. Contributions welcome!

### Development Setup

```bash
# Install with dev dependencies
make install-dev

# Run linting
make lint

# Format code
make format

# Run tests
make test
```

---

## License

MIT License - See [LICENSE](LICENSE) file for details

---

## Acknowledgments

- Google Gemini ADK for multi-agent framework
- OpenWeatherMap for weather data
- Open-source automated irrigation system project (base hardware/software)

---

## Support

- **Documentation**: This README
- **Issues**: Report bugs and issues on GitHub
- **Google ADK Docs**: https://ai.google.dev/adk

---

**Built with â¤ï¸ for smarter plant care through AI** ðŸŒ±ðŸ¤–


## Agriculture Data (USDA Quick Stats)

This service integrates USDA Quick Stats API to enrich crop context (yield, area planted, general series) for better irrigation decisions.

- API: https://quickstats.nass.usda.gov/api
- Configure key: set `USDA_QUICKSTATS_API_KEY` in `.env`
- Endpoints added:
  - `GET /api/agriculture/yield?commodity=CORN&year=2023&state=IA`
  - `GET /api/agriculture/area_planted?commodity=CORN&year=2023&state=IA`
  - `GET /api/agriculture/search?commodity=WHEAT&year=2022&statistic=YIELD`

Notes:
- These endpoints pass through commonly used Quick Stats filters (commodity_desc, statisticcat_desc, etc.).
- If the API key is missing, the endpoints return HTTP 400 with an explanatory message.

- Advisor endpoint:
  - `POST /api/gardens/{garden_id}/advisor`
    - Body: `{ "commodity": "CORN", "state": "IA", "year": 2023, "user_message": "opcional" }`
    - Combina contexto del jardín con Quick Stats y devuelve una recomendación JSON a nivel de jardín.

- Advisor endpoint:
  - `POST /api/gardens/{garden_id}/advisor`
    - Body: `{ "commodity": "CORN", "state": "IA", "year": 2023, "user_message": "opcional" }`
    - Combina contexto del jardín con Quick Stats y clima (si disponible) y devuelve una recomendación JSON a nivel de jardín.

## Audio (Speech-To-Text / Text-To-Speech)

We integrated ElevenLabs for audio features, inspired by the `fabian` branch example.

- TTS endpoint: `POST /api/audio/tts`
  - Body: `{ "text": "Hola jardín", "voice_id": "JBFqnCBsd6RMkjVDRZzb", "model_id": "eleven_multilingual_v2", "output_format": "mp3_44100_128" }`
  - Returns: JSON with `audio_base64` (MP3 by default)
- STT endpoint: `POST /api/audio/stt`
  - Multipart file upload: field `file`
  - Returns: JSON with `text` (best-effort wrapper)

Configure:
- Set `ELEVENLABS_API_KEY` in `.env`
- Install deps from `requirements.txt` (includes `elevenlabs` and `python-multipart`)

Notes:
- STT endpoint relies on ElevenLabs STT HTTP API and may require adjustments depending on account features.
