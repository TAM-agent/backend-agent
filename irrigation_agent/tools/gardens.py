from datetime import datetime
from typing import Dict, Any

from ._base import logger, USE_SIMULATION, simulator
from irrigation_agent.service.weather_service import (
    get_weather_for_garden,
    get_irrigation_recommendation,
)


def _sim_enabled() -> bool:
    try:
        return bool(simulator and (getattr(simulator, 'use_firestore', False) or USE_SIMULATION))
    except Exception:
        return USE_SIMULATION


def get_all_gardens() -> Dict[str, Any]:
    try:
        if _sim_enabled():
            gardens = simulator.get_all_gardens()
            return {
                "gardens": gardens,
                "total_gardens": len(gardens),
                "status": "success",
                "timestamp": datetime.now().isoformat(),
            }
        else:
            return {
                "gardens": {},
                "total_gardens": 0,
                "status": "error",
                "error": "Real IoT mode not implemented for gardens yet",
                "timestamp": datetime.now().isoformat(),
            }
    except Exception as e:
        logger.error(f"Error getting all gardens: {e}")
        return {
            "gardens": {},
            "total_gardens": 0,
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


def get_garden_status(garden_id: str) -> Dict[str, Any]:
    try:
        if _sim_enabled():
            garden = simulator.get_garden(garden_id)
            if not garden:
                return {
                    "status": "error",
                    "error": f"Garden {garden_id} not found",
                    "timestamp": datetime.now().isoformat(),
                }
            plants = simulator.get_garden_plants(garden_id)
            plant_status = {}
            critical_issues = []
            warnings = []
            for plant_id, plant_data in plants.items():
                moisture = plant_data.get("current_moisture")
                plant_status[plant_id] = {
                    "name": plant_data.get("name", plant_id),
                    "moisture": moisture,
                    "health": _classify_health(moisture),
                    "last_irrigation": plant_data.get("last_irrigation"),
                    "last_updated": str(plant_data.get("last_updated", "")),
                }
                if moisture is not None:
                    if moisture < 20:
                        critical_issues.append(f"{plant_id} critically dehydrated ({moisture}%)")
                    elif moisture < 40:
                        warnings.append(f"{plant_id} moisture low ({moisture}%)")
                    elif moisture > 85:
                        warnings.append(f"{plant_id} possibly overwatered ({moisture}%)")
            if critical_issues:
                overall_health = "critical"
            elif warnings:
                overall_health = "warning"
            else:
                overall_health = "healthy"
            return {
                "garden_id": garden_id,
                "garden_name": garden.get("name"),
                "personality": garden.get("personality"),
                "location": garden.get("location"),
                "plant_type": garden.get("plant_type"),
                "area_m2": garden.get("area_m2"),
                "overall_health": overall_health,
                "plant_status": plant_status,
                "critical_issues": critical_issues,
                "warnings": warnings,
                "total_plants": len(plants),
                "status": "success",
                "timestamp": datetime.now().isoformat(),
            }
        else:
            return {
                "status": "error",
                "error": "Real IoT mode not implemented for gardens yet",
                "timestamp": datetime.now().isoformat(),
            }
    except Exception as e:
        logger.error(f"Error getting garden {garden_id} status: {e}")
        return {"status": "error", "error": str(e), "timestamp": datetime.now().isoformat()}


def get_all_gardens_status() -> Dict[str, Any]:
    try:
        if _sim_enabled():
            gardens_data = simulator.get_all_gardens()
            all_gardens_status = {}
            total_critical = 0
            total_warnings = 0
            for gid in gardens_data.keys():
                garden_status = get_garden_status(gid)
                all_gardens_status[gid] = garden_status
                if garden_status.get("status") == "success":
                    total_critical += len(garden_status.get("critical_issues", []))
                    total_warnings += len(garden_status.get("warnings", []))
            overall_health = "healthy"
            if total_critical > 0:
                overall_health = "critical"
            elif total_warnings > 0:
                overall_health = "warning"
            return {
                "status": "success",
                "overall_health": overall_health,
                "gardens": all_gardens_status,
                "total_critical_issues": total_critical,
                "total_warnings": total_warnings,
                "timestamp": datetime.now().isoformat(),
            }
        else:
            return {
                "status": "error",
                "error": "Real IoT mode not implemented for gardens yet",
                "timestamp": datetime.now().isoformat(),
            }
    except Exception as e:
        logger.error(f"Error getting all gardens status: {e}")
        return {"status": "error", "error": str(e), "timestamp": datetime.now().isoformat()}


def get_plant_in_garden(garden_id: str, plant_id: str) -> Dict[str, Any]:
    try:
        if _sim_enabled():
            plant = simulator.get_garden_plant(garden_id, plant_id)
            if not plant:
                return {"status": "error", "error": "Plant not found", "timestamp": datetime.now().isoformat()}
            moisture = plant.get("current_moisture")
            return {
                "garden_id": garden_id,
                "plant_id": plant_id,
                "plant_name": plant.get("name", plant_id),
                "current_moisture": moisture,
                "health": _classify_health(moisture),
                "last_irrigation": plant.get("last_irrigation"),
                "last_updated": str(plant.get("last_updated", "")),
                "status": "success",
                "timestamp": datetime.now().isoformat(),
            }
        else:
            return {
                "status": "error",
                "error": "Real IoT mode not implemented for gardens yet",
                "timestamp": datetime.now().isoformat(),
            }
    except Exception as e:
        logger.error(f"Error getting plant {plant_id} in garden {garden_id}: {e}")
        return {"status": "error", "error": str(e), "timestamp": datetime.now().isoformat()}


def get_garden_weather(garden_id: str) -> Dict[str, Any]:
    try:
        garden = simulator.get_garden(garden_id) if simulator else None
        if not garden:
            return {"status": "error", "error": f"Garden {garden_id} not found", "timestamp": datetime.now().isoformat()}
        latitude = garden.get("latitude")
        longitude = garden.get("longitude")
        if not latitude or not longitude:
            return {"status": "error", "error": "Garden location coordinates not available", "timestamp": datetime.now().isoformat()}
        weather_data = get_weather_for_garden(latitude, longitude)
        weather_data["garden_id"] = garden_id
        weather_data["garden_name"] = garden.get("name")
        weather_data["garden_location"] = garden.get("location")
        return weather_data
    except Exception as e:
        logger.error(f"Error getting weather for garden {garden_id}: {e}")
        return {"status": "error", "error": str(e), "timestamp": datetime.now().isoformat()}


def get_irrigation_recommendation_with_weather(garden_id: str, plant_id: str) -> Dict[str, Any]:
    try:
        plant_data = get_plant_in_garden(garden_id, plant_id)
        if plant_data.get("status") != "success":
            return plant_data
        weather_data = get_garden_weather(garden_id)
        if weather_data.get("status") != "success":
            moisture = plant_data.get("current_moisture", 0)
            return {
                "action": "irrigate_soon" if moisture < 40 else "monitor",
                "reason": f"Humedad actual: {moisture}%. Sin datos meteorológicos disponibles.",
                "weather_available": False,
                "plant_data": plant_data,
                "status": "success",
                "timestamp": datetime.now().isoformat(),
            }
        recommendation = get_irrigation_recommendation(weather_data, plant_data.get("current_moisture", 0))
        recommendation["plant_data"] = {
            "garden_id": garden_id,
            "plant_id": plant_id,
            "plant_name": plant_data.get("plant_name"),
            "current_moisture": plant_data.get("current_moisture"),
            "health": plant_data.get("health"),
        }
        recommendation["weather_data"] = {
            "current_temp": weather_data.get("current", {}).get("temperature"),
            "current_humidity": weather_data.get("current", {}).get("humidity"),
            "rain_forecast": weather_data.get("forecast", [])[:2],
        }
        return recommendation
    except Exception as e:
        logger.error(f"Error getting recommendation for {plant_id} in {garden_id}: {e}")
        return {"status": "error", "error": str(e), "timestamp": datetime.now().isoformat()}



def _classify_health(moisture):
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
