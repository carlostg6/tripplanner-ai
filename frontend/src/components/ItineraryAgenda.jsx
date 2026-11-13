import { CalendarRange, Clock, MapPin } from "lucide-react";
import { Link } from "react-router-dom";
import { money, shortDate } from "../format";

/** Itinerario en formato agenda por día (Agent-Driven UI: componente "itinerary"). */
export default function ItineraryAgenda({ itinerary, showLink }) {
  if (!itinerary?.days) return null;
  const total = itinerary.days.flatMap((d) => d.activities || []).reduce((s, a) => s + Number(a.estimatedCost || 0), 0);
  return (
    <div className="card agent-card">
      <div className="card-title">
        <CalendarRange size={18} />
        <span>Itinerario · {itinerary.days.length} días</span>
        {itinerary.version > 1 && <span className="muted small">· versión {itinerary.version}</span>}
        {showLink && itinerary.tripId && <Link className="link small push" to={`/viajes/${itinerary.tripId}`}>Ver viaje →</Link>}
      </div>
      {itinerary.summary && <p className="muted">{itinerary.summary}</p>}
      <div className="agenda">
        {itinerary.days.map((d) => (
          <div key={d.day} className="agenda-day">
            <div className="agenda-date">
              <div className="agenda-num">Día {d.day}</div>
              <div className="small muted">{d.date ? shortDate(d.date) : ""}</div>
            </div>
            <div className="agenda-acts">
              {d.title && <div className="agenda-title">{d.title}</div>}
              {[...(d.activities || [])].sort((x, y) => (x.time || "99:99").localeCompare(y.time || "99:99")).map((a, i) => (
                <div key={i} className="agenda-act">
                  <span className="agenda-time"><Clock size={12} /> {a.time || "—"}</span>
                  <div>
                    <strong>{a.title}</strong>
                    {a.category && <span className="tag tag-soft">{a.category}</span>}
                    {a.description && <div className="small muted">{a.description}</div>}
                    {a.location && <div className="small muted"><MapPin size={11} /> {a.location}</div>}
                  </div>
                  {a.estimatedCost != null && <span className="small">{Number(a.estimatedCost) ? money(a.estimatedCost) : "Gratis"}</span>}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
      {total > 0 && <div className="callout">Costo estimado de actividades: <strong>{money(total)}</strong></div>}
    </div>
  );
}
