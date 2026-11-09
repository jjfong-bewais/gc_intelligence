import { useQuery } from "@tanstack/react-query";
import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, Tender } from "../api";
import { IconClock, IconSearch } from "../components/icons";
import FilterPanel, { WithFilters } from "../components/FilterPanel";
import TenderCard from "../components/TenderCard";
import { countActive, describe, filterQuery, useViewFilters } from "../filters";
import { Empty, ErrorBox, Kpi, KpiStrip, Loading, Section } from "../components/ui";
import { greeting, money, num, todayLong } from "../format";

const MONTHS = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];

export default function Dashboard() {
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const [filters, setFilters] = useViewFilters("dashboard");
  const fq = filterQuery(filters);
  const r = useQuery({ queryKey: ["dashboard", fq], queryFn: () => api(`/dashboard${fq ? `?${fq}` : ""}`), placeholderData: (p) => p });
  const submit = (e: FormEvent) => { e.preventDefault(); nav("/search", { state: { q, filters } }); };

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-[26px] font-semibold leading-tight tracking-tight">{greeting()}</h1>
          <p className="text-sm text-stone-600">{todayLong()} · datos de Guatecompras</p>
        </div>
        <form onSubmit={submit} role="search" className="flex min-h-11 w-full max-w-[340px] items-center gap-2.5 rounded-xl border border-stone-200 bg-white px-3.5 focus-within:border-brand-500 focus-within:ring-2 focus-within:ring-brand-500/20">
          <IconSearch className="text-stone-500" />
          <input aria-label="Buscar concursos" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar concursos, entidades, NOG…"
            className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-stone-500" />
        </form>
      </header>

      <GuideNotice />

      <WithFilters f={filters} panel={<FilterPanel value={filters} onChange={setFilters} />}>
        {countActive(filters) > 0 && <p className="-mb-3 text-xs text-stone-600">Con filtros: {describe(filters)}</p>}
        {r.isLoading ? <Loading /> : r.error ? <ErrorBox error={r.error} /> : <div className={`flex flex-col gap-8 transition-opacity ${r.isFetching ? "opacity-60" : ""}`}><Body d={r.data} /></div>}
      </WithFilters>
    </div>
  );
}

function Body({ d }: { d: any }) {
  const k = d.kpis;
  const monthly: { month: string; count: number }[] = (d.monthly ?? []).slice(-12);
  const max = Math.max(1, ...monthly.map((m) => m.count));
  const currentMonth = new Date().toISOString().slice(0, 7);

  return (
    <>
      <KpiStrip>
        <Kpi label="Concursos vigentes" value={num(k.open)} hint={k.new_7d && k.new_7d < k.open ? `${num(k.new_7d)} nuevos esta semana` : d.filtered ? "con tus filtros" : "en toda Guatecompras"} />
        <Kpi label="En seguimiento" value={num(k.favorites)} hint={k.favorites ? "ver en Seguimiento" : "marca concursos para seguirlos"} />
        <Kpi label="Coincidencias con inventario" value={k.inventory_items ? num(k.inventory_matches) : <span className="text-stone-400">—</span>}
          hint={k.inventory_items ? `de ${num(k.inventory_items)} productos` : undefined}
          action={k.inventory_items ? undefined : { to: "/inventory", label: "Importar inventario" }} />
        <Kpi label="Adjudicado a tus NIT" value={k.awarded_total ? money(k.awarded_total) : <span className="text-stone-400">—</span>}
          action={k.awarded_total ? undefined : { to: "/settings", label: "Configurar NIT" }} />
      </KpiStrip>

      <Section title="Recomendados para ti" more="/recommendations" moreLabel="Ver todos">
        {d.recommended.length ? (
          <div className="list">{d.recommended.map((t: Tender) => <TenderCard key={t.ocid} t={t} context="dashboard" />)}</div>
        ) : <Empty>{d.filtered ? "Ningún concurso recomendado cumple los filtros." : "Configura tus NIT en Ajustes o marca concursos con “Me interesa” para recibir recomendaciones."}</Empty>}
      </Section>

      <div className="grid gap-6 md:grid-cols-2">
        <section className="card flex flex-col gap-4 px-6">
          <div className="flex items-baseline justify-between">
            <h2 className="h-section">Publicaciones por mes</h2>
            <span className="text-xs text-stone-600">últimos {monthly.length} meses</span>
          </div>
          <div role="img" aria-label={`Concursos publicados por mes: ${monthly.map((m) => `${m.month} ${m.count}`).join(", ")}`} className="flex flex-col gap-1.5">
            <div className="flex h-32 items-end gap-2">
              {monthly.map((m) => (
                <div key={m.month} title={`${m.month}: ${num(m.count)} concursos`}
                  className={`flex-1 rounded-t ${m.month === currentMonth ? "bg-brand-200" : "bg-brand-600 hover:bg-brand-700"}`}
                  style={{ height: `${Math.max(2, (m.count / max) * 100)}%` }} />
              ))}
            </div>
            <div className="flex gap-2">
              {monthly.map((m) => <span key={m.month} className="flex-1 text-center text-[11px] text-stone-600">{MONTHS[Number(m.month.slice(5, 7)) - 1] ?? m.month}</span>)}
            </div>
          </div>
        </section>

        <section className="card flex flex-col gap-3 px-6">
          <h2 className="h-section">Cierran en los próximos 3 días</h2>
          {d.closing_soon.length ? (
            <div className="-mx-6 divide-y divide-stone-100 border-t border-stone-100">
              {d.closing_soon.slice(0, 4).map((t: Tender) => <TenderCard key={t.ocid} t={t} context="dashboard" />)}
            </div>
          ) : (
            <div className="flex flex-1 flex-col items-center justify-center gap-2 py-6 text-center">
              <IconClock size={28} className="text-stone-400" />
              <span className="text-sm text-stone-700">Nada cierra pronto</span>
              <span className="text-[13px] text-stone-600">Aquí aparecerán los concursos vigentes que cierran en los próximos días.</span>
            </div>
          )}
        </section>
      </div>

      {d.inventory_matches.length > 0 && (
        <Section title="Coinciden con tu inventario" more="/inventory">
          <div className="list">{d.inventory_matches.map((t: Tender) => <TenderCard key={t.ocid} t={t} context="inventory" />)}</div>
        </Section>
      )}
    </>
  );
}

/** Aviso para usuarios nuevos: lleva a la Guía. Se oculta para siempre al cerrarlo o abrir la guía. */
function GuideNotice() {
  const KEY = "gc.guideNotice.dismissed";
  const [hidden, setHidden] = useState(() => { try { return localStorage.getItem(KEY) === "1"; } catch { return false; } });
  if (hidden) return null;
  const dismiss = () => { try { localStorage.setItem(KEY, "1"); } catch { /* sin almacenamiento */ } setHidden(true); };
  return (
    <div className="-mt-3 flex flex-wrap items-center gap-3 rounded-2xl border border-brand-200 bg-brand-50 px-5 py-3.5 text-[13px] text-brand-800">
      <span className="min-w-0 flex-1"><b className="font-semibold">¿Primera vez aquí?</b> Descubre todo lo que puedes hacer: buscar, comparar precios, recibir recomendaciones y alertas.</span>
      <Link to="/guide" onClick={dismiss} className="btn">Ver la guía →</Link>
      <button type="button" onClick={dismiss} aria-label="Cerrar aviso" className="btn-ghost px-2 text-brand-800 hover:bg-brand-100">✕</button>
    </div>
  );
}
