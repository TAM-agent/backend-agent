"""Tool implementations for the intelligent irrigation agent.

This module provides all the functions that agents can call to interact with:
- IoT sensors (soil moisture, water tank level)
- Hardware actuators (irrigation pumps)
- External APIs (weather forecasts)
- User notifications
- Plant health analysis

Each tool returns a standardized dictionary with status, data, and timestamp.
"""

import requests
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import logging

from .config import iot_config, weather_config, notification_config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Check if we should use Firestore simulation
USE_SIMULATION = os.getenv('USE_SIMULATION', 'false').lower() == 'true'

if USE_SIMULATION:
    from .firebase_service import simulator
    logger.info("Using Firestore simulation for sensor data")


# ============================================================================
# CORE IOT MONITORING TOOLS
# ============================================================================

def check_soil_moisture(plant_name: str) -> Dict[str, Any]:
    """Read current soil moisture level from IoT sensor.

    Queries the Node.js/Express backend running on Raspberry Pi or Firestore simulation
    to retrieve the current soil moisture reading for a specific plant.

    Args:
        plant_name: Identifier for the plant sensor (e.g., 'tomato', 'basil', 'lettuce')

    Returns:
        Dictionary containing:
            - plant: Name of the plant
            - moisture_level: Moisture percentage (0-100)
            - timestamp: ISO format timestamp of the reading
            - status: 'success' or 'error'
            - error: Error message if status is 'error'

    Example:
        >>> check_soil_moisture("tomato")
        {
            "plant": "tomato",
            "moisture_level": 45,
            "timestamp": "2025-10-23T10:30:00",
            "status": "success"
        }
    """
    if USE_SIMULATION:
        moisture = simulator.get_plant_moisture(plant_name)
        if moisture is not None:
            return {
                "plant": plant_name,
                "moisture_level": moisture,
                "timestamp": datetime.now().isoformat(),
                "status": "success"
            }
        else:
            return {
                "plant": plant_name,
                "moisture_level": None,
                "timestamp": datetime.now().isoformat(),
                "status": "error",
                "error": f"Plant {plant_name} not found in simulation data"
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
            "status": "success"
        }

    except requests.RequestException as e:
        logger.error(f"Error reading soil moisture for {plant_name}: {e}")
        return {
            "plant": plant_name,
            "moisture_level": None,
            "timestamp": datetime.now().isoformat(),
            "status": "error",
            "error": str(e)
        }


def check_water_tank_level() -> Dict[str, Any]:
    """Retrieve current water tank level.

    Queries the backend or Firestore simulation to get the current water reservoir level and capacity.

    Returns:
        Dictionary containing:
            - level_percentage: Tank fill level (0-100)
            - capacity_liters: Total tank capacity
            - timestamp: ISO format timestamp
            - status: 'success' or 'error'
            - error: Error message if status is 'error'

    Example:
        >>> check_water_tank_level()
        {
            "level_percentage": 75,
            "capacity_liters": 100,
            "timestamp": "2025-10-23T10:30:00",
            "status": "success"
        }
    """
    if USE_SIMULATION:
        tank_data = simulator.get_water_tank_status()
        return {
            "level_percentage": tank_data.get("level_percentage", 0),
            "capacity_liters": tank_data.get("capacity_liters", 0),
            "timestamp": datetime.now().isoformat(),
            "status": "success"
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
            "status": "success"
        }

    except requests.RequestException as e:
        logger.error(f"Error reading water tank level: {e}")
        return {
            "level_percentage": None,
            "capacity_liters": None,
            "timestamp": datetime.now().isoformat(),
            "status": "error",
            "error": str(e)
        }


def get_sensor_history(plant_name: str, hours: int = 24) -> Dict[str, Any]:
    """Retrieve historical sensor data for pattern analysis.

    Fetches historical moisture readings from MongoDB or Firestore simulation for trend analysis,
    anomaly detection, and optimization insights.

    Args:
        plant_name: Identifier for the plant sensor
        hours: Number of hours of history to retrieve (default: 24)

    Returns:
        Dictionary containing:
            - plant: Name of the plant
            - history: List of historical readings with timestamps
            - hours_analyzed: Number of hours requested
            - timestamp: Current timestamp
            - status: 'success' or 'error'
            - error: Error message if status is 'error'

    Example:
        >>> get_sensor_history("tomato", hours=6)
        {
            "plant": "tomato",
            "history": [
                {"moisture": 45, "timestamp": "2025-10-23T08:00:00"},
                {"moisture": 42, "timestamp": "2025-10-23T09:00:00"},
                ...
            ],
            "hours_analyzed": 6,
            "timestamp": "2025-10-23T10:30:00",
            "status": "success"
        }
    """
    if USE_SIMULATION:
        history = simulator.get_plant_history(plant_name, hours)
        return {
            "plant": plant_name,
            "history": history,
            "hours_analyzed": hours,
            "timestamp": datetime.now().isoformat(),
            "status": "success"
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
            "status": "success"
        }

    except requests.RequestException as e:
        logger.error(f"Error reading sensor history for {plant_name}: {e}")
        return {
            "plant": plant_name,
            "history": [],
            "hours_analyzed": hours,
            "timestamp": datetime.now().isoformat(),
            "status": "error",
            "error": str(e)
        }


# ============================================================================
# CONTROL AND ACTUATION TOOLS
# ============================================================================

def trigger_irrigation(plant_name: str, duration_seconds: int) -> Dict[str, Any]:
    """Activate irrigation pump for specified plant and duration.

    Sends command to the backend to activate the relay controlling the water
    pump for a specific plant. Includes safety limits on maximum duration.

    Args:
        plant_name: Identifier for the plant to irrigate
        duration_seconds: How long to run the pump (max: max_irrigation_duration)

    Returns:
        Dictionary containing:
            - plant: Name of the plant
            - duration_seconds: Actual duration (capped at maximum)
            - status: 'success' or 'error'
            - timestamp: ISO format timestamp
            - error: Error message if status is 'error'

    Example:
        >>> trigger_irrigation("tomato", 30)
        {
            "plant": "tomato",
            "duration_seconds": 30,
            "status": "success",
            "timestamp": "2025-10-23T10:30:00"
        }
    """
    # Safety check: cap duration at maximum allowed
    if duration_seconds > iot_config.max_irrigation_duration:
        logger.warning(
            f"Irrigation duration {duration_seconds}s exceeds maximum "
            f"{iot_config.max_irrigation_duration}s. Capping to maximum."
        )
        duration_seconds = iot_config.max_irrigation_duration

    # Simulation path: update moisture via simulator without HTTP
    if USE_SIMULATION:
        try:
            success = simulator.trigger_irrigation(plant_name, duration_seconds)
            if success:
                logger.info(f"[SIM] Irrigation simulated for {plant_name} - {duration_seconds}s")
                return {
                    "plant": plant_name,
                    "duration_seconds": duration_seconds,
                    "status": "success",
                    "timestamp": datetime.now().isoformat(),
                    "simulated": True
                }
            else:
                return {
                    "plant": plant_name,
                    "duration_seconds": duration_seconds,
                    "status": "error",
                    "timestamp": datetime.now().isoformat(),
                    "error": "Simulation failed",
                    "simulated": True
                }
        except Exception as e:
            logger.error(f"Simulation error triggering irrigation for {plant_name}: {e}")
            return {
                "plant": plant_name,
                "duration_seconds": duration_seconds,
                "status": "error",
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "simulated": True
            }

    try:
        url = f"{iot_config.base_url}/api/irrigate"
        payload = {
            "plant": plant_name,
            "duration": duration_seconds
        }
        response = requests.post(
            url,
            json=payload,
            timeout=iot_config.pump_timeout
        )
        response.raise_for_status()

        logger.info(f"Irrigation started for {plant_name} - {duration_seconds}s")

        return {
            "plant": plant_name,
            "duration_seconds": duration_seconds,
            "status": "success",
            "timestamp": datetime.now().isoformat()
        }

    except requests.RequestException as e:
        logger.error(f"Error triggering irrigation for {plant_name}: {e}")
        return {
            "plant": plant_name,
            "duration_seconds": duration_seconds,
            "status": "error",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }


# ============================================================================
# NOTIFICATION AND REPORTING TOOLS
# ============================================================================

def send_notification(message: str, priority: str = "medium") -> Dict[str, Any]:
    """Send notification to user with priority classification.

    Sends alerts to configured notification channels (Telegram, email, etc.)
    based on priority level. Implements alert fatigue prevention.

    Args:
        message: The notification message to send
        priority: Priority level - 'low', 'medium', 'high', or 'critical'

    Returns:
        Dictionary containing:
            - message: The notification message
            - priority: Priority level
            - sent: Boolean indicating if notification was sent
            - channels: List of channels used
            - timestamp: ISO format timestamp
            - status: 'success' or 'error'

    Priority Levels:
        - CRITICAL: Immediate action required (tank empty, sensor failure, plant death risk)
        - HIGH: Urgent attention needed (low moisture, equipment malfunction)
        - MEDIUM: Important but not urgent (maintenance, optimization opportunities)
        - LOW: Informational (status updates, tips, routine notifications)

    Example:
        >>> send_notification("Water tank at 5% - refill needed", "critical")
        {
            "message": "Water tank at 5% - refill needed",
            "priority": "critical",
            "sent": True,
            "channels": ["telegram", "email"],
            "timestamp": "2025-10-23T10:30:00",
            "status": "success"
        }
    """
    priority = priority.lower()
    valid_priorities = ["low", "medium", "high", "critical"]

    if priority not in valid_priorities:
        priority = "medium"

    channels_used = []

    # Log notification (always)
    logger.info(f"[{priority.upper()}] {message}")
    channels_used.append("log")

    # Send to Telegram if configured and priority is high enough
    if notification_config.has_telegram and priority in ["high", "critical"]:
        try:
            _send_telegram_notification(message, priority)
            channels_used.append("telegram")
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")

    # Send email if configured and priority is critical
    if notification_config.has_email and priority == "critical":
        try:
            _send_email_notification(message, priority)
            channels_used.append("email")
        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")

    return {
        "message": message,
        "priority": priority,
        "sent": True,
        "channels": channels_used,
        "timestamp": datetime.now().isoformat(),
        "status": "success"
    }


def _send_telegram_notification(message: str, priority: str) -> None:
    """Send notification via Telegram Bot API."""
    url = f"https://api.telegram.org/bot{notification_config.telegram_bot_token}/sendMessage"

    # Add emoji based on priority
    emoji_map = {
        "critical": "🚨",
        "high": "⚠️",
        "medium": "ℹ️",
        "low": "💡"
    }
    emoji = emoji_map.get(priority, "ℹ️")

    # Ensure emoji selection uses safe Unicode mapping
    emoji = {
        "critical": "🚨",
        "high": "⚠️",
        "medium": "ℹ️",
        "low": "✅",
    }.get(priority, "ℹ️")

    formatted_message = f"{emoji} *{priority.upper()}*\n\n{message}"

    payload = {
        "chat_id": notification_config.telegram_chat_id,
        "text": formatted_message,
        "parse_mode": "Markdown"
    }

    response = requests.post(url, json=payload, timeout=10)
    response.raise_for_status()


def _send_email_notification(message: str, priority: str) -> None:
    """Send notification via email SMTP."""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    msg = MIMEMultipart()
    msg['From'] = notification_config.smtp_username
    msg['To'] = notification_config.notification_email
    msg['Subject'] = f"[{priority.upper()}] Irrigation System Alert"

    body = f"""
    Priority: {priority.upper()}
    Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

    {message}

    ---
    Intelligent Irrigation System
    """

    msg.attach(MIMEText(body, 'plain'))

    with smtplib.SMTP(notification_config.smtp_server, notification_config.smtp_port) as server:
        server.starttls()
        server.login(notification_config.smtp_username, notification_config.smtp_password)
        server.send_message(msg)


# ============================================================================
# WEATHER AND EXTERNAL DATA TOOLS
# ============================================================================

def get_weather_forecast(days: int = 3) -> Dict[str, Any]:
    """Fetch weather forecast from OpenWeatherMap API.

    Retrieves weather forecast data including temperature, humidity, and
    precipitation probability for optimization of irrigation schedules.

    Args:
        days: Number of days to forecast (default: 3)

    Returns:
        Dictionary containing:
            - forecast: List of forecast entries with temp, humidity, precipitation
            - days: Number of days forecasted
            - location: Location queried
            - timestamp: ISO format timestamp
            - status: 'success' or 'error'
            - error: Error message if status is 'error'

    Example:
        >>> get_weather_forecast(days=3)
        {
            "forecast": [
                {
                    "date": "2025-10-23",
                    "temp_celsius": 22,
                    "humidity": 65,
                    "precipitation_prob": 0.1,
                    "description": "partly cloudy"
                },
                ...
            ],
            "days": 3,
            "location": "Santiago,CL",
            "timestamp": "2025-10-23T10:30:00",
            "status": "success"
        }
    """
    if not weather_config.openweather_api_key:
        logger.warning("OpenWeatherMap API key not configured")
        return {
            "forecast": [],
            "days": days,
            "location": weather_config.location,
            "timestamp": datetime.now().isoformat(),
            "status": "error",
            "error": "API key not configured"
        }

    try:
        url = "https://api.openweathermap.org/data/2.5/forecast"
        params = {
            "q": weather_config.location,
            "appid": weather_config.openweather_api_key,
            "units": "metric",
            "cnt": days * 8  # 8 forecasts per day (3-hour intervals)
        }

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()

        # Process forecast data
        forecast = []
        for item in data.get("list", []):
            forecast.append({
                "date": item["dt_txt"],
                "temp_celsius": item["main"]["temp"],
                "humidity": item["main"]["humidity"],
                "precipitation_prob": item.get("pop", 0),  # Probability of precipitation
                "description": item["weather"][0]["description"]
            })

        return {
            "forecast": forecast,
            "days": days,
            "location": weather_config.location,
            "timestamp": datetime.now().isoformat(),
            "status": "success"
        }

    except requests.RequestException as e:
        logger.error(f"Error fetching weather forecast: {e}")
        return {
            "forecast": [],
            "days": days,
            "location": weather_config.location,
            "timestamp": datetime.now().isoformat(),
            "status": "error",
            "error": str(e)
        }


# ============================================================================
# ANALYSIS AND ASSESSMENT TOOLS
# ============================================================================

def analyze_plant_health(plant_name: str, image_path: Optional[str] = None) -> Dict[str, Any]:
    """Analyze plant health using sensor data and optional visual analysis.

    Assesses plant health based on historical sensor data patterns. Can be
    extended with multimodal image analysis for visual deficiency detection.

    Args:
        plant_name: Identifier for the plant to analyze
        image_path: Optional path to plant image for visual analysis

    Returns:
        Dictionary containing:
            - plant: Name of the plant
            - health_score: Numerical score (2=poor, 3=fair, 4=good)
            - avg_moisture: Average moisture over analysis period
            - issues: List of detected issues
            - recommendations: List of recommended actions
            - timestamp: ISO format timestamp
            - status: 'success' or 'error'

    Health Score Scale:
        - 4 (Good): Optimal moisture range (50-80%)
        - 3 (Fair): Suboptimal but acceptable (30-50% or >80%)
        - 2 (Poor): Critical range (<30% dehydration risk)

    Example:
        >>> analyze_plant_health("tomato")
        {
            "plant": "tomato",
            "health_score": 3,
            "avg_moisture": 42,
            "issues": ["Slightly low moisture"],
            "recommendations": ["Monitor closely", "Consider irrigation"],
            "timestamp": "2025-10-23T10:30:00",
            "status": "success"
        }
    """
    try:
        # Get recent sensor history
        history = get_sensor_history(plant_name, hours=24)

        if history["status"] == "error" or not history["history"]:
            return {
                "plant": plant_name,
                "health_score": None,
                "avg_moisture": None,
                "issues": ["No sensor data available"],
                "recommendations": ["Check sensor connectivity"],
                "timestamp": datetime.now().isoformat(),
                "status": "error"
            }

        # Calculate average moisture
        moisture_readings = [reading.get("moisture", 0) for reading in history["history"]]
        avg_moisture = sum(moisture_readings) / len(moisture_readings)

        # Determine health score and issues
        issues = []
        recommendations = []

        if avg_moisture < 30:
            health_score = 2  # Poor
            issues.append("Critical dehydration risk")
            recommendations.append("Immediate irrigation required")
        elif avg_moisture < 50:
            health_score = 3  # Fair
            issues.append("Slightly low moisture")
            recommendations.append("Monitor closely and consider irrigation")
        elif avg_moisture <= 80:
            health_score = 4  # Good
            recommendations.append("Moisture levels optimal")
        else:
            health_score = 3  # Fair
            issues.append("Possible overwatering")
            recommendations.append("Reduce irrigation frequency")

        # Check for moisture volatility
        if len(moisture_readings) > 1:
            variance = max(moisture_readings) - min(moisture_readings)
            if variance > 30:
                issues.append("High moisture volatility")
                recommendations.append("Stabilize irrigation schedule")

        # TODO: Add image analysis using multimodal LLM if image_path provided
        # This would detect visual deficiencies like chlorosis, necrosis, etc.

        return {
            "plant": plant_name,
            "health_score": health_score,
            "avg_moisture": round(avg_moisture, 1),
            "issues": issues,
            "recommendations": recommendations,
            "timestamp": datetime.now().isoformat(),
            "status": "success"
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
            "error": str(e)
        }


def get_system_status() -> Dict[str, Any]:
    """Get comprehensive system status overview.

    Queries all sensors and provides a holistic view of the irrigation system
    health, including water tank, all plant sensors, and critical issues.

    Returns:
        Dictionary containing:
            - overall_health: 'healthy', 'warning', or 'critical'
            - water_tank: Tank status information
            - plant_status: Dictionary of all plant statuses
            - critical_issues: List of critical problems
            - warnings: List of warnings
            - timestamp: ISO format timestamp
            - status: 'success' or 'error'

    Example:
        >>> get_system_status()
        {
            "overall_health": "warning",
            "water_tank": {"level": 25, "status": "low"},
            "plant_status": {
                "tomato": {"moisture": 35, "health": "fair"},
                "basil": {"moisture": 65, "health": "good"}
            },
            "critical_issues": [],
            "warnings": ["Water tank below 30%"],
            "timestamp": "2025-10-23T10:30:00",
            "status": "success"
        }
    """
    try:
        # Check water tank
        tank_status = check_water_tank_level()

        # Define plant list (this should be configurable or dynamic)
        # TODO: Make this configurable via environment or database
        plants = ["tomato", "basil", "lettuce", "pepper"]

        plant_status = {}
        critical_issues = []
        warnings = []

        # Check each plant
        for plant in plants:
            moisture_data = check_soil_moisture(plant)

            if moisture_data["status"] == "error":
                critical_issues.append(f"Sensor error for {plant}")
                plant_status[plant] = {"moisture": None, "health": "unknown"}
            else:
                moisture = moisture_data["moisture_level"]
                plant_status[plant] = {
                    "moisture": moisture,
                    "health": _classify_health(moisture)
                }

                if moisture is not None:
                    if moisture < 20:
                        critical_issues.append(f"{plant} critically dehydrated ({moisture}%)")
                    elif moisture < 40:
                        warnings.append(f"{plant} moisture low ({moisture}%)")
                    elif moisture > 85:
                        warnings.append(f"{plant} possibly overwatered ({moisture}%)")

        # Check water tank
        if tank_status["status"] == "success":
            level = tank_status["level_percentage"]
            if level is not None:
                if level < 10:
                    critical_issues.append(f"Water tank critical ({level}%)")
                elif level < 30:
                    warnings.append(f"Water tank low ({level}%)")
        else:
            critical_issues.append("Water tank sensor error")

        # Determine overall health
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
                "status": "critical" if tank_status.get("level_percentage", 100) < 10
                         else "low" if tank_status.get("level_percentage", 100) < 30
                         else "normal"
            },
            "plant_status": plant_status,
            "critical_issues": critical_issues,
            "warnings": warnings,
            "timestamp": datetime.now().isoformat(),
            "status": "success"
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
            "error": str(e)
        }


def _classify_health(moisture: Optional[float]) -> str:
    """Classify plant health based on moisture level."""
    if moisture is None:
        return "unknown"
    elif moisture < 30:
        return "poor"
    elif moisture < 50:
        return "fair"
    elif moisture <= 80:
        return "good"
    else:
        return "fair"  # Overwatering risk


# ============================================================================
# GARDEN-BASED FUNCTIONS (New Architecture)
# ============================================================================

def get_all_gardens() -> Dict[str, Any]:
    """Get all gardens from Firestore.

    Returns:
        Dictionary with garden data organized by garden ID.
        Each garden includes: id, name, personality, location, plant_type, etc.
    """
    try:
        if USE_SIMULATION:
            gardens = simulator.get_all_gardens()
            return {
                "gardens": gardens,
                "total_gardens": len(gardens),
                "status": "success",
                "timestamp": datetime.now().isoformat()
            }
        else:
            # Real IoT implementation would go here
            return {
                "gardens": {},
                "total_gardens": 0,
                "status": "error",
                "error": "Real IoT mode not implemented for gardens yet",
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        logger.error(f"Error getting all gardens: {e}")
        return {
            "gardens": {},
            "total_gardens": 0,
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


def get_garden_status(garden_id: str) -> Dict[str, Any]:
    """Get status for a specific garden and all its plants.

    Args:
        garden_id: The ID of the garden to query

    Returns:
        Dictionary containing garden info, plants status, and alerts
    """
    try:
        if USE_SIMULATION:
            # Get garden metadata
            garden = simulator.get_garden(garden_id)
            if not garden:
                return {
                    "status": "error",
                    "error": f"Garden {garden_id} not found",
                    "timestamp": datetime.now().isoformat()
                }

            # Get plants in this garden
            plants = simulator.get_garden_plants(garden_id)

            plant_status = {}
            critical_issues = []
            warnings = []

            for plant_id, plant_data in plants.items():
                moisture = plant_data.get('current_moisture')
                plant_status[plant_id] = {
                    "name": plant_data.get('name', plant_id),
                    "moisture": moisture,
                    "health": _classify_health(moisture),
                    "last_irrigation": plant_data.get('last_irrigation'),
                    "last_updated": str(plant_data.get('last_updated', ''))
                }

                if moisture is not None:
                    if moisture < 20:
                        critical_issues.append(f"{plant_id} critically dehydrated ({moisture}%)")
                    elif moisture < 40:
                        warnings.append(f"{plant_id} moisture low ({moisture}%)")
                    elif moisture > 85:
                        warnings.append(f"{plant_id} possibly overwatered ({moisture}%)")

            # Determine overall health
            if critical_issues:
                overall_health = "critical"
            elif warnings:
                overall_health = "warning"
            else:
                overall_health = "healthy"

            return {
                "garden_id": garden_id,
                "garden_name": garden.get('name'),
                "personality": garden.get('personality'),
                "location": garden.get('location'),
                "plant_type": garden.get('plant_type'),
                "area_m2": garden.get('area_m2'),
                "overall_health": overall_health,
                "plant_status": plant_status,
                "critical_issues": critical_issues,
                "warnings": warnings,
                "total_plants": len(plants),
                "status": "success",
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "status": "error",
                "error": "Real IoT mode not implemented for gardens yet",
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        logger.error(f"Error getting garden {garden_id} status: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


def get_all_gardens_status() -> Dict[str, Any]:
    """Get status for ALL gardens and their plants.

    Returns:
        Dictionary with status for each garden and overall system health.
    """
    try:
        if USE_SIMULATION:
            gardens_data = simulator.get_all_gardens()

            all_gardens_status = {}
            total_critical = 0
            total_warnings = 0

            for garden_id in gardens_data.keys():
                garden_status = get_garden_status(garden_id)
                all_gardens_status[garden_id] = garden_status

                if garden_status.get('status') == 'success':
                    total_critical += len(garden_status.get('critical_issues', []))
                    total_warnings += len(garden_status.get('warnings', []))

            # Overall system health
            if total_critical > 0:
                overall_health = "critical"
            elif total_warnings > 0:
                overall_health = "warning"
            else:
                overall_health = "healthy"

            return {
                "overall_health": overall_health,
                "total_gardens": len(all_gardens_status),
                "total_critical_issues": total_critical,
                "total_warnings": total_warnings,
                "gardens": all_gardens_status,
                "status": "success",
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "status": "error",
                "error": "Real IoT mode not implemented for gardens yet",
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        logger.error(f"Error getting all gardens status: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


def get_plant_in_garden(garden_id: str, plant_id: str) -> Dict[str, Any]:
    """Get detailed status for a specific plant in a garden.

    Args:
        garden_id: The garden ID
        plant_id: The plant ID within that garden

    Returns:
        Detailed plant data including moisture, history, health score
    """
    try:
        if USE_SIMULATION:
            plant = simulator.get_garden_plant(garden_id, plant_id)
            if not plant:
                return {
                    "status": "error",
                    "error": f"Plant {plant_id} not found in garden {garden_id}",
                    "timestamp": datetime.now().isoformat()
                }

            garden = simulator.get_garden(garden_id)

            return {
                "garden_id": garden_id,
                "garden_name": garden.get('name') if garden else None,
                "plant_id": plant_id,
                "plant_name": plant.get('name', plant_id),
                "current_moisture": plant.get('current_moisture'),
                "health_score": plant.get('health_score'),
                "health": _classify_health(plant.get('current_moisture')),
                "last_irrigation": plant.get('last_irrigation'),
                "last_updated": str(plant.get('last_updated', '')),
                "history": plant.get('history', []),
                "status": "success",
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "status": "error",
                "error": "Real IoT mode not implemented for gardens yet",
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        logger.error(f"Error getting plant {plant_id} in garden {garden_id}: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


def get_garden_weather(garden_id: str) -> Dict[str, Any]:
    """Get weather data for a specific garden location using Google Weather API.

    Args:
        garden_id: The garden ID

    Returns:
        Weather data including current conditions and forecast
    """
    try:
        # Get garden to extract coordinates
        garden = simulator.get_garden(garden_id)
        if not garden:
            return {
                "status": "error",
                "error": f"Garden {garden_id} not found",
                "timestamp": datetime.now().isoformat()
            }

        latitude = garden.get('latitude')
        longitude = garden.get('longitude')

        if not latitude or not longitude:
            return {
                "status": "error",
                "error": "Garden location coordinates not available",
                "timestamp": datetime.now().isoformat()
            }

        # Get weather data using Google Weather API
        from irrigation_agent.weather_service import get_weather_for_garden

        weather_data = get_weather_for_garden(latitude, longitude)

        # Add garden context
        weather_data['garden_id'] = garden_id
        weather_data['garden_name'] = garden.get('name')
        weather_data['garden_location'] = garden.get('location')

        return weather_data

    except Exception as e:
        logger.error(f"Error getting weather for garden {garden_id}: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


def get_irrigation_recommendation_with_weather(garden_id: str, plant_id: str) -> Dict[str, Any]:
    """Get irrigation recommendation considering weather forecast.

    Args:
        garden_id: The garden ID
        plant_id: The plant ID

    Returns:
        Recommendation with weather-based analysis
    """
    try:
        # Get plant data
        plant_data = get_plant_in_garden(garden_id, plant_id)
        if plant_data.get('status') != 'success':
            return plant_data

        # Get weather forecast
        weather_data = get_garden_weather(garden_id)
        if weather_data.get('status') != 'success':
            # Return basic recommendation without weather
            moisture = plant_data.get('current_moisture', 0)
            return {
                "action": "irrigate_soon" if moisture < 40 else "monitor",
                "reason": f"Humedad actual: {moisture}%. Sin datos meteorológicos disponibles.",
                "weather_available": False,
                "plant_data": plant_data,
                "status": "success",
                "timestamp": datetime.now().isoformat()
            }

        # Get weather-based recommendation
        from irrigation_agent.weather_service import get_irrigation_recommendation

        recommendation = get_irrigation_recommendation(
            weather_data,
            plant_data.get('current_moisture', 0)
        )

        # Add context
        recommendation['plant_data'] = {
            "garden_id": garden_id,
            "plant_id": plant_id,
            "plant_name": plant_data.get('plant_name'),
            "current_moisture": plant_data.get('current_moisture'),
            "health": plant_data.get('health')
        }
        recommendation['weather_data'] = {
            "current_temp": weather_data.get('current', {}).get('temperature'),
            "current_humidity": weather_data.get('current', {}).get('humidity'),
            "rain_forecast": weather_data.get('forecast', [])[:2]  # Next 2 days
        }

        return recommendation

    except Exception as e:
        logger.error(f"Error getting recommendation for {plant_id} in {garden_id}: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
