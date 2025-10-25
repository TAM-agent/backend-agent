"""Interactive chat interface for GrowthAI.

This script allows you to have a conversation with GrowthAI,
asking questions about your plants, getting recommendations, and more.
"""

import os
from dotenv import load_dotenv
from irrigation_agent.agent import intelligent_irrigation_agent

# Load environment variables
load_dotenv()

def print_header():
    """Print a welcome header."""
    print("\n" + "="*70)
    print("🌱 GROWTHAI - TU ASISTENTE INTELIGENTE DE RIEGO 🤖")
    print("="*70)
    print("\nBienvenido! Puedo ayudarte con:")
    print("  • Estado de tus plantas y sensores")
    print("  • Recomendaciones de riego y fertilización")
    print("  • Análisis de salud de plantas")
    print("  • Pronósticos del clima y optimización")
    print("  • Diagnóstico de problemas")
    print("\nEscribe 'salir', 'exit' o 'quit' para terminar.")
    print("="*70 + "\n")


def print_separator():
    """Print a separator line."""
    print("\n" + "-"*70 + "\n")


def chat():
    """Run the interactive chat loop."""
    print_header()

    # Check if API key is configured
    if not os.getenv("GEMINI_API_KEY"):
        print("❌ ERROR: GEMINI_API_KEY no está configurado en el archivo .env")
        print("\nPor favor:")
        print("1. Copia .env-template a .env")
        print("2. Agrega tu GEMINI_API_KEY")
        print("3. Obtén una key gratis en: https://makersuite.google.com/app/apikey")
        return

    print("✅ GrowthAI inicializado correctamente!\n")

    conversation_history = []

    while True:
        try:
            # Get user input
            user_input = input("🧑 Tú: ").strip()

            # Check for exit commands
            if user_input.lower() in ['salir', 'exit', 'quit', 'q']:
                print("\n👋 ¡Hasta luego! Cuida bien de tus plantas. 🌱\n")
                break

            # Skip empty inputs
            if not user_input:
                continue

            print("\n🤖 GrowthAI está pensando...\n")

            # Send message to agent
            response = intelligent_irrigation_agent.send_message(
                message=user_input,
                history=conversation_history
            )

            # Print agent response
            print(f"🤖 GrowthAI: {response.text}")

            # Update conversation history
            conversation_history.append({
                "role": "user",
                "content": user_input
            })
            conversation_history.append({
                "role": "assistant",
                "content": response.text
            })

            print_separator()

        except KeyboardInterrupt:
            print("\n\n👋 Conversación interrumpida. ¡Hasta luego!\n")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            print("Intenta de nuevo o escribe 'salir' para terminar.\n")


def main():
    """Main entry point."""
    try:
        chat()
    except Exception as e:
        print(f"\n❌ Error fatal: {e}")
        print("\nVerifica que:")
        print("1. Tu GEMINI_API_KEY esté configurada correctamente")
        print("2. Tengas conexión a internet")
        print("3. Las dependencias estén instaladas (pip install -r requirements.txt)")


if __name__ == "__main__":
    main()
