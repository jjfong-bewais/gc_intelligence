import { useQuery } from "@tanstack/react-query";
import { ReactNode, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import { Empty, ErrorBox, Kpi, KpiStrip, Loading, Page, Section, Segmented } from "../components/ui";
import { dateTime, num } from "../format";

/* Panel de métricas de uso (solo administradores). Un color por medida; las series de una sola medida no llevan leyenda. */
const BLUE = "#2a78d6";
const TABS = [["overview", "Resumen"], ["users", "Usuarios"], ["features", "Funcionalidades"], ["searches", "Búsquedas"], ["health", "Salud"]] as const;
type Tab = (typeof TABS)[number][0];
const DAY_NAMES = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];

const dur = (s: number | null | undefined) => {
  if (s == null) return "—";
  if (s < 60) return `${Math.round(s)} s`;
  const m = Math.floor(s / 60);
  return m < 60 ? `${m} min ${Math.round(s % 60)} s` : `${Math.floor(m / 60)} h ${m % 60} min`;
};
const pct = (v: number | null | undefined) => (v == null ? "—" : `${Math.round(v * 100)}%`);
const shortDay = (d: string) => d.slice(5).replace("-", "/");

function useMetric<T = any>(path: string, days: number, admins: boolean, enabled = true) {
  const qs = `days=${days}&exclude_admins=${!admins}`;
  return useQuery<T>({ queryKey: ["metrics", path, qs], queryFn: () => api<T>(`/admin/metrics/${path}${path.includes("?") ? "&" : "?"}${qs}`), enabled, placeholderData: (p) => p });
}

export default function Metrics() {
  const [tab, setTab] = useState<Tab>("overview");
  const [days, setDays] = useState(30);
  const [admins, setAdmins] = useState(false);
  return (
    <Page title="Métricas de uso" subtitle="Qué hacen los usuarios dentro de la herramienta. Se conservan 90 días. Los administradores no cuentan, salvo que lo actives."
      actions={<>
        <Segmented label="Periodo" value={String(days) as "7" | "30" | "90"} onChange={(v) => setDays(Number(v))} options={[["7", "7 días"], ["30", "30 días"], ["90", "90 días"]]} />
        <label className="flex min-h-9 items-center gap-2 text-[13px] text-stone-700">
          <input type="checkbox" checked={admins} onChange={(e) => setAdmins(e.target.checked)} />Incluir administradores
        </label>
      </>}>
      <div className="-mt-2 overflow-x-auto"><Segmented label="Sección" value={tab} onChange={setTab} options={TABS} /></div>
      {tab === "overview" && <Overview days={days} admins={admins} />}
      {tab === "users" && <Users days={days} admins={admins} />}
      {tab === "features" && <Features days={days} admins={admins} />}
      {tab === "searches" && <Searches days={days} admins={admins} />}
      {tab === "health" && <Health days={days} admins={admins} />}
    </Page>
  );
}

/* ───────────────────────── piezas comunes ───────────────────────── */
function Gate({ q, children }: { q: { isLoading: boolean; error: unknown; data?: any; isFetching?: boolean }; children: (d: any) => ReactNode }) {
  if (q.isLoading) return <Loading rows={3} />;
  if (q.error) return <ErrorBox error={q.error} />;
  return <div className={`flex flex-col gap-8 transition-opacity ${q.isFetching ? "opacity-60" : ""}`}>{children(q.data)}</div>;
}

function ChartCard({ title, hint, data, cols, children }: { title: string; hint?: string; data: any[]; cols: [key: string, label: string][]; children: ReactNode }) {
  return (
    <div className="card flex flex-col gap-3">
      <div><h3 className="text-sm font-semibold">{title}</h3>{hint && <p className="text-xs text-stone-600">{hint}</p>}</div>
      <div className="h-[200px]" role="img" aria-label={title}>{children}</div>
      <details className="text-xs text-stone-600">
        <summary className="cursor-pointer select-none">Ver como tabla</summary>
        <div className="mt-2 max-h-56 overflow-auto">
          <table className="w-full text-left"><thead><tr>{cols.map(([k, l]) => <th key={k} className="py-1 pr-3 font-medium">{l}</th>)}</tr></thead>
            <tbody>{data.map((r, i) => <tr key={i} className="border-t border-stone-100">{cols.map(([k]) => <td key={k} className="py-1 pr-3 tabular-nums">{r[k]}</td>)}</tr>)}</tbody></table>
        </div>
      </details>
    </div>
  );
}

const axis = { fontSize: 11, fill: "#78716c" };
const grid = <CartesianGrid stroke="#e7e5e4" strokeDasharray="3 3" vertical={false} />;
const tip = (unit: string) => <Tooltip cursor={{ stroke: "#d6d3d1" }} contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e7e5e4" }} formatter={(v: any) => [`${v} ${unit}`.trim(), ""]} separator="" labelFormatter={(l) => String(l)} />;

function DayLine({ data, k, unit, name }: { data: any[]; k: string; unit: string; name: string }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: -18 }}>
        {grid}<XAxis dataKey="day" tickFormatter={shortDay} tick={axis} tickLine={false} axisLine={{ stroke: "#d6d3d1" }} minTickGap={24} />
        <YAxis tick={axis} tickLine={false} axisLine={false} allowDecimals={false} />
        {tip(unit)}<Line type="monotone" dataKey={k} stroke={BLUE} strokeWidth={2} dot={false} activeDot={{ r: 4, stroke: "#fff", strokeWidth: 2 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}
function DayBars({ data, k, unit, name }: { data: any[]; k: string; unit: string; name: string }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: -18 }}>
        {grid}<XAxis dataKey="day" tickFormatter={shortDay} tick={axis} tickLine={false} axisLine={{ stroke: "#d6d3d1" }} minTickGap={24} />
        <YAxis tick={axis} tickLine={false} axisLine={false} />
        {tip(unit)}<Bar dataKey={k} fill={BLUE} radius={[4, 4, 0, 0]} maxBarSize={18} />
      </BarChart>
    </ResponsiveContainer>
  );
}

/** Barra horizontal de una sola medida con su valor al lado. */
function HBar({ label, value, max, right, sub }: { label: ReactNode; value: number; max: number; right?: ReactNode; sub?: ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-baseline justify-between gap-3 text-[13px]"><span className="truncate font-medium">{label}</span><span className="shrink-0 tabular-nums text-stone-700">{right ?? num(value)}</span></div>
      <div className="h-2 rounded-full bg-stone-100"><div className="h-2 rounded-full" style={{ width: `${Math.max(value ? 2 : 0, (value / (max || 1)) * 100)}%`, background: BLUE }} /></div>
      {sub && <div className="text-xs text-stone-600">{sub}</div>}
    </div>
  );
}

function Table({ cols, rows, onRow, empty = "Sin datos en este periodo." }: { cols: { key: string; label: string; align?: "right"; render?: (r: any) => ReactNode; sort?: boolean }[]; rows: any[]; onRow?: (r: any) => void; empty?: string }) {
  const [sort, setSort] = useState<{ key: string; dir: 1 | -1 } | null>(null);
  const sorted = useMemo(() => {
    if (!sort) return rows;
    return [...rows].sort((a, b) => ((a[sort.key] ?? -1) > (b[sort.key] ?? -1) ? 1 : (a[sort.key] ?? -1) < (b[sort.key] ?? -1) ? -1 : 0) * sort.dir);
  }, [rows, sort]);
  if (!rows.length) return <Empty>{empty}</Empty>;
  return (
    <div className="list overflow-x-auto">
      <table className="w-full min-w-[640px] text-left text-[13px]">
        <thead className="bg-stone-50 text-xs text-stone-600">
          <tr>{cols.map((c) => (
            <th key={c.key} className={`px-4 py-2.5 font-medium ${c.align === "right" ? "text-right" : ""}`} aria-sort={sort?.key === c.key ? (sort.dir === 1 ? "ascending" : "descending") : undefined}>
              {c.sort === false ? c.label : <button type="button" className="hover:text-zinc-900" onClick={() => setSort(sort?.key === c.key ? { key: c.key, dir: (sort.dir * -1) as 1 | -1 } : { key: c.key, dir: -1 })}>{c.label}{sort?.key === c.key ? (sort.dir === 1 ? " ↑" : " ↓") : ""}</button>}
            </th>))}</tr>
        </thead>
        <tbody className="divide-y divide-stone-100">
          {sorted.map((r, i) => (
            <tr key={r.id ?? r.route ?? r.term ?? i} onClick={onRow ? () => onRow(r) : undefined} className={onRow ? "cursor-pointer hover:bg-stone-50" : ""}>
              {cols.map((c) => <td key={c.key} className={`px-4 py-2.5 tabular-nums ${c.align === "right" ? "text-right" : ""}`}>{c.render ? c.render(r) : r[c.key] ?? "—"}</td>)}
            </tr>))}
        </tbody>
      </table>
    </div>
  );
}

/* ───────────────────────── Resumen ───────────────────────── */
function Overview({ days, admins }: { days: number; admins: boolean }) {
  const q = useMetric("overview", days, admins);
  return <Gate q={q}>{(d) => {
    const k = d.kpis;
    const max = Math.max(1, ...d.heatmap.flat());
    const alerts = d.entry_sources?.alert ?? 0;
    return (<>
      <div className="flex flex-col gap-4">
        <KpiStrip>
          <Kpi label="Usuarios activos" value={num(k.active_users)} hint={`de ${num(k.users_total)} · ${num(k.never_entered)} nunca han entrado`} />
          <Kpi label="Hoy · 7 días · 30 días" value={`${k.dau} · ${k.wau} · ${k.mau}`} hint={`Frecuencia de uso (DAU/MAU): ${pct(k.stickiness)}`} />
          <Kpi label="Sesiones" value={num(k.sessions)} hint={k.sessions_per_active_user ? `${k.sessions_per_active_user} por usuario activo` : undefined} />
          <Kpi label="Duración mediana" value={dur(k.duration_median_s)} hint={`90% duran menos de ${dur(k.duration_p90_s)}`} />
        </KpiStrip>
        <KpiStrip>
          <Kpi label="Tiempo activo mediano" value={dur(k.active_median_s)} hint="con la pestaña visible y en uso" />
          <Kpi label="Pantallas por sesión" value={k.pages_per_session ?? "—"} />
          <Kpi label="Rebote" value={pct(k.bounce_rate)} hint="una pantalla y menos de 10 s" />
          <Kpi label="Sesiones desde alertas" value={num(alerts)} hint={k.sessions ? `${pct(alerts / k.sessions)} de las sesiones` : undefined} />
        </KpiStrip>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="Usuarios activos por día" data={d.series} cols={[["day", "Día"], ["dau", "Usuarios"], ["sessions", "Sesiones"]]}><DayLine data={d.series} k="dau" unit="usuarios" name="Usuarios activos por día" /></ChartCard>
        <ChartCard title="Tiempo activo por día" hint="minutos entre todos los usuarios" data={d.series} cols={[["day", "Día"], ["active_minutes", "Minutos"]]}><DayBars data={d.series} k="active_minutes" unit="min" name="Tiempo activo por día" /></ChartCard>
      </div>
      <Section title="¿Cuándo entran?">
        <div className="card flex flex-col gap-2 overflow-x-auto">
          <p className="text-xs text-stone-600">Sesiones iniciadas por día de la semana y hora (hora de Guatemala). Más oscuro, más sesiones.</p>
          <div role="img" aria-label="Mapa de calor de sesiones por día y hora" className="grid min-w-[560px] gap-[2px]" style={{ gridTemplateColumns: "32px repeat(24, 1fr)" }}>
            <span />{Array.from({ length: 24 }, (_, h) => <span key={h} className="text-center text-[10px] text-stone-500">{h % 3 === 0 ? h : ""}</span>)}
            {d.heatmap.map((row: number[], dow: number) => (<Row key={dow} label={DAY_NAMES[dow]} row={row} max={max} />))}
          </div>
        </div>
      </Section>
      <p className="text-xs text-stone-600">Dispositivos: {Object.entries(d.devices ?? {}).map(([k2, v]) => `${k2 === "mobile" ? "móvil" : k2 === "desktop" ? "escritorio" : k2} ${v}`).join(" · ") || "—"}</p>
    </>);
  }}</Gate>;
}
function Row({ label, row, max }: { label: string; row: number[]; max: number }) {
  return (<>
    <span className="pr-1 text-right text-[10px] leading-5 text-stone-500">{label}</span>
    {row.map((v, h) => <span key={h} title={`${label} ${h}:00 — ${v} sesión(es)`} className="h-5 rounded-[3px]" style={{ background: v ? BLUE : "#f5f5f4", opacity: v ? 0.15 + 0.85 * (v / max) : 1 }} />)}
  </>);
}

/* ───────────────────────── Usuarios ───────────────────────── */
const STATUS: Record<string, [string, string]> = {
  active: ["Activo", "bg-emerald-50 text-emerald-800"], at_risk: ["En riesgo", "bg-amber-50 text-amber-800"],
  dormant: ["Dormido", "bg-red-50 text-red-800"], never: ["Sin entrar", "bg-stone-100 text-stone-700"],
};
const StatusBadge = ({ s }: { s: string }) => <span className={`badge ${STATUS[s]?.[1] ?? ""}`}>{STATUS[s]?.[0] ?? s}</span>;

function exportCsv(rows: any[]) {
  const cols = ["company", "email", "status", "last_active_at", "sessions", "active_minutes", "searches", "tender_views", "favorites_added", "feedback", "saved_searches", "inventory_imports", "score"];
  const esc = (v: any) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  const csv = [cols.join(","), ...rows.map((r) => cols.map((c) => esc(r[c])).join(","))].join("\n");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8" }));
  a.download = `uso-por-usuario-${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(a.href);
}

function Users({ days, admins }: { days: number; admins: boolean }) {
  const q = useMetric("users", days, admins);
  const [sel, setSel] = useState<number | null>(null);
  return <Gate q={q}>{(d) => (<>
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex flex-wrap gap-2 text-xs">{Object.entries(STATUS).map(([k, [l, c]]) => <span key={k} className={`badge ${c}`}>{l}: {d.status_counts?.[k] ?? 0}</span>)}</div>
      <button type="button" className="btn" onClick={() => exportCsv(d.items)}>Exportar CSV</button>
    </div>
    <p className="-mt-4 text-xs text-stone-600">Activo: entró en los últimos 7 días · En riesgo: 8–14 días · Dormido: más de 14. El puntaje pesa más las acciones de valor (seguir un concurso, guardar una alerta, importar inventario).</p>
    <Table onRow={(r) => setSel(r.id)} rows={d.items} cols={[
      { key: "company", label: "Empresa", render: (r) => <div className="flex min-w-0 flex-col"><span className="truncate font-medium">{r.company || r.email}</span><span className="truncate text-xs text-stone-600">{r.email}</span></div> },
      { key: "status", label: "Estado", render: (r) => <StatusBadge s={r.status} /> },
      { key: "last_active_at", label: "Última actividad", render: (r) => (r.last_active_at ? dateTime(r.last_active_at) : "—") },
      { key: "sessions", label: "Sesiones", align: "right" }, { key: "active_minutes", label: "Min. activos", align: "right" },
      { key: "searches", label: "Búsquedas", align: "right" }, { key: "tender_views", label: "Concursos vistos", align: "right" },
      { key: "favorites_added", label: "Seguidos", align: "right" }, { key: "saved_searches", label: "Alertas", align: "right" },
      { key: "score", label: "Puntaje", align: "right" },
    ]} empty="Todavía no hay usuarios que mostrar." />
    {sel != null && <UserDetail id={sel} days={days} onClose={() => setSel(null)} />}
    <Retention admins={admins} />
  </>)}</Gate>;
}

function UserDetail({ id, days, onClose }: { id: number; days: number; onClose: () => void }) {
  const q = useQuery({ queryKey: ["metrics", "user", id, days], queryFn: () => api<any>(`/admin/metrics/users/${id}?days=${days}`) });
  return (
    <section className="card flex flex-col gap-5" aria-label="Detalle del usuario">
      {q.isLoading ? <Loading rows={2} /> : q.error ? <ErrorBox error={q.error} /> : (() => {
        const d = q.data;
        const max = Math.max(1, ...d.features.map((f: any) => f.count));
        return (<>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="flex flex-col"><h3 className="text-base font-semibold">{d.user.company || d.user.email}</h3><span className="text-[13px] text-stone-600">{[d.user.name, d.user.email].filter(Boolean).join(" · ")}</span></div>
            <button type="button" className="btn" onClick={onClose}>Cerrar</button>
          </div>
          <div className="grid gap-6 lg:grid-cols-2">
            <div className="flex flex-col gap-3">
              <h4 className="eyebrow">Qué hace (últimos {days} días)</h4>
              {d.features.length ? d.features.slice(0, 10).map((f: any) => <HBar key={f.feature + f.action} label={`${f.label} · ${f.action}`} value={f.count} max={max} />) : <p className="text-sm text-stone-600">Sin actividad en este periodo.</p>}
            </div>
            <div className="flex flex-col gap-3">
              <h4 className="eyebrow">Sesiones recientes</h4>
              <ul className="flex flex-col divide-y divide-stone-100 text-[13px]">
                {d.sessions.slice(0, 8).map((s: any) => (
                  <li key={s.started_at} className="flex flex-wrap justify-between gap-2 py-1.5"><span>{dateTime(s.started_at)}</span>
                    <span className="text-stone-600">{dur(s.duration_s)} · activo {dur(s.active_s)}{s.source === "alert" ? " · desde alerta" : ""}</span></li>))}
                {!d.sessions.length && <li className="py-1.5 text-stone-600">Sin sesiones.</li>}
              </ul>
            </div>
          </div>
          <div className="flex flex-col gap-2">
            <h4 className="eyebrow">Línea de tiempo (últimos eventos)</h4>
            <ul className="flex max-h-72 flex-col divide-y divide-stone-100 overflow-auto text-[13px]">
              {d.events.map((e: any, i: number) => (
                <li key={i} className="flex flex-wrap gap-x-3 gap-y-0.5 py-1.5">
                  <span className="w-36 shrink-0 text-stone-600">{dateTime(e.ts)}</span>
                  <span className="font-medium">{e.label} · {e.action}</span>
                  {e.props?.q ? <span className="text-stone-700">«{e.props.q}»</span> : null}
                  {e.status && e.status >= 400 ? <span className="badge bg-red-50 text-red-800">{e.status}</span> : null}
                </li>))}
            </ul>
          </div>
        </>);
      })()}
    </section>
  );
}

function Retention({ admins }: { admins: boolean }) {
  const q = useQuery({ queryKey: ["metrics", "retention", admins], queryFn: () => api<any>(`/admin/metrics/retention?exclude_admins=${!admins}`) });
  if (!q.data?.cohorts?.length) return null;
  const cols = Math.min(q.data.weeks, 8);
  return (
    <Section title="Retención semanal">
      <div className="card flex flex-col gap-2 overflow-x-auto">
        <p className="text-xs text-stone-600">De los usuarios que entraron por primera vez cada semana, qué % volvió en las semanas siguientes.</p>
        <table className="w-full min-w-[520px] text-left text-[13px]">
          <thead className="text-xs text-stone-600"><tr><th className="py-1.5 pr-3 font-medium">Primera semana</th><th className="py-1.5 pr-3 font-medium">Usuarios</th>{Array.from({ length: cols }, (_, i) => <th key={i} className="py-1.5 pr-3 text-center font-medium">+{i}</th>)}</tr></thead>
          <tbody>{q.data.cohorts.map((c: any) => (
            <tr key={c.week} className="border-t border-stone-100"><td className="py-1.5 pr-3">{c.week}</td><td className="py-1.5 pr-3 tabular-nums">{c.size}</td>
              {c.retention.slice(0, cols).map((v: number | null, i: number) => (
                <td key={i} className="py-1 pr-3 text-center tabular-nums">{v == null ? <span className="text-stone-300">·</span> :
                  <span className="inline-block min-w-12 rounded px-1.5 py-0.5" style={{ background: `rgba(42,120,214,${0.08 + 0.55 * v})`, color: v > 0.6 ? "#fff" : "#1c1917" }}>{pct(v)}</span>}</td>))}
            </tr>))}</tbody>
        </table>
      </div>
    </Section>
  );
}

/* ───────────────────────── Funcionalidades ───────────────────────── */
function Features({ days, admins }: { days: number; admins: boolean }) {
  const q = useMetric("features", days, admins);
  return <Gate q={q}>{(d) => {
    const max = Math.max(1, ...d.items.map((f: any) => f.visits + f.actions));
    const f0 = d.funnel?.[0]?.count || 0;
    return (<>
      <Section title="Qué funciones se usan más">
        <div className="card flex flex-col gap-4">
          {d.items.map((f: any) => (
            <HBar key={f.feature} label={f.label} value={f.visits + f.actions} max={max} right={`${num(f.visits)} visitas · ${num(f.actions)} acciones`}
              sub={f.users ? `${f.users} de ${d.users_in_scope} usuarios (${pct(f.adoption)}) · ${f.visits_per_user} visitas por usuario · ${f.minutes} min en pantalla${f.last_used_at ? ` · último uso ${dateTime(f.last_used_at)}` : ""}` : "Nadie la usó en este periodo"} />))}
        </div>
        {d.unused.length > 0 && <p className="text-xs text-stone-600">Sin uso en el periodo: {d.unused.join(", ")}.</p>}
      </Section>
      <Section title="Del buscar al seguir">
        <div className="card flex flex-col gap-4">
          <p className="text-xs text-stone-600">Sesiones que llegaron a cada paso (cada paso cuenta solo las sesiones del anterior).</p>
          {d.funnel.map((s: any, i: number) => <HBar key={s.step} label={s.step} value={s.count} max={f0} right={`${num(s.count)}${i ? ` · ${pct(d.funnel[i - 1].count ? s.count / d.funnel[i - 1].count : null)} del paso anterior` : ""}`} />)}
        </div>
      </Section>
    </>);
  }}</Gate>;
}

/* ───────────────────────── Búsquedas ───────────────────────── */
function Searches({ days, admins }: { days: number; admins: boolean }) {
  const q = useMetric("searches", days, admins);
  return <Gate q={q}>{(d) => {
    const k = d.kpis;
    const maxF = Math.max(1, ...d.filters.map((f: any) => f.count));
    return (<>
      <KpiStrip>
        <Kpi label="Búsquedas" value={num(k.searches)} hint={k.per_active_searcher ? `${k.per_active_searcher} por usuario que busca (${k.searchers})` : undefined} />
        <Kpi label="Sin resultados" value={pct(k.zero_result_rate)} hint="búsquedas que no devolvieron concursos" />
        <Kpi label="Terminan en un concurso" value={pct(k.search_to_detail_rate)} hint="sesiones con búsqueda que abren un detalle" />
        <Kpi label="Lentitud (p95)" value={k.latency_p95_ms == null ? "—" : `${Math.round(k.latency_p95_ms)} ms`} hint={`${num(k.embedding_searches)} usaron IA (costo OpenAI)`} />
      </KpiStrip>
      <ChartCard title="Búsquedas por día" data={d.series} cols={[["day", "Día"], ["searches", "Búsquedas"]]}><DayBars data={d.series} k="searches" unit="búsquedas" name="Búsquedas por día" /></ChartCard>
      <div className="grid gap-6 lg:grid-cols-2">
        <Section title="Lo que más buscan"><Table cols={[{ key: "term", label: "Texto" }, { key: "count", label: "Veces", align: "right" }, { key: "users", label: "Usuarios", align: "right" }, { key: "zero_results", label: "Sin resultados", align: "right" }]} rows={d.top_terms} empty="Aún no hay búsquedas con texto." /></Section>
        <Section title="Búsquedas sin resultados"><Table cols={[{ key: "term", label: "Texto" }, { key: "count", label: "Veces", align: "right" }]} rows={d.zero_terms} empty="Ninguna búsqueda quedó sin resultados." /></Section>
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <Section title="Modo de búsqueda"><div className="card flex flex-wrap gap-2">{Object.keys(d.modes).length ? Object.entries(d.modes).map(([m, n]) => <span key={m} className="badge">{({ keyword: "Palabras clave", semantic: "Significado", hybrid: "Híbrida" } as any)[m] ?? m}: {String(n)}</span>) : <span className="text-sm text-stone-600">—</span>}</div></Section>
        <Section title="Filtros más usados"><div className="card flex flex-col gap-3">{d.filters.length ? d.filters.map((f: any) => <HBar key={f.filter} label={f.filter} value={f.count} max={maxF} />) : <span className="text-sm text-stone-600">Nadie usó filtros.</span>}</div></Section>
      </div>
      <Section title="Búsquedas recientes">
        <Table cols={[{ key: "ts", label: "Cuándo", render: (r) => dateTime(r.ts) }, { key: "who", label: "Quién" }, { key: "q", label: "Texto", render: (r) => r.q || <span className="text-stone-500">(solo filtros)</span> }, { key: "mode", label: "Modo" },
          { key: "total", label: "Resultados", align: "right" }, { key: "filters", label: "Filtros", render: (r) => (r.filters?.length ? r.filters.join(", ") : "—") }]} rows={d.recent} />
      </Section>
    </>);
  }}</Gate>;
}

/* ───────────────────────── Salud ───────────────────────── */
function Health({ days, admins }: { days: number; admins: boolean }) {
  const q = useMetric("health", days, admins);
  return <Gate q={q}>{(d) => (<>
    <KpiStrip>
      <Kpi label="Solicitudes" value={num(d.kpis.requests)} />
      <Kpi label="Errores del servidor (5xx)" value={num(d.kpis.errors_5xx)} />
      <Kpi label="Errores del usuario (4xx)" value={num(d.kpis.errors_4xx)} hint="sesión vencida, permisos, datos inválidos" />
      <Kpi label="Ingresos fallidos" value={num(d.kpis.failed_logins)} />
    </KpiStrip>
    <Section title="Rendimiento por pantalla o acción">
      <Table cols={[{ key: "route", label: "Ruta" }, { key: "count", label: "Solicitudes", align: "right" }, { key: "p50_ms", label: "p50 (ms)", align: "right" }, { key: "p95_ms", label: "p95 (ms)", align: "right" },
        { key: "errors_5xx", label: "5xx", align: "right" }, { key: "errors_4xx", label: "4xx", align: "right" }]} rows={d.items} />
    </Section>
    {d.recent_errors.length > 0 && <Section title="Últimos errores 5xx"><Table cols={[{ key: "ts", label: "Cuándo", render: (r) => dateTime(r.ts) }, { key: "route", label: "Ruta" }, { key: "status", label: "Código", align: "right" }]} rows={d.recent_errors} /></Section>}
  </>)}</Gate>;
}
