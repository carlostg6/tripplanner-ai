import { useEffect, useState } from "react";
import { api, errorText } from "../api/api";
import { Alert, Field, Modal } from "./ui";

/**
 * Crear o editar una reserva (canal 1: API Gateway → Lambda).
 * Sin campos de pago: las reservas son simuladas.
 */
export default function ReserveModal({ onClose, onSaved, initial = {}, existing, tripId }) {
  const [trips, setTrips] = useState(null);
  const [f, setF] = useState({
    tripId: existing?.tripId || tripId || initial.tripId || "",
    type: existing?.type || initial.type || "FLIGHT",
    title: existing?.title || initial.title || "",
    provider: existing?.provider || initial.provider || "",
    startDateTime: (existing?.startDateTime || initial.startDateTime || "").slice(0, 16),
    endDateTime: (existing?.endDateTime || initial.endDateTime || "").slice(0, 16),
    amount: existing?.amount ?? initial.amount ?? "",
    quantity: existing?.quantity ?? initial.quantity ?? 1,
    status: existing?.status || "SIMULADA",
    notes: existing?.notes || "",
  });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(null);

  useEffect(() => {
    api.listTrips().then((r) => {
      setTrips(r.trips);
      if (!f.tripId && r.trips[0]) setF((x) => ({ ...x, tripId: r.trips[0].tripId }));
    }).catch((e) => setErr(errorText(e)));
  }, []); // eslint-disable-line

  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setErr("");
    const body = {
      title: f.title, provider: f.provider || undefined, status: f.status, notes: f.notes || undefined,
      startDateTime: f.startDateTime || undefined, endDateTime: f.endDateTime || undefined,
      amount: f.amount === "" ? undefined : Number(f.amount), quantity: Number(f.quantity) || undefined,
    };
    try {
      let r;
      if (existing) {
        if (f.tripId !== existing.tripId) body.tripId = f.tripId;
        r = await api.updateReservation(existing.reservationId, body);
      } else {
        r = await api.createReservation({ ...body, tripId: f.tripId, type: f.type, details: initial.details });
      }
      setDone(r.reservation);
      onSaved?.(r.reservation);
    } catch (e2) {
      setErr(errorText(e2));
    } finally {
      setBusy(false);
    }
  }

  if (done) {
    return (
      <Modal title="Reserva guardada" onClose={onClose}>
        <p>La reserva <strong>{done.title}</strong> quedó registrada con estado <strong>{done.status}</strong> (código {done.confirmationCode}).</p>
        <div className="modal-actions"><button className="btn" onClick={onClose}>Listo</button></div>
      </Modal>
    );
  }

  return (
    <Modal title={existing ? "Editar reserva" : "Nueva reserva simulada"} onClose={onClose}>
      <form onSubmit={submit} className="form">
        <Alert onClose={() => setErr("")}>{err}</Alert>
        {trips?.length === 0 && <Alert kind="info">Primero crea un viaje para asociar la reserva.</Alert>}
        <Field label="Viaje asociado">
          <select value={f.tripId} onChange={set("tripId")} required>
            {(trips || []).map((t) => <option key={t.tripId} value={t.tripId}>{t.title} ({t.startDate})</option>)}
          </select>
        </Field>
        <div className="grid2">
          <Field label="Tipo">
            <select value={f.type} onChange={set("type")} disabled={!!existing}>
              <option value="FLIGHT">Vuelo</option><option value="HOTEL">Hotel</option><option value="ACTIVITY">Actividad turística</option>
            </select>
          </Field>
          <Field label="Estado" hint="Confirmada solo con un proveedor real">
            <select value={f.status} onChange={set("status")}>
              <option value="SIMULADA">Simulada</option><option value="PENDIENTE">Pendiente</option>
              <option value="CONFIRMADA" disabled={!existing?.providerReference}>Confirmada</option>
            </select>
          </Field>
        </div>
        <Field label="Descripción"><input value={f.title} onChange={set("title")} required maxLength={150} /></Field>
        <Field label="Proveedor"><input value={f.provider} onChange={set("provider")} maxLength={100} placeholder="Aerolínea, hotel u operador" /></Field>
        <div className="grid2">
          <Field label="Inicio"><input type="datetime-local" value={f.startDateTime} onChange={set("startDateTime")} /></Field>
          <Field label="Fin"><input type="datetime-local" value={f.endDateTime} onChange={set("endDateTime")} /></Field>
        </div>
        <div className="grid2">
          <Field label="Valor total (COP)"><input type="number" min="0" value={f.amount} onChange={set("amount")} /></Field>
          <Field label="Personas / unidades"><input type="number" min="1" max="20" value={f.quantity} onChange={set("quantity")} /></Field>
        </div>
        <Field label="Notas"><textarea rows={2} value={f.notes} onChange={set("notes")} maxLength={1000} /></Field>
        <p className="small muted">🔒 TripPlanner no solicita ni guarda datos de tarjetas o pagos.</p>
        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose}>Cancelar</button>
          <button className="btn" disabled={busy || !trips?.length}>{busy ? "Guardando…" : "Guardar reserva"}</button>
        </div>
      </form>
    </Modal>
  );
}
