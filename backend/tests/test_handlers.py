"""Pruebas de las Lambdas con DynamoDB simulado (moto).

Ejecutar:  cd backend && pip install -r requirements-dev.txt && pytest -q
"""
import json
import os
import sys
from datetime import date, timedelta

import boto3
import pytest
from moto import mock_aws

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ["TABLE_NAME"] = "test-table"

USER_A, USER_B = "user-aaa", "user-bbb"
START = (date.today() + timedelta(days=30)).isoformat()
END = (date.today() + timedelta(days=33)).isoformat()


def api_event(user, body=None, path=None, query=None):
    return {
        "requestContext": {"http": {"method": "POST"},
                           "authorizer": {"jwt": {"claims": {"sub": user, "email": f"{user}@x.co"}}}},
        "body": json.dumps(body) if body is not None else None,
        "pathParameters": path, "queryStringParameters": query,
    }


def agent_event(user, body=None, path=None):
    return {"source": "agent", "userId": user, "body": body or {}, "pathParameters": path}


def call(fn, event):
    r = fn(event, None)
    body = r["body"] if isinstance(r["body"], dict) else json.loads(r["body"])
    return r["statusCode"], body


@pytest.fixture
def h():
    with mock_aws():
        boto3.client("dynamodb").create_table(
            TableName="test-table", BillingMode="PAY_PER_REQUEST",
            AttributeDefinitions=[{"AttributeName": n, "AttributeType": "S"} for n in ("PK", "SK", "GSI1PK", "GSI1SK")],
            KeySchema=[{"AttributeName": "PK", "KeyType": "HASH"}, {"AttributeName": "SK", "KeyType": "RANGE"}],
            GlobalSecondaryIndexes=[{"IndexName": "GSI1", "Projection": {"ProjectionType": "ALL"},
                                     "KeySchema": [{"AttributeName": "GSI1PK", "KeyType": "HASH"},
                                                   {"AttributeName": "GSI1SK", "KeyType": "RANGE"}]}])
        import common.db as db
        db._table = None
        from handlers import itineraries, reservations, trips, users
        yield type("H", (), {"t": trips, "i": itineraries, "r": reservations, "u": users})


def new_trip(h, user=USER_A, via="api"):
    body = {"origin": "Bogotá", "destination": "Cartagena", "startDate": START, "endDate": END,
            "travelers": 3, "budget": 5000000, "currency": "COP", "interests": ["playa", "historia"]}
    ev = api_event(user, body) if via == "api" else agent_event(user, body)
    s, b = call(h.t.create_trip, ev)
    assert s == 201, b
    return b["trip"]


def test_full_demo_flow(h):
    trip = new_trip(h, via="agent")
    assert trip["title"] == "Viaje a Cartagena" and trip["status"] == "PLANEADO"

    days = [{"day": i + 1, "date": (date.fromisoformat(START) + timedelta(days=i)).isoformat(),
             "title": f"Día {i+1}", "activities": [{"time": "09:00", "title": "Ciudad amurallada", "estimatedCost": 50000}]}
            for i in range(4)]
    s, b = call(h.i.create_itinerary, agent_event(USER_A, {"tripId": trip["tripId"], "days": days}))
    assert s == 201, b
    s, b = call(h.i.create_itinerary, agent_event(USER_A, {"tripId": trip["tripId"], "days": days}))
    assert s == 409  # ya existe -> UpdateItinerary

    days[0]["activities"].append({"time": "15:00", "title": "Islas del Rosario"})
    s, b = call(h.i.update_itinerary, api_event(USER_A, {"days": days}, path={"tripId": trip["tripId"]}))
    assert s == 200 and b["itinerary"]["version"] == 2

    s, b = call(h.r.create_reservation, agent_event(USER_A, {
        "tripId": trip["tripId"], "type": "FLIGHT", "title": "BOG-CTG Avianca AV9520",
        "amount": 1350000, "quantity": 3, "details": {"flightNumber": "AV9520"}}))
    assert s == 201, b
    res = b["reservation"]
    assert res["status"] == "SIMULADA" and res["confirmationCode"].startswith("SIM-")

    # "El usuario vuelve a ingresar y recupera sus datos"
    s, b = call(h.t.get_trips, api_event(USER_A, path={"tripId": trip["tripId"]}))
    assert s == 200 and len(b["itinerary"]["days"]) == 4 and len(b["reservations"]) == 1
    s, b = call(h.t.get_trips, api_event(USER_A))
    assert b["count"] == 1
    s, b = call(h.r.get_reservations, api_event(USER_A, query={"tripId": trip["tripId"]}))
    assert b["count"] == 1


def test_user_isolation(h):
    trip = new_trip(h, USER_A)
    s, _ = call(h.t.get_trips, api_event(USER_B, path={"tripId": trip["tripId"]}))
    assert s == 404
    s, _ = call(h.t.update_trip, api_event(USER_B, {"budget": 1}, path={"tripId": trip["tripId"]}))
    assert s == 404
    s, _ = call(h.r.create_reservation, api_event(USER_B, {"tripId": trip["tripId"], "type": "HOTEL", "title": "x"}))
    assert s == 404
    s, b = call(h.t.get_trips, api_event(USER_B))
    assert b["count"] == 0


def test_validations(h):
    s, b = call(h.t.create_trip, api_event(USER_A, {"origin": "Bogotá"}))
    assert s == 400 and b["error"]["code"] == "VALIDATION_ERROR"
    fields = {e["field"] for e in b["error"]["details"]}
    assert {"destination", "startDate", "endDate", "travelers"} <= fields
    s, b = call(h.t.create_trip, api_event(USER_A, {"origin": "B", "destination": "C", "startDate": END,
                                                     "endDate": START, "travelers": 2}))
    assert s == 400
    s, b = call(h.t.create_trip, api_event(USER_A, {"origin": "B", "destination": "C", "startDate": START,
                                                     "endDate": END, "travelers": 50}))
    assert s == 400
    ev = api_event(USER_A)
    ev["body"] = "{no json"
    s, b = call(h.t.create_trip, ev)
    assert s == 400 and b["error"]["code"] == "INVALID_JSON"


def test_payment_data_rejected(h):
    trip = new_trip(h)
    s, b = call(h.r.create_reservation, api_event(USER_A, {
        "tripId": trip["tripId"], "type": "HOTEL", "title": "Hotel", "cardNumber": "4111111111111111"}))
    assert s == 400 and b["error"]["code"] == "PAYMENT_DATA_FORBIDDEN"
    s, b = call(h.r.create_reservation, api_event(USER_A, {
        "tripId": trip["tripId"], "type": "HOTEL", "title": "Hotel", "notes": "pagar con 4111 1111 1111 1111"}))
    assert s == 400 and b["error"]["code"] == "PAYMENT_DATA_FORBIDDEN"


def test_reservation_states(h):
    trip = new_trip(h)
    s, b = call(h.r.create_reservation, api_event(USER_A, {"tripId": trip["tripId"], "type": "ACTIVITY",
                                                            "title": "Tour", "status": "PENDIENTE"}))
    rid = b["reservation"]["reservationId"]
    s, b = call(h.r.update_reservation, api_event(USER_A, {"status": "CONFIRMADA"}, path={"reservationId": rid}))
    assert s == 409 and b["error"]["code"] == "CONFIRMATION_REQUIRES_PROVIDER"
    s, b = call(h.r.update_reservation, api_event(USER_A, {"status": "SIMULADA", "amount": 120000},
                                                  path={"reservationId": rid}))
    assert s == 200 and b["reservation"]["status"] == "SIMULADA" and len(b["reservation"]["statusHistory"]) == 2
    s, b = call(h.r.update_reservation, api_event(USER_A, {"status": "INVENTADO"}, path={"reservationId": rid}))
    assert s == 400
    # asociar a otro viaje
    trip2 = new_trip(h)
    s, b = call(h.r.update_reservation, api_event(USER_A, {"tripId": trip2["tripId"]}, path={"reservationId": rid}))
    assert s == 200 and b["reservation"]["tripId"] == trip2["tripId"]
    s, b = call(h.r.get_reservations, api_event(USER_A, query={"tripId": trip2["tripId"]}))
    assert b["count"] == 1


def test_preferences_and_profile(h):
    s, b = call(h.u.get_preferences, api_event(USER_A))
    assert s == 200 and b["preferences"] == {}
    s, b = call(h.u.put_preferences, agent_event(USER_A, {"activityTypes": ["playa"], "travelPace": "relajado"}))
    assert s == 200 and b["preferences"]["travelPace"] == "RELAJADO"
    s, b = call(h.u.get_profile, api_event(USER_A))
    assert s == 200 and b["profile"]["email"] == f"{USER_A}@x.co"
    ev = {"request": {"userAttributes": {"sub": USER_B, "email": "b@x.co"}}}
    assert h.u.post_confirmation(ev, None) == ev


def test_unauthenticated(h):
    ev = {"requestContext": {"http": {"method": "GET"}}, "body": None}
    s, _ = call(h.t.get_trips, ev)
    assert s == 401
    s, _ = call(h.t.get_trips, {"foo": "bar"})
    assert s == 400


def test_delete_reservation(h):
    trip = new_trip(h)
    s, b = call(h.r.create_reservation, agent_event(USER_A, {"tripId": trip["tripId"], "type": "FLIGHT", "title": "Vuelo"}))
    rid = b["reservation"]["reservationId"]
    # otro usuario no puede borrarla
    s, _ = call(h.r.delete_reservation, api_event(USER_B, path={"reservationId": rid}))
    assert s == 404
    s, b = call(h.r.delete_reservation, agent_event(USER_A, {"reservationId": rid}))
    assert s == 200 and b["deleted"] and b["reservation"]["reservationId"] == rid
    s, b = call(h.r.get_reservations, api_event(USER_A, query={"tripId": trip["tripId"]}))
    assert b["count"] == 0
    s, _ = call(h.r.delete_reservation, api_event(USER_A, path={"reservationId": rid}))
    assert s == 404
