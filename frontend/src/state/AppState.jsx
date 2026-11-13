import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { newSessionId, streamAgent } from "../api/agent";
import { currentSession, signIn as doSignIn, signOut as doSignOut } from "../auth/auth";

const Ctx = createContext(null);
export const useApp = () => useContext(Ctx);

/**
 * Hook genérico para conversar con el Orchestrator por streaming.
 * Cada mensaje del asistente acumula: texto (delta), estados de procesamiento y componentes UI.
 */
export function useAgentConversation(sessionKey) {
  const [messages, setMessages] = useState([]);
  const [busy, setBusy] = useState(false);
  const abortRef = useRef(null);
  const sessionRef = useRef(null);

  if (!sessionRef.current) {
    const stored = sessionKey && localStorage.getItem(sessionKey);
    sessionRef.current = stored || newSessionId();
    if (sessionKey && !stored) localStorage.setItem(sessionKey, sessionRef.current);
  }

  const send = useCallback(async (prompt) => {
    if (!prompt.trim() || busy) return;
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setBusy(true);
    setMessages((m) => [...m, { role: "user", text: prompt }, { role: "assistant", text: "", statuses: [], ui: [], pending: true }]);
    const patch = (fn) => setMessages((m) => {
      const copy = [...m];
      copy[copy.length - 1] = fn({ ...copy[copy.length - 1] });
      return copy;
    });
    await streamAgent({
      prompt,
      sessionId: sessionRef.current,
      signal: ctrl.signal,
      onEvent: (e) => {
        if (e.type === "text") patch((x) => ({ ...x, text: x.text + e.delta }));
        else if (e.type === "status") patch((x) => ({ ...x, statuses: [...x.statuses, e] }));
        else if (e.type === "ui") patch((x) => ({ ...x, ui: [...x.ui, e] }));
        else if (e.type === "error") patch((x) => ({ ...x, error: e.message }));
        else if (e.type === "done") patch((x) => ({ ...x, pending: false }));
      },
    });
    patch((x) => ({ ...x, pending: false }));
    setBusy(false);
  }, [busy]);

  const stop = () => { abortRef.current?.abort(); setBusy(false); };

  const reset = () => {
    stop();
    setMessages([]);
    sessionRef.current = newSessionId();
    if (sessionKey) localStorage.setItem(sessionKey, sessionRef.current);
  };

  return { messages, busy, send, stop, reset, sessionId: sessionRef.current };
}

function ChatHost({ user, children, value }) {
  // El chat principal conserva la sesión del agente entre visitas (memoria de AgentCore).
  const chat = useAgentConversation(`tp_session_${user.sub}`);
  return <Ctx.Provider value={{ ...value, chat }}>{children}</Ctx.Provider>;
}

export function AppProvider({ children }) {
  const [user, setUser] = useState(undefined);
  const [dataVersion, setDataVersion] = useState(0); // fuerza recarga tras cambios del agente

  useEffect(() => { currentSession().then((s) => setUser(s?.user || null)); }, []);

  const value = {
    user,
    signIn: async (email, pwd) => setUser(await doSignIn(email, pwd)),
    signOut: () => { doSignOut(); setUser(null); },
    dataVersion,
    bumpData: () => setDataVersion((v) => v + 1),
  };
  if (!user) return <Ctx.Provider value={{ ...value, chat: null }}>{children}</Ctx.Provider>;
  return <ChatHost key={user.sub} user={user} value={value}>{children}</ChatHost>;
}
