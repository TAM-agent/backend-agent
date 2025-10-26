"""
Telegram notification service for agent decisions and alerts.

Provides rich formatting for irrigation system events including
agent decisions, moisture alerts, and system status updates.
"""

import requests
from datetime import datetime
from typing import Dict, Any, Optional
from ..config import notification_config


def send_agent_decision_notification(
    garden_name: str,
    plant_name: str,
    decision: str,
    explanation: str,
    moisture: int,
    priority: str = "high"
) -> Dict[str, Any]:
    """
    Send a formatted Telegram notification for agent irrigation decisions.

    Args:
        garden_name: Name of the garden
        plant_name: Name of the plant
        decision: Decision made (regar, esperar, alerta, ajustar)
        explanation: Agent's explanation for the decision
        moisture: Current moisture level (0-100)
        priority: Priority level (critical, high, medium, low)

    Returns:
        Dict with status and response details
    """
    if not notification_config.has_telegram:
        return {"status": "skipped", "reason": "Telegram not configured"}

    emoji_map = {
        "regar": "💧",
        "esperar": "⏳",
        "alerta": "🚨",
        "ajustar": "⚙️"
    }
    priority_emoji = {
        "critical": "🚨",
        "high": "⚠️",
        "medium": "ℹ️",
        "low": "✅"
    }

    decision_emoji = emoji_map.get(decision, "📋")
    priority_icon = priority_emoji.get(priority, "ℹ️")

    moisture_bar = _create_moisture_bar(moisture)

    message = f"""{priority_icon} *DECISIÓN DEL AGENTE*

🌱 *Jardín:* {garden_name}
🪴 *Planta:* {plant_name}
{decision_emoji} *Decisión:* {decision.upper()}

💧 *Humedad Actual:* {moisture}%
{moisture_bar}

📝 *Explicación:*
_{explanation}_

🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

    return _send_telegram_message(message)


def send_moisture_alert(
    garden_name: str,
    plant_name: str,
    moisture: int,
    severity: str = "warning"
) -> Dict[str, Any]:
    """
    Send a moisture level alert to Telegram.

    Args:
        garden_name: Name of the garden
        plant_name: Name of the plant
        moisture: Current moisture level
        severity: Alert severity (critical, warning)

    Returns:
        Dict with status and response details
    """
    if not notification_config.has_telegram:
        return {"status": "skipped", "reason": "Telegram not configured"}

    emoji = "🚨" if severity == "critical" else "⚠️"
    status_text = "CRÍTICO" if severity == "critical" else "BAJO"

    moisture_bar = _create_moisture_bar(moisture)

    message = f"""{emoji} *ALERTA DE HUMEDAD - {status_text}*

🌱 *Jardín:* {garden_name}
🪴 *Planta:* {plant_name}

💧 *Humedad:* {moisture}%
{moisture_bar}

{"⚠️ Requiere atención inmediata" if severity == "critical" else "ℹ️ Monitorear de cerca"}

🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

    return _send_telegram_message(message)


def send_irrigation_summary(
    garden_name: str,
    plants_irrigated: list,
    total_duration: int,
    success: bool = True
) -> Dict[str, Any]:
    """
    Send irrigation completion summary to Telegram.

    Args:
        garden_name: Name of the garden
        plants_irrigated: List of plant names that were irrigated
        total_duration: Total irrigation duration in seconds
        success: Whether irrigation completed successfully

    Returns:
        Dict with status and response details
    """
    if not notification_config.has_telegram:
        return {"status": "skipped", "reason": "Telegram not configured"}

    emoji = "✅" if success else "❌"
    status = "COMPLETADO" if success else "FALLIDO"

    plants_list = "\n".join([f"   • {plant}" for plant in plants_irrigated])

    message = f"""{emoji} *RIEGO {status}*

🌱 *Jardín:* {garden_name}

🪴 *Plantas regadas:*
{plants_list}

⏱️ *Duración total:* {total_duration}s ({total_duration // 60}m {total_duration % 60}s)

🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

    return _send_telegram_message(message)


def send_system_status_update(
    gardens_count: int,
    critical_count: int,
    warnings_count: int,
    healthy_count: int
) -> Dict[str, Any]:
    """
    Send overall system status update to Telegram.

    Args:
        gardens_count: Total number of gardens
        critical_count: Number of plants in critical state
        warnings_count: Number of plants with warnings
        healthy_count: Number of healthy plants

    Returns:
        Dict with status and response details
    """
    if not notification_config.has_telegram:
        return {"status": "skipped", "reason": "Telegram not configured"}

    overall_emoji = "🚨" if critical_count > 0 else "⚠️" if warnings_count > 0 else "✅"

    message = f"""{overall_emoji} *ESTADO DEL SISTEMA*

🏡 *Jardines monitoreados:* {gardens_count}

📊 *Resumen:*
   🚨 Críticos: {critical_count}
   ⚠️ Advertencias: {warnings_count}
   ✅ Saludables: {healthy_count}

🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

    return _send_telegram_message(message)


def _create_moisture_bar(moisture: int, bar_length: int = 10) -> str:
    """Create a visual moisture level bar."""
    filled = int((moisture / 100) * bar_length)
    empty = bar_length - filled

    if moisture < 30:
        bar_char = "🟥"
    elif moisture < 50:
        bar_char = "��"
    else:
        bar_char = "🟩"

    bar = bar_char * filled + "⬜" * empty
    return f"`{bar}` {moisture}%"


def _send_telegram_message(message: str, parse_mode: str = "Markdown") -> Dict[str, Any]:
    """
    Send a message to Telegram.

    Args:
        message: Message text to send
        parse_mode: Telegram parse mode (Markdown or HTML)

    Returns:
        Dict with status and response details
    """
    try:
        url = f"https://api.telegram.org/bot{notification_config.telegram_bot_token}/sendMessage"
        payload = {
            "chat_id": notification_config.telegram_chat_id,
            "text": message,
            "parse_mode": parse_mode,
        }

        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()

        return {
            "status": "success",
            "message_sent": True,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "error",
            "message_sent": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
