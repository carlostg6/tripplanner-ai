import { Loader2, X } from "lucide-react";
import { useEffect } from "react";

const STATUS = {
  SIMULADA: { label: "Simulada", cls: "badge-sim", title: "Registrada por el sistema sin proveedor externo" },
  PENDIENTE: { label: "Pendiente", cls: "badge-pend", title: "Registrada, a la espera de confirmación" },
  CONFIRMADA: { label: "Confirmada", cls: "badge-conf", title: "Confirmada por un proveedor real" },
};

export function StatusBadge({ status }) {
  const s = STATUS[status] || { label: status, cls: "" };
  return <span className={`badge ${s.cls}`} title={s.title}>{s.label}</span>;
}

export function Spinner({ label }) {
  return <span className="spinner"><Loader2 size={16} className="spin" />{label && <span>{label}</span>}</span>;
}

export function Empty({ icon: Icon, title, children }) {
  return (
    <div className="empty">
      {Icon && <Icon size={32} />}
      <strong>{title}</strong>
      {children && <div className="muted">{children}</div>}
    </div>
  );
}

export function Alert({ kind = "error", children, onClose }) {
  if (!children) return null;
  return (
    <div className={`alert alert-${kind}`} role="alert">
      <span>{children}</span>
      {onClose && <button className="icon-btn" onClick={onClose} aria-label="Cerrar"><X size={14} /></button>}
    </div>
  );
}

export function Modal({ title, onClose, children, wide }) {
  useEffect(() => {
    const k = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [onClose]);
  return (
    <div className="modal-back" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={`modal ${wide ? "modal-wide" : ""}`} role="dialog" aria-modal="true" aria-label={title}>
        <div className="modal-head">
          <h3>{title}</h3>
          <button className="icon-btn" onClick={onClose} aria-label="Cerrar"><X size={18} /></button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function Field({ label, children, hint }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
      {hint && <small className="muted">{hint}</small>}
    </label>
  );
}
