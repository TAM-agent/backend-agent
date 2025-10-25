
from datetime import datetime
from typing import Dict, Any
import requests

from ._base import notification_config, logger


def send_notification(message: str, priority: str = "medium") -> Dict[str, Any]:
    """Send notification to user with priority classification."""
    priority = (priority or "").lower()
    if priority not in ["low", "medium", "high", "critical"]:
        priority = "medium"

    channels_used = ["log"]
    logger.info(f"[{priority.upper()}] {message}")

    if notification_config.has_telegram and priority in ["high", "critical"]:
        try:
            _send_telegram_notification(message, priority)
            channels_used.append("telegram")
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")

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
        "status": "success",
    }


def _send_telegram_notification(message: str, priority: str) -> None:
    url = f"https://api.telegram.org/bot{notification_config.telegram_bot_token}/sendMessage"
    emoji_map = {"critical": "🚨", "high": "⚠️", "medium": "ℹ️", "low": "✅"}
    emoji = emoji_map.get(priority, "ℹ️")
    formatted_message = f"{emoji} *{priority.upper()}*\n\n{message}"
    payload = {
        "chat_id": notification_config.telegram_chat_id,
        "text": formatted_message,
        "parse_mode": "Markdown",
    }
    response = requests.post(url, json=payload, timeout=10)
    response.raise_for_status()


def _send_email_notification(message: str, priority: str) -> None:
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    msg = MIMEMultipart()
    msg["From"] = notification_config.smtp_username
    msg["To"] = notification_config.notification_email
    msg["Subject"] = f"[{priority.upper()}] Irrigation System Alert"

    body = f"""
    Priority: {priority.upper()}
    {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

    {message}

    ---
    Intelligent Irrigation System
    """
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(notification_config.smtp_server, notification_config.smtp_port) as server:
        server.starttls()
        server.login(notification_config.smtp_username, notification_config.smtp_password)
        server.send_message(msg)
