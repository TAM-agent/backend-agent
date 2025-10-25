from datetime import datetime
from typing import Dict, Any, Optional

from ._base import logger
from .sensors import get_sensor_history, check_soil_moisture, check_water_tank_level


def analyze_plant_health(plant_name: str, image_path: Optional[str] = None) -> Dict[str, Any]:
    """Analyze plant health using sensor data and optional visual analysis.

    Currently based on recent moisture history. Image analysis can be added later.
    """
    try:
        history = get_sensor_history(plant_name, hours=24)
        if history["status"] == "error" or not history["history"]:
            return {
                "plant": plant_name,
                "health_score": None,
                "avg_moisture": None,
                "issues": ["No sensor data available"],
                "recommendations": ["Check sensor connectivity"],
                "timestamp": datetime.now().isoformat(),
                "status": "error",
            }

        moisture_readings = [reading.get("moisture", 0) for reading in history["history"]]
        avg_moisture = sum(moisture_readings) / len(moisture_readings)

        issues = []
        recommendations = []
        if avg_moisture < 30:
            health_score = 2
            issues.append("Critical dehydration risk")
            recommendations.append("Immediate irrigation required")
        elif avg_moisture < 50:
            health_score = 3
            issues.append("Slightly low moisture")
            recommendations.append("Monitor closely and consider irrigation")
        elif avg_moisture <= 80:
            health_score = 4
            recommendations.append("Moisture levels optimal")
        else:
            health_score = 3
            issues.append("Possible overwatering")
            recommendations.append("Reduce irrigation frequency")

        if len(moisture_readings) > 1:
            variance = max(moisture_readings) - min(moisture_readings)
            if variance > 30:
                issues.append("High moisture volatility")
                recommendations.append("Stabilize irrigation schedule")

        return {
            "plant": plant_name,
            "health_score": health_score,
            "avg_moisture": round(avg_moisture, 1),
            "issues": issues,
            "recommendations": recommendations,
            "timestamp": datetime.now().isoformat(),
            "status": "success",
        }
    except Exception as e:
        logger.error(f"Error analyzing plant health for {plant_name}: {e}")
        return {
            "plant": plant_name,
            "health_score": None,
            "avg_moisture": None,
            "issues": [str(e)],
            "recommendations": [],
            "timestamp": datetime.now().isoformat(),
            "status": "error",
            "error": str(e),
        }


def get_system_status() -> Dict[str, Any]:
    """Compute overall system status including tank and plants health."""
    try:
        tank_status = check_water_tank_level()

        # TODO: make plant list configurable
        plants = ["tomato", "basil", "lettuce", "pepper"]

        plant_status: Dict[str, Any] = {}
        critical_issues = []
        warnings = []

        for plant in plants:
            moisture_data = check_soil_moisture(plant)
            if moisture_data["status"] == "error":
                critical_issues.append(f"Sensor error for {plant}")
                plant_status[plant] = {"moisture": None, "health": "unknown"}
            else:
                moisture = moisture_data["moisture_level"]
                plant_status[plant] = {
                    "moisture": moisture,
                    "health": _classify_health(moisture),
                }
                if moisture is not None:
                    if moisture < 20:
                        critical_issues.append(f"{plant} critically dehydrated ({moisture}%)")
                    elif moisture < 40:
                        warnings.append(f"{plant} moisture low ({moisture}%)")
                    elif moisture > 85:
                        warnings.append(f"{plant} possibly overwatered ({moisture}%)")

        if tank_status["status"] == "success":
            level = tank_status["level_percentage"]
            if level is not None:
                if level < 10:
                    critical_issues.append(f"Water tank critical ({level}%)")
                elif level < 30:
                    warnings.append(f"Water tank low ({level}%)")
        else:
            critical_issues.append("Water tank sensor error")

        if critical_issues:
            overall_health = "critical"
        elif warnings:
            overall_health = "warning"
        else:
            overall_health = "healthy"

        return {
            "overall_health": overall_health,
            "water_tank": {
                "level_percentage": tank_status.get("level_percentage"),
                "capacity_liters": tank_status.get("capacity_liters"),
                "status": "critical"
                if tank_status.get("level_percentage", 100) < 10
                else "low"
                if tank_status.get("level_percentage", 100) < 30
                else "normal",
            },
            "plant_status": plant_status,
            "critical_issues": critical_issues,
            "warnings": warnings,
            "timestamp": datetime.now().isoformat(),
            "status": "success",
        }
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        return {
            "overall_health": "unknown",
            "water_tank": {},
            "plant_status": {},
            "critical_issues": [str(e)],
            "warnings": [],
            "timestamp": datetime.now().isoformat(),
            "status": "error",
            "error": str(e),
        }


def _classify_health(moisture: Optional[float]) -> str:
    if moisture is None:
        return "unknown"
    elif moisture < 30:
        return "poor"
    elif moisture < 50:
        return "fair"
    elif moisture <= 80:
        return "good"
    else:
        return "fair"
