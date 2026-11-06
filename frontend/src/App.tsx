import { useQuery, useQueryClient } from "@tanstack/react-query";
import { NavLink, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { api } from "./api";
import { Loading } from "./components/ui";
import Alerts from "./pages/Alerts";
import Dashboard from "./pages/Dashboard";
import Favorites from "./pages/Favorites";
import Inventory from "./pages/Inventory";
import Login from "./pages/Login";
import Opportunities from "./pages/Opportunities";
import Recommendations from "./pages/Recommendations";
import Search from "./pages/Search";
import Settings from "./pages/Settings";
import Suppliers from "./pages/Suppliers";
import TenderDetail from "./pages/TenderDetail";

const NAV = [
  ["/", "Resumen"], ["/search", "Buscar"], ["/recommendations", "Para ti"], ["/opportunities", "Oportunidades"],
  ["/inventory", "Inventario"], ["/favorites", "Favoritos"], ["/alerts", "Alertas"], ["/suppliers", "Proveedores"], ["/settings", "Ajustes"],
] as const;

export default function App() {
  const qc = useQueryClient();
  const nav = useNavigate();
  const me = useQuery({ queryKey: ["me"], queryFn: () => api("/auth/me"), retry: false });
  if (me.isLoading) return <Loading />;
  if (!me.data) return <Login />;
  const u = me.data;
  return (
    <div className="mx-auto max-w-6xl px-4 pb-16">
      {u.demo && (
        <div className="mt-2 rounded-lg bg-amber-100 px-3 py-1.5 text-center text-xs text-amber-900 dark:bg-amber-900/40 dark:text-amber-200">
          Modo demo: los datos son sintéticos y no provienen de Guatecompras.
        </div>
      )}
      <header className="flex flex-wrap items-center gap-x-4 gap-y-2 py-3">
        <div className="font-semibold">GC Intelligence</div>
        <nav className="flex flex-1 flex-wrap gap-1 text-sm">
          {NAV.map(([to, label]) => (
            <NavLink key={to} to={to} end={to === "/"}
              className={({ isActive }) => `rounded-lg px-2.5 py-1 ${isActive ? "bg-brand-500 text-white" : "hover:bg-slate-200 dark:hover:bg-slate-800"}`}>
              {label}
            </NavLink>
          ))}
        </nav>
        <button className="btn" onClick={async () => { await api("/auth/logout", { method: "POST" }); qc.clear(); nav("/"); location.reload(); }}>
          Salir
        </button>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/search" element={<Search />} />
          <Route path="/tenders/:nog" element={<TenderDetail />} />
          <Route path="/recommendations" element={<Recommendations />} />
          <Route path="/opportunities" element={<Opportunities />} />
          <Route path="/inventory" element={<Inventory />} />
          <Route path="/favorites" element={<Favorites />} />
          <Route path="/alerts" element={<Alerts />} />
          <Route path="/suppliers" element={<Suppliers />} />
          <Route path="/suppliers/:sid" element={<Suppliers />} />
          <Route path="/settings" element={<Settings user={u} />} />
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </main>
    </div>
  );
}
