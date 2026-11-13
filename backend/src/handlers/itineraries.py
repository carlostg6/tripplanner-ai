"""Lambdas de itinerarios: CreateItinerary, GetItinerary, UpdateItinerary."""
from common import db
from common.http import ApiError, handler, to_plain
from common.validation import validate_itinerary


def _trip_id(req):
    tid = (req.path or {}).get("tripId") or req.body.get("tripId")
    if not tid:
        raise ApiError(400, "VALIDATION_ERROR", "Falta tripId.")
    return tid


def _body(req):
    return {k: v for k, v in req.body.items() if k != "tripId"}


@handler
def create_itinerary(req):
    trip_id = _trip_id(req)
    trip = db.require_trip(req.user_id, trip_id)
    data = validate_itinerary(_body(req), trip)
    ts = db.now_iso()
    item = {
        "PK": db.user_pk(req.user_id), "SK": f"ITIN#{trip_id}",
        "entityType": "ITINERARY", "tripId": trip_id, "userId": req.user_id,
        "version": 1, "createdAt": ts, "updatedAt": ts, "createdBy": req.source,
        **data,
    }
    db.put_new(item)  # 409 si ya existe -> usar UpdateItinerary
    return 201, {"itinerary": to_plain(db.clean(item))}


@handler
def get_itinerary(req):
    trip_id = _trip_id(req)
    db.require_trip(req.user_id, trip_id)
    item = db.get(req.user_id, f"ITIN#{trip_id}")
    if not item:
        raise ApiError(404, "ITINERARY_NOT_FOUND", "Este viaje aún no tiene itinerario.")
    return 200, {"itinerary": to_plain(db.clean(item))}


@handler
def update_itinerary(req):
    trip_id = _trip_id(req)
    trip = db.require_trip(req.user_id, trip_id)
    current = db.get(req.user_id, f"ITIN#{trip_id}")
    if not current:
        raise ApiError(404, "ITINERARY_NOT_FOUND", "Este viaje aún no tiene itinerario.")
    data = validate_itinerary(_body(req), trip)
    data["version"] = int(current.get("version", 1)) + 1
    item = db.update(req.user_id, f"ITIN#{trip_id}", data)
    return 200, {"itinerary": to_plain(db.clean(item))}
