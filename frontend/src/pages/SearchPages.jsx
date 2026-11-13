/**
 * Módulos "Consulta de vuelos" e "Información meteorológica".
 * Ambos usan el canal agéntico: el formulario arma la instrucción, el
 * Orchestrator delega en Flight/Weather Agent (MCP) y la UI renderiza el
 * resultado estructurado que llega en el stream.
 */
import { CloudSun, Plane, Search } from "lucide-react";
import { useState } from "react";
import { ChatMessages } from "../components/ChatThread";
import { Field } from "../components/ui";
import { addDays, todayIso } from "../format";
import { useAgentConversation } from "../state/AppState";

export function FlightsPage() {
  const conv = useAgentConversation(null);
  const [f, setF] = useState({ origin: "Bogotá", destination: "Cartagena", dep: addDays(todayIso(), 28), ret: addDays(todayIso(), 31), pax: 3 });
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const submit = (e) => {
    e.preventDefault();
    conv.send(`Busca y compara vuelos de ${f.origin} a ${f.destination}, ida ${f.dep}${f.ret ? ` y regreso ${f.ret}` : " (solo ida)"}, para ${f.pax} pasajero(s). Solo vuelos, no consultes el clima ni crees nada.`);
  };
  return (
    <div className="page">
      <header className="page-head"><div><h1><Plane size={22} /> Consulta de vuelos</h1><p className="muted">Flight Agent · MCP de vuelos</p></div></header>
      <form className="card search-form" onSubmit={submit}>
        <Field label="Origen"><input value={f.origin} onChange={set("origin")} required /></Field>
        <Field label="Destino"><input value={f.destination} onChange={set("destination")} required /></Field>
        <Field label="Ida"><input type="date" min={todayIso()} value={f.dep} onChange={set("dep")} required /></Field>
        <Field label="Regreso"><input type="date" min={f.dep} value={f.ret} onChange={set("ret")} /></Field>
        <Field label="Pasajeros"><input type="number" min="1" max="9" value={f.pax} onChange={set("pax")} /></Field>
        <button className="btn" disabled={conv.busy}><Search size={16} /> {conv.busy ? "Buscando…" : "Buscar"}</button>
      </form>
      <ChatMessages messages={conv.messages.filter((m) => m.role === "assistant").slice(-1)} />
    </div>
  );
}

export function WeatherPage() {
  const conv = useAgentConversation(null);
  const [f, setF] = useState({ city: "Cartagena", start: addDays(todayIso(), 1), end: addDays(todayIso(), 5) });
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const submit = (e) => {
    e.preventDefault();
    conv.send(`¿Cómo estará el clima en ${f.city} del ${f.start} al ${f.end}? Incluye temperatura, condiciones y probabilidad de lluvia por día. Solo clima.`);
  };
  return (
    <div className="page">
      <header className="page-head"><div><h1><CloudSun size={22} /> Información meteorológica</h1><p className="muted">Weather Agent · MCP de clima (Open-Meteo)</p></div></header>
      <form className="card search-form" onSubmit={submit}>
        <Field label="Destino"><input value={f.city} onChange={set("city")} required /></Field>
        <Field label="Desde"><input type="date" value={f.start} onChange={set("start")} required /></Field>
        <Field label="Hasta"><input type="date" min={f.start} value={f.end} onChange={set("end")} required /></Field>
        <button className="btn" disabled={conv.busy}><Search size={16} /> {conv.busy ? "Consultando…" : "Consultar"}</button>
      </form>
      <ChatMessages messages={conv.messages.filter((m) => m.role === "assistant").slice(-1)} />
    </div>
  );
}
