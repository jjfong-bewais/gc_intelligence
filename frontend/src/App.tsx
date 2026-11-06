import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { NavLink, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { api } from "./api";
import { IconLogout, IconSearch } from "./components/icons";
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

const GROUPS: { title: string; items: [string, string][] }[] = [
  { title: "Descubrir", items: [["/", "Resumen"], ["/search", "Buscar"], ["/recommendations", "Para ti"], ["/opportunities", "Oportunidades"]] },
  { title: "Mi trabajo", items: [["/favorites", "Seguimiento"], ["/inventory", "Inventario"], ["/alerts", "Alertas"]] },
  { title: "Mercado", items: [["/suppliers", "Proveedores"]] },
];

const linkCls = ({ isActive }: { isActive: boolean }) =>
  `flex min-h-9 shrink-0 items-center rounded-lg px-2.5 text-sm transition-colors ${isActive ? "bg-stone-100 font-medium text-zinc-900" : "text-stone-700 hover:bg-stone-50 hover:text-zinc-900"}`;

const Logo = () => (
  <div className="flex items-center gap-2.5">
    <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-zinc-900 text-[13px] font-semibold text-white">GC</div>
    <span className="text-[15px] font-semibold tracking-tight">GC Intelligence</span>
  </div>
);

export default function App() {
  const qc = useQueryClient();
  const nav = useNavigate();
  const loc = useLocation();
  const me = useQuery({ queryKey: ["me"], queryFn: () => api("/auth/me"), retry: false });

  // ⌘K / Ctrl+K abre la búsqueda desde cualquier pantalla.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); nav("/search", { state: { focus: Date.now() } }); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [nav]);

  useEffect(() => { window.scrollTo(0, 0); }, [loc.pathname]);

  if (me.isLoading) return <div className="flex min-h-screen items-center justify-center"><div className="h-6 w-6 animate-spin rounded-full border-2 border-stone-200 border-t-zinc-900" aria-label="Cargando" /></div>;
  if (!me.data) return <Login />;
  const u = me.data;
  const initials = String(u.org_name ?? u.email ?? "?").split(/\s+/).map((w: string) => w[0]).join("").slice(0, 2).toUpperCase();
  const logout = async () => { await api("/auth/logout", { method: "POST" }); qc.clear(); nav("/"); location.reload(); };

  return (
    <div className="min-h-screen md:flex">
      {/* Barra lateral (escritorio) */}
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col gap-6 overflow-y-auto border-r border-stone-200 bg-white px-4 py-6 md:flex">
        <div className="px-2"><Logo /></div>
        <button type="button" onClick={() => nav("/search", { state: { focus: Date.now() } })}
          className="flex min-h-9 items-center gap-2 rounded-lg border border-stone-200 px-2.5 text-[13px] text-stone-600 hover:bg-stone-50">
          <IconSearch size={15} /><span className="flex-1 text-left">Buscar…</span>
          <kbd className="rounded border border-stone-200 px-1.5 font-sans text-[11px]">⌘K</kbd>
        </button>
        <nav aria-label="Principal" className="flex flex-col gap-5">
          {GROUPS.map((g) => (
            <div key={g.title} className="flex flex-col gap-0.5">
              <div className="eyebrow px-2.5 pb-1.5">{g.title}</div>
              {g.items.map(([to, label]) => <NavLink key={to} to={to} end={to === "/"} className={linkCls}>{label}</NavLink>)}
            </div>
          ))}
        </nav>
        <div className="mt-auto flex items-center gap-2.5 border-t border-stone-200 px-1 pt-4">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand-100 text-[13px] font-semibold text-brand-800">{initials}</div>
          <div className="flex min-w-0 flex-1 flex-col">
            <span className="truncate text-[13px] font-medium">{u.org_name}</span>
            <NavLink to="/settings" className="text-xs text-stone-600 hover:text-zinc-900">Ajustes</NavLink>
          </div>
          <button type="button" onClick={logout} aria-label="Cerrar sesión" title="Cerrar sesión" className="btn-icon border-transparent"><IconLogout /></button>
        </div>
      </aside>

      {/* Barra superior (móvil) */}
      <header className="sticky top-0 z-10 flex flex-col gap-2 border-b border-stone-200 bg-white/90 px-4 pb-2 pt-3 backdrop-blur md:hidden">
        <div className="flex items-center justify-between">
          <Logo />
          <button type="button" onClick={logout} aria-label="Cerrar sesión" className="btn-icon border-transparent"><IconLogout /></button>
        </div>
        <nav aria-label="Principal" className="-mx-1 flex gap-1 overflow-x-auto pb-1">
          {[...GROUPS.flatMap((g) => g.items), ["/settings", "Ajustes"]].map(([to, label]) => (
            <NavLink key={to} to={to} end={to === "/"} className={linkCls}>{label}</NavLink>
          ))}
        </nav>
      </header>

      <main className="min-w-0 flex-1 px-4 pb-16 pt-6 sm:px-8 md:pt-8 lg:px-12">
        <div className="mx-auto flex max-w-[1040px] flex-col gap-6">
          {u.demo && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-center text-xs text-amber-900">
              Modo demo: los datos son sintéticos y no provienen de Guatecompras.
            </div>
          )}
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
        </div>
      </main>
    </div>
  );
}
