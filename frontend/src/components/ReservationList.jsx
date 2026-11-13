import { BedDouble, Plane, Ticket } from "lucide-react";
import { Link } from "react-router-dom";
import { money, shortDate, time, TYPE_LABEL } from "../format";
import { StatusBadge } from "./ui";

const ICON = { FLIGHT: Plane, HOTEL: BedDouble, ACTIVITY: Ticket };

/** Listado de reservas con estados (Agent-Driven UI: componentes "reservation(s)"). */
export default function ReservationList({ reservations, onEdit, title = "Reservas" }) {
  if (!reservations) return null;
  return (
    <div className="card agent-card">
      <div className="card-title"><Ticket size={18} /><span>{title}</span><span className="muted small">· {reservations.length}</span></div>
      {reservations.length === 0 && <div className="muted">No hay reservas.</div>}
      <div className="res-list">
        {reservations.map((r) => {
          const Icon = ICON[r.type] || Ticket;
          return (
            <div key={r.reservationId} className="res-row">
              <div className={`res-icon res-${(r.type || "").toLowerCase()}`}><Icon size={16} /></div>
              <div className="res-main">
                <strong>{r.title}</strong>
                <div className="small muted">
                  {TYPE_LABEL[r.type]}{r.provider ? ` · ${r.provider}` : ""}
                  {r.startDateTime ? ` · ${shortDate(r.startDateTime)} ${r.startDateTime.length > 10 ? time(r.startDateTime) : ""}` : ""}
                  {r.tripDestination && <> · <Link className="link" to={`/viajes/${r.tripId}`}>{r.tripDestination}</Link></>}
                </div>
                <div className="small muted">Código {r.confirmationCode}{r.quantity ? ` · ${r.quantity} pers.` : ""}</div>
              </div>
              <div className="res-side">
                <StatusBadge status={r.status} />
                <span className="small">{money(r.amount, r.currency)}</span>
                {onEdit && <button className="btn btn-ghost btn-sm" onClick={() => onEdit(r)}>Editar</button>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
