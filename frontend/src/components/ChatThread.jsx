import { Bot, CheckCircle2, Loader2, Square, User } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import AgentRenderer from "./AgentRenderer";

function Statuses({ statuses, pending }) {
  if (!statuses?.length) return pending ? <div className="status-line"><Loader2 size={14} className="spin" /> Orchestrator interpretando tu solicitud…</div> : null;
  return (
    <div className="statuses">
      {statuses.map((s, i) => {
        const last = i === statuses.length - 1 && pending;
        return (
          <div key={i} className={`status-line ${last ? "active" : ""}`}>
            {last ? <Loader2 size={14} className="spin" /> : <CheckCircle2 size={14} />}
            <span className="status-agent">{s.agent}</span> {s.message}
          </div>
        );
      })}
    </div>
  );
}

export function ChatMessages({ messages }) {
  const end = useRef(null);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [messages]);
  return (
    <div className="chat-msgs">
      {messages.map((m, i) =>
        m.role === "user" ? (
          <div key={i} className="msg msg-user"><div className="bubble">{m.text}</div><div className="avatar"><User size={16} /></div></div>
        ) : (
          <div key={i} className="msg msg-bot">
            <div className="avatar bot"><Bot size={16} /></div>
            <div className="msg-body">
              <Statuses statuses={m.statuses} pending={m.pending} />
              {m.ui.map((e, j) => <AgentRenderer key={j} event={e} />)}
              {m.text && <div className="bubble md"><ReactMarkdown>{m.text}</ReactMarkdown>{m.pending && <span className="caret" />}</div>}
              {m.error && <div className="alert alert-error">{m.error}</div>}
            </div>
          </div>
        ),
      )}
      <div ref={end} />
    </div>
  );
}

export function ChatInput({ onSend, busy, onStop, placeholder }) {
  const [v, setV] = useState("");
  const submit = (e) => {
    e.preventDefault();
    if (!v.trim()) return;
    onSend(v.trim());
    setV("");
  };
  return (
    <form className="chat-input" onSubmit={submit}>
      <textarea
        rows={2} value={v} maxLength={4000} placeholder={placeholder || "Escribe tu mensaje…"}
        onChange={(e) => setV(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) submit(e); }}
      />
      {busy
        ? <button type="button" className="btn btn-ghost" onClick={onStop}><Square size={14} /> Detener</button>
        : <button className="btn" disabled={!v.trim()}>Enviar</button>}
    </form>
  );
}
