import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { NavLink, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { api } from "./api";
import { Perm, RequirePerm } from "./auth";
import { IconSearch } from "./components/icons";
import { useTelemetry } from "./telemetry";
import Alerts from "./pages/Alerts";
import ChangePassword from "./pages/ChangePassword";
import Dashboard from "./pages/Dashboard";
import Favorites from "./pages/Favorites";
import Guide from "./pages/Guide";
import Inventory from "./pages/Inventory";
import Login from "./pages/Login";
import Admin from "./pages/Admin";
import Buyer from "./pages/Buyer";
import Market from "./pages/Market";
import Opportunities from "./pages/Opportunities";
import Recommendations from "./pages/Recommendations";
import Search from "./pages/Search";
import Settings from "./pages/Settings";
import Suppliers from "./pages/Suppliers";
import TenderDetail from "./pages/TenderDetail";

type NavItem = [to: string, label: string, perm?: Perm];

// Barra superior: lo que se usa cada día. Ajustes, guía y administración van en el menú de la cuenta.
const MAIN: NavItem[] = [
  ["/", "Hoy"], ["/search", "Concursos", "search"], ["/market", "Mercado", "suppliers"], ["/favorites", "Seguimiento", "favorites"],
  ["/inventory", "Inventario", "inventory"], ["/alerts", "Alertas", "alerts"],
];
const MOBILE: NavItem[] = [["/", "Hoy"], ["/search", "Concursos", "search"], ["/favorites", "Seguimiento", "favorites"], ["/market", "Mercado", "suppliers"]];

const Logo = () => (
  <div className="flex items-center gap-2.5">
    <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-white font-display text-[13px] font-bold text-brand-700">GC</div>
    <span className="font-display text-[15px] font-semibold tracking-tight text-white">GC Intelligence</span>
  </div>
);

export default function App() {
  const qc = useQueryClient();
  const nav = useNavigate();
  const loc = useLocation();
  const me = useQuery({ queryKey: ["me"], queryFn: () => api("/auth/me"), retry: false });
  useTelemetry(!!me.data && !me.data.must_change_password);  // pantallas vistas y tiempo activo (panel de métricas)
  const perms: string[] = me.data?.permissions ?? [];

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
  const logout = async () => { await api("/auth/logout", { method: "POST" }); qc.clear(); nav("/"); location.reload(); };
  if (u.must_change_password) return <ChangePassword onLogout={logout} />;
  const initials = String(u.org_name ?? u.email ?? "?").split(/\s+/).map((w: string) => w[0]).join("").slice(0, 2).toUpperCase();

  const allowed = (items: NavItem[]) => items.filter(([, , perm]) => !perm || perms.includes(perm));
  const isAdmin = perms.includes("admin");
  const moreItems: NavItem[] = [["/inventory", "Inventario", "inventory"], ["/alerts", "Alertas", "alerts"], ["/settings", "Ajustes"], ["/guide", "Guía"], ...(isAdmin ? [["/admin", "Administración"] as NavItem] : [])];

  return (
    <div className="min-h-screen pb-16 md:pb-0">
      {/* Barra superior */}
      <header className="sticky top-0 z-20 bg-brand-700 shadow-sm">
        <div className="mx-auto flex h-14 max-w-[1240px] items-center gap-4 px-4 sm:px-8">
          <NavLink to="/" aria-label="Inicio"><Logo /></NavLink>
          <nav aria-label="Principal" className="ml-4 hidden items-center gap-1 md:flex">
            {allowed(MAIN).map(([to, label]) => (
              <NavLink key={to} to={to} end={to === "/"} className={({ isActive }) => `topnav-link ${isActive ? "is-active" : ""}`}>{label}</NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <button type="button" onClick={() => nav("/search", { state: { focus: Date.now() } })} aria-label="Buscar (⌘K)"
              className="flex min-h-9 items-center gap-2 rounded-lg bg-white/10 px-3 text-[13px] text-white/90 hover:bg-white/20">
              <IconSearch size={15} /><span className="hidden sm:inline">Buscar</span><kbd className="hidden rounded border border-white/30 px-1.5 font-sans text-[11px] sm:inline">⌘K</kbd>
            </button>
            <AccountMenu initials={initials} user={u} items={moreItems} onLogout={logout} perms={perms} />
          </div>
        </div>
      </header>

      <main className="min-w-0 px-4 pb-16 pt-6 sm:px-8 md:pt-8">
        <div className="mx-auto flex max-w-[1240px] flex-col gap-6">
          {u.demo && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-center text-xs text-amber-900">
              Modo demo: los datos son sintéticos y no provienen de Guatecompras.
            </div>
          )}
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/search" element={<RequirePerm perm="search"><Search /></RequirePerm>} />
            <Route path="/tenders/:nog" element={<RequirePerm perm="search"><TenderDetail /></RequirePerm>} />
            <Route path="/recommendations" element={<RequirePerm perm="recommendations"><Recommendations /></RequirePerm>} />
            <Route path="/opportunities" element={<RequirePerm perm="opportunities"><Opportunities /></RequirePerm>} />
            <Route path="/inventory" element={<RequirePerm perm="inventory"><Inventory /></RequirePerm>} />
            <Route path="/favorites" element={<RequirePerm perm="favorites"><Favorites /></RequirePerm>} />
            <Route path="/alerts" element={<RequirePerm perm="alerts"><Alerts /></RequirePerm>} />
            <Route path="/market" element={<RequirePerm perm="suppliers"><Market /></RequirePerm>} />
            <Route path="/suppliers" element={<RequirePerm perm="suppliers"><Suppliers /></RequirePerm>} />
            <Route path="/suppliers/:sid" element={<RequirePerm perm="suppliers"><Suppliers /></RequirePerm>} />
            <Route path="/buyers" element={<RequirePerm perm="search"><Buyer /></RequirePerm>} />
            <Route path="/guide" element={<Guide />} />
            <Route path="/admin" element={<RequirePerm perm="admin"><Admin /></RequirePerm>} />
            <Route path="/users" element={<Navigate to="/admin?tab=usuarios" replace />} />
            <Route path="/metrics" element={<Navigate to="/admin?tab=uso" replace />} />
            <Route path="/settings" element={<Settings user={u} />} />
            <Route path="*" element={<Navigate to="/" />} />
          </Routes>
        </div>
      </main>

      {/* Barra inferior (móvil) */}
      <nav aria-label="Principal" className="fixed inset-x-0 bottom-0 z-20 grid grid-cols-5 border-t border-stone-200 bg-white md:hidden">
        {allowed(MOBILE).map(([to, label]) => (
          <NavLink key={to} to={to} end={to === "/"} className={({ isActive }) => `flex min-h-14 items-center justify-center text-[12px] font-medium ${isActive ? "text-brand-700" : "text-stone-600"}`}>{label}</NavLink>
        ))}
        <MoreMenu items={allowed(moreItems)} />
      </nav>
    </div>
  );
}

function AccountMenu({ initials, user, items, onLogout, perms }: { initials: string; user: any; items: NavItem[]; onLogout: () => void; perms: string[] }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const close = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);
  const links = items.filter(([to, , perm]) => ["/settings", "/guide", "/admin"].includes(to) && (!perm || perms.includes(perm)));
  return (
    <div ref={ref} className="relative">
      <button type="button" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen(!open)}
        className="flex h-9 w-9 items-center justify-center rounded-full bg-white text-[13px] font-semibold text-brand-800" aria-label="Cuenta">{initials}</button>
      {open && (
        <div role="menu" className="absolute right-0 top-11 z-30 flex w-56 flex-col rounded-xl border border-stone-200 bg-white p-1.5 text-[13px] shadow-lg">
          <div className="truncate px-3 py-2 text-xs text-stone-600">{user.org_name}</div>
          {links.map(([to, label]) => (
            <NavLink key={to} to={to} role="menuitem" onClick={() => setOpen(false)} className="rounded-lg px-3 py-2 text-zinc-900 hover:bg-stone-100">{label}</NavLink>
          ))}
          <button type="button" role="menuitem" onClick={onLogout} className="rounded-lg px-3 py-2 text-left text-zinc-900 hover:bg-stone-100">Cerrar sesión</button>
        </div>
      )}
    </div>
  );
}

function MoreMenu({ items }: { items: NavItem[] }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative flex">
      <button type="button" aria-expanded={open} onClick={() => setOpen(!open)} className="flex min-h-14 flex-1 items-center justify-center text-[12px] font-medium text-stone-600">Más</button>
      {open && (
        <div role="menu" className="absolute bottom-14 right-2 flex w-48 flex-col rounded-xl border border-stone-200 bg-white p-1.5 text-[13px] shadow-lg">
          {items.map(([to, label]) => <NavLink key={to} to={to} role="menuitem" onClick={() => setOpen(false)} className="rounded-lg px-3 py-2.5 text-zinc-900 hover:bg-stone-100">{label}</NavLink>)}
        </div>
      )}
    </div>
  );
}
