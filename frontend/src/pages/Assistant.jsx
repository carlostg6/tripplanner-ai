import { Bot, RotateCcw } from "lucide-react";
import { useEffect, useRef } from "react";
import { ChatInput, ChatMessages } from "../components/ChatThread";
import { useApp } from "../state/AppState";

const SUGGESTIONS = [
  "Quiero organizar unas vacaciones de cuatro días en Cartagena. Salgo desde Bogotá, viajo con dos personas más y tengo un presupuesto de 5 millones de pesos. Quiero conocer el clima, encontrar vuelos y organizar algunas actividades turísticas.",
  "Crea el viaje con el vuelo más económico, genera el itinerario y registra la reserva.",
  "Muéstrame mis viajes guardados",
  "¿Qué reservas tengo pendientes?",
];

export default function Assistant() {
  const { chat, bumpData } = useApp();
  const wasBusy = useRef(false);

  // Cuando el agente termina, refrescamos las vistas de negocio (pudo crear viajes/reservas).
  useEffect(() => {
    if (wasBusy.current && !chat.busy) bumpData();
    wasBusy.current = chat.busy;
  }, [chat.busy]); // eslint-disable-line

  return (
    <div className="page chat-page">
      <header className="page-head">
        <div>
          <h1>Asistente de viajes</h1>
          <p className="muted small">Orchestrator Agent · Flight Agent (MCP) · Weather Agent (MCP) · Tools de negocio — HTTP streaming</p>
        </div>
        <button className="btn btn-ghost btn-sm" onClick={chat.reset} title="Nueva conversación"><RotateCcw size={14} /> Nueva conversación</button>
      </header>
      {chat.messages.length === 0 ? (
        <div className="chat-empty">
          <Bot size={40} />
          <h3>¿A dónde quieres ir?</h3>
          <p className="muted">Cuéntame tu plan: origen, destino, días, número de viajeros y presupuesto.</p>
          <div className="suggestions">
            {SUGGESTIONS.map((s) => <button key={s} className="suggestion" onClick={() => chat.send(s)}>{s}</button>)}
          </div>
        </div>
      ) : (
        <ChatMessages messages={chat.messages} />
      )}
      <ChatInput onSend={chat.send} busy={chat.busy} onStop={chat.stop} placeholder="Ej: Quiero ir 4 días a Cartagena desde Bogotá con 2 personas más…" />
    </div>
  );
}
