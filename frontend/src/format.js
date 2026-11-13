export const money = (n, currency = "COP") =>
  n == null || n === "" ? "—"
    : new Intl.NumberFormat("es-CO", { style: "currency", currency, maximumFractionDigits: currency === "COP" ? 0 : 2 }).format(Number(n));

export const shortDate = (iso) =>
  iso ? new Date(iso.length === 10 ? iso + "T00:00:00" : iso).toLocaleDateString("es-CO", { weekday: "short", day: "numeric", month: "short" }) : "—";

export const longDate = (iso) =>
  iso ? new Date(iso.length === 10 ? iso + "T00:00:00" : iso).toLocaleDateString("es-CO", { day: "numeric", month: "long", year: "numeric" }) : "—";

export const time = (iso) => (iso ? iso.slice(11, 16) : "—");

export const duration = (min) => `${Math.floor(min / 60)} h ${String(min % 60).padStart(2, "0")} min`;

export const daysBetween = (a, b) => Math.round((new Date(b + "T00:00:00") - new Date(a + "T00:00:00")) / 86400000) + 1;

export const daysUntil = (iso) => Math.ceil((new Date(iso + "T00:00:00") - new Date(new Date().toDateString())) / 86400000);

export const todayIso = () => new Date().toISOString().slice(0, 10);

export const addDays = (iso, n) => {
  const d = new Date(iso + "T00:00:00");
  d.setDate(d.getDate() + n);
  return d.toISOString().slice(0, 10);
};

export const TYPE_LABEL = { FLIGHT: "Vuelo", HOTEL: "Hotel", ACTIVITY: "Actividad" };
export const TRIP_STATUS_LABEL = { PLANEADO: "Planeado", EN_CURSO: "En curso", COMPLETADO: "Completado", CANCELADO: "Cancelado" };
