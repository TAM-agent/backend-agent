"""Google Weather API integration service.

This module provides functions to fetch weather data using Google's Weather API.
"""

import os
import logging
import requests
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

WEATHER_API_ENDPOINT = "https://weather.googleapis.com/v1/locations:forecast"


def get_weather_for_garden(latitude: float, longitude: float) -> Dict[str, Any]:
    """
    Get current weather and forecast for a garden location using Google Weather API.

    Args:
        latitude: Latitude coordinate of the garden
        longitude: Longitude coordinate of the garden

    Returns:
        Dictionary with weather data:
        {
            "current": {...},
            "forecast": [...],
            "status": "success|error",
            "timestamp": "..."
        }
    """
    try:
        # Get API key from environment or use Application Default Credentials
        api_key = os.getenv("GOOGLE_WEATHER_API_KEY")

        # Build request
        params = {
            "latLng": {
                "latitude": latitude,
                "longitude": longitude
            },
            "languageCode": "es",  # Spanish
            "units": "metric"
        }

        headers = {}
        if api_key:
            headers["X-Goog-Api-Key"] = api_key

        # Make request to Weather API
        response = requests.post(
            WEATHER_API_ENDPOINT,
            json=params,
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            weather_data = response.json()

            # Extract relevant information
            current_conditions = extract_current_conditions(weather_data)
            forecast = extract_forecast(weather_data)

            return {
                "current": current_conditions,
                "forecast": forecast,
                "location": {
                    "latitude": latitude,
                    "longitude": longitude
                },
                "status": "success",
                "timestamp": datetime.now().isoformat()
            }
        else:
            logger.error(f"Weather API error: {response.status_code} - {response.text}")
            return {
                "status": "error",
                "error": f"API returned status {response.status_code}",
                "timestamp": datetime.now().isoformat()
            }

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching weather data: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Unexpected error in weather service: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


def extract_current_conditions(weather_data: Dict) -> Dict[str, Any]:
    """Extract current weather conditions from API response."""
    try:
        # Google Weather API structure may vary, adapt as needed
        current = weather_data.get("currentConditions", {})

        return {
            "temperature": current.get("temperature", {}).get("value"),
            "humidity": current.get("humidity", {}).get("value"),
            "precipitation": current.get("precipitation", {}).get("value"),
            "wind_speed": current.get("windSpeed", {}).get("value"),
            "condition": current.get("weatherCondition", {}).get("description"),
            "uv_index": current.get("uvIndex", {}).get("value")
        }
    except Exception as e:
        logger.warning(f"Error extracting current conditions: {e}")
        return {}


def extract_forecast(weather_data: Dict) -> list:
    """Extract weather forecast from API response."""
    try:
        forecasts = weather_data.get("dailyForecasts", [])

        forecast_list = []
        for day in forecasts[:7]:  # Next 7 days
            forecast_list.append({
                "date": day.get("date"),
                "temp_max": day.get("temperatureMax", {}).get("value"),
                "temp_min": day.get("temperatureMin", {}).get("value"),
                "precipitation_probability": day.get("precipitationProbability", {}).get("value"),
                "precipitation_amount": day.get("precipitationAmount", {}).get("value"),
                "condition": day.get("weatherCondition", {}).get("description")
            })

        return forecast_list
    except Exception as e:
        logger.warning(f"Error extracting forecast: {e}")
        return []


def should_skip_irrigation(weather_forecast: Dict) -> Dict[str, Any]:
    """
    Analyze weather forecast to determine if irrigation should be skipped.

    Args:
        weather_forecast: Weather data from get_weather_for_garden()

    Returns:
        Dictionary with recommendation:
        {
            "skip_irrigation": bool,
            "reason": str,
            "rain_expected": bool,
            "rain_probability": float,
            "rain_amount_mm": float
        }
    """
    try:
        if weather_forecast.get("status") != "success":
            return {
                "skip_irrigation": False,
                "reason": "No weather data available",
                "rain_expected": False
            }

        forecast = weather_forecast.get("forecast", [])
        if not forecast:
            return {
                "skip_irrigation": False,
                "reason": "No forecast data",
                "rain_expected": False
            }

        # Check next 24-48 hours
        upcoming_weather = forecast[:2]  # Next 2 days

        total_rain = 0
        max_probability = 0

        for day in upcoming_weather:
            prob = day.get("precipitation_probability", 0)
            amount = day.get("precipitation_amount", 0)

            if prob:
                max_probability = max(max_probability, prob)
            if amount:
                total_rain += amount

        # Decision logic
        skip = False
        reason = ""

        if max_probability >= 70 and total_rain >= 5:
            skip = True
            reason = f"Lluvia muy probable ({max_probability}%) con {total_rain:.1f}mm esperados en 48h"
        elif max_probability >= 50 and total_rain >= 10:
            skip = True
            reason = f"Lluvia probable ({max_probability}%) con {total_rain:.1f}mm esperados en 48h"
        elif total_rain >= 15:
            skip = True
            reason = f"Se esperan {total_rain:.1f}mm de lluvia en las próximas 48h"

        return {
            "skip_irrigation": skip,
            "reason": reason if skip else "No se espera lluvia significativa",
            "rain_expected": max_probability >= 40,
            "rain_probability": max_probability,
            "rain_amount_mm": total_rain
        }

    except Exception as e:
        logger.error(f"Error analyzing weather for irrigation: {e}")
        return {
            "skip_irrigation": False,
            "reason": f"Error analyzing weather: {str(e)}",
            "rain_expected": False
        }


def get_irrigation_recommendation(weather_data: Dict, current_moisture: float) -> Dict[str, Any]:
    """
    Get irrigation recommendation based on weather and current soil moisture.

    Args:
        weather_data: Weather forecast data
        current_moisture: Current soil moisture percentage

    Returns:
        Recommendation dictionary with action and reasoning
    """
    try:
        current = weather_data.get("current", {})
        temperature = current.get("temperature")
        humidity = current.get("humidity")

        # Check if we should skip due to rain
        rain_check = should_skip_irrigation(weather_data)

        # Base recommendation on moisture
        if current_moisture < 30:
            urgency = "critical"
            base_action = "irrigate_now"
        elif current_moisture < 45:
            urgency = "moderate"
            base_action = "irrigate_soon"
        else:
            urgency = "low"
            base_action = "monitor"

        # Adjust based on weather
        if rain_check["skip_irrigation"] and urgency != "critical":
            final_action = "skip"
            reason = f"Humedad actual: {current_moisture}%. {rain_check['reason']}"
        elif temperature and temperature > 30 and current_moisture < 50:
            final_action = "irrigate_soon"
            reason = f"Temperatura alta ({temperature}°C) aumenta evaporación. Humedad: {current_moisture}%"
        else:
            final_action = base_action
            reason = f"Humedad actual: {current_moisture}%. Temp: {temperature}°C, Humedad ambiental: {humidity}%"

        return {
            "action": final_action,
            "reason": reason,
            "urgency": urgency,
            "weather_considered": True,
            "rain_forecast": rain_check,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error generating irrigation recommendation: {e}")
        return {
            "action": "monitor",
            "reason": f"Error analyzing weather: {str(e)}",
            "urgency": "unknown",
            "weather_considered": False,
            "timestamp": datetime.now().isoformat()
        }
