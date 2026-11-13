"""Adaptador de peticiones/respuestas.

Cada Lambda de negocio puede ser invocada por dos vías:
  1. API Gateway HTTP API (canal 1, frontend). El usuario se toma del JWT de Cognito
     ya validado por el authorizer de API Gateway (claim `sub`).
  2. Invocación directa desde las Tools del Orchestrator Agent (canal 2). El agente
     envía {"source": "agent", "userId": ..., "pathParameters": ..., "body": ...}.
     Solo el rol de ejecución de AgentCore tiene permiso lambda:InvokeFunction,
     por lo que esa vía no es accesible desde Internet.
"""
import json
import logging
import os
import uuid
from decimal import Decimal

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, details=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details


class Request:
    def __init__(self, user_id, path, query, body, source, email=None):
        self.user_id = user_id
        self.path = path or {}
        self.query = query or {}
        self.body = body or {}
        self.source = source
        self.email = email


def _json_default(o):
    if isinstance(o, Decimal):
        return int(o) if o % 1 == 0 else float(o)
    raise TypeError(f"Tipo no serializable: {type(o)}")


def to_plain(obj):
    """Convierte Decimals de DynamoDB a tipos nativos."""
    return json.loads(json.dumps(obj, default=_json_default))


def parse_event(event) -> Request:
    request_context = event.get("requestContext") or {}
    if request_context.get("http"):  # API Gateway HTTP API v2
        claims = (request_context.get("authorizer") or {}).get("jwt", {}).get("claims", {})
        user_id = claims.get("sub")
        if not user_id:
            raise ApiError(401, "UNAUTHORIZED", "Sesión no válida.")
        raw = event.get("body")
        if raw and event.get("isBase64Encoded"):
            import base64
            raw = base64.b64decode(raw).decode("utf-8")
        try:
            body = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            raise ApiError(400, "INVALID_JSON", "El cuerpo de la petición no es JSON válido.")
        if not isinstance(body, dict):
            raise ApiError(400, "INVALID_JSON", "El cuerpo debe ser un objeto JSON.")
        return Request(user_id, event.get("pathParameters"), event.get("queryStringParameters"),
                       body, "api", claims.get("email"))

    if event.get("source") == "agent":
        user_id = event.get("userId")
        if not user_id or not isinstance(user_id, str):
            raise ApiError(401, "UNAUTHORIZED", "La invocación del agente no incluye userId.")
        body = event.get("body") or {}
        if not isinstance(body, dict):
            raise ApiError(400, "INVALID_BODY", "body debe ser un objeto.")
        return Request(user_id, event.get("pathParameters"), event.get("queryStringParameters"),
                       body, "agent")

    raise ApiError(400, "UNKNOWN_SOURCE", "Origen de invocación no soportado.")


def response(status: int, payload, source="api"):
    if source == "agent":
        return {"statusCode": status, "body": to_plain(payload)}
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(payload, default=_json_default, ensure_ascii=False),
    }


def handler(fn):
    """Decorador: parseo, manejo de errores y códigos HTTP homogéneos."""
    def wrapper(event, context):
        source = "agent" if event.get("source") == "agent" else "api"
        request_id = getattr(context, "aws_request_id", str(uuid.uuid4()))
        try:
            req = parse_event(event)
            status, payload = fn(req)
            return response(status, payload, source)
        except ApiError as e:
            logger.info("ApiError %s %s %s", e.status, e.code, e.message)
            err = {"error": {"code": e.code, "message": e.message}}
            if e.details:
                err["error"]["details"] = e.details
            return response(e.status, err, source)
        except Exception:  # nunca exponer detalles internos
            logger.exception("Error no controlado (requestId=%s)", request_id)
            return response(500, {"error": {"code": "INTERNAL_ERROR",
                                            "message": "Ocurrió un error interno. Intenta de nuevo.",
                                            "requestId": request_id}}, source)
    wrapper.__name__ = fn.__name__
    return wrapper
