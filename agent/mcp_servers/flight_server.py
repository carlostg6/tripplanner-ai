"""MCP de vuelos (stdio).

Proveedor real: Google Flights vía SerpAPI (https://serpapi.com/google-flights-api),
activo cuando existe la variable de entorno SERPAPI_KEY. Se hace una búsqueda de
solo ida por trayecto (ida y, si aplica, regreso) y se normaliza al mismo JSON
que consume la UI. Los resultados se guardan en caché 30 min para ahorrar cuota.

Respaldo: si no hay clave, SerpAPI falla o no devuelve vuelos, se generan ofertas
*simuladas pero realistas y deterministas* (distancia real entre aeropuertos,
antelación, día de la semana y aerolíneas de cada mercado). El campo `simulated`
y `source` le indican a la UI cuál fuente se usó.

Tools:
  - search_airports(query)
  - search_flights(origin, destination, departure_date, return_date, passengers, max_results)
"""
import hashlib
import json
import math
import os
import random
import sys
import time
import unicodedata
from datetime import date, datetime, timedelta

import httpx

sys.path.insert(0, os.path.dirname(__file__))
from _compat import Server  # noqa: E402

mcp = Server("tripplanner-flights")

AIRPORTS = {
    "BOG": ("Bogotá", "Aeropuerto El Dorado", "CO", 4.7016, -74.1469, ["bogota", "bogotá"]),
    "CTG": ("Cartagena", "Aeropuerto Rafael Núñez", "CO", 10.4424, -75.513, ["cartagena"]),
    "MDE": ("Medellín", "Aeropuerto José María Córdova", "CO", 6.1645, -75.4231, ["medellin", "medellín", "rionegro"]),
    "CLO": ("Cali", "Aeropuerto Alfonso Bonilla Aragón", "CO", 3.5432, -76.3816, ["cali"]),
    "BAQ": ("Barranquilla", "Aeropuerto Ernesto Cortissoz", "CO", 10.8896, -74.7808, ["barranquilla"]),
    "SMR": ("Santa Marta", "Aeropuerto Simón Bolívar", "CO", 11.1196, -74.2306, ["santa marta"]),
    "ADZ": ("San Andrés", "Aeropuerto Gustavo Rojas Pinilla", "CO", 12.5836, -81.7112, ["san andres", "san andrés"]),
    "PEI": ("Pereira", "Aeropuerto Matecaña", "CO", 4.8127, -75.7395, ["pereira"]),
    "BGA": ("Bucaramanga", "Aeropuerto Palonegro", "CO", 7.1265, -73.1848, ["bucaramanga"]),
    "LET": ("Leticia", "Aeropuerto Alfredo Vásquez Cobo", "CO", -4.1935, -69.9432, ["leticia"]),
    "MIA": ("Miami", "Miami International", "US", 25.7959, -80.287, ["miami"]),
    "MAD": ("Madrid", "Adolfo Suárez Madrid-Barajas", "ES", 40.4983, -3.5676, ["madrid"]),
    "CUN": ("Cancún", "Aeropuerto Internacional de Cancún", "MX", 21.0365, -86.8771, ["cancun", "cancún"]),
    "LIM": ("Lima", "Aeropuerto Jorge Chávez", "PE", -12.0219, -77.1143, ["lima"]),
    "PTY": ("Ciudad de Panamá", "Aeropuerto de Tocumen", "PA", 9.0714, -79.3835, ["panama", "panamá"]),
}

DOMESTIC = [("Avianca", "AV"), ("LATAM", "LA"), ("JetSMART", "JA"), ("Wingo", "P5"), ("Clic", "VE")]
INTERNATIONAL = [("Avianca", "AV"), ("LATAM", "LA"), ("Copa Airlines", "CM"), ("American Airlines", "AA"),
                 ("Iberia", "IB"), ("Wingo", "P5")]
LOW_COST = {"JetSMART", "Wingo"}
CABIN_BAGGAGE = {"JetSMART": "Solo artículo personal", "Wingo": "Solo artículo personal"}


def _norm(s):
    s = unicodedata.normalize("NFD", (s or "").lower().strip())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def resolve_airport(q: str):
    q = (q or "").strip()
    if q.upper() in AIRPORTS:
        return q.upper()
    n = _norm(q).split(",")[0].strip()
    for code, a in AIRPORTS.items():
        if n == _norm(a[0]) or n in [_norm(x) for x in a[5]]:
            return code
    return None


def _distance_km(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, [AIRPORTS[a][3], AIRPORTS[a][4], AIRPORTS[b][3], AIRPORTS[b][4]])
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def _rng(*parts):
    seed = int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:12], 16)
    return random.Random(seed)


def _offers_for_leg(orig, dest, d: date, passengers: int, max_results: int):
    dist = _distance_km(orig, dest)
    domestic = AIRPORTS[orig][2] == AIRPORTS[dest][2] == "CO"
    airlines = DOMESTIC if domestic else INTERNATIONAL
    rng = _rng(orig, dest, d.isoformat())
    duration_min = int(dist / 720 * 60 + 35)
    advance = max((d - date.today()).days, 0)
    advance_factor = 1.6 if advance < 7 else 1.25 if advance < 21 else 1.0 if advance < 60 else 0.9
    weekday_factor = 1.15 if d.weekday() in (4, 6) else 0.95 if d.weekday() in (1, 2) else 1.0
    base_cop = (95000 + dist * 310) if domestic else (450000 + dist * 420)

    offers = []
    slots = sorted(rng.sample(range(5 * 60, 22 * 60, 25), k=min(max_results + 3, 20)))
    for i, start_min in enumerate(slots[:max_results + 3]):
        name, code = airlines[rng.randrange(len(airlines))]
        stops = 0 if domestic or dist < 2500 else rng.choice([0, 0, 1])
        dur = duration_min + (stops * rng.randint(70, 160)) + rng.randint(-5, 15)
        low = name in LOW_COST
        price_pp = base_cop * advance_factor * weekday_factor * (0.72 if low else 1.0) * rng.uniform(0.85, 1.3)
        if 6 * 60 <= start_min <= 9 * 60 or 17 * 60 <= start_min <= 19 * 60:
            price_pp *= 1.1  # horas pico
        price_pp = int(round(price_pp / 1000) * 1000)
        dep = datetime.combine(d, datetime.min.time()) + timedelta(minutes=start_min)
        arr = dep + timedelta(minutes=dur)
        offers.append({
            "offerId": f"{code}{rng.randint(1000, 9899)}-{d.strftime('%m%d')}",
            "airline": name, "airlineCode": code,
            "flightNumber": f"{code}{rng.randint(100, 9899)}",
            "origin": orig, "destination": dest,
            "departureTime": dep.isoformat(timespec="minutes"),
            "arrivalTime": arr.isoformat(timespec="minutes"),
            "durationMinutes": dur, "stops": stops,
            "cabin": "Económica",
            "baggage": CABIN_BAGGAGE.get(name, "Equipaje de mano 10 kg"),
            "pricePerPerson": price_pp, "totalPrice": price_pp * passengers,
            "currency": "COP", "seatsLeft": rng.randint(2, 9),
        })
    # Quitar duplicados de aerolínea+hora y limitar
    seen, unique = set(), []
    for o in offers:
        k = (o["airline"], o["departureTime"])
        if k not in seen:
            seen.add(k)
            unique.append(o)
    unique = unique[:max_results]
    if unique:
        cheapest = min(unique, key=lambda o: o["pricePerPerson"])
        fastest = min(unique, key=lambda o: o["durationMinutes"])
        cheapest.setdefault("tags", []).append("Más económico")
        fastest.setdefault("tags", []).append("Más rápido")
    return sorted(unique, key=lambda o: o["departureTime"])


SERPAPI_URL = "https://serpapi.com/search.json"
_CACHE: dict = {}
_CACHE_TTL = 1800


def _serpapi_key() -> str:
    return os.environ.get("SERPAPI_KEY", "").strip()


def _real_leg(orig: str, dest: str, d: date, passengers: int, max_results: int):
    """Busca un trayecto de solo ida en Google Flights (SerpAPI). Devuelve lista de ofertas o lanza excepción."""
    key = (orig, dest, d.isoformat(), passengers)
    hit = _CACHE.get(key)
    if hit and time.time() - hit[0] < _CACHE_TTL:
        return hit[1][:max_results]
    r = httpx.get(SERPAPI_URL, timeout=httpx.Timeout(30.0), params={
        "engine": "google_flights", "departure_id": orig, "arrival_id": dest,
        "outbound_date": d.isoformat(), "type": "2", "adults": passengers,
        "currency": "COP", "hl": "es", "gl": "co", "api_key": _serpapi_key(),
    })
    r.raise_for_status()
    data = r.json()
    if data.get("error"):
        raise RuntimeError(f"SerpAPI: {data['error']}")
    raw = (data.get("best_flights") or []) + (data.get("other_flights") or [])
    # Google Flights muestra el precio total para todos los pasajeros de la búsqueda.
    price_is_total = os.environ.get("SERPAPI_PRICE_IS_TOTAL", "true").lower() == "true"
    offers = []
    for f in raw:
        segs = f.get("flights") or []
        if not segs or not isinstance(f.get("price"), (int, float)):
            continue
        first, last = segs[0], segs[-1]
        fn = (first.get("flight_number") or "").replace(" ", "")
        code = "".join(ch for ch in fn[:2] if ch.isalnum()).upper() or "XX"
        total = int(f["price"]) if price_is_total else int(f["price"]) * passengers
        per = int(round(total / passengers, -2))
        offers.append({
            "offerId": f"{fn or code}-{d.strftime('%m%d')}-{len(offers)}",
            "airline": first.get("airline") or "Aerolínea",
            "airlineCode": code,
            "airlineLogo": first.get("airline_logo") or f.get("airline_logo"),
            "flightNumber": fn or code,
            "origin": (first.get("departure_airport") or {}).get("id", orig),
            "destination": (last.get("arrival_airport") or {}).get("id", dest),
            "departureTime": ((first.get("departure_airport") or {}).get("time") or "").replace(" ", "T"),
            "arrivalTime": ((last.get("arrival_airport") or {}).get("time") or "").replace(" ", "T"),
            "durationMinutes": int(f.get("total_duration") or sum(x.get("duration", 0) for x in segs)),
            "stops": len(f.get("layovers") or []),
            "cabin": first.get("travel_class") or "Económica",
            "baggage": "Ver condiciones de la aerolínea",
            "pricePerPerson": per, "totalPrice": total, "currency": "COP",
        })
    if not offers:
        raise RuntimeError("Google Flights no devolvió vuelos para esa ruta/fecha")
    offers.sort(key=lambda o: o["departureTime"])
    _CACHE[key] = (time.time(), offers)
    return offers[:max_results]


def _tag(offers):
    if offers:
        min(offers, key=lambda o: o["totalPrice"]).setdefault("tags", []).append("Más económico")
        min(offers, key=lambda o: o["durationMinutes"]).setdefault("tags", []).append("Más rápido")
    return offers


@mcp.tool()
def search_airports(query: str) -> str:
    """Busca el código IATA de un aeropuerto a partir del nombre de la ciudad."""
    code = resolve_airport(query)
    if not code:
        return json.dumps({"results": [], "message": f"No se encontró aeropuerto para '{query}'."}, ensure_ascii=False)
    a = AIRPORTS[code]
    return json.dumps({"results": [{"iata": code, "city": a[0], "airport": a[1], "country": a[2]}]}, ensure_ascii=False)


@mcp.tool()
def search_flights(origin: str, destination: str, departure_date: str, return_date: str = "",
                   passengers: int = 1, max_results: int = 5) -> str:
    """Busca vuelos entre dos ciudades o códigos IATA (Google Flights real si hay SERPAPI_KEY).

    Args:
        origin: ciudad o código IATA de origen (ej. "Bogotá" o "BOG").
        destination: ciudad o código IATA de destino.
        departure_date: fecha de ida AAAA-MM-DD.
        return_date: fecha de regreso AAAA-MM-DD (opcional).
        passengers: número de pasajeros (1-9).
        max_results: máximo de ofertas por trayecto (1-8).
    Devuelve JSON con ofertas de ida (outbound) y regreso (inbound): aerolínea, número
    de vuelo, horarios, duración, escalas, precio por persona y total en COP.
    """
    o, d = resolve_airport(origin), resolve_airport(destination)
    if not o or not d:
        missing = origin if not o else destination
        return json.dumps({"error": f"No hay aeropuerto disponible para '{missing}'.",
                           "available": sorted(AIRPORTS)}, ensure_ascii=False)
    if o == d:
        return json.dumps({"error": "El origen y el destino son iguales."}, ensure_ascii=False)
    try:
        dep = date.fromisoformat(departure_date)
        ret = date.fromisoformat(return_date) if return_date else None
    except ValueError:
        return json.dumps({"error": "Fechas inválidas, usa AAAA-MM-DD."}, ensure_ascii=False)
    if dep < date.today():
        return json.dumps({"error": "La fecha de salida ya pasó."}, ensure_ascii=False)
    if ret and ret < dep:
        return json.dumps({"error": "La fecha de regreso es anterior a la salida."}, ensure_ascii=False)
    passengers = max(1, min(int(passengers or 1), 9))
    max_results = max(1, min(int(max_results or 5), 8))

    source, simulated, note = "simulado · TripPlanner Flight MCP", True, None
    outbound = inbound = None
    if _serpapi_key():
        try:
            outbound = _tag(_real_leg(o, d, dep, passengers, max_results))
            inbound = _tag(_real_leg(d, o, ret, passengers, max_results)) if ret else []
            source, simulated = "Google Flights (vía SerpAPI)", False
        except Exception as e:  # noqa: BLE001 — la demo nunca se cae: se usan datos simulados
            print(f"[flight_mcp] SerpAPI no disponible: {type(e).__name__}: {e}", file=sys.stderr)
            note = "Google Flights no respondió; se muestran datos simulados."
            outbound = inbound = None
    if outbound is None:
        outbound = _offers_for_leg(o, d, dep, passengers, max_results)
        inbound = _offers_for_leg(d, o, ret, passengers, max_results) if ret else []

    result = {
        "source": source,
        "simulated": simulated,
        "note": note,
        "origin": {"iata": o, "city": AIRPORTS[o][0]},
        "destination": {"iata": d, "city": AIRPORTS[d][0]},
        "departureDate": dep.isoformat(), "returnDate": ret.isoformat() if ret else None,
        "passengers": passengers, "currency": "COP",
        "outbound": outbound,
        "inbound": inbound,
    }
    if result["outbound"]:
        best_out = min(result["outbound"], key=lambda x: x["totalPrice"])["totalPrice"]
        best_in = min(result["inbound"], key=lambda x: x["totalPrice"])["totalPrice"] if result["inbound"] else 0
        result["cheapestRoundTripTotal"] = best_out + best_in
    return json.dumps(result, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run(transport="stdio")
