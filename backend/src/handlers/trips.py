"""Lambdas de viajes: CreateTrip, GetTrips, UpdateTrip."""
from common import db
from common.http import ApiError, handler, to_plain
from common.validation import validate_trip


def _trip_out(item):
    return to_plain(db.clean(item))


@handler
def create_trip(req):
    data = validate_trip(req.body)
    trip_id = db.new_id("trip")
    ts = db.now_iso()
    if not data.get("title"):
        data["title"] = f"Viaje a {data['destination']}"
    item = {
        "PK": db.user_pk(req.user_id), "SK": f"TRIP#{trip_id}",
        "entityType": "TRIP", "tripId": trip_id, "userId": req.user_id,
        "status": "PLANEADO", "createdAt": ts, "updatedAt": ts, "createdBy": req.source,
        **data,
    }
    db.put_new(item)
    return 201, {"trip": _trip_out(item)}


@handler
def get_trips(req):
    """Sin tripId: lista de viajes. Con tripId: detalle con itinerario y reservas."""
    trip_id = (req.path or {}).get("tripId") or (req.query or {}).get("tripId") or req.body.get("tripId")
    if trip_id:
        trip = db.require_trip(req.user_id, trip_id)
        itin = db.get(req.user_id, f"ITIN#{trip_id}")
        reservations = [r for r in db.query_trip_reservations(trip_id) if r.get("userId") == req.user_id]
        return 200, {
            "trip": _trip_out(trip),
            "itinerary": to_plain(db.clean(itin)) if itin else None,
            "reservations": [to_plain(db.clean(r)) for r in reservations],
        }
    status = (req.query or {}).get("status") or req.body.get("status")
    trips = db.query_prefix(req.user_id, "TRIP#")
    if status:
        trips = [t for t in trips if t.get("status") == status.upper()]
    trips.sort(key=lambda t: t.get("startDate", ""))
    return 200, {"trips": [_trip_out(t) for t in trips], "count": len(trips)}


@handler
def update_trip(req):
    trip_id = (req.path or {}).get("tripId") or req.body.get("tripId")
    if not trip_id:
        raise ApiError(400, "VALIDATION_ERROR", "Falta tripId.")
    body = {k: v for k, v in req.body.items() if k != "tripId"}
    data = validate_trip(body, partial=True)
    current = db.require_trip(req.user_id, trip_id)
    start = data.get("startDate", current.get("startDate"))
    end = data.get("endDate", current.get("endDate"))
    if start and end and end < start:
        raise ApiError(400, "VALIDATION_ERROR", "La fecha de regreso debe ser posterior a la salida.")
    item = db.update(req.user_id, f"TRIP#{trip_id}", data)
    return 200, {"trip": _trip_out(item)}
