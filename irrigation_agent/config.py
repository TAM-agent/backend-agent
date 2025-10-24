"""Configuration management for the intelligent irrigation system.

This module defines configuration dataclasses for different aspects of the system:
- IrrigationConfiguration: Agent behavior and AI model settings
- IoTConfiguration: Hardware connection and control parameters
- WeatherConfiguration: External weather API integration
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass
class IrrigationConfiguration:
    """Configuration for agent behavior and AI models.

    Attributes:
        critic_model: High-capability model for complex analysis tasks (nutrient analysis, optimization)
        worker_model: Fast model for operational tasks (monitoring, alerts)
        max_retry_attempts: Number of retry attempts for failed operations
        sensor_polling_interval: Time between automated monitoring cycles (seconds)
        alert_cooldown_minutes: Minimum time between similar alerts to prevent notification fatigue
    """
    critic_model: str = os.getenv("CRITIC_MODEL", "gemini-2.5-pro")
    worker_model: str = os.getenv("AI_MODEL", "gemini-2.5-flash")
    max_retry_attempts: int = int(os.getenv("MAX_RETRY_ATTEMPTS", "3"))
    sensor_polling_interval: int = int(os.getenv("SENSOR_POLLING_INTERVAL", "300"))
    alert_cooldown_minutes: int = int(os.getenv("ALERT_COOLDOWN_MINUTES", "30"))


@dataclass
class IoTConfiguration:
    """Configuration for IoT hardware connections.

    Attributes:
        raspberry_pi_ip: IP address of the Raspberry Pi running the Node.js backend
        backend_port: Port where the Express API is listening
        sensor_timeout: Timeout for sensor reading requests (seconds)
        pump_timeout: Timeout for irrigation pump activation requests (seconds)
        max_irrigation_duration: Maximum allowed irrigation duration for safety (seconds)
    """
    raspberry_pi_ip: str = os.getenv("RASPBERRY_PI_IP", "192.168.1.100")
    backend_port: int = int(os.getenv("BACKEND_PORT", "3000"))
    sensor_timeout: int = int(os.getenv("SENSOR_TIMEOUT", "10"))
    pump_timeout: int = int(os.getenv("PUMP_TIMEOUT", "30"))
    max_irrigation_duration: int = int(os.getenv("MAX_IRRIGATION_DURATION", "1800"))

    @property
    def base_url(self) -> str:
        """Constructs the base URL for API calls to the Raspberry Pi backend."""
        return f"http://{self.raspberry_pi_ip}:{self.backend_port}"


@dataclass
class WeatherConfiguration:
    """Configuration for weather service integration.

    Attributes:
        openweather_api_key: API key for OpenWeatherMap service
        location: City and country code for weather queries (e.g., "Santiago,CL")
        forecast_days: Number of days to include in weather forecasts
    """
    openweather_api_key: str = os.getenv("OPENWEATHER_API_KEY", "")
    location: str = os.getenv("WEATHER_LOCATION", "Santiago,CL")
    forecast_days: int = int(os.getenv("FORECAST_DAYS", "3"))


@dataclass
class NotificationConfiguration:
    """Configuration for notification channels.

    Attributes:
        telegram_bot_token: Telegram Bot API token
        telegram_chat_id: Telegram chat ID for sending messages
        smtp_server: SMTP server for email notifications
        smtp_port: SMTP server port
        smtp_username: SMTP authentication username
        smtp_password: SMTP authentication password
        notification_email: Email address to send notifications to
    """
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")
    smtp_server: str = os.getenv("SMTP_SERVER", "")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_username: str = os.getenv("SMTP_USERNAME", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    notification_email: str = os.getenv("NOTIFICATION_EMAIL", "")

    @property
    def has_telegram(self) -> bool:
        """Check if Telegram is configured."""
        return bool(self.telegram_bot_token and self.telegram_chat_id)

    @property
    def has_email(self) -> bool:
        """Check if email is configured."""
        return bool(self.smtp_server and self.smtp_username and self.notification_email)


# Global configuration instances
config = IrrigationConfiguration()
iot_config = IoTConfiguration()
weather_config = WeatherConfiguration()
notification_config = NotificationConfiguration()
