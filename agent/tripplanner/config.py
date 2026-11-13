"""Configuración del agente (variables de entorno del AgentCore Runtime)."""
import os
import sys
from pathlib import Path

AWS_REGION = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))

# Modelos de Bedrock (inference profiles). Ajusta según los habilitados en tu cuenta.
ORCHESTRATOR_MODEL_ID = os.getenv("ORCHESTRATOR_MODEL_ID", "us.anthropic.claude-sonnet-4-6")
SPECIALIST_MODEL_ID = os.getenv("SPECIALIST_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")

# AgentCore Memory (opcional). Si no se define, se usa memoria en proceso.
MEMORY_ID = os.getenv("MEMORY_ID", "")

# Nombres de las Lambdas que respaldan cada Tool. Se puede pegar tal cual la salida
# `ToolFunctionNames` del stack SAM: "CreateTrip=fn1,GetTrips=fn2,..."
_DEFAULT_PREFIX = os.getenv("PROJECT_NAME", "tripplanner")
TOOL_NAMES = ["CreateTrip", "GetTrips", "UpdateTrip", "CreateItinerary", "UpdateItinerary",
              "CreateReservation", "GetReservations", "UpdateReservation", "GetPreferences", "SavePreferences"]


def _parse_tool_functions():
    mapping = {n: f"{_DEFAULT_PREFIX}-{n}" for n in TOOL_NAMES}
    raw = os.getenv("TOOL_FUNCTIONS", "")
    for pair in filter(None, (p.strip() for p in raw.split(","))):
        if "=" in pair:
            k, v = pair.split("=", 1)
            mapping[k.strip()] = v.strip()
    return mapping


TOOL_FUNCTIONS = _parse_tool_functions()

# Solo para desarrollo local: permite enviar user_id en el payload sin JWT.
ALLOW_INSECURE_LOCAL_USER = os.getenv("ALLOW_INSECURE_LOCAL_USER", "false").lower() == "true"

MCP_DIR = Path(__file__).resolve().parent.parent / "mcp_servers"
PYTHON = sys.executable
