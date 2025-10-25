from datetime import datetime
from typing import Dict, Any
import logging
import requests
from irrigation_agent.config import weather_config

logger = logging.getLogger(__name__)

def get_weather_forecast(days: int = 3) -> Dict[str, Any]:
    """Fetch weather forecast from OpenWeatherMap API.

    Retrieves weather forecast data including temperature, humidity, and
    precipitation probability for optimization of irrigation schedules.
    """
    if not weather_config.openweather_api_key:
        logger.warning("OpenWeatherMap API key not configured")
        return {
            "forecast": [],
            "days": days,
            "location": weather_config.location,
            "timestamp": datetime.now().isoformat(),
            "status": "error",
            "error": "API key not configured",
        }
    try:
        url = "https://api.openweathermap.org/data/2.5/forecast"
        params = {
            "q": weather_config.location,
            "appid": weather_config.openweather_api_key,
            "units": "metric",
            "cnt": days * 8,
        }
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        forecast = []
        for item in data.get("list", []):
            forecast.append(
                {
                    "date": item["dt_txt"],
                    "temp_celsius": item["main"]["temp"],
                    "humidity": item["main"]["humidity"],
                    "precipitation_prob": item.get("pop", 0),
                    "description": item["weather"][0]["description"],
                }
            )
        return {
            "forecast": forecast,
            "days": days,
            "location": weather_config.location,
            "timestamp": datetime.now().isoformat(),
            "status": "success",
        }
    except requests.RequestException as e:
        logger.error(f"Error fetching weather forecast: {e}")
        return {
            "forecast": [],
            "days": days,
            "location": weather_config.location,
            "timestamp": datetime.now().isoformat(),
            "status": "error",
            "error": str(e),
        }
