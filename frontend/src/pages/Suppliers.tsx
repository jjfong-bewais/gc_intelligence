import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, Tender } from "../api";
import TenderCard from "../components/TenderCard";
import { Empty, ErrorBox, Loading, Page } from "../components/ui";
import { money } from "../format";

export default function Suppliers() {
  const { sid } = useParams();
  return sid ? <Detail sid={sid} /> : <List />;
}

function List() {
  const [q, setQ] = useState("");
  const r = useQuery({ queryKey: ["sup", q], queryFn: () => api(`/suppliers?q=${encodeURIComponent(q)}&limit=30`) });
  return (
    <Page title="Proveedores">
      <input className="input" placeholder="Buscar por nombre o NIT…" value={q} onChange={(e) => setQ(e.target.value)} />
      {r.isLoading ? <Loading /> : r.data?.items.length ? (
        <div className="card divide-y divide-slate-100 dark:divide-slate-800">{r.data.items.map((s: any) => (
          <Link key={s.id} to={`/suppliers/${s.id}`} className="flex justify-between py-1.5 hover:underline"><span>{s.name}</span><span className="muted">{s.id}</span></Link>))}</div>
      ) : <Empty>Sin resultados.</Empty>}
    </Page>
  );
}

function Detail({ sid }: { sid: string }) {
  const [tab, setTab] = useState<"awarded" | "bid" | "matching">("awarded");
  const p = useQuery({ queryKey: ["sup", sid], queryFn: () => api(`/suppliers/${sid}`) });
  const t = useQuery({ queryKey: ["sup-t", sid, tab], queryFn: () => api<{ items: Tender[] }>(tab === "matching" ? `/suppliers/${sid}/matching-tenders` : `/suppliers/${sid}/tenders?role=${tab}`) });
  if (p.isLoading) return <Loading />;
  if (p.error) return <ErrorBox error={p.error} />;
  const d = p.data;
  return (
    <Page title={d.name}>
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="card"><div className="muted">Concursos adjudicados</div><div className="text-2xl font-semibold">{d.awarded_tenders}</div><div className="muted">{money(d.awarded_total)}</div></div>
        <div className="card"><div className="muted">Concursos donde cotizó</div><div className="text-2xl font-semibold">{d.bid_tenders}</div></div>
        <div className="card"><div className="muted">Clases principales</div><div className="mt-1 flex flex-wrap gap-1">{d.top_classes.map((c: any) => <span key={c.unspsc} className="badge">{c.unspsc} ×{c.n}</span>)}</div></div>
      </div>
      <div className="card"><div className="muted mb-1">Entidades que más le adjudican</div>
        <div className="flex flex-wrap gap-1">{d.top_buyers.map((b: any) => <span key={b.name} className="badge">{b.name} ×{b.n}</span>)}</div></div>
      <div className="flex gap-1">{([["awarded", "Ganados"], ["bid", "Cotizados"], ["matching", "Vigentes parecidos"]] as const).map(([k, l]) => (
        <button key={k} className={`btn ${tab === k ? "btn-primary" : ""}`} onClick={() => setTab(k)}>{l}</button>))}</div>
      {t.isLoading ? <Loading /> : t.data?.items.length ? <div className="space-y-2">{t.data.items.map((x) => <TenderCard key={x.ocid} t={x} context="supplier" />)}</div> : <Empty>Sin concursos.</Empty>}
    </Page>
  );
}
