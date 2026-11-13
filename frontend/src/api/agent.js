/**
 * Canal 2 · Interacción agéntica: Frontend → HTTP streaming → AgentCore → Orchestrator.
 * No pasa por API Gateway. Se envía el access token de Cognito, que valida el
 * customJWTAuthorizer del runtime, y un session id estable (≥33 caracteres).
 *
 * Eventos (SSE `data: {...}`): start | status | text | ui | error | done
 */
import { getAccessToken } from "../auth/auth";
import { agentInvocationUrl, config } from "../config";
import { mockAgentStream } from "../mock/mockAgent";

export function newSessionId() {
  return `tp-${crypto.randomUUID()}-${Date.now()}`; // > 33 caracteres
}

export function parseSSEChunk(buffer, onEvent) {
  const parts = buffer.split(/\r?\n\r?\n/);
  const rest = parts.pop();
  for (const part of parts) {
    const data = part
      .split(/\r?\n/)
      .filter((l) => l.startsWith("data:"))
      .map((l) => l.slice(5).replace(/^ /, ""))
      .join("\n");
    if (!data) continue;
    try {
      const evt = JSON.parse(data);
      onEvent(typeof evt === "string" ? { type: "text", delta: evt } : evt);
    } catch {
      onEvent({ type: "text", delta: data });
    }
  }
  return rest;
}

export async function streamAgent({ prompt, sessionId, onEvent, signal }) {
  if (config.mock) return mockAgentStream(prompt, onEvent, signal);
  const token = await getAccessToken();
  let res;
  try {
    res = await fetch(agentInvocationUrl(), {
      method: "POST",
      signal,
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        Accept: "text/event-stream",
        "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": sessionId,
      },
      body: JSON.stringify({ prompt }),
    });
  } catch (e) {
    if (e.name === "AbortError") return;
    onEvent({ type: "error", message: "No fue posible conectar con el asistente." });
    return onEvent({ type: "done" });
  }
  if (!res.ok) {
    const msg = res.status === 401 || res.status === 403
      ? "No autorizado para usar el asistente. Ingresa de nuevo."
      : `El asistente respondió con error ${res.status}.`;
    onEvent({ type: "error", message: msg });
    return onEvent({ type: "done" });
  }
  const ctype = res.headers.get("content-type") || "";
  if (!ctype.includes("text/event-stream")) {
    const body = await res.text();
    try {
      const j = JSON.parse(body);
      onEvent({ type: "text", delta: typeof j === "string" ? j : j.result || j.message || body });
    } catch {
      onEvent({ type: "text", delta: body });
    }
    return onEvent({ type: "done" });
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let sawDone = false;
  const wrapped = (e) => {
    if (e.type === "done") sawDone = true;
    onEvent(e);
  };
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer = parseSSEChunk(buffer + decoder.decode(value, { stream: true }), wrapped);
    }
    parseSSEChunk(buffer + "\n\n", wrapped);
  } catch (e) {
    if (e.name !== "AbortError") wrapped({ type: "error", message: "Se interrumpió la conexión con el asistente." });
  }
  if (!sawDone) onEvent({ type: "done" });
}
