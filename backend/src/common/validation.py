"""Validaciones de negocio: tipos, rangos, fechas y estados permitidos."""
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from .http import ApiError

RESERVATION_TYPES = {"FLIGHT", "HOTEL", "ACTIVITY"}
RESERVATION_STATUSES = {"SIMULADA", "PENDIENTE", "CONFIRMADA"}
# CONFIRMADA solo es alcanzable con referencia de un proveedor real.
ALLOWED_TRANSITIONS = {
    "SIMULADA": {"SIMULADA", "PENDIENTE"},
    "PENDIENTE": {"PENDIENTE", "SIMULADA", "CONFIRMADA"},
    "CONFIRMADA": {"CONFIRMADA"},
}
TRIP_STATUSES = {"PLANEADO", "EN_CURSO", "COMPLETADO", "CANCELADO"}
CURRENCIES = {"COP", "USD", "EUR"}

_CARD_RE = re.compile(r"(?:\d[ -]?){13,19}")
_FORBIDDEN_KEYS = {"card", "cardnumber", "card_number", "cvv", "cvc", "tarjeta", "numerotarjeta",
                   "pan", "expiry", "expiration", "securitycode"}


def _errors():
    return []


def reject_payment_data(obj, path="body"):
    """Prohibido recibir/guardar datos de tarjetas: rechaza llaves sospechosas o PANs."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            norm = re.sub(r"[^a-z]", "", str(k).lower())
            if norm in _FORBIDDEN_KEYS:
                raise ApiError(400, "PAYMENT_DATA_FORBIDDEN",
                               "TripPlanner no acepta datos de tarjetas ni de pago.")
            reject_payment_data(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            reject_payment_data(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        for m in _CARD_RE.finditer(obj):
            digits = re.sub(r"\D", "", m.group())
            if 13 <= len(digits) <= 19 and _luhn(digits):
                raise ApiError(400, "PAYMENT_DATA_FORBIDDEN",
                               "TripPlanner no acepta datos de tarjetas ni de pago.")


def _luhn(digits: str) -> bool:
    total, alt = 0, False
    for d in reversed(digits):
        n = int(d)
        if alt:
            n *= 2
            if n > 9:
                n -= 9
        total += n
        alt = not alt
    return total % 10 == 0


class V:
    """Acumulador de errores de validación por campo."""

    def __init__(self, data: dict):
        self.data = data or {}
        self.errors = []
        self.out = {}

    def fail(self, field, msg):
        self.errors.append({"field": field, "message": msg})

    def string(self, field, required=False, min_len=1, max_len=200, upper=False):
        v = self.data.get(field)
        if v is None or v == "":
            if required:
                self.fail(field, "Campo obligatorio.")
            return None
        if not isinstance(v, str):
            self.fail(field, "Debe ser texto.")
            return None
        v = v.strip()
        if not (min_len <= len(v) <= max_len):
            self.fail(field, f"Debe tener entre {min_len} y {max_len} caracteres.")
            return None
        v = v.upper() if upper else v
        self.out[field] = v
        return v

    def integer(self, field, required=False, min_v=None, max_v=None):
        v = self.data.get(field)
        if v is None:
            if required:
                self.fail(field, "Campo obligatorio.")
            return None
        if isinstance(v, bool) or not isinstance(v, (int, float, str)):
            self.fail(field, "Debe ser un número entero.")
            return None
        try:
            iv = int(v)
            if float(v) != iv:
                raise ValueError
        except (ValueError, TypeError):
            self.fail(field, "Debe ser un número entero.")
            return None
        if (min_v is not None and iv < min_v) or (max_v is not None and iv > max_v):
            self.fail(field, f"Debe estar entre {min_v} y {max_v}.")
            return None
        self.out[field] = iv
        return iv

    def number(self, field, required=False, min_v=0, max_v=10**12):
        v = self.data.get(field)
        if v is None:
            if required:
                self.fail(field, "Campo obligatorio.")
            return None
        if isinstance(v, bool):
            self.fail(field, "Debe ser numérico.")
            return None
        try:
            d = Decimal(str(v))
        except (InvalidOperation, ValueError):
            self.fail(field, "Debe ser numérico.")
            return None
        if d.is_nan() or d < min_v or d > max_v:
            self.fail(field, f"Debe estar entre {min_v} y {max_v}.")
            return None
        self.out[field] = d
        return d

    def date(self, field, required=False, allow_past=False):
        v = self.data.get(field)
        if v is None or v == "":
            if required:
                self.fail(field, "Campo obligatorio.")
            return None
        try:
            d = date.fromisoformat(str(v)[:10])
        except ValueError:
            self.fail(field, "Fecha inválida, usa el formato AAAA-MM-DD.")
            return None
        if not allow_past and d < date.today() - timedelta(days=1):
            self.fail(field, "La fecha no puede estar en el pasado.")
            return None
        if d > date.today() + timedelta(days=730):
            self.fail(field, "La fecha está demasiado lejos (máx. 2 años).")
            return None
        self.out[field] = d.isoformat()
        return d

    def datetime(self, field, required=False):
        v = self.data.get(field)
        if v is None or v == "":
            if required:
                self.fail(field, "Campo obligatorio.")
            return None
        try:
            dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        except ValueError:
            self.fail(field, "Fecha/hora inválida (ISO 8601).")
            return None
        self.out[field] = dt.isoformat()
        return dt

    def enum(self, field, allowed, required=False, default=None):
        v = self.data.get(field, default)
        if v is None:
            if required:
                self.fail(field, "Campo obligatorio.")
            return None
        if not isinstance(v, str) or v.upper() not in allowed:
            self.fail(field, f"Valor no permitido. Opciones: {', '.join(sorted(allowed))}.")
            return None
        self.out[field] = v.upper()
        return v.upper()

    def string_list(self, field, max_items=20, max_len=80):
        v = self.data.get(field)
        if v is None:
            return None
        if not isinstance(v, list) or len(v) > max_items or not all(isinstance(x, str) for x in v):
            self.fail(field, f"Debe ser una lista de hasta {max_items} textos.")
            return None
        clean = [x.strip()[:max_len] for x in v if x.strip()]
        self.out[field] = clean
        return clean

    def raise_if_errors(self):
        if self.errors:
            raise ApiError(400, "VALIDATION_ERROR", "Hay datos inválidos en la petición.", self.errors)
        return self.out


def validate_trip(data: dict, partial=False):
    reject_payment_data(data)
    v = V(data)
    v.string("title", max_len=120)
    v.string("origin", required=not partial, max_len=80)
    v.string("destination", required=not partial, max_len=80)
    start = v.date("startDate", required=not partial)
    end = v.date("endDate", required=not partial)
    v.integer("travelers", required=not partial, min_v=1, max_v=20)
    v.number("budget", min_v=0, max_v=10**11)
    v.enum("currency", CURRENCIES, default=None if partial else "COP")
    v.string_list("interests")
    v.string("notes", max_len=1000)
    if partial:
        v.enum("status", TRIP_STATUSES)
    if start and end:
        if end < start:
            v.fail("endDate", "La fecha de regreso debe ser posterior o igual a la de salida.")
        elif (end - start).days > 60:
            v.fail("endDate", "El viaje no puede durar más de 60 días.")
    out = v.raise_if_errors()
    if partial and not out:
        raise ApiError(400, "EMPTY_UPDATE", "No se envió ningún campo para actualizar.")
    return out


def validate_itinerary(data: dict, trip: dict | None = None):
    reject_payment_data(data)
    days = data.get("days")
    errors = []
    if not isinstance(days, list) or not (1 <= len(days) <= 60):
        raise ApiError(400, "VALIDATION_ERROR", "Hay datos inválidos en la petición.",
                       [{"field": "days", "message": "Debe ser una lista de 1 a 60 días."}])
    clean_days = []
    for i, day in enumerate(days):
        if not isinstance(day, dict):
            errors.append({"field": f"days[{i}]", "message": "Debe ser un objeto."})
            continue
        dv = V(day)
        dnum = dv.integer("day", required=True, min_v=1, max_v=60)
        ddate = dv.date("date", allow_past=True)
        dv.string("title", max_len=120)
        acts = day.get("activities", [])
        clean_acts = []
        if not isinstance(acts, list) or len(acts) > 20:
            dv.fail("activities", "Debe ser una lista de hasta 20 actividades.")
            acts = []
        for j, act in enumerate(acts):
            av = V(act if isinstance(act, dict) else {})
            av.string("time", max_len=5)
            av.string("title", required=True, max_len=150)
            av.string("description", max_len=500)
            av.string("location", max_len=150)
            av.number("estimatedCost", min_v=0, max_v=10**10)
            av.string("category", max_len=40)
            if act.get("time") if isinstance(act, dict) else None:
                if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", str(act["time"])):
                    av.fail("time", "Hora inválida (HH:MM).")
            for e in av.errors:
                e["field"] = f"days[{i}].activities[{j}].{e['field']}"
            dv.errors.extend(av.errors)
            clean_acts.append(av.out)
        if trip and ddate:
            if not (trip["startDate"] <= ddate.isoformat() <= trip["endDate"]):
                dv.fail("date", "La fecha del día debe estar dentro de las fechas del viaje.")
        for e in dv.errors:
            if not e["field"].startswith("days["):
                e["field"] = f"days[{i}].{e['field']}"
        errors.extend(dv.errors)
        out = dv.out
        out["activities"] = clean_acts
        clean_days.append(out)
    if errors:
        raise ApiError(400, "VALIDATION_ERROR", "Hay datos inválidos en la petición.", errors)
    nums = [d["day"] for d in clean_days]
    if len(nums) != len(set(nums)):
        raise ApiError(400, "VALIDATION_ERROR", "Hay días repetidos en el itinerario.")
    v = V(data)
    v.string("summary", max_len=1000)
    extra = v.raise_if_errors()
    return {"days": sorted(clean_days, key=lambda d: d["day"]), **extra}


def validate_reservation(data: dict, partial=False):
    reject_payment_data(data)
    v = V(data)
    if not partial:
        v.string("tripId", required=True, max_len=64)
        v.enum("type", RESERVATION_TYPES, required=True)
    v.string("title", required=not partial, max_len=150)
    v.string("provider", max_len=100)
    v.string("providerReference", max_len=100)
    v.datetime("startDateTime")
    v.datetime("endDateTime")
    v.number("amount", min_v=0, max_v=10**11)
    v.enum("currency", CURRENCIES, default=None if partial else "COP")
    v.integer("quantity", min_v=1, max_v=20)
    v.enum("status", RESERVATION_STATUSES, default=None if partial else "SIMULADA")
    v.string("notes", max_len=1000)
    details = data.get("details")
    if details is not None:
        if not isinstance(details, dict) or len(str(details)) > 4000:
            v.fail("details", "Debe ser un objeto de máximo 4KB.")
        else:
            from .http import to_plain
            import json
            v.out["details"] = json.loads(json.dumps(to_plain(details)), parse_float=Decimal)
    out = v.raise_if_errors()
    if partial and not out:
        raise ApiError(400, "EMPTY_UPDATE", "No se envió ningún campo para actualizar.")
    if out.get("status") == "CONFIRMADA" and not out.get("providerReference") and not partial:
        raise ApiError(409, "CONFIRMATION_REQUIRES_PROVIDER",
                       "Una reserva solo puede quedar CONFIRMADA con la referencia de un proveedor real.")
    return out


def validate_preferences(data: dict):
    reject_payment_data(data)
    v = V(data)
    v.number("budgetPerDay", min_v=0, max_v=10**10)
    v.enum("currency", CURRENCIES)
    v.string_list("activityTypes")
    v.string_list("dietaryRestrictions")
    v.string_list("accessibilityNeeds")
    v.string_list("preferredAirlines")
    v.enum("seatPreference", {"VENTANA", "PASILLO", "INDIFERENTE"})
    v.enum("travelPace", {"RELAJADO", "MODERADO", "INTENSO"})
    v.string("homeCity", max_len=80)
    v.string("notes", max_len=1000)
    out = v.raise_if_errors()
    if not out:
        raise ApiError(400, "EMPTY_UPDATE", "No se envió ninguna preferencia.")
    return out


def validate_profile(data: dict):
    reject_payment_data(data)
    v = V(data)
    v.string("name", max_len=100)
    v.string("phone", max_len=30)
    v.string("country", max_len=60)
    v.enum("language", {"ES", "EN"})
    out = v.raise_if_errors()
    if not out:
        raise ApiError(400, "EMPTY_UPDATE", "No se envió ningún campo.")
    return out
