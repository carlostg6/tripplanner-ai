import React from "react";
import ReactDOM from "react-dom/client";
import { HashRouter, Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { Spinner } from "./components/ui";
import Assistant from "./pages/Assistant";
import AuthPage from "./pages/AuthPage";
import Dashboard from "./pages/Dashboard";
import Preferences from "./pages/Preferences";
import Reservations from "./pages/Reservations";
import { FlightsPage, WeatherPage } from "./pages/SearchPages";
import TripDetail from "./pages/TripDetail";
import Trips from "./pages/Trips";
import { AppProvider, useApp } from "./state/AppState";
import "./styles.css";

function Root() {
  const { user } = useApp();
  if (user === undefined) return <div className="center-screen"><Spinner label="Cargando TripPlanner…" /></div>;
  if (!user) return <AuthPage />;
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="asistente" element={<Assistant />} />
        <Route path="vuelos" element={<FlightsPage />} />
        <Route path="clima" element={<WeatherPage />} />
        <Route path="viajes" element={<Trips />} />
        <Route path="viajes/:tripId" element={<TripDetail />} />
        <Route path="reservas" element={<Reservations />} />
        <Route path="preferencias" element={<Preferences />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <AppProvider>
      <HashRouter><Root /></HashRouter>
    </AppProvider>
  </React.StrictMode>,
);
