import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api";
import FilterPanel, { WithFilters } from "../components/FilterPanel";
import { Empty, ErrorBox, Loading, Page } from "../components/ui";
import { filterQuery, useViewFilters } from "../filters";
import { money, nameCase, sentenceCase, supplierName } from "../format";
import { HelpLink } from "./Guide";

export default function Opportunities() {
  const [filters, setFilters] = useViewFilters("opportunities");
  const fq = filterQuery(filters);
  const q = useQuery({ queryKey: ["opps", fq], queryFn: () => api(`/opportunities${fq ? `?${fq}` : ""}`), placeholderData: (p) => p });
  const d = q.data;
  return (
    <Page title={<span className="inline-flex items-center gap-2">Oportunidades <HelpLink section="oportunidades" /></span>} subtitle="Categorías donde participan proveedores parecidos a ti (por mezcla de clases UNSPSC) y donde tú aún no participas. Los filtros limitan qué concursos cuentan.">
      <WithFilters f={filters} panel={<FilterPanel value={filters} onChange={setFilters} />}>
      {q.isLoading ? <Loading rows={4} /> : q.error ? <ErrorBox error={q.error} /> : !d.peers.length ? (
        <Empty action={<Link to="/settings" className="btn mt-2">Configurar NIT</Link>}>Agrega tus NIT en Ajustes para encontrar proveedores semejantes y las clases donde participan.</Empty>
      ) : (
        <>
          <section className="flex flex-col gap-3">
            <h2 className="h-section">Proveedores semejantes</h2>
            <div className="flex flex-wrap gap-2">{d.peers.map((p: any) => (
              <Link key={p.id} to={`/suppliers/${p.id}`} className="badge py-1 text-[13px] hover:bg-stone-200">{supplierName(p.name)} <span className="text-stone-600">{Math.round(p.similarity * 100)}%</span></Link>))}</div>
          </section>
          <div className="grid gap-4 md:grid-cols-2">
            {d.opportunities.map((o: any) => (
              <article key={o.unspsc_class} className="card flex flex-col gap-3">
                <div className="flex items-start justify-between gap-3">
                  <h3 className="text-sm font-semibold leading-snug">{sentenceCase(o.label)}</h3>
                  <span className="badge shrink-0 tabular-nums">{o.unspsc_class}</span>
                </div>
                <p className="text-[13px] text-stone-600">{o.examples.map((e: string) => sentenceCase(e)).join(" · ")}</p>
                <dl className="grid grid-cols-2 gap-3 border-t border-stone-100 pt-3 text-[13px]">
                  <div><dt className="text-xs text-stone-600">Semejantes que participan</dt><dd className="font-medium">{o.n_peers} · {o.peer_participations} veces</dd></div>
                  <div><dt className="text-xs text-stone-600">Adjudicado a ellos</dt><dd className="font-medium tabular-nums">{money(o.peer_awarded_amount)}</dd></div>
                </dl>
                <p className="text-xs text-stone-600">Ej.: {o.top_peers.map((n: string) => nameCase(supplierName(n))).join(", ")}</p>
                <Link className="btn self-start" to="/search" state={{ unspsc: o.unspsc_class, filters: { ...filters, status_details: { op: "in", values: ["Vigente"] } } }}>Ver {o.open_now} vigente(s) →</Link>
              </article>
            ))}
          </div>
          {!d.opportunities.length && <Empty>Ninguna categoría nueva cumple estos filtros.</Empty>}
        </>
      )}
      </WithFilters>
    </Page>
  );
}
