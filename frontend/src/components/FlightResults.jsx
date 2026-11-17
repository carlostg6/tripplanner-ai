import { ArrowRight, Briefcase, Clock, Plane } from "lucide-react";
import { useMemo, useState } from "react";
import { duration, money, shortDate, time } from "../format";
import ReserveModal from "./ReserveModal";

const SORTS = { price: "Precio", duration: "Duración", departure: "Salida" };

function sortOffers(list, by) {
  const k = { price: (o) => o.totalPrice, duration: (o) => o.durationMinutes, departure: (o) => o.departureTime }[by];
  return [...list].sort((a, b) => (k(a) > k(b) ? 1 : k(a) < k(b) ? -1 : 0));
}

function FlightCard({ o, cheapest, onReserve, selected, onSelect }) {
  const diff = o.totalPrice - cheapest;
  return (
    <div className={`flight-card ${selected ? "selected" : ""}`} onClick={onSelect}>
      <div className="flight-airline">
        {o.airlineLogo
          ? <img className="airline-logo img" src={o.airlineLogo} alt={o.airline} />
          : <div className="airline-logo">{o.airlineCode}</div>}
        <div>
          <strong>{o.airline}</strong>
          <div className="muted small">{o.flightNumber} · {o.cabin}</div>
        </div>
        <div className="tags">{(o.tags || []).map((t) => <span key={t} className="tag">{t}</span>)}</div>
      </div>
      <div className="flight-route">
        <div><div className="big">{time(o.departureTime)}</div><div className="muted small">{o.origin}</div></div>
        <div className="flight-line">
          <span className="small muted"><Clock size={12} /> {duration(o.durationMinutes)}</span>
          <div className="line"><Plane size={14} /></div>
          <span className="small muted">{o.stops === 0 ? "Directo" : `${o.stops} escala`}</span>
        </div>
        <div><div className="big">{time(o.arrivalTime)}</div><div className="muted small">{o.destination}</div></div>
      </div>
      <div className="flight-price">
        <div className="big">{money(o.totalPrice, o.currency)}</div>
        <div className="muted small">{money(o.pricePerPerson, o.currency)} / persona</div>
        <div className="small">{diff === 0 ? <span className="ok">Mejor precio</span> : <span className="muted">+{money(diff)}</span>}</div>
        <div className="muted small"><Briefcase size={12} /> {o.baggage}</div>
        {onReserve && (
          <button className="btn btn-sm" onClick={(e) => { e.stopPropagation(); onReserve(o); }}>Reservar (simulada)</button>
        )}
      </div>
    </div>
  );
}

function Leg({ title, offers, onReserve }) {
  const [by, setBy] = useState("price");
  const [sel, setSel] = useState(null);
  const sorted = useMemo(() => sortOffers(offers, by), [offers, by]);
  if (!offers?.length) return null;
  const cheapest = Math.min(...offers.map((o) => o.totalPrice));
  return (
    <div className="leg">
      <div className="leg-head">
        <h4>{title}</h4>
        <div className="seg">
          {Object.entries(SORTS).map(([k, l]) => (
            <button key={k} className={by === k ? "active" : ""} onClick={() => setBy(k)}>{l}</button>
          ))}
        </div>
      </div>
      <div className="stack">
        {sorted.map((o) => (
          <FlightCard key={o.offerId + o.departureTime} o={o} cheapest={cheapest} onReserve={onReserve}
                      selected={sel === o.offerId} onSelect={() => setSel(o.offerId)} />
        ))}
      </div>
    </div>
  );
}

/** Tarjetas comparativas de vuelos (Agent-Driven UI: componente "flights"). */
export default function FlightResults({ data, compact }) {
  const [reserve, setReserve] = useState(null);
  if (!data) return null;
  const pax = data.passengers || 1;
  return (
    <div className="card agent-card">
      <div className="card-title">
        <Plane size={18} />
        <span>Vuelos {data.origin?.city} <ArrowRight size={14} /> {data.destination?.city}</span>
        <span className="muted small">· {pax} pasajero{pax > 1 ? "s" : ""}</span>
        {data.simulated
          ? <span className="badge badge-sim" title={data.source}>Fuente simulada</span>
          : <span className="badge badge-conf" title={data.source}>Google Flights · tiempo real</span>}
      </div>
      {data.note && <div className="callout callout-warn">{data.note}</div>}
      {data.cheapestRoundTripTotal && (
        <div className="callout">Ida y regreso más económico para todos: <strong>{money(data.cheapestRoundTripTotal)}</strong></div>
      )}
      <Leg title={`Ida · ${shortDate(data.departureDate)}`} offers={compact ? data.outbound.slice(0, 3) : data.outbound}
           onReserve={(o) => setReserve({ o, pax })} />
      <Leg title={`Regreso · ${shortDate(data.returnDate)}`} offers={compact ? (data.inbound || []).slice(0, 3) : data.inbound}
           onReserve={(o) => setReserve({ o, pax })} />
      {reserve && (
        <ReserveModal
          onClose={() => setReserve(null)}
          initial={{
            type: "FLIGHT",
            title: `Vuelo ${reserve.o.origin} → ${reserve.o.destination} ${reserve.o.airline} ${reserve.o.flightNumber}`,
            provider: reserve.o.airline, startDateTime: reserve.o.departureTime, endDateTime: reserve.o.arrivalTime,
            amount: reserve.o.totalPrice, quantity: reserve.pax,
            details: { flightNumber: reserve.o.flightNumber, origin: reserve.o.origin, destination: reserve.o.destination,
                       baggage: reserve.o.baggage, source: data.source },
          }}
        />
      )}
    </div>
  );
}
