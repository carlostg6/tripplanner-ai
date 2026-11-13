import { CloudSun, LayoutDashboard, LogOut, Luggage, MessageCircle, Plane, Settings2, Ticket } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";
import { config } from "../config";
import { useApp } from "../state/AppState";

const NAV = [
  ["/", "Dashboard", LayoutDashboard],
  ["/asistente", "Asistente", MessageCircle],
  ["/vuelos", "Vuelos", Plane],
  ["/clima", "Clima", CloudSun],
  ["/viajes", "Mis viajes", Luggage],
  ["/reservas", "Reservas", Ticket],
  ["/preferencias", "Preferencias", Settings2],
];

export default function Layout() {
  const { user, signOut, chat } = useApp();
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-logo"><Plane size={18} /></div>
          <div><strong>TripPlanner AI</strong><div className="small">Your AI Travel Companion</div></div>
        </div>
        <nav>
          {NAV.map(([to, label, Icon]) => (
            <NavLink key={to} to={to} end={to === "/"} className={({ isActive }) => (isActive ? "active" : "")}>
              <Icon size={18} /> <span>{label}</span>
              {to === "/asistente" && chat?.busy && <span className="dot" title="El asistente está trabajando" />}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-foot">
          {config.mock && <div className="badge badge-sim">Modo demo local</div>}
          <div className="small">{user?.name}<div className="muted">{user?.email}</div></div>
          <button className="btn btn-ghost btn-sm" onClick={signOut}><LogOut size={14} /> Salir</button>
        </div>
      </aside>
      <main className="main"><Outlet /></main>
    </div>
  );
}
