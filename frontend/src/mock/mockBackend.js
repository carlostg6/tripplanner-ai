/**
 * SOLO DESARROLLO (VITE_MOCK=true): imita el backend en el navegador para poder
 * diseñar la interfaz sin AWS. En producción nunca se usa: los datos reales
 * vienen de API Gateway → Lambda → DynamoDB.
 */
const KEY = "tp_mock_db";
const load = () => JSON.parse(localStorage.getItem(KEY) || '{"trips":{},"itins":{},"res":{},"prefs":{}}');
const save = (db) => localStorage.setItem(KEY, JSON.stringify(db));
const id = (p) => `${p}_${Math.random().toString(16).slice(2, 14)}`;
const now = () => new Date().toISOString().slice(0, 19) + "+00:00";
const err = (status, code, message) => Object.assign(new Error(message), { status, code });

export async function mockApi(method, path, body = {}, query = {}) {
  await new Promise((r) => setTimeout(r, 150));
  const db = load();
  const seg = path.split("/").filter(Boolean).map(decodeURIComponent);
  let out;
  if (seg[0] === "me") out = { profile: { name: "Viajero", email: "demo@tripplanner.ai" } };
  else if (seg[0] === "preferences") {
    if (method === "PUT") db.prefs = { ...db.prefs, ...body, updatedAt: now() };
    out = { preferences: db.prefs };
  } else if (seg[0] === "trips" && seg.length === 1) {
    if (method === "POST") {
      const t = { tripId: id("trip"), status: "PLANEADO", currency: "COP", title: `Viaje a ${body.destination}`,
                  ...body, createdAt: now(), updatedAt: now() };
      db.trips[t.tripId] = t;
      out = { trip: t };
    } else {
      const trips = Object.values(db.trips).sort((a, b) => a.startDate.localeCompare(b.startDate));
      out = { trips, count: trips.length };
    }
  } else if (seg[0] === "trips" && seg.length === 2) {
    const t = db.trips[seg[1]];
    if (!t) throw err(404, "TRIP_NOT_FOUND", "El viaje no existe.");
    if (method === "PUT") Object.assign(t, body, { updatedAt: now() });
    out = method === "PUT" ? { trip: t } : {
      trip: t, itinerary: db.itins[seg[1]] || null,
      reservations: Object.values(db.res).filter((r) => r.tripId === seg[1]),
    };
  } else if (seg[0] === "trips" && seg[2] === "itinerary") {
    if (!db.trips[seg[1]]) throw err(404, "TRIP_NOT_FOUND", "El viaje no existe.");
    if (method === "GET") {
      if (!db.itins[seg[1]]) throw err(404, "ITINERARY_NOT_FOUND", "Sin itinerario.");
    } else if (method === "POST" && db.itins[seg[1]]) throw err(409, "ALREADY_EXISTS", "Ya existe.");
    else {
      const prev = db.itins[seg[1]];
      db.itins[seg[1]] = { tripId: seg[1], ...body, version: prev ? prev.version + 1 : 1, updatedAt: now() };
    }
    out = { itinerary: db.itins[seg[1]] };
  } else if (seg[0] === "reservations" && seg.length === 1) {
    if (method === "POST") {
      const t = db.trips[body.tripId];
      if (!t) throw err(404, "TRIP_NOT_FOUND", "El viaje no existe.");
      const rid = id("res");
      const r = { reservationId: rid, status: "SIMULADA", currency: "COP", ...body, tripDestination: t.destination,
                  confirmationCode: `SIM-${rid.slice(-6).toUpperCase()}`, createdAt: now(), updatedAt: now() };
      r.statusHistory = [{ status: r.status, at: now() }];
      db.res[rid] = r;
      out = { reservation: r };
    } else {
      let list = Object.values(db.res);
      if (query?.tripId) list = list.filter((r) => r.tripId === query.tripId);
      if (query?.status) list = list.filter((r) => r.status === query.status);
      if (query?.type) list = list.filter((r) => r.type === query.type);
      list.sort((a, b) => b.createdAt.localeCompare(a.createdAt));
      out = { reservations: list, count: list.length };
    }
  } else if (seg[0] === "reservations") {
    const r = db.res[seg[1]];
    if (!r) throw err(404, "RESERVATION_NOT_FOUND", "La reserva no existe.");
    if (body.status === "CONFIRMADA" && !r.providerReference)
      throw err(409, "CONFIRMATION_REQUIRES_PROVIDER", "Solo un proveedor real puede confirmar la reserva.");
    if (body.tripId) body.tripDestination = db.trips[body.tripId]?.destination;
    if (body.status && body.status !== r.status) r.statusHistory.push({ status: body.status, at: now() });
    Object.assign(r, body, { updatedAt: now() });
    out = { reservation: r };
  } else throw err(404, "NOT_FOUND", "Ruta no encontrada.");
  save(db);
  return JSON.parse(JSON.stringify(out));
}
