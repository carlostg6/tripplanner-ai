import { Plane } from "lucide-react";
import { useState } from "react";
import { confirmSignUp, signUp } from "../auth/auth";
import { Alert, Field } from "../components/ui";
import { config } from "../config";
import { useApp } from "../state/AppState";

export default function AuthPage() {
  const { signIn } = useApp();
  const [mode, setMode] = useState("login");
  const [f, setF] = useState({ email: "", password: "", name: "", code: "" });
  const [err, setErr] = useState("");
  const [info, setInfo] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    setErr(""); setBusy(true);
    try {
      if (mode === "login") await signIn(f.email, f.password);
      else if (mode === "signup") {
        await signUp(f.email, f.password, f.name);
        setInfo("Te enviamos un código de verificación al correo.");
        setMode("confirm");
      } else {
        await confirmSignUp(f.email, f.code);
        await signIn(f.email, f.password);
      }
    } catch (e2) {
      const m = e2?.code === "NotAuthorizedException" ? "Correo o contraseña incorrectos."
        : e2?.code === "UserNotConfirmedException" ? (setMode("confirm"), "Confirma tu correo con el código recibido.")
        : e2?.code === "InvalidPasswordException" ? "La contraseña necesita 8+ caracteres, mayúscula, minúscula y número."
        : e2?.code === "UsernameExistsException" ? "Ya existe una cuenta con ese correo."
        : e2?.message || "No fue posible continuar.";
      setErr(m);
    } finally { setBusy(false); }
  }

  return (
    <div className="auth">
      <div className="auth-hero">
        <div className="brand-logo big"><Plane size={28} /></div>
        <h1>TripPlanner AI</h1>
        <p>Planifica, organiza y gestiona tus viajes con un equipo de agentes: Orchestrator, Flight y Weather.</p>
        <ul>
          <li>✈️ Vuelos comparados al instante</li>
          <li>🌤️ Clima por día en tu destino</li>
          <li>🗓️ Itinerarios y reservas guardados</li>
        </ul>
      </div>
      <form className="auth-card" onSubmit={submit}>
        <h2>{mode === "login" ? "Ingresar" : mode === "signup" ? "Crear cuenta" : "Verificar correo"}</h2>
        {config.mock && <Alert kind="info">Modo demo local: cualquier correo y contraseña funcionan.</Alert>}
        <Alert kind="info">{info}</Alert>
        <Alert onClose={() => setErr("")}>{err}</Alert>
        {mode === "signup" && <Field label="Nombre"><input value={f.name} onChange={set("name")} required /></Field>}
        <Field label="Correo"><input type="email" value={f.email} onChange={set("email")} required autoComplete="email" /></Field>
        {mode !== "confirm" && (
          <Field label="Contraseña"><input type="password" value={f.password} onChange={set("password")} required minLength={8} autoComplete={mode === "login" ? "current-password" : "new-password"} /></Field>
        )}
        {mode === "confirm" && <Field label="Código de verificación"><input value={f.code} onChange={set("code")} required /></Field>}
        <button className="btn btn-block" disabled={busy}>{busy ? "Procesando…" : mode === "login" ? "Ingresar" : mode === "signup" ? "Registrarme" : "Verificar"}</button>
        <div className="small center">
          {mode === "login"
            ? <>¿No tienes cuenta? <button type="button" className="link" onClick={() => setMode("signup")}>Regístrate</button></>
            : <>¿Ya tienes cuenta? <button type="button" className="link" onClick={() => setMode("login")}>Ingresa</button></>}
        </div>
      </form>
    </div>
  );
}
