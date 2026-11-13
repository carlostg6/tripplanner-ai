import { CloudSun, Luggage, MessageCircle, Plane, Plus, Ticket, Wallet } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, errorText } from "../api/api";
import ReservationList from "../components/ReservationList";
import TripCard from "../components/TripCard";
import { Alert, Empty, Spinner } from "../components/ui";
import { money, todayIso } from "../format";
import { useApp } from "../state/AppState";

const DEMO_PROMPT = "Quiero organizar unas vacaciones de cuatro días en Cartagena. Salgo desde Bogotá, viajo con dos personas más y tengo un presupuesto de 5 millones de pesos. Quiero conocer el clima, encontrar vuelos y organizar algunas actividades turísticas.";

export default function Dashboard() {
  const { user, chat, dataVersion } = useApp();
  const nav = useNavigate();
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    Promise.all([api.listTrips(), api.listReservations()])
      .then(([t, r]) => setData({ trips: t.trips, reservations: r.reservations }))
      .catch((e) => setErr(errorText(e)));
  }, [dataVersion]);

  const upcoming = data?.trips.filter((t) => t.endDate >= todayIso() && t.status !== "CANCELADO") || [];
  const reserved = data?.reservations.reduce((s, r) => s + Number(r.amount || 0), 0) || 0;
  const budget = upcoming.reduce((s, t) => s + Number(t.budget || 0), 0);

  const startDemo = () => { chat.send(DEMO_PROMPT); nav("/asistente"); };

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1>Hola, {user?.name} 👋</h1>
          <p className="muted">Este es el resumen de tus viajes.</p>
        </div>
        <button className="btn" onClick={startDemo}><MessageCircle size={16} /> Planear con el asistente</button>
      </header>
      <Alert onClose={() => setErr("")}>{err}</Alert>

      <div className="stats">
        <div className="stat"><Luggage size={18} /><div><div className="big">{upcoming.length}</div><div className="muted small">Próximos viajes</div></div></div>
        <div className="stat"><Ticket size={18} /><div><div className="big">{data?.reservations.length ?? "—"}</div><div className="muted small">Reservas</div></div></div>
        <div className="stat"><Wallet size={18} /><div><div className="big">{money(reserved)}</div><div className="muted small">Reservado de {money(budget)}</div></div></div>
      </div>

      <section className="quick">
        <Link to="/asistente" className="quick-btn"><MessageCircle size={18} /> Hablar con el asistente</Link>
        <Link to="/vuelos" className="quick-btn"><Plane size={18} /> Buscar vuelos</Link>
        <Link to="/clima" className="quick-btn"><CloudSun size={18} /> Consultar clima</Link>
        <Link to="/viajes?nuevo=1" className="quick-btn"><Plus size={18} /> Nuevo viaje</Link>
      </section>

      <section>
        <div className="section-head"><h2>Próximos viajes</h2><Link className="link" to="/viajes">Ver todos →</Link></div>
        {!data ? <Spinner label="Cargando…" /> : upcoming.length ? (
          <div className="trip-grid">{upcoming.slice(0, 3).map((t) => <TripCard key={t.tripId} trip={t} />)}</div>
        ) : (
          <Empty icon={Luggage} title="Aún no tienes viajes">
            <button className="btn btn-sm" onClick={startDemo}>Prueba: “4 días en Cartagena desde Bogotá”</button>
          </Empty>
        )}
      </section>

      <section>
        <div className="section-head"><h2>Reservas recientes</h2><Link className="link" to="/reservas">Gestionar →</Link></div>
        {data && <ReservationList reservations={data.reservations.slice(0, 5)} title="Últimas reservas" />}
      </section>
    </div>
  );
}
