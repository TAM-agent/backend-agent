"""WebSocket connection manager and endpoint."""
import logging
import json
from datetime import datetime
from typing import Set, Dict

from fastapi import WebSocket, WebSocketDisconnect, HTTPException

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for real-time communication."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.device_connections: Dict[str, Set[WebSocket]] = {}
        self.websocket_devices: Dict[WebSocket, str] = {}

    async def connect(self, websocket: WebSocket, device_id: str):
        await websocket.accept()
        self.active_connections.add(websocket)
        self.device_connections.setdefault(device_id, set()).add(websocket)
        self.websocket_devices[websocket] = device_id
        logger.info(f"New WebSocket connection. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        did = self.websocket_devices.pop(websocket, None)
        if did and did in self.device_connections:
            conns = self.device_connections.get(did)
            if conns is not None:
                conns.discard(websocket)
                if not conns:
                    self.device_connections.pop(did, None)
        logger.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Send message to all connected clients."""
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error sending to WebSocket: {e}")
                disconnected.add(connection)

        # Clean up disconnected clients
        for connection in disconnected:
            self.disconnect(connection)

    async def send_personal(self, message: dict, websocket: WebSocket):
        """Send message to specific client."""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
            self.disconnect(websocket)

    async def send_to_device(self, device_id: str, message: dict):
        """Send a message to all sockets associated with a device_id."""
        conns = self.device_connections.get(device_id, set())
        disconnected = set()
        for ws in list(conns):
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.error(f"Error sending to device {device_id}: {e}")
                disconnected.add(ws)
        for ws in disconnected:
            self.disconnect(ws)


# Global connection manager instance
manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket, device_id: str, tools_available: bool, config):
    """
    WebSocket endpoint for real-time notifications and agent communications.

    The client connects to this endpoint to receive:
    - Real-time alerts (low moisture, low tank, high temperature)
    - Agent decisions and explanations
    - Irrigation actions taken automatically
    - System status updates

    Messages sent to clients have this format:
    {
        "type": "alert" | "agent_decision" | "system_update" | "chat_response",
        "data": {...},
        "timestamp": "ISO timestamp"
    }
    """
    await manager.connect(websocket, device_id)

    try:
        # Send welcome message
        await manager.send_personal({
            "type": "connection",
            "message": "Conectado a GrowthAI - Sistema de Irrigacion Inteligente",
            "device_id": device_id,
            "timestamp": datetime.now().isoformat()
        }, websocket)

        # Listen for incoming messages from client
        while True:
            data = await websocket.receive_json()

            message_type = data.get("type")

            # Relay device-originated events as normalized notifications
            relay_types = {"alert", "agent_decision", "system_update", "event"}
            if message_type in relay_types:
                payload = {
                    "type": message_type,
                    "device_id": device_id,
                    "garden_id": data.get("garden_id"),
                    "data": data.get("data", data),
                    "timestamp": datetime.now().isoformat(),
                }
                await manager.broadcast(payload)
                continue

            if message_type == "ping":
                await manager.send_personal({
                    "type": "pong",
                    "device_id": device_id,
                    "timestamp": datetime.now().isoformat()
                }, websocket)
                continue

            if message_type == "chat":
                # Garden-scoped chat: require garden_id and include plants info as context
                user_message = data.get("message", "")
                garden_id = data.get("garden_id")

                if not tools_available:
                    await manager.send_personal({
                        "type": "chat_response",
                        "response": "Lo siento, el agente no esta disponible en este momento.",
                        "timestamp": datetime.now().isoformat()
                    }, websocket)
                    continue

                if not garden_id:
                    await manager.send_personal({
                        "type": "error",
                        "message": "El chat es por jardin. Incluye 'garden_id' en el mensaje.",
                        "timestamp": datetime.now().isoformat()
                    }, websocket)
                    continue

                try:
                    from irrigation_agent.utils.genai_utils import get_genai_client, extract_text, extract_json_object
                    from irrigation_agent.tools import get_garden_status
                    from prompts import WEBSOCKET_CHAT_PROMPT

                    client = get_genai_client()
                    garden_data = get_garden_status(garden_id)
                    if garden_data.get("status") != "success":
                        await manager.send_personal({
                            "type": "error",
                            "message": f"Jardin '{garden_id}' no encontrado o sin datos",
                            "timestamp": datetime.now().isoformat()
                        }, websocket)
                        continue

                    personality = garden_data.get("personality", "neutral")
                    garden_name = garden_data.get("garden_name", garden_id)

                    context_prompt = WEBSOCKET_CHAT_PROMPT.format(
                        garden_name=garden_name,
                        personality=personality,
                        garden_data=garden_data,
                        user_message=user_message
                    )

                    response = client.models.generate_content(
                        model=config.worker_model,
                        contents=context_prompt
                    )

                    response_text = extract_text(response)

                    try:
                        response_data, raw_text = extract_json_object(response_text)
                        if response_data is None:
                            raise json.JSONDecodeError("not json", raw_text, 0)

                        _ws_msg = str(response_data.get("message", "")).strip()
                        if garden_name and garden_name.lower() not in _ws_msg.lower():
                            _ws_msg = f"{garden_name}: {_ws_msg}"
                        await manager.send_personal({
                            "type": "chat_response",
                            "garden_id": garden_id,
                            "garden_name": garden_name,
                            "message": _ws_msg,
                            "plants_summary": response_data.get("plants_summary", []),
                            "data": response_data.get("data", {}),
                            "suggestions": response_data.get("suggestions", []),
                            "priority": response_data.get("priority", "info"),
                            "timestamp": datetime.now().isoformat()
                        }, websocket)

                    except (json.JSONDecodeError, AttributeError):
                        _ws_fallback = response_text.strip()
                        if garden_name and garden_name.lower() not in _ws_fallback.lower():
                            _ws_fallback = f"{garden_name}: {_ws_fallback}"
                        await manager.send_personal({
                            "type": "chat_response",
                            "garden_id": garden_id,
                            "garden_name": garden_name,
                            "message": _ws_fallback,
                            "plants_summary": [],
                            "data": {},
                            "suggestions": [],
                            "priority": "info",
                            "timestamp": datetime.now().isoformat()
                        }, websocket)

                except Exception as e:
                    logger.error(f"Error in WebSocket garden chat: {e}")
                    await manager.send_personal({
                        "type": "error",
                        "message": f"Error al procesar mensaje: {str(e)}",
                        "timestamp": datetime.now().isoformat()
                    }, websocket)

            elif message_type == "request_status":
                # Client requesting current system status
                try:
                    from irrigation_agent.tools import get_system_status
                    status = get_system_status()
                    await manager.send_personal({
                        "type": "system_status",
                        "data": status,
                        "timestamp": datetime.now().isoformat()
                    }, websocket)
                except Exception as e:
                    logger.error(f"Error getting status: {e}")
                    await manager.send_personal({
                        "type": "error",
                        "message": str(e),
                        "timestamp": datetime.now().isoformat()
                    }, websocket)

            elif message_type == "ping":
                # Keep-alive ping
                await manager.send_personal({
                    "type": "pong",
                    "timestamp": datetime.now().isoformat()
                }, websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)
