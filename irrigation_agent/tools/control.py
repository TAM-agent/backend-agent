from datetime import datetime
from typing import Dict, Any
import requests

from ._base import logger, USE_SIMULATION, simulator, iot_config


def trigger_irrigation(plant_name: str, duration_seconds: int) -> Dict[str, Any]:
    """Activate irrigation pump for specified plant and duration.

    Honors safety limits and supports simulation mode.
    """
    if duration_seconds > iot_config.max_irrigation_duration:
        logger.warning(
            f"Irrigation duration {duration_seconds}s exceeds maximum {iot_config.max_irrigation_duration}s. Capping."
        )
        duration_seconds = iot_config.max_irrigation_duration

    if USE_SIMULATION:
        try:
            success = simulator.trigger_irrigation(plant_name, duration_seconds) if simulator else False
            if success:
                logger.info(f"[SIM] Irrigation simulated for {plant_name} - {duration_seconds}s")
                return {
                    "plant": plant_name,
                    "duration_seconds": duration_seconds,
                    "status": "success",
                    "timestamp": datetime.now().isoformat(),
                    "simulated": True,
                }
            return {
                "plant": plant_name,
                "duration_seconds": duration_seconds,
                "status": "error",
                "timestamp": datetime.now().isoformat(),
                "error": "Simulation failed",
                "simulated": True,
            }
        except Exception as e:
            logger.error(f"Simulation error triggering irrigation for {plant_name}: {e}")
            return {
                "plant": plant_name,
                "duration_seconds": duration_seconds,
                "status": "error",
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "simulated": True,
            }

    try:
        url = f"{iot_config.base_url}/api/irrigate"
        payload = {"plant": plant_name, "duration": duration_seconds}
        response = requests.post(url, json=payload, timeout=iot_config.pump_timeout)
        response.raise_for_status()
        logger.info(f"Irrigation started for {plant_name} - {duration_seconds}s")
        return {
            "plant": plant_name,
            "duration_seconds": duration_seconds,
            "status": "success",
            "timestamp": datetime.now().isoformat(),
        }
    except requests.RequestException as e:
        logger.error(f"Error triggering irrigation for {plant_name}: {e}")
        return {
            "plant": plant_name,
            "duration_seconds": duration_seconds,
            "status": "error",
            "timestamp": datetime.now().isoformat(),
            "error": str(e),
        }
