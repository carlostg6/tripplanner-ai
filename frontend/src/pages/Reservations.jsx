import { Plus, Ticket } from "lucide-react";
import { useEffect, useState } from "react";
import { api, errorText } from "../api/api";
import ReservationList from "../components/ReservationList";
import ReserveModal from "../components/ReserveModal";
import { Alert, Spinner, StatusBadge } from "../components/ui";
import { TYPE_LABEL } from "../format";
import { useApp } from "../state/AppState";

export default function Reservations() {
  const { dataVersion } = useApp();
  const [list, setList] = useState(null);
  const [q, setQ] = useState({ status: "", type: "" });
  const [err, setErr] = useState("");
  const [modal, setModal] = useState(null);

  const load = () => api.listReservations(q).then((r) => setList(r.reservations)).catch((e) => setErr(errorText(e)));
  useEffect(() => { load(); }, [q, dataVersion]); // eslint-disable-line

  return (
    <div className="page">
      <header className="page-head">
        <div><h1><Ticket size={22} /> Gestión de reservas</h1><p className="muted">Reservas simuladas, persistidas en DynamoDB.</p></div>
        <button className="btn" onClick={() => setModal("new")}><Plus size={16} /> Nueva reserva</button>
      </header>
      <div className="card legend">
        <span><StatusBadge status="SIMULADA" /> Registrada por el sistema sin proveedor externo</span>
        <span><StatusBadge status="PENDIENTE" /> A la espera de confirmación</span>
        <span><StatusBadge status="CONFIRMADA" /> Confirmada por un proveedor real</span>
      </div>
      <div className="filters">
        <select value={q.status} onChange={(e) => setQ({ ...q, status: e.target.value })}>
          <option value="">Todos los estados</option><option value="SIMULADA">Simulada</option><option value="PENDIENTE">Pendiente</option><option value="CONFIRMADA">Confirmada</option>
        </select>
        <select value={q.type} onChange={(e) => setQ({ ...q, type: e.target.value })}>
          <option value="">Todos los tipos</option>
          {Object.entries(TYPE_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </div>
      <Alert onClose={() => setErr("")}>{err}</Alert>
      {!list ? <Spinner label="Cargando reservas…" /> : <ReservationList reservations={list} onEdit={(r) => setModal({ edit: r })} />}
      {modal === "new" && <ReserveModal onClose={() => { setModal(null); load(); }} />}
      {modal?.edit && <ReserveModal existing={modal.edit} onClose={() => { setModal(null); load(); }} />}
    </div>
  );
}
