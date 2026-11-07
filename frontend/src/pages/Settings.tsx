import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, ReactNode, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { IconX } from "../components/icons";
import { Empty, ErrorBox, Kpi, KpiStrip, Loading, Page, Segmented } from "../components/ui";
import { date, money, nameCase, num, sentenceCase, supplierName } from "../format";

type Nit = { id: string; nit: string; label: string; name: string | null; found: boolean };

export default function Settings({ user }: { user: any }) {
  return (
    <Page title="Ajustes" subtitle={user.org_name}>
      <AccountCard user={user} />
      <NitsCard />
      <HistoryCard />
    </Page>
  );
}

/* ── Correo de la cuenta ─────────────────────────────────────────────────── */

function AccountCard({ user }: { user: any }) {
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [email, setEmail] = useState(user.email);
  const [password, setPassword] = useState("");
  const [ok, setOk] = useState(false);
  const save = useMutation({
    mutationFn: () => api("/auth/email", { method: "PUT", body: { email, password } }),
    onSuccess: (u) => { qc.setQueryData(["me"], u); setEditing(false); setPassword(""); setOk(true); },
  });
  const submit = (e: FormEvent) => { e.preventDefault(); save.mutate(); };
  const cancel = () => { setEditing(false); setEmail(user.email); setPassword(""); save.reset(); };

  return (
    <section className="card flex flex-col gap-4 p-6">
      <div>
        <h2 className="h-section">Correo electrónico</h2>
        <p className="mt-1 text-[13px] text-stone-600">Con este correo inicias sesión y a él enviamos las alertas y avisos de la plataforma.</p>
      </div>
      {!editing ? (
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-sm font-medium">{user.email}</span>
          <button type="button" className="action-pill" onClick={() => { setEditing(true); setOk(false); }}>Modificar</button>
          {ok && <span className="text-[13px] text-green-700">Correo actualizado</span>}
        </div>
      ) : (
        <form onSubmit={submit} className="flex max-w-sm flex-col gap-3">
          <label className="flex flex-col gap-1 text-[13px] text-stone-700">
            Nuevo correo
            <input className="input" type="email" required autoFocus value={email} onChange={(e) => setEmail(e.target.value)} />
          </label>
          <label className="flex flex-col gap-1 text-[13px] text-stone-700">
            Contraseña actual
            <input className="input" type="password" required autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
            <span className="text-xs text-stone-500">La pedimos para confirmar que eres tú.</span>
          </label>
          {save.error && <p className="text-[13px] text-red-700">{(save.error as Error).message}</p>}
          <div className="flex gap-2">
            <button className="btn btn-primary" disabled={save.isPending}>Guardar</button>
            <button type="button" className="btn" onClick={cancel}>Cancelar</button>
          </div>
        </form>
      )}
    </section>
  );
}

/* ── NIT de la empresa ───────────────────────────────────────────────────── */

function NitsCard() {
  const qc = useQueryClient();
  const list = useQuery({ queryKey: ["org-nits"], queryFn: () => api<{ items: Nit[] }>("/org/suppliers") });
  const [dialog, setDialog] = useState<null | { mode: "add" } | { mode: "edit"; nit: Nit }>(null);
  const [confirming, setConfirming] = useState<string | null>(null);
  const refresh = (items: Nit[]) => {
    qc.setQueryData(["org-nits"], { items });
    // Los NIT alimentan recomendaciones, oportunidades e historial: se recalcula todo.
    qc.invalidateQueries({ predicate: (q) => q.queryKey[0] !== "org-nits" });
  };
  const del = useMutation({
    mutationFn: (nit: string) => api<{ items: Nit[] }>(`/org/suppliers/${encodeURIComponent(nit)}`, { method: "DELETE" }),
    onSuccess: (r) => { setConfirming(null); refresh(r.items); },
  });

  return (
    <section className="card flex flex-col gap-4 p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="h-section">NIT de tu empresa</h2>
          <p className="mt-1 text-[13px] text-stone-600">Con ellos construimos tu perfil de recomendaciones, oportunidades y tu historial.</p>
        </div>
        <button type="button" className="btn btn-primary" onClick={() => setDialog({ mode: "add" })}>+ Agregar NIT</button>
      </div>

      {list.isLoading ? <Loading rows={2} /> : list.error ? <ErrorBox error={list.error} /> : !list.data?.items.length ? (
        <Empty action={<button type="button" className="btn" onClick={() => setDialog({ mode: "add" })}>Agregar el primero</button>}>
          Aún no has agregado NIT. Agrega al menos uno para recibir recomendaciones basadas en lo que tu empresa ya ha cotizado y ganado.
        </Empty>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-stone-200">
          <table className="min-w-[640px]">
            <thead className="bg-white">
              <tr className="[&>th]:py-3 [&>th:first-child]:pl-5 [&>th:last-child]:pr-5">
                <th>Nombre</th><th>NIT</th><th>Razón social en Guatecompras</th><th className="text-right">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {list.data.items.map((n) => (
                <tr key={n.id} className="[&>td]:py-3.5 [&>td]:align-middle [&>td:first-child]:pl-5 [&>td:last-child]:pr-5">
                  <td className="font-medium text-brand-700">{n.label || <span className="font-normal italic text-stone-500">Sin nombre</span>}</td>
                  <td className="font-mono tabular-nums">{n.nit}</td>
                  <td>{n.found ? supplierName(n.name) : <span className="text-stone-500">Sin registros en Guatecompras</span>}</td>
                  <td className="text-right">
                    {confirming === n.nit ? (
                      <span className="inline-flex items-center gap-2">
                        <span className="text-[13px] text-stone-700">¿Eliminar?</span>
                        <button type="button" className="action-pill is-danger" disabled={del.isPending} onClick={() => del.mutate(n.nit)}>Sí, eliminar</button>
                        <button type="button" className="action-pill" onClick={() => setConfirming(null)}>No</button>
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-2">
                        <button type="button" className="action-pill" onClick={() => setDialog({ mode: "edit", nit: n })}>Modificar</button>
                        <button type="button" className="action-pill" onClick={() => setConfirming(n.nit)}>Eliminar</button>
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {del.error && <p className="text-[13px] text-red-700">{(del.error as Error).message}</p>}

      {dialog && (
        <NitDialog
          initial={dialog.mode === "edit" ? dialog.nit : undefined}
          onClose={() => setDialog(null)}
          onSaved={(items) => { refresh(items); setDialog(null); }}
        />
      )}
    </section>
  );
}

function NitDialog({ initial, onClose, onSaved }: { initial?: Nit; onClose: () => void; onSaved: (items: Nit[]) => void }) {
  const [nit, setNit] = useState(initial?.nit ?? "");
  const [label, setLabel] = useState(initial?.label ?? "");
  const first = useRef<HTMLInputElement>(null);
  const save = useMutation({
    mutationFn: () => initial
      ? api<{ items: Nit[] }>(`/org/suppliers/${encodeURIComponent(initial.nit)}`, { method: "PUT", body: { nit, label } })
      : api<{ items: Nit[] }>("/org/suppliers", { method: "POST", body: { nit, label } }),
    onSuccess: (r) => onSaved(r.items),
  });
  useEffect(() => {
    first.current?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-900/30 p-4" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <form role="dialog" aria-modal="true" aria-labelledby="nit-dialog-title" className="card flex w-full max-w-md flex-col gap-4 p-6 shadow-xl"
        onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
        <div className="flex items-start justify-between gap-3">
          <h3 id="nit-dialog-title" className="h-section">{initial ? "Modificar NIT" : "Agregar NIT"}</h3>
          <button type="button" className="btn-icon border-transparent" aria-label="Cerrar" onClick={onClose}><IconX size={16} /></button>
        </div>
        <label className="flex flex-col gap-1 text-[13px] text-stone-700">
          Nombre de identificación
          <input ref={first} className="input" required maxLength={200} placeholder="Ej. Casa matriz, Sucursal Xela" value={label} onChange={(e) => setLabel(e.target.value)} />
        </label>
        <label className="flex flex-col gap-1 text-[13px] text-stone-700">
          NIT
          <input className="input font-mono" required inputMode="text" placeholder="Ej. 1234567-8" value={nit} onChange={(e) => setNit(e.target.value)} />
          <span className="text-xs text-stone-500">Sin guiones ni espacios también funciona. Puede terminar en K.</span>
        </label>
        {save.error && <p className="text-[13px] text-red-700">{(save.error as Error).message}</p>}
        <div className="flex justify-end gap-2">
          <button type="button" className="btn" onClick={onClose}>Cancelar</button>
          <button className="btn btn-primary" disabled={save.isPending}>{initial ? "Guardar cambios" : "Agregar"}</button>
        </div>
      </form>
    </div>
  );
}

/* ── Historial en Guatecompras ───────────────────────────────────────────── */

type Group = { key: string; participated: number; won: number; lost: number; awarded_amount: number; win_rate: number | null; sample?: string };
type HItem = {
  ocid: string; nog: number; title: string; buyer_name: string; published_at: string | null; status_details: string | null;
  method: string | null; n_tenderers: number | null; awarded_amount: number | null; bid_amount: number | null; winners: string[];
};
type History = {
  has_data: boolean;
  totals: null | {
    participated: number; won: number; lost: number; in_progress: number; void: number; decided: number; win_rate: number | null;
    awarded_amount: number; avg_award: number | null; bid_amount: number; bids_with_amount: number; buyers_won: number;
    buyers_participated: number; avg_competitors: number | null; first_at: string | null; last_at: string | null;
  };
  by_nit: { id: string; nit: string; label: string; name: string | null; participated: number; won: number; decided: number; win_rate: number | null; awarded_amount: number }[];
  monthly: Group[]; top_buyers: Group[]; top_classes: Group[]; methods: Group[]; regions: Group[];
  competitors: { id: string; name: string; n: number; amount: number }[];
  recent: { won: HItem[]; lost: HItem[]; in_progress: HItem[] };
};

const pct = (v: number | null | undefined) => (v == null ? "—" : `${new Intl.NumberFormat("es-GT", { maximumFractionDigits: 1 }).format(v * 100)} %`);
const WON = "#4338ca";
const NOT_WON = "#7c86f2";

function HistoryCard() {
  const h = useQuery({ queryKey: ["org-history"], queryFn: () => api<History>("/org/history") });
  return (
    <section className="flex flex-col gap-4">
      <div>
        <h2 className="h-section">Tu historial en Guatecompras</h2>
        <p className="mt-1 text-[13px] text-stone-600">Resumen de todos los concursos 2026 en los que tus NIT ofertaron o resultaron adjudicados.</p>
      </div>
      {h.isLoading ? <Loading rows={4} /> : h.error ? <ErrorBox error={h.error} /> : !h.data?.has_data || !h.data.totals ? (
        <Empty>{h.data?.by_nit.length ? "No encontramos ofertas ni adjudicaciones de tus NIT en los datos de Guatecompras de 2026." : "Agrega un NIT para ver tu historial."}</Empty>
      ) : <HistoryBody d={h.data} t={h.data.totals} />}
    </section>
  );
}

function HistoryBody({ d, t }: { d: History; t: NonNullable<History["totals"]> }) {
  const [tab, setTab] = useState<"won" | "lost" | "in_progress">("won");
  return (
    <>
      <KpiStrip>
        <Kpi label="Concursos participados" value={num(t.participated)} hint={t.first_at ? `${date(t.first_at)} – ${date(t.last_at)}` : undefined} />
        <Kpi label="Adjudicados" value={num(t.won)} hint={`${num(t.lost)} no adjudicados`} />
        <Kpi label="% de adjudicación" value={pct(t.win_rate)} hint={`Sobre ${num(t.decided)} concursos con resultado`} />
        <Kpi label="Monto adjudicado" value={money(t.awarded_amount)} hint={t.avg_award != null ? `Promedio ${money(t.avg_award)} por concurso` : undefined} />
      </KpiStrip>
      <KpiStrip>
        <Kpi label="En curso" value={num(t.in_progress)} hint="Vigentes o en evaluación" />
        <Kpi label="Desiertos o anulados" value={num(t.void)} hint="No cuentan en el % de adjudicación" />
        <Kpi label="Entidades compradoras" value={num(t.buyers_won)} hint={`Te adjudicaron · ${num(t.buyers_participated)} donde participaste`} />
        <Kpi label="Oferentes por concurso" value={t.avg_competitors == null ? "—" : num(t.avg_competitors)} hint="Promedio en los concursos donde participaste" />
      </KpiStrip>

      {d.monthly.length > 0 && <MonthlyChart rows={d.monthly} />}

      {d.by_nit.length > 1 && (
        <Panel title="Por NIT">
          <table className="min-w-[560px]"><thead><tr><th>Nombre</th><th>NIT</th><th className="text-right">Participados</th><th className="text-right">Adjudicados</th><th className="text-right">% adj.</th><th className="text-right">Monto adjudicado</th></tr></thead>
            <tbody>{d.by_nit.map((n) => (
              <tr key={n.id}><td className="font-medium">{n.label || supplierName(n.name) || "—"}</td><td className="font-mono tabular-nums">{n.nit}</td>
                <td className="text-right tabular-nums">{num(n.participated)}</td><td className="text-right tabular-nums">{num(n.won)}</td>
                <td className="text-right tabular-nums">{pct(n.win_rate)}</td><td className="text-right tabular-nums">{money(n.awarded_amount)}</td></tr>
            ))}</tbody></table>
        </Panel>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <GroupTable title="Principales entidades compradoras" head="Entidad" rows={d.top_buyers} render={(r) => nameCase(r.key)} />
        <GroupTable title="Principales categorías (UNSPSC)" head="Categoría" rows={d.top_classes}
          render={(r) => <span className="flex flex-col"><span className="font-mono text-xs text-stone-600">{r.key}</span><span className="line-clamp-1">{sentenceCase(r.sample)}</span></span>} />
        <GroupTable title="Modalidades de compra" head="Modalidad" rows={d.methods} render={(r) => r.key} />
        <GroupTable title="Departamentos" head="Departamento" rows={d.regions} render={(r) => nameCase(r.key)} />
      </div>

      {d.competitors.length > 0 && (
        <Panel title="Competidores que te ganaron" subtitle="Proveedores adjudicados en concursos donde ofertaste y no ganaste.">
          <table className="min-w-[480px]"><thead><tr><th>Proveedor</th><th className="text-right">Veces</th><th className="text-right">Monto adjudicado</th></tr></thead>
            <tbody>{d.competitors.map((c) => (
              <tr key={c.id}><td><Link to={`/suppliers/${c.id}`}>{supplierName(c.name)}</Link></td>
                <td className="text-right tabular-nums">{num(c.n)}</td><td className="text-right tabular-nums">{money(c.amount)}</td></tr>
            ))}</tbody></table>
        </Panel>
      )}

      <Panel title="Concursos (NOG)" actions={
        <Segmented label="Tipo de concursos" value={tab} onChange={setTab}
          options={[["won", `Adjudicados · ${num(t.won)}`], ["lost", `No adjudicados · ${num(t.lost)}`], ["in_progress", `En curso · ${num(t.in_progress)}`]] as const} />
      }>
        <NogTable kind={tab} items={d.recent[tab]} total={tab === "won" ? t.won : tab === "lost" ? t.lost : t.in_progress} />
      </Panel>
    </>
  );
}

function Panel({ title, subtitle, actions, children }: { title: string; subtitle?: string; actions?: ReactNode; children: ReactNode }) {
  return (
    <div className="card flex flex-col gap-3 p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><h3 className="text-sm font-semibold">{title}</h3>{subtitle && <p className="mt-0.5 text-xs text-stone-600">{subtitle}</p>}</div>
        {actions}
      </div>
      <div className="overflow-x-auto">{children}</div>
    </div>
  );
}

function GroupTable({ title, head, rows, render }: { title: string; head: string; rows: Group[]; render: (r: Group) => ReactNode }) {
  if (!rows.length) return null;
  return (
    <Panel title={title}>
      <table><thead><tr><th>{head}</th><th className="text-right">Part.</th><th className="text-right">Adj.</th><th className="text-right">Monto</th></tr></thead>
        <tbody>{rows.map((r) => (
          <tr key={r.key}><td>{render(r)}</td><td className="text-right tabular-nums">{num(r.participated)}</td>
            <td className="text-right tabular-nums">{num(r.won)}</td><td className="whitespace-nowrap text-right tabular-nums">{money(r.awarded_amount)}</td></tr>
        ))}</tbody></table>
    </Panel>
  );
}

function NogTable({ kind, items, total }: { kind: "won" | "lost" | "in_progress"; items: HItem[]; total: number }) {
  if (!items.length) return <p className="py-4 text-[13px] text-stone-600">Sin concursos en esta categoría.</p>;
  return (
    <>
      <table className="min-w-[720px]">
        <thead><tr><th>NOG</th><th>Concurso</th><th>Entidad</th><th>Publicado</th>
          {kind === "lost" && <th>Adjudicado a</th>}
          <th className="text-right">{kind === "won" ? "Monto adjudicado" : "Tu oferta"}</th></tr></thead>
        <tbody>{items.map((i) => (
          <tr key={i.ocid}>
            <td className="whitespace-nowrap font-mono tabular-nums"><Link to={`/tenders/${i.nog}`}>{i.nog}</Link></td>
            <td className="max-w-[280px]"><span className="line-clamp-2">{sentenceCase(i.title)}</span>
              {kind === "in_progress" && i.status_details && <span className="badge mt-1">{i.status_details}</span>}</td>
            <td className="max-w-[200px]"><span className="line-clamp-2 text-stone-700">{nameCase(i.buyer_name)}</span></td>
            <td className="whitespace-nowrap text-stone-600">{date(i.published_at)}</td>
            {kind === "lost" && <td className="max-w-[180px]"><span className="line-clamp-2">{i.winners.length ? i.winners.map(supplierName).join(", ") : "—"}</span></td>}
            <td className="whitespace-nowrap text-right tabular-nums">{money(kind === "won" ? i.awarded_amount : i.bid_amount)}</td>
          </tr>
        ))}</tbody>
      </table>
      {total > items.length && <p className="pt-2 text-xs text-stone-600">Mostrando los {num(items.length)} más recientes de {num(total)}.</p>}
    </>
  );
}

/* Barras apiladas por mes: adjudicados (oscuro) + no adjudicados/en curso (claro) = participados. */
function MonthlyChart({ rows }: { rows: Group[] }) {
  const [hover, setHover] = useState<number | null>(null);
  const max = Math.max(1, ...rows.map((r) => r.participated));
  const label = (k: string) => new Intl.DateTimeFormat("es-GT", { month: "short", timeZone: "UTC" }).format(new Date(`${k}-01T00:00:00Z`)).replace(".", "");
  const H = 160;
  return (
    <Panel title="Participación por mes" actions={
      <div className="flex items-center gap-4 text-xs text-stone-700">
        <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm" style={{ background: WON }} />Adjudicados</span>
        <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm" style={{ background: NOT_WON }} />Otros participados</span>
      </div>
    }>
      <div className="relative flex min-w-[420px] items-end gap-2 border-b border-stone-200 pt-6" style={{ height: H + 24 }} onMouseLeave={() => setHover(null)}>
        {rows.map((r, i) => {
          const total = (r.participated / max) * H;
          const won = (r.won / max) * H;
          return (
            <div key={r.key} className="relative flex h-full flex-1 cursor-default flex-col items-center justify-end" onMouseEnter={() => setHover(i)}
              tabIndex={0} onFocus={() => setHover(i)} onBlur={() => setHover(null)}
              aria-label={`${label(r.key)}: ${r.participated} participados, ${r.won} adjudicados`}>
              {hover === i && (
                <div className="pointer-events-none absolute bottom-full z-10 mb-1 whitespace-nowrap rounded-lg border border-stone-200 bg-white px-3 py-2 text-xs shadow-md">
                  <div className="font-medium capitalize">{label(r.key)} {r.key.slice(0, 4)}</div>
                  <div className="text-stone-700">{num(r.participated)} participados · {num(r.won)} adjudicados</div>
                  <div className="text-stone-700">{money(r.awarded_amount)} adjudicado</div>
                </div>
              )}
              <div className="flex w-full max-w-[36px] flex-col justify-end gap-[2px]" style={{ height: total }}>
                {r.participated > r.won && <div className="w-full rounded-t-[4px]" style={{ background: NOT_WON, height: total - won - (r.won ? 2 : 0), opacity: hover == null || hover === i ? 1 : 0.55 }} />}
                {r.won > 0 && <div className={`w-full ${r.participated > r.won ? "" : "rounded-t-[4px]"}`} style={{ background: WON, height: won, opacity: hover == null || hover === i ? 1 : 0.55 }} />}
              </div>
            </div>
          );
        })}
      </div>
      <div className="flex min-w-[420px] gap-2 pt-1.5">
        {rows.map((r) => <div key={r.key} className="flex-1 text-center text-[11px] capitalize text-stone-600">{label(r.key)}</div>)}
      </div>
    </Panel>
  );
}
