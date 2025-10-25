"""
Simple WebSocket test client in Python
"""
import asyncio
import websockets
import json
from datetime import datetime

async def test_websocket():
    uri = "ws://localhost:8080/ws"

    print("=" * 70)
    print("  PROBANDO WEBSOCKET + AGENTE GROWTHAI")
    print("=" * 70)
    print()

    try:
        async with websockets.connect(uri) as websocket:
            print(f"[OK] Conectado a {uri}")
            print()

            # Esperar mensaje de bienvenida
            welcome = await websocket.recv()
            data = json.loads(welcome)
            print(f"[{data['type']}] {data.get('message', json.dumps(data, indent=2))}")
            print()

            # Enviar mensaje de chat
            print("Enviando: '¿Como estan mis plantas?'")
            await websocket.send(json.dumps({
                "type": "chat",
                "message": "¿Como estan mis plantas?"
            }))

            # Esperar respuesta
            response = await websocket.recv()
            data = json.loads(response)
            print()
            print(f"[{data['type']}] Respuesta del agente (JSON estructurado):")
            print(f"  Mensaje: {data.get('message', data.get('response', 'N/A'))}")

            if data.get('plants_mentioned'):
                print(f"  Plantas mencionadas: {', '.join(data['plants_mentioned'])}")

            if data.get('data'):
                print(f"  Datos:")
                for key, value in data['data'].items():
                    print(f"    • {key}: {value}")

            if data.get('suggestions'):
                print(f"  Sugerencias:")
                for suggestion in data['suggestions']:
                    print(f"    - {suggestion}")

            print(f"  Prioridad: {data.get('priority', 'info').upper()}")
            print()

            # Solicitar estado del sistema
            print("Solicitando estado del sistema...")
            await websocket.send(json.dumps({
                "type": "request_status"
            }))

            status_response = await websocket.recv()
            status_data = json.loads(status_response)
            print()
            print(f"[{status_data['type']}] Estado del sistema recibido:")

            if 'data' in status_data:
                plants = status_data['data'].get('plants', [])
                print(f"  Plantas: {len(plants)}")
                for plant in plants:
                    print(f"    • {plant['name']}: {plant.get('current_moisture', 'N/A')}% humedad")

                tank = status_data['data'].get('water_tank', {})
                print(f"  Tanque: {tank.get('level_percentage', 'N/A')}%")

            print()
            print("=" * 70)
            print("  PRUEBA COMPLETADA EXITOSAMENTE")
            print("=" * 70)

    except Exception as e:
        print(f"[ERROR] {e}")
        print()
        print("Asegurate de que el servidor este corriendo:")
        print("  python main.py")

if __name__ == "__main__":
    asyncio.run(test_websocket())
