import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, Tender } from "../api";
import { IconSearch } from "../components/icons";
import TenderCard from "../components/TenderCard";
import { Empty, ErrorBox, Kpi, KpiStrip, Loading, MERCADO_TABS, Page, Section, Segmented, TabNav } from "../components/ui";
import { money, nameCase, num, supplierName } from "../format";

export default function Suppliers() {
  const { sid } = useParams();
  return sid ? <Detail sid={sid} /> : <List />;
}

function List() {
  const [q, setQ] = useState("");
  const r = useQuery({ queryKey: ["sup", q], queryFn: () => api(`/suppliers?q=${encodeURIComponent(q)}&limit=30`), placeholderData: (p) => p });
  return (
    <Page title="Proveedores" subtitle="Consulta qué ha ganado y cotizado cualquier proveedor del Estado.">
      <TabNav tabs={MERCADO_TABS} />
      <label className="search-box">
        <IconSearch size={18} className="text-stone-600" /><span className="sr-only">Buscar proveedor</span>
        <input className="min-w-0 flex-1 bg-transparent text-[15px] outline-none placeholder:text-stone-500" placeholder="Nombre o NIT…" value={q} onChange={(e) => setQ(e.target.value)} />
      </label>
      {r.isLoading ? <Loading /> : r.data?.items.length ? (
        <div className="list">{r.data.items.map((s: any) => (
          <Link key={s.id} to={`/suppliers/${s.id}`} className="flex items-center justify-between gap-4 px-5 py-3 text-sm text-zinc-900 hover:bg-stone-50">
            <span className="font-medium">{supplierName(s.name)}</span><span className="text-xs tabular-nums text-stone-600">{s.id.replace("GT-NIT-", "NIT ")}</span>
          </Link>))}</div>
      ) : <Empty>Sin resultados.</Empty>}
    </Page>
  );
}

const TABS = [["awarded", "Ganados"], ["bid", "Cotizados"], ["matching", "Vigentes parecidos"]] as const;

function Detail({ sid }: { sid: string }) {
  const [tab, setTab] = useState<(typeof TABS)[number][0]>("awarded");
  const p = useQuery({ queryKey: ["sup", sid], queryFn: () => api(`/suppliers/${sid}`) });
  const t = useQuery({ queryKey: ["sup-t", sid, tab], queryFn: () => api<{ items: Tender[] }>(tab === "matching" ? `/suppliers/${sid}/matching-tenders` : `/suppliers/${sid}/tenders?role=${tab}`) });
  if (p.isLoading) return <Loading rows={3} />;
  if (p.error) return <ErrorBox error={p.error} />;
  const d = p.data;
  return (
    <Page title={supplierName(d.name)} subtitle={sid.replace("GT-NIT-", "NIT ")}>
      <KpiStrip>
        <Kpi label="Concursos ganados" value={num(d.awarded_tenders)} />
        <Kpi label="Monto adjudicado" value={money(d.awarded_total)} />
        <Kpi label="Concursos cotizados" value={num(d.bid_tenders)} />
        <Kpi label="Tasa de éxito" value={d.bid_tenders ? `${Math.round((d.awarded_tenders / d.bid_tenders) * 100)}%` : "—"} />
      </KpiStrip>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="card flex flex-col gap-3"><span className="eyebrow">Clases principales</span>
          <div className="flex flex-wrap gap-1.5">{d.top_classes.map((c: any) => <span key={c.unspsc} className="badge tabular-nums">{c.unspsc} · {c.n}</span>)}</div></div>
        <div className="card flex flex-col gap-3"><span className="eyebrow">Entidades que más le adjudican</span>
          <div className="flex flex-wrap gap-1.5">{d.top_buyers.map((b: any) => <span key={b.name} className="badge">{nameCase(b.name)} · {b.n}</span>)}</div></div>
      </div>
      <Section title={<Segmented label="Concursos del proveedor" value={tab} options={TABS} onChange={setTab} />}>
        {t.isLoading ? <Loading /> : t.data?.items.length
          ? <div className="list">{t.data.items.map((x) => <TenderCard key={x.ocid} t={x} context="supplier" />)}</div>
          : <Empty>Sin concursos.</Empty>}
      </Section>
    </Page>
  );
}
