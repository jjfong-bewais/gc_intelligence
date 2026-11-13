import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { api, Tender } from "../api";
import TenderCard from "../components/TenderCard";
import { ErrorBox, Kpi, KpiStrip, Loading, Page, Section } from "../components/ui";
import { money, nameCase, num, supplierName } from "../format";

/** Perfil de una entidad compradora. */
export default function Buyer() {
  const [sp] = useSearchParams();
  const name = sp.get("name") ?? "";
  const p = useQuery({ queryKey: ["buyer", name], queryFn: () => api(`/buyers/profile?name=${encodeURIComponent(name)}`), enabled: name.length >= 2 });
  if (!name) return <ErrorBox error={new Error("Falta el nombre de la entidad")} />;
  if (p.isLoading) return <Loading rows={3} />;
  if (p.error) return <ErrorBox error={p.error} />;
  const d = p.data;
  return (
    <Page title={nameCase(d.name)} subtitle="Perfil de la entidad compradora" actions={<Link to="/market" className="btn">← Mercado</Link>}>
      <KpiStrip>
        <Kpi label="Concursos publicados" value={num(d.tenders)} hint={`${num(d.open)} vigentes`} />
        <Kpi label="Monto adjudicado" value={money(d.awarded_total)} hint={`${num(d.awarded_tenders)} concursos adjudicados`} />
        <Kpi label="Oferentes por concurso" value={d.avg_bidders ?? "—"} hint="promedio" />
        <Kpi label="Modalidades" value={d.methods.length ? nameCase(d.methods[0].name) : "—"} hint={d.methods.length ? `${num(d.methods[0].n)} concursos` : undefined} />
      </KpiStrip>
      <div className="grid gap-4 md:grid-cols-2">
        <section className="card flex flex-col gap-3">
          <h2 className="h-section">A quién le adjudica más</h2>
          {d.top_winners.length ? (
            <ol className="flex flex-col divide-y divide-stone-100 text-[13px]">{d.top_winners.map((w: any) => (
              <li key={w.id} className="flex items-baseline justify-between gap-3 py-1.5">
                <Link to={`/suppliers/${w.id}`} className="font-medium text-zinc-900 hover:text-brand-800">{supplierName(w.name)}</Link>
                <span className="shrink-0 text-xs text-stone-600 tabular-nums">{w.n} · {money(w.amount)}</span>
              </li>))}</ol>
          ) : <p className="muted">Sin adjudicaciones registradas.</p>}
        </section>
        <section className="card flex flex-col gap-3">
          <h2 className="h-section">Qué compra</h2>
          <div className="flex flex-wrap gap-1.5">{d.top_classes.map((c: any) => (
            <Link key={c.unspsc} to="/search" state={{ unspsc: c.unspsc }} className="badge tabular-nums hover:bg-stone-200">{c.unspsc} · {c.n}</Link>))}</div>
        </section>
      </div>
      <Section title="Concursos recientes">
        <div className="list">{d.recent.map((t: Tender) => <TenderCard key={t.ocid} t={t} context="buyer" />)}</div>
      </Section>
    </Page>
  );
}
