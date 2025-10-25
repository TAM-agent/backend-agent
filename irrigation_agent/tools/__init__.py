"""Tools package exposing agent tools via organized submodules.

This package re-exports functions from specialized submodules to preserve
backward compatibility with previous rom irrigation_agent.tools import ...
imports. Implementation currently delegates to legacy code in tools_old
where applicable, to enable incremental refactor.
"""

# API/external tools
from .tools_api import get_weather_forecast  # noqa: F401

# Sensors
from .sensors import (
    check_soil_moisture,
    check_water_tank_level,
    get_sensor_history,
)  # noqa: F401

# Control/actuation
from .control import trigger_irrigation  # noqa: F401

# Notifications
from .notifications import send_notification  # noqa: F401

# Analysis
from .analysis import analyze_plant_health, get_system_status  # noqa: F401

# Gardens
from .gardens import (
    get_all_gardens,
    get_garden_status,
    get_all_gardens_status,
    get_plant_in_garden,
    get_garden_weather,
    get_irrigation_recommendation_with_weather,
)  # noqa: F401
