/**
 * SOLO DESARROLLO (VITE_MOCK=true): reproduce el protocolo de eventos del
 * Orchestrator para trabajar la UI sin AgentCore. No reemplaza a los agentes.
 */
import { mockApi } from "./mockBackend";

const sleep = (ms, signal) =>
  new Promise((r, j) => {
    const t = setTimeout(r, ms);
    signal?.addEventListener("abort", () => { clearTimeout(t); j(Object.assign(new Error(), { name: "AbortError" })); });
  });

const addDays = (d, n) => { const x = new Date(d + "T00:00:00"); x.setDate(x.getDate() + n); return x.toISOString().slice(0, 10); };

function flights(dep, ret, pax) {
  const leg = (o, d, date, seed) =>
    [["Avianca", "AV", 7, 0, 412000], ["LATAM", "LA", 9, 30, 389000], ["JetSMART", "JA", 12, 5, 294000],
     ["Wingo", "P5", 15, 40, 301000], ["Avianca", "AV", 18, 15, 455000]].map(([a, c, h, m, p], i) => {
      const depT = `${date}T${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
      const arr = new Date(new Date(depT).getTime() + (88 + i * 3) * 60000);
      const pp = p + seed * 7000;
      return { offerId: `${c}${seed}${i}`, airline: a, airlineCode: c, flightNumber: `${c}${9500 + i * 7 + seed}`, origin: o, destination: d,
        departureTime: depT, arrivalTime: arr.toISOString().slice(0, 16), durationMinutes: 88 + i * 3, stops: 0,
        cabin: "Económica", baggage: c === "JA" || c === "P5" ? "Solo artículo personal" : "Equipaje de mano 10 kg",
        pricePerPerson: pp, totalPrice: pp * pax, currency: "COP", seatsLeft: 3 + i,
        tags: i === 2 ? ["Más económico"] : i === 0 ? ["Más rápido"] : undefined };
    });
  return { source: "simulado · TripPlanner Flight MCP", simulated: true, origin: { iata: "BOG", city: "Bogotá" },
    destination: { iata: "CTG", city: "Cartagena" }, departureDate: dep, returnDate: ret, passengers: pax, currency: "COP",
    outbound: leg("BOG", "CTG", dep, 0), inbound: leg("CTG", "BOG", ret, 1) };
}

function weather(start, n) {
  const conds = [["Mayormente despejado", "🌤️", 10], ["Parcialmente nublado", "⛅", 25], ["Chubascos ligeros", "🌦️", 55], ["Despejado", "☀️", 5]];
  return { location: { name: "Cartagena", country: "Colombia" }, source: "Open-Meteo · pronóstico", startDate: start, endDate: addDays(start, n - 1),
    days: Array.from({ length: n }, (_, i) => ({ date: addDays(start, i), condition: conds[i % 4][0], icon: conds[i % 4][1],
      tempMax: 31 + (i % 2), tempMin: 25, precipitationMm: i === 2 ? 3.2 : 0, rainProbability: conds[i % 4][2] })),
    summary: { avgTempMax: 31.5, maxRainProbability: 55, rainyDays: 1 } };
}

async function type(text, onEvent, signal) {
  for (const w of text.split(/(?<= )/)) { await sleep(18, signal); onEvent({ type: "text", delta: w }); }
}

export async function mockAgentStream(prompt, onEvent, signal) {
  try {
    const p = prompt.toLowerCase();
    const start = addDays(new Date().toISOString().slice(0, 10), 28);
    const end = addDays(start, 3);
    onEvent({ type: "start", sessionId: "mock" });
    await sleep(300, signal);
    if (/(crea|guarda|registra|reserva)/.test(p)) {
      onEvent({ type: "status", agent: "Tool CreateTrip", message: "Guardando tu viaje…" });
      await sleep(500, signal);
      const { trip } = await mockApi("POST", "/trips", { origin: "Bogotá", destination: "Cartagena", startDate: start, endDate: end, travelers: 3, budget: 5000000, interests: ["playa", "historia"] });
      onEvent({ type: "ui", component: "trip", data: trip });
      onEvent({ type: "status", agent: "Tool CreateItinerary", message: "Generando y guardando el itinerario…" });
      await sleep(600, signal);
      const acts = [
        [["09:00", "Ciudad Amurallada a pie", "Centro Histórico", 0, "cultura"], ["15:00", "Castillo San Felipe", "San Lázaro", 135000, "historia"], ["19:30", "Cena en Getsemaní", "Getsemaní", 270000, "gastronomía"]],
        [["08:00", "Tour Islas del Rosario + Playa Blanca", "Muelle La Bodeguita", 750000, "playa"], ["19:00", "Atardecer en Café del Mar", "Baluarte de Santo Domingo", 150000, "ocio"]],
        [["09:30", "Volcán del Totumo", "Santa Catalina", 360000, "aventura"], ["16:00", "Museo del Oro Zenú", "Plaza de Bolívar", 0, "cultura"]],
        [["08:30", "Desayuno típico y compras", "Bocagrande", 120000, "gastronomía"], ["13:00", "Traslado al aeropuerto", "Rafael Núñez", 45000, "transporte"]],
      ];
      const days = acts.map((a, i) => ({ day: i + 1, date: addDays(start, i), title: ["Historia y Getsemaní", "Islas del Rosario", "Volcán y museo", "Regreso"][i],
        activities: a.map(([time, title, location, estimatedCost, category]) => ({ time, title, location, estimatedCost, category })) }));
      const { itinerary } = await mockApi("POST", `/trips/${trip.tripId}/itinerary`, { days, summary: "4 días entre historia, playa y gastronomía." });
      onEvent({ type: "ui", component: "itinerary", data: itinerary });
      onEvent({ type: "status", agent: "Tool CreateReservation", message: "Registrando la reserva simulada…" });
      await sleep(500, signal);
      const { reservation } = await mockApi("POST", "/reservations", { tripId: trip.tripId, type: "FLIGHT", title: "Vuelo BOG → CTG JetSMART JA9514", provider: "JetSMART", startDateTime: `${start}T12:05`, amount: 882000, quantity: 3 });
      onEvent({ type: "ui", component: "reservation", data: reservation });
      await type(`¡Listo! Guardé tu **viaje a Cartagena** (${start} → ${end}, 3 viajeros), generé un itinerario de 4 días y registré la reserva **simulada** del vuelo JetSMART por $882.000 COP.\n\nCosto estimado: vuelos ida y regreso ≈ $1.8 M + actividades ≈ $2.2 M → **≈ $4.0 M de tus $5 M**. Puedes verlo en *Mis viajes* cuando quieras.`, onEvent, signal);
    } else {
      const onlyWeather = p.includes("solo clima"), onlyFlights = p.includes("solo vuelos");
      if (!onlyWeather) onEvent({ type: "status", agent: "Orchestrator", message: "Delegando la búsqueda de vuelos al Flight Agent…" });
      if (!onlyFlights) onEvent({ type: "status", agent: "Orchestrator", message: "Delegando el clima al Weather Agent…" });
      await sleep(700, signal);
      if (!onlyWeather) onEvent({ type: "status", agent: "Flight Agent", message: "Consultando vuelos en el MCP de vuelos…" });
      if (!onlyFlights) onEvent({ type: "status", agent: "Weather Agent", message: "Consultando el clima en el MCP de clima…" });
      await sleep(900, signal);
      if (!onlyWeather) onEvent({ type: "ui", component: "flights", data: flights(start, end, 3) });
      if (!onlyFlights) onEvent({ type: "ui", component: "weather", data: weather(start, 4) });
      if (onlyFlights) { await type("La opción más económica es **JetSMART** ($294.000 por persona). Si quieres equipaje de mano incluido, **LATAM 09:30** es el mejor balance. Puedes reservarla (simulada) desde la tarjeta.", onEvent, signal); onEvent({ type: "done" }); return; }
      if (onlyWeather) { await type("Clima cálido: 25–32 °C, con chubascos probables el tercer día. Lleva ropa ligera, protector solar y planea actividades bajo techo esa tarde.", onEvent, signal); onEvent({ type: "done" }); return; }
      await type(`Propuse fechas del **${start} al ${end}** (4 días). Para 3 viajeros la opción más económica es **JetSMART** a $294.000 por persona; si prefieres equipaje de mano incluido, **LATAM 09:30** es buen balance.\n\nEl clima en Cartagena estará entre 25 °C y 32 °C, con chubascos probables el tercer día: conviene dejar ese día para museos.\n\n¿Quieres que **cree el viaje**, arme el itinerario y registre la reserva del vuelo?`, onEvent, signal);
    }
    onEvent({ type: "done" });
  } catch (e) {
    if (e.name !== "AbortError") { onEvent({ type: "error", message: e.message }); onEvent({ type: "done" }); }
  }
}
