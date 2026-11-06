import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, Tender } from "../api";
import TenderCard, { FAV_LABELS, FavButton, Feedback, StatusBadge } from "../components/TenderCard";
import { ErrorBox, Loading, Page } from "../components/ui";
import { date, dateTime, money, money2 } from "../format";

export default function TenderDetail() {
  const { nog } = useParams();
  const qc = useQueryClient();
  const t = useQuery({ queryKey: ["tender", nog], queryFn: () => api(`/tenders/${nog}`) });
  const comp = useQuery({ queryKey: ["comp", nog], queryFn: () => api(`/tenders/${nog}/price-comparables`) });
  const sim = useQuery({ queryKey: ["similar", nog], queryFn: () => api<{ items: Tender[] }>(`/tenders/${nog}/similar?status=awarded`) });
  if (t.isLoading) return <Loading />;
  if (t.error) return <ErrorBox error={t.error} />;
  const d = t.data;
  return (
    <Page title={`NOG ${d.nog}`} actions={<div className="flex gap-1"><Feedback t={d} context="detail" /><FavButton t={d} />
      <a className="btn" href={d.portal_url} target="_blank" rel="noreferrer">Guatecompras ↗</a></div>}>
      <div className="card space-y-2">
        <StatusBadge t={d} />
        <h2 className="text-lg font-medium">{d.title}</h2>
        <dl className="grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
          <Row k="Entidad" v={d.buyer_name} /><Row k="Unidad" v={d.unit_name || "—"} />
          <Row k="Modalidad" v={d.method || "—"} /><Row k="Publicado" v={date(d.published_at)} />
          <Row k="Cierre de ofertas" v={dateTime(d.deadline_at)} /><Row k="Oferentes" v={d.n_tenderers ?? "—"} />
        </dl>
        {d.favorite && <FavNote t={d} onSaved={() => qc.invalidateQueries({ queryKey: ["tender", nog] })} />}
      </div>

      <Block title="Renglones">
        <table className="w-full text-sm"><thead><tr><th>Descripción</th><th>UNSPSC</th><th>Cantidad</th></tr></thead>
          <tbody>{d.items.map((i: any) => <tr key={i.id} className="border-t border-slate-100 dark:border-slate-800">
            <td>{i.description}</td><td>{i.unspsc}</td><td>{i.quantity ?? "—"} {i.unit ?? ""}</td></tr>)}</tbody></table>
      </Block>

      <Block title="Comparación con adjudicaciones pasadas">
        {comp.isLoading ? <Loading /> : comp.error ? <ErrorBox error={comp.error} /> : (
          <div className="space-y-5">
            {comp.data.items.map((c: any) => <ItemComparables key={c.item.id} c={c} />)}
            {comp.data.similar_tenders && (
              <div>
                <h3 className="mb-1 font-medium">Concursos adjudicados parecidos (monto total)</h3>
                {comp.data.similar_tenders.stats && <p className="muted mb-1">Mediana {money(comp.data.similar_tenders.stats.median)} · rango intercuartil {money(comp.data.similar_tenders.stats.p25)} – {money(comp.data.similar_tenders.stats.p75)}</p>}
                <table className="w-full text-sm"><tbody>{comp.data.similar_tenders.tenders.map((s: any) => (
                  <tr key={s.nog} className="border-t border-slate-100 dark:border-slate-800">
                    <td><Link className="hover:underline" to={`/tenders/${s.nog}`}>{s.title}</Link><div className="muted">{s.buyer_name}</div></td>
                    <td className="text-right tabular-nums">{money(s.awarded_total)}</td><td className="muted">{Math.round(s.similarity * 100)}%</td></tr>))}</tbody></table>
              </div>
            )}
          </div>
        )}
      </Block>

      {(d.bids.length > 0 || d.awards.length > 0) && (
        <Block title="Oferentes y adjudicación">
          <table className="w-full text-sm"><thead><tr><th>Proveedor</th><th>Oferta</th><th>Resultado</th></tr></thead><tbody>
            {d.bids.map((b: any, i: number) => <tr key={i} className="border-t border-slate-100 dark:border-slate-800">
              <td>{b.supplier_id ? <Link className="hover:underline" to={`/suppliers/${b.supplier_id}`}>{b.supplier_name}</Link> : b.supplier_name}</td>
              <td className="tabular-nums">{money2(b.amount)}</td><td>{b.status ?? ""}</td></tr>)}
            {d.awards.map((a: any, i: number) => <tr key={`a${i}`} className="border-t border-slate-100 dark:border-slate-800">
              <td>{a.supplier_id ? <Link className="hover:underline" to={`/suppliers/${a.supplier_id}`}>{a.supplier_name}</Link> : a.supplier_name}</td>
              <td className="tabular-nums">{money2(a.amount)}</td><td><span className="badge">Adjudicado</span></td></tr>)}
          </tbody></table>
        </Block>
      )}
      {d.documents.length > 0 && (
        <Block title="Documentos"><ul className="list-disc pl-5 text-sm">{d.documents.map((x: any, i: number) =>
          <li key={i}><a className="text-brand-600 hover:underline" href={x.url} target="_blank" rel="noreferrer">{x.title || x.doc_type}</a></li>)}</ul></Block>
      )}
      <Block title="Adjudicados similares">
        {sim.data?.items.length ? <div className="space-y-2">{sim.data.items.slice(0, 5).map((x) => <TenderCard key={x.ocid} t={x} context="similar" />)}</div> : <p className="muted">Sin resultados.</p>}
      </Block>
    </Page>
  );
}

function ItemComparables({ c }: { c: any }) {
  const s = c.stats;
  return (
    <div>
      <h3 className="font-medium">{c.item.description} <span className="muted">· {c.item.quantity ?? ""} {c.item.unit ?? ""}</span></h3>
      {!s ? <p className="muted">No hay precios comparables suficientes (solo se derivan precios unitarios de adjudicaciones de un renglón).</p> : (
        <>
          <p className="muted">{s.n} observaciones · mediana {money2(s.median)} · P25–P75 {money2(s.p25)} – {money2(s.p75)} · mín {money2(s.min)} · máx {money2(s.max)}</p>
          {c.trend.length > 1 && (
            <div className="h-36"><ResponsiveContainer><LineChart data={c.trend}>
              <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.3} /><XAxis dataKey="period" fontSize={11} /><YAxis fontSize={11} width={50} /><Tooltip formatter={(v: number) => money2(v)} />
              <Line type="monotone" dataKey="median" name="Mediana" stroke="#2563eb" strokeWidth={2} dot /></LineChart></ResponsiveContainer></div>
          )}
          <table className="mt-1 w-full text-sm"><thead><tr><th>Concurso</th><th>Proveedor</th><th className="text-right">Precio unit.</th><th>Fecha</th><th></th></tr></thead><tbody>
            {c.comparables.slice(0, 8).map((x: any) => (
              <tr key={x.nog + x.awarded_at} className="border-t border-slate-100 dark:border-slate-800">
                <td><Link className="hover:underline" to={`/tenders/${x.nog}`}>{x.title}</Link><div className="muted">{x.buyer_name}</div></td>
                <td>{x.supplier}</td><td className="text-right tabular-nums">{money2(x.unit_price)}</td><td>{date(x.awarded_at)}</td>
                <td className="muted">{Math.round(x.similarity * 100)}%</td></tr>))}
          </tbody></table>
        </>
      )}
    </div>
  );
}

function FavNote({ t, onSaved }: { t: Tender; onSaved: () => void }) {
  const save = async (status: string, note: string) => { await api(`/favorites/${t.ocid}`, { method: "PUT", body: { status, note } }); onSaved(); };
  return (
    <div className="flex flex-wrap items-center gap-2 border-t border-slate-100 pt-2 dark:border-slate-800">
      <select className="input w-auto" value={t.favorite!} onChange={(e) => save(e.target.value, t.note ?? "")}>
        {Object.entries(FAV_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select>
      <input className="input flex-1" placeholder="Nota" defaultValue={t.note ?? ""} onBlur={(e) => e.target.value !== (t.note ?? "") && save(t.favorite!, e.target.value)} />
    </div>
  );
}
const Row = ({ k, v }: { k: string; v: React.ReactNode }) => <div className="flex gap-2"><dt className="muted w-32 shrink-0">{k}</dt><dd>{v}</dd></div>;
const Block = ({ title, children }: { title: string; children: React.ReactNode }) => <section className="card space-y-2"><h2 className="font-medium">{title}</h2>{children}</section>;
