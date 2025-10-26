"""
Telegram notification service for agent decisions and alerts.

Provides rich formatting for irrigation system events including
agent decisions, moisture alerts, and system status updates.
Uses Telegram HTML parse mode to avoid Markdown escaping issues.
"""

from datetime import datetime
from typing import Dict, Any, Optional

import requests

from ..config import notification_config


def send_agent_decision_notification(
    garden_name: str,
    plant_name: str,
    decision: str,
    explanation: str,
    moisture: int,
    priority: str = "high",
    personality: Optional[str] = None,
) -> Dict[str, Any]:
    """Send a formatted Telegram notification for agent irrigation decisions."""
    if not notification_config.has_telegram:
        return {"status": "skipped", "reason": "Telegram not configured"}

    emoji_map = {
        "regar": "💧",
        "esperar": "⏳",
        "alerta": "⚠️",
        "ajustar": "🛠️",
    }
    priority_emoji = {
        "critical": "🔴",
        "high": "🟠",
        "medium": "🟡",
        "low": "🟢",
    }

    decision_emoji = emoji_map.get(decision, "🌱")
    priority_icon = priority_emoji.get(priority, "🟡")

    personality_emoji = _get_personality_emoji(personality)
    bar_html = _create_moisture_bar(moisture)

    g = _escape_html(garden_name)
    p = _escape_html(plant_name)
    exp = _escape_html(explanation)

    message = (
        f"{priority_icon} <b>Decisión del agente</b> {personality_emoji}\n\n"
        f"🏡 <b>Jardín:</b> {g}\n"
        f"🌿 <b>Planta:</b> {p}\n"
        f"{decision_emoji} <b>Decisión:</b> {decision.upper()}\n\n"
        f"💧 <b>Humedad actual:</b> {moisture}%\n"
        f"{bar_html}\n\n"
        f"📝 <b>Explicación:</b> <i>{exp}</i>\n\n"
        f"🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    return _send_telegram_message(message, parse_mode="HTML")


def send_moisture_alert(
    garden_name: str,
    plant_name: str,
    moisture: int,
    severity: str = "warning",
) -> Dict[str, Any]:
    """Send a moisture level alert to Telegram."""
    if not notification_config.has_telegram:
        return {"status": "skipped", "reason": "Telegram not configured"}

    emoji = "🚨" if severity == "critical" else "⚠️"
    status_text = "CRÍTICO" if severity == "critical" else "BAJO"

    bar_html = _create_moisture_bar(moisture)

    g = _escape_html(garden_name)
    p = _escape_html(plant_name)

    note = (
        "🚨 Requiere atención inmediata" if severity == "critical" else "🔎 Monitorear de cerca"
    )

    message = (
        f"{emoji} <b>Alerta de humedad - {status_text}</b>\n\n"
        f"🏡 <b>Jardín:</b> {g}\n"
        f"🌿 <b>Planta:</b> {p}\n\n"
        f"💧 <b>Humedad:</b> {moisture}%\n"
        f"{bar_html}\n\n"
        f"{note}\n\n"
        f"🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    return _send_telegram_message(message, parse_mode="HTML")


def send_irrigation_summary(
    garden_name: str,
    plants_irrigated: list,
    total_duration: int,
    success: bool = True,
) -> Dict[str, Any]:
    """Send irrigation completion summary to Telegram."""
    if not notification_config.has_telegram:
        return {"status": "skipped", "reason": "Telegram not configured"}

    emoji = "✅" if success else "❌"
    status = "COMPLETADO" if success else "FALLIDO"

    g = _escape_html(garden_name)
    plants_list = "\n".join([f" • {_escape_html(str(plant))}" for plant in plants_irrigated])

    message = (
        f"{emoji} <b>Riego {status}</b>\n\n"
        f"🏡 <b>Jardín:</b> {g}\n\n"
        f"🌿 <b>Plantas regadas:</b>\n{plants_list}\n\n"
        f"⏱️ <b>Duración total:</b> {total_duration}s ({total_duration // 60}m {total_duration % 60}s)\n\n"
        f"🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    return _send_telegram_message(message, parse_mode="HTML")


def send_system_status_update(
    gardens_count: int,
    critical_count: int,
    warnings_count: int,
    healthy_count: int,
) -> Dict[str, Any]:
    """Send overall system status update to Telegram."""
    if not notification_config.has_telegram:
        return {"status": "skipped", "reason": "Telegram not configured"}

    overall_emoji = "🚨" if critical_count > 0 else ("⚠️" if warnings_count > 0 else "✅")

    message = (
        f"{overall_emoji} <b>Estado del sistema</b>\n\n"
        f"📊 <b>Jardines monitoreados:</b> {gardens_count}\n\n"
        f"🧾 <b>Resumen:</b>\n"
        f"   🚨 Críticos: {critical_count}\n"
        f"   ⚠️ Advertencias: {warnings_count}\n"
        f"   ✅ Saludables: {healthy_count}\n\n"
        f"🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    return _send_telegram_message(message, parse_mode="HTML")


def _create_moisture_bar(moisture: int, bar_length: int = 10) -> str:
    """Create a visual moisture level bar as HTML."""
    filled = max(0, min(bar_length, int((moisture / 100) * bar_length)))
    empty = bar_length - filled
    bar = ("🟦" * filled) + ("⬜" * empty)
    return f"<code>{bar}</code> {moisture}%"


def _get_personality_emoji(personality: Optional[str]) -> str:
    """Map personality to an emoji indicator."""
    if not personality:
        return ""
    mapping = {
        "friendly": "🙂",
        "professional": "🧑‍💼",
        "playful": "😜",
        "caring": "🤝",
        "neutral": "🤖",
    }
    return mapping.get(personality.lower(), "🌱")


def _escape_html(text: str) -> str:
    """Minimal HTML escaping for Telegram HTML parse mode."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _send_telegram_message(message: str, parse_mode: str = "HTML") -> Dict[str, Any]:
    """Send a message to Telegram using the Bot API."""
    try:
        url = f"https://api.telegram.org/bot{notification_config.telegram_bot_token}/sendMessage"
        payload = {
            "chat_id": notification_config.telegram_chat_id,
            "text": message,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }

        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()

        return {
            "status": "success",
            "message_sent": True,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        return {
            "status": "error",
            "message_sent": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }

