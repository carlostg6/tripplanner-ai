"""Flight Agent y Weather Agent: especialistas que usan sus MCP.

Patrón "agents as tools": el Orchestrator los ve como dos tools
(`flight_specialist`, `weather_specialist`). Cada especialista es un Agent de
Strands independiente con sus propias herramientas MCP (stdio) y su prompt.

Para la Agent-Driven UI se extraen los resultados estructurados (JSON) que
devolvieron las herramientas MCP y se emiten como eventos `ui` hacia el frontend.
"""
import json
import logging
import os
import threading
from typing import Callable

from mcp import StdioServerParameters, stdio_client
try:
    from mcp.client.stdio import get_default_environment
except ImportError:  # versiones antiguas del SDK
    def get_default_environment():
        return {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "LANG", "USER", "SHELL", "TERM")}
from strands import Agent, tool
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient

from . import config

logger = logging.getLogger(__name__)

FLIGHT_PROMPT = """Eres Flight Agent, especialista en vuelos de TripPlanner AI.
- Usa SIEMPRE la herramienta search_flights para consultar vuelos; nunca inventes datos.
- Si te dan una ciudad, la herramienta acepta nombres de ciudad o códigos IATA.
- Si hay fecha de regreso, búscala en la misma llamada (return_date).
- Responde en español, breve: compara 2-3 mejores opciones (más económica, más rápida,
  mejor horario) con aerolínea, número de vuelo, horario y precio total para todos los pasajeros.
- Indica que los precios provienen de una fuente simulada si el resultado lo dice.
"""

WEATHER_PROMPT = """Eres Weather Agent, especialista en clima de TripPlanner AI.
- Usa SIEMPRE la herramienta get_weather_forecast; nunca inventes datos.
- Responde en español, breve: temperatura, condiciones y probabilidad de lluvia por día,
  y una recomendación práctica (ropa, mejores horas para actividades al aire libre).
- Si la fuente es una referencia histórica, acláralo.
"""

_lock = threading.Lock()
_clients: dict[str, MCPClient] = {}


def _mcp_client(name: str, script: str) -> MCPClient:
    """Cliente MCP stdio compartido por el contenedor (se inicia una sola vez)."""
    with _lock:
        if name not in _clients:
            # El SDK de MCP solo hereda unas pocas variables al subproceso (PATH, HOME…);
            # se pasan explícitamente las que necesitan los servidores (p. ej. SERPAPI_KEY).
            env = {**get_default_environment(),
                   **{k: v for k, v in os.environ.items()
                      if k in ("SERPAPI_KEY", "SERPAPI_PRICE_IS_TOTAL", "AWS_REGION", "HTTPS_PROXY", "HTTP_PROXY",
                               "NO_PROXY", "SSL_CERT_FILE", "REQUESTS_CA_BUNDLE")}}
            params = StdioServerParameters(command=config.PYTHON, args=[str(config.MCP_DIR / script)], env=env)
            client = MCPClient(lambda: stdio_client(params), startup_timeout=60)
            client.start()
            _clients[name] = client
        return _clients[name]


def flight_mcp_tools():
    return _mcp_client("flights", "flight_server.py").list_tools_sync()


def weather_mcp_tools():
    return _mcp_client("weather", "weather_server.py").list_tools_sync()


def extract_tool_results(messages, tool_name: str) -> list[dict]:
    """Devuelve los JSON que retornó `tool_name` dentro de la conversación del especialista."""
    names, results = {}, []
    for msg in messages:
        for block in msg.get("content", []):
            if "toolUse" in block:
                names[block["toolUse"]["toolUseId"]] = block["toolUse"]["name"]
            elif "toolResult" in block:
                tr = block["toolResult"]
                if names.get(tr.get("toolUseId", "")) != tool_name:
                    continue
                for c in tr.get("content", []):
                    data = c.get("json")
                    if data is None and "text" in c:
                        try:
                            data = json.loads(c["text"])
                        except (json.JSONDecodeError, TypeError):
                            continue
                    if isinstance(data, dict):
                        results.append(data)
    return results


def _model(temperature=0.2):
    return BedrockModel(model_id=config.SPECIALIST_MODEL_ID, region_name=config.AWS_REGION,
                        temperature=temperature)


def make_specialist_tools(emit: Callable[[str, dict], None]):
    @tool
    def flight_specialist(request: str) -> str:
        """Delegar al Flight Agent la búsqueda y comparación de vuelos.

        Args:
            request: instrucción completa en lenguaje natural con origen, destino,
                     fecha de ida (AAAA-MM-DD), fecha de regreso y número de pasajeros.
        """
        emit("status", {"agent": "Flight Agent", "message": "Consultando vuelos en el MCP de vuelos…"})
        agent = Agent(name="flight_agent", model=_model(), system_prompt=FLIGHT_PROMPT,
                      tools=flight_mcp_tools(), callback_handler=None)
        answer = str(agent(request))
        for data in extract_tool_results(agent.messages, "search_flights"):
            if not data.get("error"):
                emit("flights", data)
        return answer

    @tool
    def weather_specialist(request: str) -> str:
        """Delegar al Weather Agent la consulta del clima de un destino.

        Args:
            request: instrucción con la ciudad y el rango de fechas (AAAA-MM-DD).
        """
        emit("status", {"agent": "Weather Agent", "message": "Consultando el clima en el MCP de clima…"})
        agent = Agent(name="weather_agent", model=_model(), system_prompt=WEATHER_PROMPT,
                      tools=weather_mcp_tools(), callback_handler=None)
        answer = str(agent(request))
        for data in extract_tool_results(agent.messages, "get_weather_forecast"):
            if not data.get("error"):
                emit("weather", data)
        return answer

    return [flight_specialist, weather_specialist]
