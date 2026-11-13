import { CloudSun, Droplets, Umbrella } from "lucide-react";
import { shortDate } from "../format";

/** Tarjetas meteorológicas por día (Agent-Driven UI: componente "weather"). */
export default function WeatherCards({ data }) {
  if (!data?.days) return null;
  return (
    <div className="card agent-card">
      <div className="card-title">
        <CloudSun size={18} />
        <span>Clima en {data.location?.name}{data.location?.country ? `, ${data.location.country}` : ""}</span>
        <span className="muted small">· {data.source}</span>
      </div>
      {data.note && <div className="callout callout-warn">{data.note}</div>}
      {data.summary && (
        <div className="weather-summary">
          <span>Máx. promedio <strong>{data.summary.avgTempMax ?? "—"} °C</strong></span>
          {data.summary.maxRainProbability != null && <span>Lluvia máx. <strong>{data.summary.maxRainProbability}%</strong></span>}
          <span>Días con lluvia <strong>{data.summary.rainyDays}</strong></span>
        </div>
      )}
      <div className="weather-grid">
        {data.days.map((d) => (
          <div key={d.date} className="weather-day">
            <div className="muted small">{shortDate(d.date)}</div>
            <div className="weather-icon" aria-hidden>{d.icon}</div>
            <div className="small">{d.condition}</div>
            <div className="temps"><strong>{Math.round(d.tempMax)}°</strong><span className="muted"> / {Math.round(d.tempMin)}°</span></div>
            <div className="small rain">
              {d.rainProbability != null
                ? <><Umbrella size={12} /> {d.rainProbability}%</>
                : <><Droplets size={12} /> {d.precipitationMm ?? 0} mm</>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
