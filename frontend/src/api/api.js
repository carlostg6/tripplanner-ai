/** Canal 1 · Operaciones de negocio: Frontend → API Gateway → Lambda → DynamoDB. */
import { getAccessToken } from "../auth/auth";
import { config } from "../config";
import { mockApi } from "../mock/mockBackend";

export class ApiError extends Error {
  constructor(status, code, message, details) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

async function request(method, path, body, query) {
  if (config.mock) return mockApi(method, path, body, query);
  const token = await getAccessToken();
  const qs = query ? "?" + new URLSearchParams(Object.entries(query).filter(([, v]) => v)).toString() : "";
  let res;
  try {
    res = await fetch(`${config.apiUrl}${path}${qs}`, {
      method,
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(0, "NETWORK", "No hay conexión con el servidor.");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const e = data.error || {};
    const msg =
      res.status === 401 ? "Tu sesión expiró. Ingresa de nuevo."
      : res.status === 429 ? "Demasiadas solicitudes, espera un momento."
      : e.message || "Ocurrió un error.";
    throw new ApiError(res.status, e.code, msg, e.details);
  }
  return data;
}

export const api = {
  me: () => request("GET", "/me"),
  updateMe: (b) => request("PUT", "/me", b),
  getPreferences: () => request("GET", "/preferences"),
  savePreferences: (b) => request("PUT", "/preferences", b),

  listTrips: (status) => request("GET", "/trips", null, { status }),
  getTrip: (id) => request("GET", `/trips/${encodeURIComponent(id)}`),
  createTrip: (b) => request("POST", "/trips", b),
  updateTrip: (id, b) => request("PUT", `/trips/${encodeURIComponent(id)}`, b),

  getItinerary: (tripId) => request("GET", `/trips/${encodeURIComponent(tripId)}/itinerary`),
  createItinerary: (tripId, b) => request("POST", `/trips/${encodeURIComponent(tripId)}/itinerary`, b),
  updateItinerary: (tripId, b) => request("PUT", `/trips/${encodeURIComponent(tripId)}/itinerary`, b),

  listReservations: (q) => request("GET", "/reservations", null, q),
  createReservation: (b) => request("POST", "/reservations", b),
  updateReservation: (id, b) => request("PUT", `/reservations/${encodeURIComponent(id)}`, b),
};

export function errorText(e) {
  if (e?.details?.length) return `${e.message} ${e.details.map((d) => `${d.field}: ${d.message}`).join(" · ")}`;
  return e?.message || "Ocurrió un error.";
}
