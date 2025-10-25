# Delegating wrappers to legacy implementations for staged refactor
from datetime import datetime
from typing import Dict, Any
import requests

from ._base import logger, USE_SIMULATION, simulator, iot_config


def check_soil_moisture(plant_name: str) -> Dict[str, Any]:
    """Read current soil moisture level from IoT sensor or simulation."""
    if USE_SIMULATION:
        moisture = simulator.get_plant_moisture(plant_name) if simulator else None
        if moisture is not None:
            return {
                "plant": plant_name,
                "moisture_level": moisture,
                "timestamp": datetime.now().isoformat(),
                "status": "success",
            }
        return {
            "plant": plant_name,
            "moisture_level": None,
            "timestamp": datetime.now().isoformat(),
            "status": "error",
            "error": f"Plant {plant_name} not found in simulation data",
        }

    try:
        url = f"{iot_config.base_url}/api/sensors/{plant_name}"
        response = requests.get(url, timeout=iot_config.sensor_timeout)
        response.raise_for_status()
        data = response.json()
        return {
            "plant": plant_name,
            "moisture_level": data.get("moisture", 0),
            "timestamp": datetime.now().isoformat(),
            "status": "success",
        }
    except requests.RequestException as e:
        logger.error(f"Error reading soil moisture for {plant_name}: {e}")
        return {
            "plant": plant_name,
            "moisture_level": None,
            "timestamp": datetime.now().isoformat(),
            "status": "error",
            "error": str(e),
        }


def check_water_tank_level() -> Dict[str, Any]:
    """Retrieve current water tank level."""
    if USE_SIMULATION:
        tank_data = simulator.get_water_tank_status() if simulator else {}
        return {
            "level_percentage": tank_data.get("level_percentage", 0),
            "capacity_liters": tank_data.get("capacity_liters", 0),
            "timestamp": datetime.now().isoformat(),
            "status": "success",
        }

    try:
        url = f"{iot_config.base_url}/api/water-tank"
        response = requests.get(url, timeout=iot_config.sensor_timeout)
        response.raise_for_status()
        data = response.json()
        return {
            "level_percentage": data.get("level", 0),
            "capacity_liters": data.get("capacity", 0),
            "timestamp": datetime.now().isoformat(),
            "status": "success",
        }
    except requests.RequestException as e:
        logger.error(f"Error reading water tank level: {e}")
        return {
            "level_percentage": None,
            "capacity_liters": None,
            "timestamp": datetime.now().isoformat(),
            "status": "error",
            "error": str(e),
        }


def get_sensor_history(plant_name: str, hours: int = 24) -> Dict[str, Any]:
    """Retrieve historical sensor data for pattern analysis."""
    if USE_SIMULATION:
        history = simulator.get_plant_history(plant_name, hours) if simulator else []
        return {
            "plant": plant_name,
            "history": history,
            "hours_analyzed": hours,
            "timestamp": datetime.now().isoformat(),
            "status": "success",
        }

    try:
        url = f"{iot_config.base_url}/api/sensors/{plant_name}/history"
        params = {"hours": hours}
        response = requests.get(url, params=params, timeout=iot_config.sensor_timeout)
        response.raise_for_status()
        data = response.json()
        return {
            "plant": plant_name,
            "history": data.get("history", []),
            "hours_analyzed": hours,
            "timestamp": datetime.now().isoformat(),
            "status": "success",
        }
    except requests.RequestException as e:
        logger.error(f"Error reading sensor history for {plant_name}: {e}")
        return {
            "plant": plant_name,
            "history": [],
            "hours_analyzed": hours,
            "timestamp": datetime.now().isoformat(),
            "status": "error",
            "error": str(e),
        }
