import { CalendarDays, MapPin, Users, Wallet } from "lucide-react";
import { Link } from "react-router-dom";
import { daysBetween, daysUntil, money, shortDate, TRIP_STATUS_LABEL } from "../format";

/** Tarjeta de viaje: destino, fechas, viajeros y presupuesto. */
export default function TripCard({ trip, compact }) {
  if (!trip) return null;
  const until = trip.startDate ? daysUntil(trip.startDate) : null;
  return (
    <Link to={`/viajes/${trip.tripId}`} className="card trip-card">
      <div className="trip-cover">
        <MapPin size={18} />
        <div>
          <div className="trip-dest">{trip.destination}</div>
          <div className="small">desde {trip.origin}</div>
        </div>
        <span className="trip-status">{TRIP_STATUS_LABEL[trip.status] || trip.status}</span>
      </div>
      <div className="trip-body">
        <strong>{trip.title}</strong>
        <div className="trip-meta">
          <span><CalendarDays size={14} /> {shortDate(trip.startDate)} – {shortDate(trip.endDate)} · {daysBetween(trip.startDate, trip.endDate)} días</span>
          <span><Users size={14} /> {trip.travelers} viajero{trip.travelers > 1 ? "s" : ""}</span>
          {trip.budget != null && <span><Wallet size={14} /> {money(trip.budget, trip.currency)}</span>}
        </div>
        {!compact && until != null && until >= 0 && (
          <div className="small accent">{until === 0 ? "¡Es hoy!" : `Faltan ${until} días`}</div>
        )}
      </div>
    </Link>
  );
}
