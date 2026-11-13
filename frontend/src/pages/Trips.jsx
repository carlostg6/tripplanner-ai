import { Luggage, Plus } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, errorText } from "../api/api";
import TripCard from "../components/TripCard";
import { Alert, Empty, Field, Modal, Spinner } from "../components/ui";
import { addDays, todayIso, TRIP_STATUS_LABEL } from "../format";
import { useApp } from "../state/AppState";

export function TripForm({ initial, onSubmit, onCancel, submitLabel = "Guardar" }) {
  const [f, setF] = useState({
    title: "", origin: "", destination: "", startDate: addDays(todayIso(), 14), endDate: addDays(todayIso(), 17),
    travelers: 1, budget: "", currency: "COP", interests: "", notes: "", ...initial,
    ...(initial?.interests ? { interests: initial.interests.join(", ") } : {}),
  });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    setBusy(true); setErr("");
    try {
      await onSubmit({
        title: f.title || undefined, origin: f.origin, destination: f.destination, startDate: f.startDate,
        endDate: f.endDate, travelers: Number(f.travelers), budget: f.budget === "" ? undefined : Number(f.budget),
        currency: f.currency, notes: f.notes || undefined, ...(initial?.status ? { status: f.status } : {}),
        interests: f.interests ? f.interests.split(",").map((s) => s.trim()).filter(Boolean) : undefined,
      });
    } catch (e2) { setErr(errorText(e2)); } finally { setBusy(false); }
  }

  return (
    <form className="form" onSubmit={submit}>
      <Alert onClose={() => setErr("")}>{err}</Alert>
      <Field label="Nombre del viaje (opcional)"><input value={f.title} onChange={set("title")} maxLength={120} /></Field>
      <div className="grid2">
        <Field label="Origen"><input value={f.origin} onChange={set("origin")} required /></Field>
        <Field label="Destino"><input value={f.destination} onChange={set("destination")} required /></Field>
      </div>
      <div className="grid2">
        <Field label="Salida"><input type="date" value={f.startDate} onChange={set("startDate")} required /></Field>
        <Field label="Regreso"><input type="date" min={f.startDate} value={f.endDate} onChange={set("endDate")} required /></Field>
      </div>
      <div className="grid3">
        <Field label="Viajeros"><input type="number" min="1" max="20" value={f.travelers} onChange={set("travelers")} required /></Field>
        <Field label="Presupuesto"><input type="number" min="0" value={f.budget} onChange={set("budget")} /></Field>
        <Field label="Moneda"><select value={f.currency} onChange={set("currency")}><option>COP</option><option>USD</option><option>EUR</option></select></Field>
      </div>
      {initial?.status && (
        <Field label="Estado">
          <select value={f.status} onChange={set("status")}>
            {Object.entries(TRIP_STATUS_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </Field>
      )}
      <Field label="Intereses" hint="Separados por comas: playa, historia, gastronomía…"><input value={f.interests} onChange={set("interests")} /></Field>
      <Field label="Notas"><textarea rows={2} value={f.notes} onChange={set("notes")} maxLength={1000} /></Field>
      <div className="modal-actions">
        {onCancel && <button type="button" className="btn btn-ghost" onClick={onCancel}>Cancelar</button>}
        <button className="btn" disabled={busy}>{busy ? "Guardando…" : submitLabel}</button>
      </div>
    </form>
  );
}

export default function Trips() {
  const { dataVersion } = useApp();
  const [params, setParams] = useSearchParams();
  const nav = useNavigate();
  const [trips, setTrips] = useState(null);
  const [status, setStatus] = useState("");
  const [err, setErr] = useState("");
  const creating = params.get("nuevo") === "1";

  useEffect(() => {
    api.listTrips(status).then((r) => setTrips(r.trips)).catch((e) => setErr(errorText(e)));
  }, [status, dataVersion]);

  return (
    <div className="page">
      <header className="page-head">
        <div><h1><Luggage size={22} /> Mis viajes</h1><p className="muted">Viajes guardados, itinerarios y reservas.</p></div>
        <button className="btn" onClick={() => setParams({ nuevo: "1" })}><Plus size={16} /> Nuevo viaje</button>
      </header>
      <div className="seg">
        {[["", "Todos"], ...Object.entries(TRIP_STATUS_LABEL)].map(([k, l]) => (
          <button key={k} className={status === k ? "active" : ""} onClick={() => setStatus(k)}>{l}</button>
        ))}
      </div>
      <Alert onClose={() => setErr("")}>{err}</Alert>
      {!trips ? <Spinner label="Cargando viajes…" /> : trips.length === 0 ? (
        <Empty icon={Luggage} title="No hay viajes">Crea uno aquí o pídeselo al asistente.</Empty>
      ) : (
        <div className="trip-grid">{trips.map((t) => <TripCard key={t.tripId} trip={t} />)}</div>
      )}
      {creating && (
        <Modal title="Nuevo viaje" onClose={() => setParams({})}>
          <TripForm submitLabel="Crear viaje" onCancel={() => setParams({})}
            onSubmit={async (b) => { const r = await api.createTrip(b); nav(`/viajes/${r.trip.tripId}`); }} />
        </Modal>
      )}
    </div>
  );
}
