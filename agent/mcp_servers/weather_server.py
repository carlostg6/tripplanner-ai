"""MCP de clima (stdio) basado en Open-Meteo (gratuito, sin API key).

Tools:
  - get_weather_forecast(city, start_date, end_date): pronóstico diario por fechas.
    Si las fechas superan el horizonte del pronóstico (16 días), devuelve una
    referencia histórica (mismas fechas del año anterior) indicándolo en `source`.
"""
import json
import os
import sys
from datetime import date, timedelta

import httpx

sys.path.insert(0, os.path.dirname(__file__))
from _compat import Server  # noqa: E402

mcp = Server("tripplanner-weather")

GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_HORIZON_DAYS = 15
TIMEOUT = httpx.Timeout(10.0)

# Respaldo local para ciudades frecuentes (evita depender del geocoding).
KNOWN_CITIES = {
    "bogota": ("Bogotá", "Colombia", 4.711, -74.0721),
    "cartagena": ("Cartagena", "Colombia", 10.391, -75.4794),
    "medellin": ("Medellín", "Colombia", 6.2442, -75.5812),
    "cali": ("Cali", "Colombia", 3.4516, -76.532),
    "barranquilla": ("Barranquilla", "Colombia", 10.9685, -74.7813),
    "santa marta": ("Santa Marta", "Colombia", 11.2408, -74.199),
    "san andres": ("San Andrés", "Colombia", 12.5847, -81.7006),
    "pereira": ("Pereira", "Colombia", 4.8133, -75.6961),
    "bucaramanga": ("Bucaramanga", "Colombia", 7.1193, -73.1227),
    "leticia": ("Leticia", "Colombia", -4.2153, -69.9406),
    "miami": ("Miami", "Estados Unidos", 25.7617, -80.1918),
    "madrid": ("Madrid", "España", 40.4168, -3.7038),
    "cancun": ("Cancún", "México", 21.1619, -86.8515),
    "lima": ("Lima", "Perú", -12.0464, -77.0428),
}

# Códigos WMO -> descripción en español + ícono
WMO = {
    0: ("Despejado", "☀️"), 1: ("Mayormente despejado", "🌤️"), 2: ("Parcialmente nublado", "⛅"),
    3: ("Nublado", "☁️"), 45: ("Niebla", "🌫️"), 48: ("Niebla con escarcha", "🌫️"),
    51: ("Llovizna ligera", "🌦️"), 53: ("Llovizna", "🌦️"), 55: ("Llovizna intensa", "🌧️"),
    61: ("Lluvia ligera", "🌦️"), 63: ("Lluvia moderada", "🌧️"), 65: ("Lluvia fuerte", "🌧️"),
    80: ("Chubascos ligeros", "🌦️"), 81: ("Chubascos", "🌧️"), 82: ("Chubascos fuertes", "⛈️"),
    95: ("Tormenta eléctrica", "⛈️"), 96: ("Tormenta con granizo", "⛈️"), 99: ("Tormenta fuerte con granizo", "⛈️"),
}


def _norm(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFD", s.lower().strip())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def geocode(city: str):
    key = _norm(city).split(",")[0].strip()
    if key in KNOWN_CITIES:
        name, country, lat, lon = KNOWN_CITIES[key]
        return {"name": name, "country": country, "latitude": lat, "longitude": lon}
    r = httpx.get(GEO_URL, params={"name": city, "count": 1, "language": "es"}, timeout=TIMEOUT)
    r.raise_for_status()
    results = r.json().get("results") or []
    if not results:
        return None
    g = results[0]
    return {"name": g["name"], "country": g.get("country", ""), "latitude": g["latitude"], "longitude": g["longitude"]}


def _daily(url, lat, lon, start, end, with_prob=True):
    daily = ["weathercode", "temperature_2m_max", "temperature_2m_min", "precipitation_sum"]
    if with_prob:
        daily.append("precipitation_probability_max")
    r = httpx.get(url, params={
        "latitude": lat, "longitude": lon, "daily": ",".join(daily), "timezone": "auto",
        "start_date": start.isoformat(), "end_date": end.isoformat()}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()["daily"]


def build_days(d: dict, shift_years=0):
    days = []
    for i, day in enumerate(d["time"]):
        code = d["weathercode"][i]
        desc, icon = WMO.get(code, ("Variable", "🌡️"))
        dt = date.fromisoformat(day)
        if shift_years:
            dt = dt.replace(year=dt.year + shift_years)
        probs = d.get("precipitation_probability_max")
        days.append({
            "date": dt.isoformat(),
            "condition": desc, "icon": icon, "weatherCode": code,
            "tempMax": d["temperature_2m_max"][i], "tempMin": d["temperature_2m_min"][i],
            "precipitationMm": d["precipitation_sum"][i],
            "rainProbability": probs[i] if probs else None,
        })
    return days


@mcp.tool()
def get_weather_forecast(city: str, start_date: str = "", end_date: str = "") -> str:
    """Pronóstico del clima por día para una ciudad y rango de fechas (AAAA-MM-DD).

    Devuelve JSON con temperatura máxima/mínima (°C), condición, precipitación (mm)
    y probabilidad de lluvia (%) cuando está disponible. Si no se envían fechas,
    devuelve los próximos 5 días.
    """
    try:
        today = date.today()
        start = date.fromisoformat(start_date) if start_date else today
        end = date.fromisoformat(end_date) if end_date else start + timedelta(days=4)
        if end < start:
            start, end = end, start
        end = min(end, start + timedelta(days=15))
        loc = geocode(city)
        if not loc:
            return json.dumps({"error": f"No se encontró la ciudad '{city}'."}, ensure_ascii=False)

        horizon = today + timedelta(days=FORECAST_HORIZON_DAYS)
        if start <= horizon:
            d = _daily(FORECAST_URL, loc["latitude"], loc["longitude"], max(start, today), min(end, horizon))
            days, source = build_days(d), "Open-Meteo · pronóstico"
            note = None if end <= horizon else "Parte del rango supera el horizonte del pronóstico (16 días)."
        else:
            # Referencia histórica: mismas fechas del año anterior
            ps, pe = start.replace(year=start.year - 1), end.replace(year=end.year - 1)
            d = _daily(ARCHIVE_URL, loc["latitude"], loc["longitude"], ps, pe, with_prob=False)
            days, source = build_days(d, shift_years=1), "Open-Meteo · referencia histórica (año anterior)"
            note = "Las fechas están fuera del horizonte de pronóstico; se muestran valores históricos como referencia."

        temps = [x["tempMax"] for x in days if x["tempMax"] is not None]
        probs = [x["rainProbability"] for x in days if x["rainProbability"] is not None]
        return json.dumps({
            "location": loc, "startDate": start.isoformat(), "endDate": end.isoformat(),
            "source": source, "note": note, "days": days,
            "summary": {
                "avgTempMax": round(sum(temps) / len(temps), 1) if temps else None,
                "maxRainProbability": max(probs) if probs else None,
                "rainyDays": sum(1 for x in days if (x["precipitationMm"] or 0) >= 1),
            },
        }, ensure_ascii=False)
    except ValueError:
        return json.dumps({"error": "Fechas inválidas, usa AAAA-MM-DD."}, ensure_ascii=False)
    except httpx.HTTPError as e:
        return json.dumps({"error": f"El servicio de clima no respondió: {type(e).__name__}"}, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run(transport="stdio")
