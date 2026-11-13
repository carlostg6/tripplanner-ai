import { describe, expect, it } from "vitest";
import { parseSSEChunk } from "./api/agent";

describe("parseSSEChunk", () => {
  it("parsea eventos completos y conserva el resto", () => {
    const out = [];
    const rest = parseSSEChunk('data: {"type":"text","delta":"Hola"}\n\ndata: {"type":"ui","component":"flights","data":{}}\n\ndata: {"ty', (e) => out.push(e));
    expect(out.map((e) => e.type)).toEqual(["text", "ui"]);
    expect(rest).toBe('data: {"ty');
    parseSSEChunk(rest + 'pe":"done"}\n\n', (e) => out.push(e));
    expect(out.at(-1).type).toBe("done");
  });
  it("acepta strings JSON y CRLF", () => {
    const out = [];
    parseSSEChunk('data: "texto"\r\n\r\n', (e) => out.push(e));
    expect(out[0]).toEqual({ type: "text", delta: "texto" });
  });
});
