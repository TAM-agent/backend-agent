"""Background monitoring service for gardens and plants."""
import os
import logging
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)


async def agent_analyze_and_act(condition: str, data: dict, tools_available: bool, config) -> dict:
    """
    Use the agent to analyze a condition and decide what action to take.

    Args:
        condition: Description of the alert condition (e.g., "high temperature", "low moisture")
        data: Relevant sensor data
        tools_available: Whether irrigation tools are available
        config: Configuration object

    Returns:
        Dictionary with agent's decision, explanation, and actions taken
    """
    if not tools_available:
        return {
            "decision": "no_action",
            "explanation": "Agent tools not available",
            "actions": []
        }

    try:
        from irrigation_agent.utils.genai_utils import get_genai_client, extract_text, extract_json_object
        from irrigation_agent.tools import trigger_irrigation
        from prompts import AGENT_DECISION_PROMPT

        client = get_genai_client()

        # Extract garden personality from data
        personality = data.get("personality", "professional")
        garden_name = data.get("garden_name", "el jardin")

        # Build personality-based communication style
        personality_styles = {
            "friendly": "Usa un tono amigable, carinoso y cercano. Habla como un amigo que cuida sus plantas con amor.",
            "professional": "Usa un tono profesional, tecnico y preciso. Proporciona datos y recomendaciones basadas en mejores practicas.",
            "playful": "Usa un tono divertido, creativo y alegre. Haz que el cuidado de plantas sea entretenido.",
            "caring": "Usa un tono compasivo y maternal. Muestra preocupacion genuina por el bienestar de las plantas.",
            "neutral": "Usa un tono informativo y objetivo. Proporciona hechos sin agregar emociones."
        }
        style_instruction = personality_styles.get(personality, personality_styles["neutral"])

        prompt = AGENT_DECISION_PROMPT.format(
            garden_name=garden_name,
            personality=personality,
            style_instruction=style_instruction,
            condition=condition,
            data=data
        )

        response = client.models.generate_content(
            model=config.worker_model,
            contents=prompt
        )

        # Extract response text
        response_text = extract_text(response)

        # Try to parse JSON from response
        decision_obj, raw_text = extract_json_object(response_text)
        if decision_obj is None:
            decision = {
                "decision": "alerta",
                "explanation": raw_text,
                "priority": "medium"
            }
        else:
            decision = decision_obj

        # Execute actions based on decision
        actions_taken = []
        if decision.get("decision") == "regar" and decision.get("plant_id"):
            try:
                duration = decision.get("action_params", {}).get("duration", 30)
                result = trigger_irrigation(decision["plant_id"], duration)
                actions_taken.append({
                    "type": "irrigation",
                    "plant": decision["plant_id"],
                    "duration": duration,
                    "result": result
                })
            except Exception as e:
                logger.error(f"Error executing irrigation: {e}")
                actions_taken.append({
                    "type": "irrigation",
                    "error": str(e)
                })

        decision["actions_taken"] = actions_taken
        decision["timestamp"] = datetime.now().isoformat()

        # Send Telegram notification for agent decisions
        try:
            from irrigation_agent.service.telegram_service import send_agent_decision_notification
            send_agent_decision_notification(
                garden_name=garden_name,
                plant_name=data.get("plant_name", decision.get("plant_id", "Unknown")),
                decision=decision.get("decision", "unknown"),
                explanation=decision.get("explanation", ""),
                moisture=data.get("moisture", 0),
                priority=decision.get("priority", "medium")
            )
        except Exception as telegram_err:
            logger.warning(f"Failed to send Telegram notification: {telegram_err}")

        return decision

    except Exception as e:
        logger.error(f"Error in agent analysis: {e}")
        return {
            "decision": "error",
            "explanation": f"Error al analizar: {str(e)}",
            "actions": [],
            "timestamp": datetime.now().isoformat()
        }


async def process_garden_monitoring(garden_id: str, garden_data: dict, manager, tools_available: bool, config, collect_results: bool = False):
    """
    Process monitoring for a single garden. Returns alerts and decisions if collect_results=True.

    Args:
        garden_id: Garden identifier
        garden_data: Garden status data
        manager: WebSocket connection manager
        tools_available: Whether irrigation tools are available
        config: Configuration object
        collect_results: Whether to collect and return alerts/decisions

    Returns:
        Tuple of (alerts, decisions) if collect_results=True, otherwise ([], [])
    """
    if garden_data.get("status") != "success":
        return [], []

    garden_name = garden_data.get("garden_name", garden_id)
    personality = garden_data.get("personality", "neutral")
    alerts = []
    decisions = []

    for plant_id, plant_data in garden_data.get("plant_status", {}).items():
        moisture = plant_data.get("moisture")
        if moisture is None:
            continue

        if moisture < 30:
            alert = {
                "type": "low_moisture",
                "severity": "critical",
                "garden_id": garden_id,
                "garden_name": garden_name,
                "plant_id": plant_id,
                "plant_name": plant_data.get("name", plant_id),
                "moisture": moisture,
                "message": f"[{garden_name}] Humedad critica en {plant_id}: {moisture}%"
            }
            if collect_results:
                alerts.append(alert)

            decision = await agent_analyze_and_act(
                f"Humedad critica detectada en planta {plant_id} del jardin {garden_name}",
                {
                    "garden_id": garden_id,
                    "garden_name": garden_name,
                    "personality": personality,
                    "plant_id": plant_id,
                    "plant_name": plant_data.get("name", plant_id),
                    "moisture": moisture,
                    "threshold": 30,
                    "last_irrigation": plant_data.get("last_irrigation")
                },
                tools_available,
                config
            )
            if collect_results:
                decisions.append(decision)

            await manager.broadcast({
                "type": "agent_decision",
                "garden_id": garden_id,
                "garden_name": garden_name,
                "personality": personality,
                "alert": alert,
                "decision": decision,
                "timestamp": datetime.now().isoformat()
            })

        elif moisture < 45:
            alert = {
                "type": "low_moisture",
                "severity": "warning",
                "garden_id": garden_id,
                "garden_name": garden_name,
                "plant_id": plant_id,
                "plant_name": plant_data.get("name", plant_id),
                "moisture": moisture,
                "message": f"[{garden_name}] Humedad baja en {plant_id}: {moisture}%"
            }
            if collect_results:
                alerts.append(alert)

            # Send Telegram alert for low moisture warnings
            try:
                from irrigation_agent.service.telegram_service import send_moisture_alert
                send_moisture_alert(
                    garden_name=garden_name,
                    plant_name=plant_data.get("name", plant_id),
                    moisture=moisture,
                    severity="warning"
                )
            except Exception as telegram_err:
                logger.warning(f"Failed to send Telegram moisture alert: {telegram_err}")

            await manager.broadcast({
                "type": "alert",
                "garden_id": garden_id,
                "garden_name": garden_name,
                "personality": personality,
                "alert": alert,
                "timestamp": datetime.now().isoformat()
            })

    return alerts, decisions


async def monitor_system(tools_available: bool):
    """
    Continuously monitor ALL gardens and their plants.
    Triggers agent decisions based on garden context and personality.
    Runs as a background task when the application starts.

    Args:
        tools_available: Whether irrigation tools are available
    """
    logger.info("Starting garden monitoring task")

    while True:
        try:
            if not tools_available:
                await asyncio.sleep(60)
                continue

            # Import dependencies
            from irrigation_agent.tools import get_all_gardens_status
            from irrigation_agent.config import config
            from api.websocket import manager

            # Get status for all gardens
            gardens_status = get_all_gardens_status()

            if gardens_status.get("status") != "success":
                logger.error(f"Error getting gardens status: {gardens_status.get('error')}")
                await asyncio.sleep(60)
                continue

            for garden_id, garden_data in gardens_status.get("gardens", {}).items():
                await process_garden_monitoring(
                    garden_id,
                    garden_data,
                    manager,
                    tools_available,
                    config,
                    collect_results=False
                )

            # Sleep for monitoring interval
            monitoring_interval = int(os.getenv('MONITORING_INTERVAL_SECONDS', '30'))
            await asyncio.sleep(monitoring_interval)

        except Exception as e:
            logger.error(f"Error in monitoring task: {e}")
            await asyncio.sleep(60)
