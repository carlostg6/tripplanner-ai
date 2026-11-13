"""Tools de negocio del Orchestrator. Cada una invoca la Lambda que la respalda.

Flujo (Figura 2): Usuario → Orchestrator → Tool → Lambda (valida y ejecuta) → DynamoDB → respuesta.

Las tools se construyen por petición (closure) con el `user_id` extraído del JWT
del usuario, de modo que el modelo NUNCA decide de qué usuario son los datos.
"""
import json
import logging
from typing import Callable, Optional

import boto3
from botocore.config import Config
from strands import tool

from . import config

logger = logging.getLogger(__name__)
_lambda = boto3.client("lambda", region_name=config.AWS_REGION,
                       config=Config(retries={"max_attempts": 3, "mode": "standard"}, read_timeout=15))


def invoke_lambda(tool_name: str, user_id: str, body: dict | None = None, path: dict | None = None,
                  query: dict | None = None):
    """Invoca la Lambda de negocio y devuelve (status, body)."""
    event = {"source": "agent", "userId": user_id, "body": body or {},
             "pathParameters": path or {}, "queryStringParameters": query or {}}
    try:
        resp = _lambda.invoke(FunctionName=config.TOOL_FUNCTIONS[tool_name],
                              InvocationType="RequestResponse", Payload=json.dumps(event).encode())
        payload = json.loads(resp["Payload"].read() or b"{}")
        if resp.get("FunctionError"):
            logger.error("Lambda %s FunctionError: %s", tool_name, payload)
            return 500, {"error": {"code": "LAMBDA_ERROR", "message": "La operación falló."}}
        return payload.get("statusCode", 500), payload.get("body", {})
    except Exception as e:  # noqa: BLE001
        logger.exception("Error invocando %s", tool_name)
        return 503, {"error": {"code": "UNAVAILABLE", "message": f"Servicio no disponible ({type(e).__name__})."}}


def _clean(d: dict) -> dict:
    return {k: v for k, v in d.items() if v not in (None, "", [])}


def make_business_tools(user_id: str, emit: Callable[[str, dict], None]):
    def run(tool_name, component=None, pick=None, **kw):
        status, body = invoke_lambda(tool_name, user_id, **kw)
        if status >= 400:
            return json.dumps({"ok": False, "status": status, **body}, ensure_ascii=False)
        if component:
            emit(component, pick(body) if pick else body)
        return json.dumps({"ok": True, **body}, ensure_ascii=False, default=str)

    @tool
    def create_trip(origin: str, destination: str, start_date: str, end_date: str, travelers: int,
                    budget: Optional[float] = None, currency: str = "COP", title: str = "",
                    interests: Optional[list[str]] = None, notes: str = "") -> str:
        """CreateTrip: crea y guarda un viaje del usuario en DynamoDB.

        Args:
            origin: ciudad de origen. destination: ciudad de destino.
            start_date / end_date: AAAA-MM-DD. travelers: número total de viajeros (incluye al usuario).
            budget: presupuesto total. currency: COP, USD o EUR.
            title: nombre opcional del viaje. interests: lista de intereses (playa, historia...).
        Devuelve el viaje creado con su tripId.
        """
        body = _clean({"origin": origin, "destination": destination, "startDate": start_date, "endDate": end_date,
                       "travelers": travelers, "budget": budget, "currency": currency, "title": title,
                       "interests": interests, "notes": notes})
        return run("CreateTrip", "trip", lambda b: b["trip"], body=body)

    @tool
    def get_trips(trip_id: str = "", status: str = "") -> str:
        """GetTrips: consulta los viajes guardados del usuario.

        Sin trip_id devuelve la lista; con trip_id devuelve el detalle con itinerario y reservas.
        status opcional: PLANEADO, EN_CURSO, COMPLETADO, CANCELADO.
        """
        if trip_id:
            return run("GetTrips", "trip_detail", path={"tripId": trip_id})
        return run("GetTrips", "trips", lambda b: {"trips": b["trips"]}, query=_clean({"status": status}))

    @tool
    def update_trip(trip_id: str, title: str = "", origin: str = "", destination: str = "",
                    start_date: str = "", end_date: str = "", travelers: Optional[int] = None,
                    budget: Optional[float] = None, status: str = "", notes: str = "") -> str:
        """UpdateTrip: actualiza datos de un viaje existente (solo los campos enviados)."""
        body = _clean({"title": title, "origin": origin, "destination": destination, "startDate": start_date,
                       "endDate": end_date, "travelers": travelers, "budget": budget, "status": status, "notes": notes})
        return run("UpdateTrip", "trip", lambda b: b["trip"], path={"tripId": trip_id}, body=body)

    @tool
    def create_itinerary(trip_id: str, days: list[dict], summary: str = "") -> str:
        """CreateItinerary: crea el itinerario día por día de un viaje.

        Args:
            trip_id: id del viaje (de create_trip o get_trips).
            days: lista de días: [{"day": 1, "date": "AAAA-MM-DD", "title": "...",
                   "activities": [{"time": "HH:MM", "title": "...", "description": "...",
                                   "location": "...", "estimatedCost": 0, "category": "cultura"}]}]
                  Las fechas deben estar dentro del rango del viaje.
            summary: resumen corto del itinerario.
        """
        return run("CreateItinerary", "itinerary", lambda b: b["itinerary"], path={"tripId": trip_id},
                   body=_clean({"days": days, "summary": summary}))

    @tool
    def update_itinerary(trip_id: str, days: list[dict], summary: str = "") -> str:
        """UpdateItinerary: reemplaza el itinerario de un viaje con la lista completa de días.

        Primero usa get_trips(trip_id) para leer el itinerario actual y envía todos los días (modificados y no).
        """
        return run("UpdateItinerary", "itinerary", lambda b: b["itinerary"], path={"tripId": trip_id},
                   body=_clean({"days": days, "summary": summary}))

    @tool
    def create_reservation(trip_id: str, type: str, title: str, provider: str = "",
                           start_datetime: str = "", end_datetime: str = "", amount: Optional[float] = None,
                           currency: str = "COP", quantity: Optional[int] = None, status: str = "SIMULADA",
                           details: Optional[dict] = None, notes: str = "") -> str:
        """CreateReservation: registra una reserva SIMULADA asociada a un viaje.

        Args:
            trip_id: viaje al que se asocia. type: FLIGHT, HOTEL o ACTIVITY.
            title: descripción (ej. "Vuelo BOG-CTG AV9520"). provider: aerolínea/hotel/operador.
            start_datetime / end_datetime: ISO 8601. amount: valor total. quantity: personas/unidades.
            status: SIMULADA (por defecto) o PENDIENTE. Nunca CONFIRMADA sin proveedor real.
            details: datos extra (número de vuelo, horarios, etc.). NUNCA datos de pago.
        """
        body = _clean({"tripId": trip_id, "type": type, "title": title, "provider": provider,
                       "startDateTime": start_datetime, "endDateTime": end_datetime, "amount": amount,
                       "currency": currency, "quantity": quantity, "status": status, "details": details,
                       "notes": notes})
        return run("CreateReservation", "reservation", lambda b: b["reservation"], body=body)

    @tool
    def get_reservations(trip_id: str = "", status: str = "", type: str = "") -> str:
        """GetReservations: consulta reservas del usuario, opcionalmente por viaje, estado o tipo."""
        return run("GetReservations", "reservations", lambda b: {"reservations": b["reservations"]},
                   query=_clean({"tripId": trip_id, "status": status, "type": type}))

    @tool
    def update_reservation(reservation_id: str, status: str = "", title: str = "", amount: Optional[float] = None,
                           start_datetime: str = "", end_datetime: str = "", quantity: Optional[int] = None,
                           trip_id: str = "", notes: str = "") -> str:
        """UpdateReservation: actualiza una reserva o su estado (SIMULADA ↔ PENDIENTE) o la asocia a otro viaje."""
        body = _clean({"status": status, "title": title, "amount": amount, "startDateTime": start_datetime,
                       "endDateTime": end_datetime, "quantity": quantity, "tripId": trip_id, "notes": notes})
        return run("UpdateReservation", "reservation", lambda b: b["reservation"],
                   path={"reservationId": reservation_id}, body=body)

    @tool
    def save_preferences(activity_types: Optional[list[str]] = None, dietary_restrictions: Optional[list[str]] = None,
                         budget_per_day: Optional[float] = None, travel_pace: str = "",
                         preferred_airlines: Optional[list[str]] = None, seat_preference: str = "",
                         home_city: str = "", notes: str = "") -> str:
        """Guarda preferencias de viaje persistentes del usuario (gustos y restricciones).

        travel_pace: RELAJADO, MODERADO o INTENSO. seat_preference: VENTANA, PASILLO o INDIFERENTE.
        Úsala cuando el usuario exprese una preferencia estable (ej. "soy vegetariano", "odio madrugar").
        """
        body = _clean({"activityTypes": activity_types, "dietaryRestrictions": dietary_restrictions,
                       "budgetPerDay": budget_per_day, "travelPace": travel_pace,
                       "preferredAirlines": preferred_airlines, "seatPreference": seat_preference,
                       "homeCity": home_city, "notes": notes})
        return run("SavePreferences", "preferences", lambda b: b["preferences"], body=body)

    return [create_trip, get_trips, update_trip, create_itinerary, update_itinerary,
            create_reservation, get_reservations, update_reservation, save_preferences]


def load_preferences(user_id: str) -> dict:
    status, body = invoke_lambda("GetPreferences", user_id)
    return body.get("preferences", {}) if status == 200 else {}
