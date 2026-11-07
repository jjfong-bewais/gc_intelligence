import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, Tender } from "../api";
import { IconArrowLeft, IconExternal } from "../components/icons";
import TenderCard, { FAV_LABELS, FavButton, Feedback, StatusBadge } from "../components/TenderCard";
import { ErrorBox, Loading, Segmented } from "../components/ui";
import { closeLabel, date, money, money2, nameCase, num, sentenceCase, stripHtml, supplierName } from "../format";

export default function TenderDetail() {
  const { nog } = useParams();
  const nav = useNavigate();
  const qc = useQueryClient();
  const t = useQuery({ queryKey: ["tender", nog], queryFn: () => api(`/tenders/${nog}`) });
  const comp = useQuery({ queryKey: ["comp", nog], queryFn: () => api(`/tenders/${nog}/price-comparables`) });
  const sim = useQuery({ queryKey: ["similar", nog], queryFn: () => api<{ items: Tender[] }>(`/tenders/${nog}/similar?status=awarded`) });

  const back = (
    <button type="button" onClick={() => (window.history.length > 1 ? nav(-1) : nav("/search"))} className="inline-flex items-center gap-1.5 self-start text-[13px] text-stone-600 hover:text-zinc-900">
      <IconArrowLeft size={14} />Volver
    </button>
  );
  if (t.isLoading) return <div className="flex flex-col gap-6">{back}<Loading rows={3} /></div>;
  if (t.error) return <div className="flex flex-col gap-6">{back}<ErrorBox error={t.error} /></div>;
  const d = t.data;
  const firstStats = comp.data?.items?.find((c: any) => c.stats)?.stats;

  return (
    <div className="flex flex-col gap-6">
      {back}

      <header className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center gap-2.5 text-[13px] text-stone-600">
          <StatusBadge t={d} /><span>NOG {d.nog}</span>
          {d.method && <><span aria-hidden="true">·</span><span>{d.method}</span></>}
        </div>
        <div className="flex flex-wrap items-start justify-between gap-5">
          <h1 className="min-w-0 flex-[1_1_520px] text-2xl font-semibold leading-snug tracking-tight">{sentenceCase(d.title)}</h1>
          <div className="flex flex-wrap items-center gap-2">
            <Feedback t={d} context="detail" />
            <FavButton t={d} label />
            <a className="btn" href={d.portal_url} target="_blank" rel="noreferrer">Guatecompras <IconExternal size={14} /></a>
          </div>
        </div>
      </header>

      <section aria-label="Datos clave" className="grid grid-cols-2 gap-px overflow-hidden rounded-2xl border border-stone-200 bg-stone-100 lg:grid-cols-4 [&>*]:bg-white">
        <Fact k="Entidad" v={nameCase(d.buyer_name)} sub={d.unit_name ? nameCase(d.unit_name) : undefined} />
        <Fact k="Publicado" v={date(d.published_at)} sub={d.n_tenderers != null ? `${d.n_tenderers} oferente(s)` : undefined} />
        <Fact k="Cierre de ofertas" v={d.deadline_at ? date(d.deadline_at) : <span className="text-stone-600">No publicado</span>} sub={d.deadline_at && d.is_open ? closeLabel(d.deadline_at) : undefined} />
        <Fact k="Precio de referencia (mediana)" v={firstStats ? <span className="text-lg text-brand-800">{money(firstStats.median)}</span> : <span className="text-stone-600">Sin datos</span>}
          sub={firstStats ? `${firstStats.n} adjudicaciones comparables` : undefined} />
      </section>

      {d.favorite ? (
        <FavNote t={d} onSaved={() => qc.invalidateQueries({ queryKey: ["tender", nog] })} />
      ) : (
        <p className="text-[13px] text-stone-600">Sigue este concurso para registrar si lo cotizaste, ganaste o perdiste, y agregar notas.</p>
      )}

      <Block title="¿A qué precio se ha adjudicado esto antes?" aside="precio unitario de adjudicaciones parecidas">
        {comp.isLoading ? <Loading rows={2} /> : comp.error ? <ErrorBox error={comp.error} /> : (
          <div className="flex flex-col gap-8">
            {comp.data.items.map((c: any) => <ItemComparables key={c.item.id} c={c} multi={comp.data.items.length > 1} />)}
            {comp.data.similar_tenders?.tenders?.length > 0 && (
              <div className="flex flex-col gap-2">
                <h3 className="text-sm font-semibold">Concursos adjudicados parecidos · monto total</h3>
                {comp.data.similar_tenders.stats && (
                  <p className="text-[13px] text-stone-700">Mediana <b>{money(comp.data.similar_tenders.stats.median)}</b> · la mitad quedó entre {money(comp.data.similar_tenders.stats.p25)} y {money(comp.data.similar_tenders.stats.p75)}</p>
                )}
                <div className="overflow-x-auto">
                  <table className="min-w-[560px]">
                    <thead><tr><th>Concurso</th><th className="text-right">Monto</th><th className="text-right">Similitud</th></tr></thead>
                    <tbody>{comp.data.similar_tenders.tenders.map((s: any) => (
                      <tr key={s.nog}>
                        <td><Link className="font-medium text-zinc-900 hover:text-brand-800" to={`/tenders/${s.nog}`}>{sentenceCase(s.title)}</Link><div className="mt-0.5 text-xs text-stone-600">{nameCase(s.buyer_name)}</div></td>
                        <td className="text-right font-medium tabular-nums">{money(s.awarded_total)}</td>
                        <td className="text-right text-stone-600 tabular-nums">{Math.round(s.similarity * 100)}%</td>
                      </tr>))}</tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}
      </Block>

      <Block title="Renglones">
        <div className="overflow-x-auto">
          <table className="min-w-[520px]">
            <thead><tr><th>Descripción</th><th>UNSPSC</th><th className="text-right">Cantidad</th></tr></thead>
            <tbody>{d.items.map((i: any) => (
              <tr key={i.id}><td>{sentenceCase(i.description)}</td><td className="text-stone-600 tabular-nums">{i.unspsc}</td>
                <td className="text-right tabular-nums">{i.quantity != null ? num(i.quantity) : "—"} {i.unit ? i.unit.toLowerCase() : ""}</td></tr>))}</tbody>
          </table>
        </div>
      </Block>

      {(d.bids.length > 0 || d.awards.length > 0) && (
        <Block title="Oferentes y adjudicación">
          <div className="overflow-x-auto">
            <table className="min-w-[520px]">
              <thead><tr><th>Proveedor</th><th className="text-right">Monto</th><th>Resultado</th></tr></thead>
              <tbody>
                {d.awards.map((a: any, i: number) => (
                  <tr key={`a${i}`}><td><Supplier id={a.supplier_id} name={a.supplier_name} /></td><td className="text-right font-medium tabular-nums">{money2(a.amount)}</td><td><span className="pill-open">Adjudicado</span></td></tr>))}
                {d.bids.map((b: any, i: number) => (
                  <tr key={i}><td><Supplier id={b.supplier_id} name={b.supplier_name} /></td><td className="text-right tabular-nums">{money2(b.amount)}</td><td className="text-stone-600">{b.status ?? ""}</td></tr>))}
              </tbody>
            </table>
          </div>
        </Block>
      )}

      {d.documents.length > 0 && (
        <Block title="Documentos">
          <ul className="flex flex-col gap-1.5 text-[13px]">{d.documents.map((x: any, i: number) => (
            <li key={i}><a className="inline-flex items-center gap-1.5" href={x.url} target="_blank" rel="noreferrer">{stripHtml(x.title || x.doc_type)}<IconExternal size={13} /></a></li>))}</ul>
        </Block>
      )}

      <section className="flex flex-col gap-3">
        <h2 className="h-section">Adjudicados similares</h2>
        {sim.isLoading ? <Loading rows={3} /> : sim.data?.items.length
          ? <div className="list">{sim.data.items.slice(0, 5).map((x) => <TenderCard key={x.ocid} t={x} context="similar" />)}</div>
          : <p className="muted">Sin resultados.</p>}
      </section>
    </div>
  );
}

/** Barra de rango tipo diagrama de caja. Las etiquetas van en columnas fijas para que nunca se encimen. */
function PriceRange({ s }: { s: any }) {
  const iqr = Math.max(0, s.p75 - s.p25);
  // Escala recortada a los "bigotes" (1.5×IQR) para que valores extremos no aplasten la caja.
  const lo = Math.max(s.min, s.p25 - 1.5 * iqr);
  const hi = Math.min(s.max, s.p75 + 1.5 * iqr);
  const span = Math.max(1e-9, hi - lo);
  const pos = (v: number) => Math.min(100, Math.max(0, ((v - lo) / span) * 100));
  const cutLo = s.min < lo, cutHi = s.max > hi;
  const cols: [string, number, boolean][] = [["Mín.", s.min, false], ["P25", s.p25, false], ["Mediana", s.median, true], ["P75", s.p75, false], ["Máx.", s.max, false]];
  return (
    <div className="flex flex-col gap-3">
      <div role="img" className="relative mx-1 h-7"
        aria-label={`Mínimo ${money2(s.min)}, percentil 25 ${money2(s.p25)}, mediana ${money2(s.median)}, percentil 75 ${money2(s.p75)}, máximo ${money2(s.max)}`}>
        <div className="absolute inset-x-0 top-[13px] h-0.5 rounded bg-stone-200" />
        <div className="absolute top-1.5 h-4 rounded bg-brand-100" style={{ left: `${pos(s.p25)}%`, width: `${Math.max(0.5, pos(s.p75) - pos(s.p25))}%` }} />
        <div className="absolute top-0 h-7 w-[3px] -translate-x-1/2 rounded bg-brand-600" style={{ left: `${pos(s.median)}%` }} />
        {cutLo && <span className="absolute -left-1 top-[5px] text-xs leading-none text-stone-500" title={`El mínimo (${money2(s.min)}) queda fuera de escala`}>‹</span>}
        {cutHi && <span className="absolute -right-1 top-[5px] text-xs leading-none text-stone-500" title={`El máximo (${money2(s.max)}) queda fuera de escala`}>›</span>}
      </div>
      <dl className="grid grid-cols-5 gap-1 text-center sm:gap-2">
        {cols.map(([l, v, hl]) => (
          <div key={l} className={`flex min-w-0 flex-col gap-0.5 rounded-lg px-1 py-1.5 ${hl ? "bg-brand-50" : ""}`}>
            <dt className={`text-[11px] ${hl ? "font-medium text-brand-800" : "text-stone-600"}`}>{l}</dt>
            <dd className={`whitespace-nowrap text-xs tabular-nums sm:text-[13px] ${hl ? "font-semibold text-brand-800" : "font-medium text-zinc-900"}`}>{money(v)}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

const compact = (v: number) => new Intl.NumberFormat("es-GT", { style: "currency", currency: "GTQ", notation: "compact", maximumFractionDigits: 1 }).format(v);

function TrendTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="rounded-lg border border-stone-200 bg-white px-3 py-2 text-xs shadow-md">
      <div className="font-medium text-zinc-900">{p.period.replace("-T", " · T")}</div>
      <div className="mt-1 flex items-center gap-1.5 text-stone-700"><span className="h-2 w-2 rounded-full bg-brand-600" />Mediana <b className="tabular-nums text-zinc-900">{money2(p.median)}</b></div>
      {p.n != null && <div className="mt-0.5 text-stone-600">{p.n} adjudicacion{p.n === 1 ? "" : "es"}</div>}
    </div>
  );
}

function ItemComparables({ c, multi }: { c: any; multi: boolean }) {
  const s = c.stats;
  return (
    <div className="flex flex-col gap-4">
      {multi && <h3 className="text-sm font-semibold">{sentenceCase(c.item.description)} <span className="font-normal text-stone-600">· {c.item.quantity ?? ""} {c.item.unit?.toLowerCase() ?? ""}</span></h3>}
      {!s ? <p className="muted">Todavía no hay precios comparables para este renglón (solo se derivan de adjudicaciones de un renglón).</p> : (
        <>
          <PriceRange s={s} />
          <p className="text-[13px] leading-relaxed text-stone-700">
            En <b>{s.n}</b> adjudicaciones parecidas, la mitad quedó entre <b>{money(s.p25)} y {money(s.p75)}</b>; la mediana fue <b>{money2(s.median)}</b>.
          </p>
          {c.trend.length > 1 && (
            <div className="flex flex-col gap-1.5">
              <span className="text-xs text-stone-600">Mediana por trimestre · pasa el cursor para ver el detalle</span>
              <div className="h-40">
                <ResponsiveContainer><LineChart data={c.trend} margin={{ left: 0, right: 12, top: 8, bottom: 0 }}>
                  <CartesianGrid vertical={false} stroke="#f5f5f4" />
                  <XAxis dataKey="period" fontSize={11} tickLine={false} axisLine={false} stroke="#57534e" tickFormatter={(v) => String(v).replace("-T", " T")} padding={{ left: 12, right: 12 }} />
                  <YAxis fontSize={11} width={64} tickLine={false} axisLine={false} stroke="#57534e" tickFormatter={compact} domain={["auto", "auto"]} />
                  <Tooltip content={<TrendTooltip />} cursor={{ stroke: "#a8a29e", strokeDasharray: "3 3" }} />
                  <Line type="monotone" dataKey="median" name="Mediana" stroke="#4f46e5" strokeWidth={2} dot={{ r: 3, fill: "#fff", strokeWidth: 2 }} activeDot={{ r: 5, fill: "#4f46e5", stroke: "#fff", strokeWidth: 2 }} />
                </LineChart></ResponsiveContainer>
              </div>
            </div>
          )}
          <div className="overflow-x-auto">
            <table className="min-w-[640px]">
              <thead><tr><th>Concurso</th><th>Proveedor</th><th className="text-right">Precio unit.</th><th className="text-right">Fecha</th></tr></thead>
              <tbody>{c.comparables.slice(0, 8).map((x: any) => (
                <tr key={x.nog + x.awarded_at}>
                  <td><Link className="font-medium text-zinc-900 hover:text-brand-800" to={`/tenders/${x.nog}`}>{sentenceCase(x.title)}</Link>
                    <div className="mt-0.5 text-xs text-stone-600">{nameCase(x.buyer_name)} · {Math.round(x.similarity * 100)}% similar</div></td>
                  <td className="text-stone-700">{supplierName(x.supplier)}</td>
                  <td className="text-right font-medium tabular-nums">{money2(x.unit_price)}</td>
                  <td className="whitespace-nowrap text-right text-stone-600">{date(x.awarded_at)}</td>
                </tr>))}</tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

function FavNote({ t, onSaved }: { t: Tender; onSaved: () => void }) {
  const save = async (status: string, note: string) => { await api(`/favorites/${t.ocid}`, { method: "PUT", body: { status, note } }); onSaved(); };
  return (
    <section aria-label="Mi estado" className="flex flex-wrap items-center gap-4 rounded-2xl border border-stone-200 bg-white px-5 py-3.5">
      <span className="text-[13px] text-stone-600">Mi estado</span>
      <div className="overflow-x-auto">
        <Segmented label="Estado de seguimiento" value={t.favorite!} options={Object.entries(FAV_LABELS) as [string, string][]} onChange={(v) => save(v, t.note ?? "")} />
      </div>
      <label className="flex flex-[1_1_240px]">
        <span className="sr-only">Nota</span>
        <input className="input bg-stone-50" placeholder="Agregar una nota…" defaultValue={t.note ?? ""}
          onBlur={(e) => e.target.value !== (t.note ?? "") && save(t.favorite!, e.target.value)} />
      </label>
    </section>
  );
}

const Supplier = ({ id, name }: { id?: string; name: string }) =>
  id ? <Link className="font-medium text-zinc-900 hover:text-brand-800" to={`/suppliers/${id}`}>{supplierName(name)}</Link> : <>{supplierName(name)}</>;

const Fact = ({ k, v, sub }: { k: string; v: ReactNode; sub?: string }) => (
  <div className="flex min-w-0 flex-col gap-1 px-5 py-4">
    <span className="text-xs text-stone-600">{k}</span>
    <span className="text-sm font-medium">{v}</span>
    {sub && <span className="truncate text-xs text-stone-600">{sub}</span>}
  </div>
);

const Block = ({ title, aside, children }: { title: string; aside?: string; children: ReactNode }) => (
  <section className="card flex flex-col gap-5 p-6">
    <div className="flex flex-wrap items-baseline justify-between gap-2">
      <h2 className="h-section">{title}</h2>
      {aside && <span className="text-xs text-stone-600">{aside}</span>}
    </div>
    {children}
  </section>
);
