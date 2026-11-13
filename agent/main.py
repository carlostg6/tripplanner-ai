"""Entrypoint del AgentCore Runtime (canal 2: HTTP streaming directo desde el frontend).

Request  (POST /invocations, Authorization: Bearer <access token de Cognito>)
         {"prompt": "Quiero organizar unas vacaciones..."}
Response text/event-stream; cada evento `data:` es un JSON:
  {"type": "start",  "sessionId": ...}
  {"type": "status", "agent": "Flight Agent", "message": "..."}      → indicadores de procesamiento
  {"type": "text",   "delta": "..."}                                  → texto en streaming
  {"type": "ui",     "component": "flights|weather|trip|trips|trip_detail|itinerary|reservation|reservations|preferences",
                     "data": {...}}                                   → Agent-Driven UI
  {"type": "error",  "message": "..."}
  {"type": "done"}
"""
import base64
import os
import json
import logging
import queue
import uuid

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from tripplanner import config
from tripplanner.orchestrator import build_orchestrator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tripplanner")

_middleware = []
if os.getenv("LOCAL_CORS_ORIGIN"):  # solo desarrollo local (python main.py + vite)
    from starlette.middleware import Middleware
    from starlette.middleware.cors import CORSMiddleware
    _middleware.append(Middleware(CORSMiddleware, allow_origins=[os.environ["LOCAL_CORS_ORIGIN"]],
                                  allow_methods=["POST", "OPTIONS"], allow_headers=["*"]))
app = BedrockAgentCoreApp(middleware=_middleware or None)

TOOL_LABELS = {
    "flight_specialist": ("Orchestrator", "Delegando la búsqueda de vuelos al Flight Agent…"),
    "weather_specialist": ("Orchestrator", "Delegando el clima al Weather Agent…"),
    "create_trip": ("Tool CreateTrip", "Guardando tu viaje…"),
    "get_trips": ("Tool GetTrips", "Consultando tus viajes…"),
    "update_trip": ("Tool UpdateTrip", "Actualizando el viaje…"),
    "create_itinerary": ("Tool CreateItinerary", "Generando y guardando el itinerario…"),
    "update_itinerary": ("Tool UpdateItinerary", "Actualizando el itinerario…"),
    "create_reservation": ("Tool CreateReservation", "Registrando la reserva simulada…"),
    "get_reservations": ("Tool GetReservations", "Consultando reservas…"),
    "update_reservation": ("Tool UpdateReservation", "Actualizando la reserva…"),
    "save_preferences": ("Tool SavePreferences", "Guardando tus preferencias…"),
}


def _jwt_claims(token: str) -> dict:
    """Decodifica el payload del JWT. La firma ya fue validada por el
    authorizer JWT de AgentCore (customJWTAuthorizer con Cognito)."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
    except Exception:  # noqa: BLE001
        return {}


def resolve_user(payload: dict, context) -> str | None:
    headers = {k.lower(): v for k, v in ((getattr(context, "request_headers", None) or {}).items())}
    auth = headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        sub = _jwt_claims(auth[7:]).get("sub")
        if sub:
            return sub
    if config.ALLOW_INSECURE_LOCAL_USER:
        return payload.get("user_id") or "local-dev-user"
    return None


@app.entrypoint
async def invoke(payload: dict, context):
    prompt = (payload or {}).get("prompt", "").strip()
    session_id = getattr(context, "session_id", None) or payload.get("session_id") or str(uuid.uuid4())
    user_id = resolve_user(payload, context)

    if not user_id:
        yield {"type": "error", "message": "No autenticado: falta el token del usuario."}
        return
    if not prompt or len(prompt) > 4000:
        yield {"type": "error", "message": "El mensaje está vacío o es demasiado largo."}
        return

    ui_queue: "queue.Queue[dict]" = queue.Queue()

    def emit(component: str, data: dict):
        if component == "status":
            ui_queue.put({"type": "status", **data})
        else:
            ui_queue.put({"type": "ui", "component": component, "data": data})

    def drain():
        while True:
            try:
                yield ui_queue.get_nowait()
            except queue.Empty:
                return

    yield {"type": "start", "sessionId": session_id}
    seen_tools = set()
    try:
        agent = build_orchestrator(user_id, session_id, emit)
        async for event in agent.stream_async(prompt):
            for e in drain():
                yield e
            if "data" in event and isinstance(event["data"], str):
                yield {"type": "text", "delta": event["data"]}
            elif "current_tool_use" in event:
                tu = event["current_tool_use"] or {}
                tid, name = tu.get("toolUseId"), tu.get("name")
                if tid and name and tid not in seen_tools:
                    seen_tools.add(tid)
                    agent_label, msg = TOOL_LABELS.get(name, ("Orchestrator", f"Usando {name}…"))
                    yield {"type": "status", "agent": agent_label, "tool": name, "message": msg}
        for e in drain():
            yield e
    except Exception:  # noqa: BLE001
        logger.exception("Error en la invocación")
        for e in drain():
            yield e
        yield {"type": "error", "message": "El asistente tuvo un problema procesando tu solicitud. Intenta de nuevo."}
    yield {"type": "done"}


if __name__ == "__main__":
    app.run()
