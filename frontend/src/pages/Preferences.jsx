import { Settings2 } from "lucide-react";
import { useEffect, useState } from "react";
import { api, errorText } from "../api/api";
import { Alert, Field, Spinner } from "../components/ui";
import { useApp } from "../state/AppState";

const LISTS = [
  ["activityTypes", "Tipos de actividades", "playa, cultura, gastronomía, aventura"],
  ["dietaryRestrictions", "Restricciones alimentarias", "vegetariano, sin gluten"],
  ["accessibilityNeeds", "Accesibilidad", "movilidad reducida"],
  ["preferredAirlines", "Aerolíneas preferidas", "Avianca, LATAM"],
];

export default function Preferences() {
  const { dataVersion } = useApp();
  const [f, setF] = useState(null);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    api.getPreferences().then((r) => {
      const p = r.preferences || {};
      setF({
        homeCity: p.homeCity || "", budgetPerDay: p.budgetPerDay ?? "", currency: p.currency || "COP",
        travelPace: p.travelPace || "MODERADO", seatPreference: p.seatPreference || "INDIFERENTE", notes: p.notes || "",
        ...Object.fromEntries(LISTS.map(([k]) => [k, (p[k] || []).join(", ")])),
        updatedAt: p.updatedAt,
      });
    }).catch((e) => setErr(errorText(e)));
  }, [dataVersion]);

  if (!f) return <div className="page">{err ? <Alert>{err}</Alert> : <Spinner label="Cargando…" />}</div>;
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  async function save(e) {
    e.preventDefault();
    setErr(""); setMsg("");
    try {
      await api.savePreferences({
        homeCity: f.homeCity || undefined, currency: f.currency, travelPace: f.travelPace, seatPreference: f.seatPreference,
        budgetPerDay: f.budgetPerDay === "" ? undefined : Number(f.budgetPerDay), notes: f.notes || undefined,
        ...Object.fromEntries(LISTS.map(([k]) => [k, f[k].split(",").map((s) => s.trim()).filter(Boolean)])),
      });
      setMsg("Preferencias guardadas. El asistente las tendrá en cuenta en tus próximos planes.");
    } catch (e2) { setErr(errorText(e2)); }
  }

  return (
    <div className="page narrow">
      <header className="page-head"><div><h1><Settings2 size={22} /> Preferencias de viaje</h1>
        <p className="muted">Se guardan en DynamoDB y el Orchestrator las usa al planear.{f.updatedAt && ` Última actualización: ${f.updatedAt.slice(0, 10)}.`}</p></div></header>
      <form className="card form" onSubmit={save}>
        <Alert kind="ok" onClose={() => setMsg("")}>{msg}</Alert>
        <Alert onClose={() => setErr("")}>{err}</Alert>
        <div className="grid3">
          <Field label="Ciudad de origen habitual"><input value={f.homeCity} onChange={set("homeCity")} /></Field>
          <Field label="Presupuesto diario"><input type="number" min="0" value={f.budgetPerDay} onChange={set("budgetPerDay")} /></Field>
          <Field label="Moneda"><select value={f.currency} onChange={set("currency")}><option>COP</option><option>USD</option><option>EUR</option></select></Field>
        </div>
        <div className="grid2">
          <Field label="Ritmo de viaje"><select value={f.travelPace} onChange={set("travelPace")}><option value="RELAJADO">Relajado</option><option value="MODERADO">Moderado</option><option value="INTENSO">Intenso</option></select></Field>
          <Field label="Asiento"><select value={f.seatPreference} onChange={set("seatPreference")}><option value="VENTANA">Ventana</option><option value="PASILLO">Pasillo</option><option value="INDIFERENTE">Indiferente</option></select></Field>
        </div>
        {LISTS.map(([k, label, ph]) => <Field key={k} label={label} hint="Separados por comas"><input value={f[k]} onChange={set(k)} placeholder={ph} /></Field>)}
        <Field label="Otras notas"><textarea rows={3} value={f.notes} onChange={set("notes")} maxLength={1000} /></Field>
        <div className="modal-actions"><button className="btn">Guardar preferencias</button></div>
      </form>
    </div>
  );
}
