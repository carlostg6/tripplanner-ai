import { ArrowLeft, CalendarRange, Pencil, Plus, Sparkles, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, errorText } from "../api/api";
import ItineraryAgenda from "../components/ItineraryAgenda";
import ReservationList from "../components/ReservationList";
import ReserveModal from "../components/ReserveModal";
import TripCard from "../components/TripCard";
import { Alert, Empty, Modal, Spinner } from "../components/ui";
import { addDays, daysBetween, money } from "../format";
import { useApp } from "../state/AppState";
import { TripForm } from "./Trips";

function ItineraryEditor({ trip, itinerary, onSaved, onCancel }) {
  const n = daysBetween(trip.startDate, trip.endDate);
  const [days, setDays] = useState(() =>
    Array.from({ length: n }, (_, i) => {
      const ex = itinerary?.days?.find((d) => d.day === i + 1);
      return { day: i + 1, date: addDays(trip.startDate, i), title: ex?.title || "", activities: ex?.activities?.length ? ex.activities.map((a) => ({ ...a })) : [] };
    }),
  );
  const [summary, setSummary] = useState(itinerary?.summary || "");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const upd = (i, fn) => setDays((ds) => ds.map((d, j) => (j === i ? fn({ ...d, activities: [...d.activities] }) : d)));

  async function save() {
    setBusy(true); setErr("");
    const body = {
      summary: summary || undefined,
      days: days.map((d) => ({
        day: d.day, date: d.date, title: d.title || undefined,
        activities: d.activities.filter((a) => a.title?.trim()).map((a) => ({
          time: a.time || undefined, title: a.title, location: a.location || undefined, category: a.category || undefined,
          description: a.description || undefined, estimatedCost: a.estimatedCost === "" || a.estimatedCost == null ? undefined : Number(a.estimatedCost),
        })),
      })),
    };
    try {
      const r = itinerary ? await api.updateItinerary(trip.tripId, body) : await api.createItinerary(trip.tripId, body);
      onSaved(r.itinerary);
    } catch (e) { setErr(errorText(e)); } finally { setBusy(false); }
  }

  return (
    <Modal title={itinerary ? "Editar itinerario" : "Crear itinerario"} onClose={onCancel} wide>
      <Alert onClose={() => setErr("")}>{err}</Alert>
      <label className="field"><span>Resumen</span><input value={summary} onChange={(e) => setSummary(e.target.value)} maxLength={1000} /></label>
      <div className="editor">
        {days.map((d, i) => (
          <div key={d.day} className="editor-day">
            <div className="editor-day-head">
              <strong>Día {d.day}</strong><span className="muted small">{d.date}</span>
              <input placeholder="Título del día" value={d.title} onChange={(e) => upd(i, (x) => ({ ...x, title: e.target.value }))} />
            </div>
            {d.activities.map((a, j) => (
              <div key={j} className="editor-act">
                <input type="time" value={a.time || ""} onChange={(e) => upd(i, (x) => { x.activities[j] = { ...a, time: e.target.value }; return x; })} />
                <input placeholder="Actividad" value={a.title || ""} onChange={(e) => upd(i, (x) => { x.activities[j] = { ...a, title: e.target.value }; return x; })} />
                <input placeholder="Lugar" value={a.location || ""} onChange={(e) => upd(i, (x) => { x.activities[j] = { ...a, location: e.target.value }; return x; })} />
                <input type="number" min="0" placeholder="Costo" value={a.estimatedCost ?? ""} onChange={(e) => upd(i, (x) => { x.activities[j] = { ...a, estimatedCost: e.target.value }; return x; })} />
                <button className="icon-btn" aria-label="Quitar" onClick={() => upd(i, (x) => { x.activities.splice(j, 1); return x; })}><Trash2 size={14} /></button>
              </div>
            ))}
            <button className="btn btn-ghost btn-sm" onClick={() => upd(i, (x) => { x.activities.push({ time: "", title: "" }); return x; })}><Plus size={12} /> Actividad</button>
          </div>
        ))}
      </div>
      <div className="modal-actions">
        <button className="btn btn-ghost" onClick={onCancel}>Cancelar</button>
        <button className="btn" onClick={save} disabled={busy}>{busy ? "Guardando…" : "Guardar itinerario"}</button>
      </div>
    </Modal>
  );
}

export default function TripDetail() {
  const { tripId } = useParams();
  const { chat, dataVersion } = useApp();
  const nav = useNavigate();
  const [d, setD] = useState(null);
  const [err, setErr] = useState("");
  const [modal, setModal] = useState(null);

  const load = () => api.getTrip(tripId).then(setD).catch((e) => setErr(errorText(e)));
  useEffect(() => { load(); }, [tripId, dataVersion]); // eslint-disable-line

  if (err && !d) return <div className="page"><Alert>{err}</Alert><Link className="link" to="/viajes">← Volver</Link></div>;
  if (!d) return <div className="page"><Spinner label="Cargando viaje…" /></div>;
  const { trip, itinerary, reservations } = d;
  const spent = reservations.reduce((s, r) => s + Number(r.amount || 0), 0)
    + (itinerary?.days || []).flatMap((x) => x.activities || []).reduce((s, a) => s + Number(a.estimatedCost || 0), 0);

  const askAgent = () => {
    chat.send(`Genera y guarda un itinerario para mi viaje ${trip.tripId} a ${trip.destination} (${trip.startDate} a ${trip.endDate}, ${trip.travelers} viajeros${trip.budget ? `, presupuesto ${trip.budget} ${trip.currency}` : ""}). Ten en cuenta el clima.`);
    nav("/asistente");
  };

  return (
    <div className="page">
      <Link className="link" to="/viajes"><ArrowLeft size={14} /> Mis viajes</Link>
      <header className="page-head">
        <div><h1>{trip.title}</h1><p className="muted">{trip.origin} → {trip.destination}</p></div>
        <button className="btn btn-ghost" onClick={() => setModal("edit")}><Pencil size={14} /> Editar viaje</button>
      </header>
      <Alert onClose={() => setErr("")}>{err}</Alert>
      <div className="detail-top">
        <TripCard trip={trip} />
        {trip.budget != null && (
          <div className="card budget">
            <div className="muted small">Presupuesto</div>
            <div className="big">{money(trip.budget, trip.currency)}</div>
            <div className="bar"><div style={{ width: `${Math.min(100, (spent / trip.budget) * 100 || 0)}%` }} className={spent > trip.budget ? "over" : ""} /></div>
            <div className="small">Comprometido: {money(spent)} · Disponible: {money(trip.budget - spent)}</div>
            {trip.interests?.length > 0 && <div className="chips">{trip.interests.map((x) => <span key={x} className="tag tag-soft">{x}</span>)}</div>}
          </div>
        )}
      </div>

      <section>
        <div className="section-head">
          <h2>Itinerario</h2>
          <div className="row">
            <button className="btn btn-ghost btn-sm" onClick={askAgent}><Sparkles size={14} /> Generar con el asistente</button>
            <button className="btn btn-sm" onClick={() => setModal("itin")}><CalendarRange size={14} /> {itinerary ? "Editar" : "Crear"}</button>
          </div>
        </div>
        {itinerary ? <ItineraryAgenda itinerary={itinerary} /> : <Empty icon={CalendarRange} title="Sin itinerario todavía" />}
      </section>

      <section>
        <div className="section-head">
          <h2>Reservas del viaje</h2>
          <button className="btn btn-sm" onClick={() => setModal("res")}><Plus size={14} /> Nueva reserva</button>
        </div>
        <ReservationList reservations={reservations} onEdit={(r) => setModal({ edit: r })} />
      </section>

      {modal === "edit" && (
        <Modal title="Editar viaje" onClose={() => setModal(null)}>
          <TripForm initial={trip} onCancel={() => setModal(null)}
            onSubmit={async (b) => { await api.updateTrip(trip.tripId, b); setModal(null); load(); }} />
        </Modal>
      )}
      {modal === "itin" && <ItineraryEditor trip={trip} itinerary={itinerary} onCancel={() => setModal(null)} onSaved={() => { setModal(null); load(); }} />}
      {modal === "res" && <ReserveModal tripId={trip.tripId} onClose={() => { setModal(null); load(); }} />}
      {modal?.edit && <ReserveModal existing={modal.edit} onClose={() => { setModal(null); load(); }} />}
    </div>
  );
}
