"""Pruebas del agente sin llamar a Bedrock.

- Tools de negocio → handlers Lambda reales sobre DynamoDB simulado (moto).
- Extracción de resultados MCP para la Agent-Driven UI.
- MCP de clima con respuesta HTTP simulada.
- Protocolo de streaming del entrypoint con un agente falso.
"""
import asyncio
import json
import os
import sys
from datetime import date, timedelta
from types import SimpleNamespace

import boto3
import pytest
from moto import mock_aws

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "..", "backend", "src"))
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ["TABLE_NAME"] = "agent-test"

START = (date.today() + timedelta(days=30)).isoformat()
END = (date.today() + timedelta(days=33)).isoformat()


@pytest.fixture
def wired_tools(monkeypatch):
    """Conecta invoke_lambda directamente con los handlers (sin AWS Lambda)."""
    with mock_aws():
        boto3.client("dynamodb").create_table(
            TableName="agent-test", BillingMode="PAY_PER_REQUEST",
            AttributeDefinitions=[{"AttributeName": n, "AttributeType": "S"} for n in ("PK", "SK", "GSI1PK", "GSI1SK")],
            KeySchema=[{"AttributeName": "PK", "KeyType": "HASH"}, {"AttributeName": "SK", "KeyType": "RANGE"}],
            GlobalSecondaryIndexes=[{"IndexName": "GSI1", "Projection": {"ProjectionType": "ALL"},
                                     "KeySchema": [{"AttributeName": "GSI1PK", "KeyType": "HASH"},
                                                   {"AttributeName": "GSI1SK", "KeyType": "RANGE"}]}])
        import common.db as db
        db._table = None
        from handlers import itineraries, reservations, trips, users
        from tripplanner import business_tools as bt
        routes = {"CreateTrip": trips.create_trip, "GetTrips": trips.get_trips, "UpdateTrip": trips.update_trip,
                  "CreateItinerary": itineraries.create_itinerary, "UpdateItinerary": itineraries.update_itinerary,
                  "CreateReservation": reservations.create_reservation,
                  "GetReservations": reservations.get_reservations,
                  "UpdateReservation": reservations.update_reservation,
                  "DeleteReservation": reservations.delete_reservation,
                  "GetPreferences": users.get_preferences, "SavePreferences": users.put_preferences}

        def fake_invoke(name, user_id, body=None, path=None, query=None):
            r = routes[name]({"source": "agent", "userId": user_id, "body": body or {},
                              "pathParameters": path or {}, "queryStringParameters": query or {}}, None)
            return r["statusCode"], r["body"]

        monkeypatch.setattr(bt, "invoke_lambda", fake_invoke)
        events = []
        tools = {t.tool_name: t for t in bt.make_business_tools("user-1", lambda c, d: events.append((c, d)))}
        yield tools, events, bt


def call(t, **kw):
    return json.loads(t._tool_func(**kw))


def test_business_tools_demo_flow(wired_tools):
    tools, events, bt = wired_tools
    assert len(tools) == 10
    r = call(tools["create_trip"], origin="Bogotá", destination="Cartagena", start_date=START, end_date=END,
             travelers=3, budget=5000000)
    assert r["ok"], r
    trip_id = r["trip"]["tripId"]
    days = [{"day": i + 1, "date": (date.fromisoformat(START) + timedelta(days=i)).isoformat(),
             "activities": [{"time": "10:00", "title": "Playa Blanca", "estimatedCost": 80000}]} for i in range(4)]
    assert call(tools["create_itinerary"], trip_id=trip_id, days=days)["ok"]
    r = call(tools["create_reservation"], trip_id=trip_id, type="FLIGHT", title="BOG-CTG JA1551",
             provider="JetSMART", amount=882000, quantity=3, details={"flightNumber": "JA1551"})
    assert r["ok"] and r["reservation"]["status"] == "SIMULADA"
    r = call(tools["get_trips"], trip_id=trip_id)
    assert len(r["itinerary"]["days"]) == 4 and len(r["reservations"]) == 1
    assert [c for c, _ in events] == ["trip", "itinerary", "reservation", "trip_detail"]
    # errores llegan al modelo como ok=False, sin excepción
    r = call(tools["create_reservation"], trip_id=trip_id, type="HOTEL", title="x", status="CONFIRMADA")
    assert r["ok"] is False and r["status"] == 409
    assert call(tools["save_preferences"], activity_types=["playa"], travel_pace="relajado")["ok"]
    assert bt.load_preferences("user-1")["travelPace"] == "RELAJADO"


def test_extract_tool_results():
    from tripplanner.specialists import extract_tool_results
    msgs = [
        {"role": "assistant", "content": [{"toolUse": {"toolUseId": "a", "name": "search_flights", "input": {}}}]},
        {"role": "user", "content": [{"toolResult": {"toolUseId": "a", "status": "success",
                                                     "content": [{"text": json.dumps({"outbound": [1]})}]}}]},
        {"role": "assistant", "content": [{"toolUse": {"toolUseId": "b", "name": "search_airports", "input": {}}}]},
        {"role": "user", "content": [{"toolResult": {"toolUseId": "b", "content": [{"text": "{}"}]}}]},
    ]
    assert extract_tool_results(msgs, "search_flights") == [{"outbound": [1]}]


def test_weather_server_parsing(monkeypatch):
    sys.path.insert(0, os.path.join(ROOT, "mcp_servers"))
    import weather_server as ws

    class R:
        def __init__(self, d): self.d = d
        def raise_for_status(self): pass
        def json(self): return self.d

    def fake_get(url, params, timeout):
        n = (date.fromisoformat(params["end_date"]) - date.fromisoformat(params["start_date"])).days + 1
        days = [(date.fromisoformat(params["start_date"]) + timedelta(days=i)).isoformat() for i in range(n)]
        daily = {"time": days, "weathercode": [1] * n, "temperature_2m_max": [31.5] * n,
                 "temperature_2m_min": [25.0] * n, "precipitation_sum": [0.0] * n}
        if "precipitation_probability_max" in params["daily"]:
            daily["precipitation_probability_max"] = [20] * n
        return R({"daily": daily})

    monkeypatch.setattr(ws.httpx, "get", fake_get)
    near = (date.today() + timedelta(days=3)).isoformat()
    near_end = (date.today() + timedelta(days=6)).isoformat()
    out = json.loads(ws.get_weather_forecast("Cartagena", near, near_end))
    assert out["location"]["name"] == "Cartagena" and len(out["days"]) == 4
    assert out["days"][0]["rainProbability"] == 20 and out["days"][0]["condition"] == "Mayormente despejado"
    far = json.loads(ws.get_weather_forecast("Cartagena", START, END))
    assert "histórica" in far["source"] and far["days"][0]["date"] == START


def test_streaming_protocol(monkeypatch):
    import main

    class FakeAgent:
        def __init__(self, emit): self.emit = emit
        async def stream_async(self, prompt):
            yield {"current_tool_use": {"toolUseId": "t1", "name": "flight_specialist"}}
            yield {"current_tool_use": {"toolUseId": "t1", "name": "flight_specialist"}}  # dedupe
            self.emit("flights", {"outbound": []})
            yield {"data": "Encontré "}
            yield {"data": "vuelos."}

    monkeypatch.setattr(main, "build_orchestrator", lambda u, s, emit: FakeAgent(emit))
    header = "e30." + __import__("base64").urlsafe_b64encode(b'{"sub":"abc"}').decode().rstrip("=") + ".sig"
    ctx = SimpleNamespace(session_id="s" * 40, request_headers={"Authorization": f"Bearer {header}"})

    async def collect():
        return [e async for e in main.invoke({"prompt": "hola"}, ctx)]

    events = asyncio.run(collect())
    types = [e["type"] for e in events]
    assert types == ["start", "status", "ui", "text", "text", "done"], types
    assert events[2]["component"] == "flights"

    ctx_noauth = SimpleNamespace(session_id="x", request_headers={})
    async def collect2():
        return [e async for e in main.invoke({"prompt": "hola"}, ctx_noauth)]
    assert asyncio.run(collect2())[0]["type"] == "error"


def test_update_and_delete_reservation_tools(wired_tools):
    tools, events, _ = wired_tools
    trip_id = call(tools["create_trip"], origin="Bogotá", destination="Cartagena", start_date=START,
                   end_date=END, travelers=3)["trip"]["tripId"]
    rid = call(tools["create_reservation"], trip_id=trip_id, type="HOTEL", title="Hotel Centro")["reservation"]["reservationId"]
    r = call(tools["update_reservation"], reservation_id=rid, provider="Hotel Charleston", amount=900000, status="PENDIENTE")
    assert r["ok"] and r["reservation"]["provider"] == "Hotel Charleston" and r["reservation"]["status"] == "PENDIENTE"
    r = call(tools["delete_reservation"], reservation_id=rid)
    assert r["ok"] and r["deleted"] and events[-1][0] == "reservation_deleted"
    assert call(tools["get_reservations"])["count"] == 0
    assert call(tools["delete_reservation"], reservation_id=rid)["status"] == 404
