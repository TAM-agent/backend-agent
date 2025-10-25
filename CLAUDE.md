# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an **Intelligent Irrigation Agent** built on Google's Gemini ADK (Agent Development Kit). It uses a multi-agent architecture to transform traditional threshold-based irrigation into an AI-powered system that makes proactive, context-aware decisions about plant care.

**Key Distinction**: This is NOT a simple automation system. The agents analyze trends, integrate weather forecasts, diagnose plant health issues, and explain their reasoning—going far beyond "if moisture < 30%, water plant."

## Development Commands

### Installation & Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment (required)
cp .env-template .env
# Edit .env with your API keys: GEMINI_API_KEY, OPENWEATHER_API_KEY, RASPBERRY_PI_IP
```

### Testing Tools Directly
```bash
# Test system status (most comprehensive check)
python -c "from irrigation_agent.tools import get_system_status; import json; print(json.dumps(get_system_status(), indent=2))"

# Test individual sensors
python -c "from irrigation_agent.tools import check_soil_moisture; print(check_soil_moisture('tomato'))"

# Test weather integration
python -c "from irrigation_agent.tools import get_weather_forecast; import json; print(json.dumps(get_weather_forecast(3), indent=2))"
```

### Running the API Server
```bash
# Start FastAPI server (for Cloud Run or local testing)
python main.py

# Server runs on port 8080 by default
# Access interactive API docs at http://localhost:8080/docs
```

### Deployment
```bash
# Deploy to Google Cloud Run via Cloud Build
gcloud builds submit --config cloudbuild.yaml

# View logs
gcloud run services logs tail intelligent-irrigation-agent --region us-east1
```

## Multi-Agent Architecture

This system uses a **hierarchical multi-agent structure** with Google Gemini ADK:

```
intelligent_irrigation_agent (root)
└── irrigation_orchestrator (coordinator)
    ├── sensor_monitor_agent       [Model: gemini-2.5-flash]
    ├── nutrient_analyzer_agent    [Model: gemini-2.5-pro]
    ├── optimization_agent         [Model: gemini-2.5-pro]
    └── alert_manager_agent        [Model: gemini-2.5-flash]
```

### Agent Responsibilities

**irrigation_orchestrator** ([agent.py](irrigation_agent/agent.py))
- Main coordinator that delegates to specialized sub-agents
- Synthesizes insights from multiple domains (sensors, plant health, weather, alerts)
- Resolves conflicts between agent recommendations
- Orchestrates both interactive Q&A and automated monitoring workflows

**sensor_monitor_agent** ([sensor_monitor.py](irrigation_agent/sub_agents/sensor_monitor.py))
- Monitors IoT sensors continuously
- Detects anomalies (stuck sensors, erratic readings, equipment failures)
- Analyzes historical patterns and trends
- Uses fast model (gemini-2.5-flash) for real-time operations

**nutrient_analyzer_agent** ([nutrient_analyzer.py](irrigation_agent/sub_agents/nutrient_analyzer.py))
- Assesses plant health (scoring 2-4)
- Diagnoses nutrient deficiencies (N, P, K, Ca, Mg, Fe)
- Recommends specific fertilizers with NPK ratios
- Uses complex model (gemini-2.5-pro) for botanical knowledge

**optimization_agent** ([optimization_agent.py](irrigation_agent/sub_agents/optimization_agent.py))
- Integrates weather forecasts from OpenWeatherMap
- Optimizes irrigation schedules for efficiency
- Calculates precise watering durations
- Makes cost-benefit analyses (e.g., "skip irrigation before rain")

**alert_manager_agent** ([alert_manager.py](irrigation_agent/sub_agents/alert_manager.py))
- Classifies notifications by priority (CRITICAL/HIGH/MEDIUM/LOW)
- Prevents alert fatigue with cooldown periods
- Routes to appropriate channels (Telegram, email, logs)
- Provides context-aware, actionable messages

## Key Files and Their Roles

### Core System Files

**[irrigation_agent/agent.py](irrigation_agent/agent.py)** - Agent hierarchy definition
- Defines `intelligent_irrigation_agent` (root)
- Defines `irrigation_orchestrator` (coordinator)
- Contains detailed agent instructions and coordination workflows
- **Critical**: The agent instructions are extensive and encode coordination logic

**[irrigation_agent/tools.py](irrigation_agent/tools.py)** - Tool implementations
- All functions that agents can call to interact with hardware/APIs
- Each tool returns standardized `{"status": "success/error", "data": {...}, "timestamp": "..."}` format
- Tools include: `check_soil_moisture()`, `trigger_irrigation()`, `get_weather_forecast()`, `analyze_plant_health()`
- **Important**: Tools use the global config instances from config.py

**[irrigation_agent/config.py](irrigation_agent/config.py)** - Configuration management
- Defines dataclasses for different config domains: `IrrigationConfiguration`, `IoTConfiguration`, `WeatherConfiguration`, `NotificationConfiguration`
- Loads from environment variables via `python-dotenv`
- Exports global instances: `config`, `iot_config`, `weather_config`, `notification_config`
- **Pattern**: Access configs like `config.worker_model` or `iot_config.base_url`

**[main.py](main.py)** - FastAPI REST API server
- Entry point for Cloud Run deployment
- Exposes agent tools as REST endpoints (GET /api/status, POST /api/irrigate, etc.)
- Auto-generates OpenAPI docs at `/docs` and `/redoc`
- Gracefully degrades if irrigation_agent modules fail to import

### Sub-Agent Files

**[irrigation_agent/sub_agents/](irrigation_agent/sub_agents/)** - Specialized agents
- Each file defines one sub-agent with specific tools and instructions
- Follow consistent pattern: Agent definition with model, description, tools list, and detailed instruction prompt
- **When modifying**: Pay careful attention to agent instructions—they encode domain expertise

## Important Development Patterns

### Adding a New Tool

1. **Define the tool function in [tools.py](irrigation_agent/tools.py)**:
```python
def my_new_tool(param: str) -> Dict[str, Any]:
    """Docstring that agents see to understand the tool.

    Args:
        param: Description for the agent

    Returns:
        Dictionary with status, data, timestamp
    """
    try:
        result = perform_operation(param)
        return {
            "result": result,
            "status": "success",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error in my_new_tool: {e}")
        return {"status": "error", "error": str(e)}
```

2. **Add to relevant agent in [sub_agents/](irrigation_agent/sub_agents/)**:
```python
from google.adk.tools import FunctionTool
from ..tools import my_new_tool

agent = Agent(
    name="sensor_monitor_agent",
    tools=[
        FunctionTool(my_new_tool),
        # ... other tools
    ]
)
```

3. **Update agent instructions** if the new tool changes capabilities significantly

### Modifying Agent Behavior

**DO**: Edit the `instruction` field in agent definitions—this is where the agent's expertise and behavior is encoded

**DON'T**: Hardcode logic in tools.py that should be agent decisions. Tools should be low-level operations; agents should make the high-level decisions about when/how to use them.

### Configuration Changes

All configuration comes from environment variables loaded in [config.py](irrigation_agent/config.py). Never hardcode IPs, API keys, or thresholds in agent or tool code.

**Pattern for adding new config**:
1. Add to appropriate dataclass in config.py
2. Load from `os.getenv("ENV_VAR_NAME", "default")`
3. Document in .env-template and README.md

## API Integration with Hardware

The system communicates with a Node.js backend running on Raspberry Pi via REST API. The base URL is constructed as `http://{RASPBERRY_PI_IP}:{BACKEND_PORT}` (configured via env vars).

**Expected Backend Endpoints**:
- `GET /api/sensors/{plant_name}` - Current moisture reading
- `GET /api/sensors/{plant_name}/history?hours=24` - Historical data
- `GET /api/water-tank` - Tank level and capacity
- `POST /api/irrigate` - Trigger irrigation pump

**For Development Without Hardware**: See README.md "Mock Backend for Testing" section for a Flask-based simulator.

## Testing Considerations

- Tools can be tested individually by importing and calling them directly
- Use environment variable `RASPBERRY_PI_IP=localhost` with mock backend for integration testing
- Agent behavior testing requires Google Gemini API key (get free at https://makersuite.google.com/app/apikey)
- FastAPI endpoints can be tested via `/docs` interactive interface or `curl`

## Cloud Run Deployment Architecture

The application is containerized and deployed to Google Cloud Run:
- **Entry point**: [main.py](main.py) with uvicorn server
- **Build config**: [cloudbuild.yaml](cloudbuild.yaml) defines CI/CD pipeline
- **Port**: Must listen on port 8080 (Cloud Run requirement)
- **Environment**: Set env vars via `--set-env-vars` in gcloud deploy command or Secret Manager
- **Scaling**: Configured for 0-10 instances, 512Mi RAM, 1 CPU

## Model Selection Strategy

The system uses **two different Gemini models** strategically:
- **gemini-2.5-flash** (worker_model): Fast operations (monitoring, alerts, coordination)
- **gemini-2.5-pro** (critic_model): Complex analysis (plant health, optimization)

**Rationale**: Balance speed for real-time monitoring with power for botanical expertise and complex optimization.

## Custom Plant Configuration

To add/modify plants in the system, edit the plant list in [tools.py](irrigation_agent/tools.py) `get_system_status()` function around line 550:

```python
plants = ["tomato", "basil", "lettuce", "pepper", "cucumber"]
```

Each plant needs a corresponding backend sensor endpoint.

## Critical Dependencies

- **google-adk**: Agent Development Kit - core framework for multi-agent system
- **google-genai**: Gemini models integration
- **fastapi + uvicorn**: REST API server for Cloud Run
- **requests**: Communication with IoT backend
- **pydantic**: Data validation and configuration
- **python-dotenv**: Environment variable management

**Version constraints**: google-cloud-aiplatform[adk,agent-engines]>=1.117.0 required for latest agent features.
