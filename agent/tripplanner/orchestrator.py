"""Orchestrator Agent: interpreta, decide y coordina.

Memoria (tres mecanismos):
  1. Ventana de contexto: SlidingWindowConversationManager (mensajes recientes de la sesión).
  2. Memoria de corto plazo de AgentCore: eventos de la conversación por sesión/actor
     (permite continuar la conversación tras cerrar y volver a abrir la app).
  3. Memoria de largo plazo de AgentCore: estrategias de preferencias de usuario,
     hechos semánticos y resúmenes, recuperadas por namespace en cada turno.
Además, las preferencias persistidas en DynamoDB se inyectan en el prompt
(DynamoDB es la fuente de verdad; la memoria ayuda a conversar mejor).
"""
import json
import logging
from datetime import date
from typing import Callable

from strands import Agent
from strands.agent.conversation_manager import SlidingWindowConversationManager
from strands.models import BedrockModel

from . import config
from .business_tools import load_preferences, make_business_tools
from .specialists import make_specialist_tools

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Eres TripPlanner AI, el Orchestrator Agent de una plataforma de viajes. Hoy es {today}.
Coordinas a dos especialistas y a las herramientas de negocio:
- flight_specialist → Flight Agent (MCP de vuelos).
- weather_specialist → Weather Agent (MCP de clima).
- create_trip, get_trips, update_trip, create_itinerary, update_itinerary,
  create_reservation, get_reservations, update_reservation, delete_reservation, save_preferences
  → backend (Lambda + DynamoDB).

Reglas de decisión:
1. Para planear un viaje llama a flight_specialist y weather_specialist (puedes llamarlos en paralelo)
   con origen, destino, fechas exactas AAAA-MM-DD y número de pasajeros.
   Si el usuario no da fechas, propone fechas concretas razonables (p. ej. dentro de 3-4 semanas,
   con la duración pedida), dilo explícitamente y continúa sin bloquear la conversación.
2. "Viajo con dos personas más" significa 3 viajeros en total.
3. Cuando el usuario pida crear/guardar el viaje: create_trip → create_itinerary (un día por cada
   día del viaje, 2-4 actividades por día con hora, lugar y costo estimado en COP, coherentes con el
   clima y el presupuesto) → si eligió un vuelo, create_reservation tipo FLIGHT con los datos del vuelo.
   Usa los tripId reales que devuelven las herramientas, nunca los inventes.
4. Las reservas son SIMULADAS: créalas con status SIMULADA (o PENDIENTE si el usuario lo pide).
   Nunca digas que una reserva está confirmada por un proveedor real.
5. Gestión de reservas por chat:
   - Crear: create_reservation (tipo FLIGHT, HOTEL o ACTIVITY) asociada a un viaje existente.
   - Modificar: get_reservations para ubicarla y update_reservation con solo los campos que cambian.
   - Eliminar: get_reservations, muestra al usuario cuáles se borrarán (título y código SIM-…) y pide
     confirmación explícita; solo tras un "sí" llama delete_reservation una vez por reserva. Si el usuario
     ya dijo claramente cuáles borrar ("elimina todas", "borra la de Wingo"), esa es la confirmación.
     Informa cuántas se eliminaron. Las CONFIRMADAS por proveedor real no se pueden borrar.
6. NUNCA pidas ni aceptes datos de tarjetas, CVV ni información de pago.
7. Para "mis viajes" o recuperar información usa get_trips / get_reservations (no la memoria).
8. Si el usuario expresa una preferencia estable, guárdala con save_preferences.
9. Controla el presupuesto: compara el costo de vuelos + actividades contra el presupuesto e infórmalo.
10. Precios y vuelos: cita SIEMPRE aerolínea, número de vuelo, hora y precio exactos tal como vienen en los
   resultados de las herramientas; los totales deben ser sumas exactas de esos valores. No inventes nombres
   como "Opción 3": el usuario solo ve las tarjetas con aerolínea y número de vuelo.
11. Días de la semana: usa únicamente el calendario de referencia de abajo; nunca los calcules de memoria.
12. El frontend ya muestra tarjetas visuales de vuelos, clima, viajes, itinerarios y reservas con los
   datos de las herramientas: NO repitas tablas largas; da un resumen claro, recomendaciones y el
   siguiente paso sugerido. Responde siempre en español, con tono cercano y en formato Markdown breve.

Calendario de referencia (fecha → día): {calendar}

Preferencias guardadas del usuario (DynamoDB): {preferences}
"""

_DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def _calendar(days: int = 75) -> str:
    from datetime import timedelta
    t = date.today()
    return ", ".join(f"{(t + timedelta(d)).isoformat()} {_DIAS[(t + timedelta(d)).weekday()]}" for d in range(days))

# Respaldo local si no hay AgentCore Memory (p. ej. pruebas locales).
_local_history: dict[str, list] = {}


def _session_manager(user_id: str, session_id: str):
    if not config.MEMORY_ID:
        return None
    try:
        from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig, RetrievalConfig
        from bedrock_agentcore.memory.integrations.strands.session_manager import AgentCoreMemorySessionManager
        cfg = AgentCoreMemoryConfig(
            memory_id=config.MEMORY_ID, session_id=session_id, actor_id=user_id,
            retrieval_config={
                "/users/{actorId}/preferences": RetrievalConfig(top_k=5, relevance_score=0.4),
                "/users/{actorId}/facts": RetrievalConfig(top_k=5, relevance_score=0.5),
                "/summaries/{actorId}/{sessionId}": RetrievalConfig(top_k=2, relevance_score=0.4),
            },
        )
        return AgentCoreMemorySessionManager(cfg, region_name=config.AWS_REGION)
    except Exception:  # noqa: BLE001
        logger.exception("No se pudo iniciar AgentCore Memory; se usa memoria local")
        return None


def build_orchestrator(user_id: str, session_id: str, emit: Callable[[str, dict], None]) -> Agent:
    prefs = load_preferences(user_id)
    session_manager = _session_manager(user_id, session_id)
    kwargs = {}
    if session_manager:
        kwargs["session_manager"] = session_manager
    else:
        kwargs["messages"] = _local_history.setdefault(f"{user_id}:{session_id}", [])

    agent = Agent(
        name="orchestrator",
        model=BedrockModel(model_id=config.ORCHESTRATOR_MODEL_ID, region_name=config.AWS_REGION,
                           temperature=0.3, max_tokens=4000),
        system_prompt=SYSTEM_PROMPT.format(today=f"{date.today().isoformat()} ({_DIAS[date.today().weekday()]})",
                                           calendar=_calendar(),
                                           preferences=json.dumps(prefs, ensure_ascii=False) if prefs else "ninguna"),
        tools=make_specialist_tools(emit) + make_business_tools(user_id, emit),
        conversation_manager=SlidingWindowConversationManager(window_size=40),
        callback_handler=None,
        **kwargs,
    )
    if not session_manager:
        _local_history[f"{user_id}:{session_id}"] = agent.messages
    return agent
