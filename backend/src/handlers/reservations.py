"""Lambdas de reservas: CreateReservation, GetReservations, UpdateReservation, DeleteReservation.

Reservas SIMULADAS pero persistentes. Estados: SIMULADA | PENDIENTE | CONFIRMADA.
CONFIRMADA exige `providerReference` (solo si se integra un proveedor real).
"""
from common import db
from common.http import ApiError, handler, to_plain
from common.validation import ALLOWED_TRANSITIONS, validate_reservation


def _out(item):
    return to_plain(db.clean(item))


@handler
def create_reservation(req):
    data = validate_reservation(req.body)
    trip = db.require_trip(req.user_id, data["tripId"])
    res_id = db.new_id("res")
    ts = db.now_iso()
    item = {
        "PK": db.user_pk(req.user_id), "SK": f"RES#{res_id}",
        "GSI1PK": f"TRIP#{trip['tripId']}", "GSI1SK": f"RES#{ts}#{res_id}",
        "entityType": "RESERVATION", "reservationId": res_id, "userId": req.user_id,
        "tripDestination": trip.get("destination"),
        "confirmationCode": f"SIM-{res_id[-6:].upper()}",
        "createdAt": ts, "updatedAt": ts, "createdBy": req.source,
        "statusHistory": [{"status": data["status"], "at": ts}],
        **data,
    }
    db.put_new(item)
    return 201, {"reservation": _out(item)}


@handler
def get_reservations(req):
    q = {**(req.query or {}), **{k: v for k, v in req.body.items() if isinstance(v, str)}}
    res_id = (req.path or {}).get("reservationId") or q.get("reservationId")
    if res_id:
        item = db.get(req.user_id, f"RES#{res_id}")
        if not item:
            raise ApiError(404, "RESERVATION_NOT_FOUND", "La reserva no existe o no te pertenece.")
        return 200, {"reservation": _out(item)}
    trip_id = q.get("tripId")
    if trip_id:
        db.require_trip(req.user_id, trip_id)
        items = [r for r in db.query_trip_reservations(trip_id) if r.get("userId") == req.user_id]
    else:
        items = db.query_prefix(req.user_id, "RES#")
    if q.get("status"):
        items = [r for r in items if r.get("status") == q["status"].upper()]
    if q.get("type"):
        items = [r for r in items if r.get("type") == q["type"].upper()]
    items.sort(key=lambda r: r.get("createdAt", ""), reverse=True)
    return 200, {"reservations": [_out(r) for r in items], "count": len(items)}


@handler
def update_reservation(req):
    res_id = (req.path or {}).get("reservationId") or req.body.get("reservationId")
    if not res_id:
        raise ApiError(400, "VALIDATION_ERROR", "Falta reservationId.")
    body = {k: v for k, v in req.body.items() if k not in ("reservationId", "tripId", "type")}
    new_trip = req.body.get("tripId")
    data = validate_reservation(body, partial=True) if body else {}
    current = db.get(req.user_id, f"RES#{res_id}")
    if not current:
        raise ApiError(404, "RESERVATION_NOT_FOUND", "La reserva no existe o no te pertenece.")

    if new_trip and new_trip != current.get("tripId"):  # reasociar a otro viaje
        trip = db.require_trip(req.user_id, new_trip)
        data.update({"tripId": new_trip, "GSI1PK": f"TRIP#{new_trip}",
                     "tripDestination": trip.get("destination")})
    if not data:
        raise ApiError(400, "EMPTY_UPDATE", "No se envió ningún campo para actualizar.")

    new_status = data.get("status")
    if new_status and new_status != current["status"]:
        if new_status not in ALLOWED_TRANSITIONS[current["status"]]:
            raise ApiError(409, "INVALID_STATUS_TRANSITION",
                           f"No se puede pasar de {current['status']} a {new_status}.")
        if new_status == "CONFIRMADA" and not (data.get("providerReference") or current.get("providerReference")):
            raise ApiError(409, "CONFIRMATION_REQUIRES_PROVIDER",
                           "Solo un proveedor real puede confirmar la reserva (falta providerReference).")
        data["statusHistory"] = list(current.get("statusHistory", [])) + [{"status": new_status, "at": db.now_iso()}]
    item = db.update(req.user_id, f"RES#{res_id}", data)
    return 200, {"reservation": _out(item)}


@handler
def delete_reservation(req):
    """Elimina una reserva del usuario. Solo el dueño puede borrarla (la PK es su `sub`).

    Una reserva CONFIRMADA por un proveedor real no se borra: primero debe cancelarse con el proveedor.
    """
    res_id = (req.path or {}).get("reservationId") or req.body.get("reservationId")
    if not res_id or not isinstance(res_id, str) or len(res_id) > 64:
        raise ApiError(400, "VALIDATION_ERROR", "Falta reservationId.")
    current = db.get(req.user_id, f"RES#{res_id}")
    if not current:
        raise ApiError(404, "RESERVATION_NOT_FOUND", "La reserva no existe o no te pertenece.")
    if current.get("status") == "CONFIRMADA":
        raise ApiError(409, "CONFIRMED_RESERVATION",
                       "Una reserva confirmada por un proveedor real no se puede eliminar desde TripPlanner.")
    db.delete(req.user_id, f"RES#{res_id}")
    return 200, {"deleted": True, "reservation": _out(current)}
