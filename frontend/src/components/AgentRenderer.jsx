import { Heart } from "lucide-react";
import FlightResults from "./FlightResults";
import ItineraryAgenda from "./ItineraryAgenda";
import ReservationList from "./ReservationList";
import TripCard from "./TripCard";
import WeatherCards from "./WeatherCards";

/**
 * Agent-Driven UI: el agente decide y devuelve datos estructurados; aquí se
 * transforman en el componente visual apropiado.
 */
export default function AgentRenderer({ event }) {
  const { component, data } = event;
  switch (component) {
    case "flights":
      return <FlightResults data={data} compact />;
    case "weather":
      return <WeatherCards data={data} />;
    case "trip":
      return <div className="trip-grid one"><TripCard trip={data} /></div>;
    case "trips":
      return <div className="trip-grid">{data.trips.map((t) => <TripCard key={t.tripId} trip={t} compact />)}</div>;
    case "trip_detail":
      return (
        <>
          <div className="trip-grid one"><TripCard trip={data.trip} /></div>
          {data.itinerary && <ItineraryAgenda itinerary={data.itinerary} />}
          {data.reservations?.length > 0 && <ReservationList reservations={data.reservations} />}
        </>
      );
    case "itinerary":
      return <ItineraryAgenda itinerary={data} showLink />;
    case "reservation":
      return <ReservationList reservations={[data]} title="Reserva registrada" />;
    case "reservations":
      return <ReservationList reservations={data.reservations} />;
    case "preferences":
      return (
        <div className="card agent-card">
          <div className="card-title"><Heart size={18} /><span>Preferencias guardadas</span></div>
          <div className="chips">
            {Object.entries(data).filter(([k]) => !["userId", "entityType", "createdAt", "updatedAt"].includes(k))
              .map(([k, v]) => <span key={k} className="tag tag-soft">{k}: {Array.isArray(v) ? v.join(", ") : String(v)}</span>)}
          </div>
        </div>
      );
    default:
      return null;
  }
}
