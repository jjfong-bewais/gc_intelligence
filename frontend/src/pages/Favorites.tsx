import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, Tender } from "../api";
import { IconBookmark } from "../components/icons";
import TenderCard, { FAV_LABELS, publishedLabel } from "../components/TenderCard";
import { Empty, ErrorBox, Loading, Page, Segmented, useFeedback } from "../components/ui";
import { money, nameCase, sentenceCase } from "../format";
import { HistoryCard } from "./Settings";

const VIEWS = [["board", "Tablero"], ["list", "Lista"], ["history", "Historial"]] as const;
type View = (typeof VIEWS)[number][0];
const COLUMNS = ["por_cotizar", "cotizado", "ganado", "perdido", "descartado"] as const;

export default function Favorites() {
  const [view, setView] = useState<View>("board");
  const [f, setF] = useState("");
  const q = useQuery({ queryKey: ["favs"], queryFn: () => api<{ items: Tender[] }>("/favorites") });
  const all = q.data?.items ?? [];
  const count = (s: string) => all.filter((t) => !s || t.favorite === s).length;
  const opts = [["", `Todos ${count("")}`], ...Object.entries(FAV_LABELS).map(([v, l]) => [v, `${l} ${count(v)}`])] as [string, string][];
  return (
    <Page title="Seguimiento" subtitle="Los concursos que sigues, el precio que piensas ofertar y en qué etapa va cada uno."
      actions={<Segmented label="Vista" value={view} options={VIEWS} onChange={setView} />}>
      {view === "history" ? <HistoryCard /> : q.isLoading ? <Loading /> : q.error ? <ErrorBox error={q.error} /> : !all.length ? (
        <Empty icon={<IconBookmark size={28} />} action={<Link to="/search" className="btn mt-2">Buscar concursos</Link>}>Usa el ícono de marcador en cualquier concurso para seguirlo aquí.</Empty>
      ) : view === "board" ? <Board items={all} /> : (
        <>
          <div className="overflow-x-auto"><Segmented label="Filtrar por estado" value={f} options={opts} onChange={setF} /></div>
          <div className="list">{all.filter((t) => !f || t.favorite === f).map((t) => <TenderCard key={t.ocid} t={t} context="favorites" extra={
            <div className="mt-1 flex flex-wrap items-center gap-2 text-xs"><span className="badge">{FAV_LABELS[t.favorite!]}</span>{t.note && <span className="text-stone-600">{t.note}</span>}</div>} />)}</div>
        </>
      )}
    </Page>
  );
}

/** Tablero por etapa. Se mueve un concurso con el selector de su tarjeta (accesible con teclado). */
function Board({ items }: { items: Tender[] }) {
  const qc = useQueryClient();
  const { toast } = useFeedback();
  const move = useMutation({
    mutationFn: ({ t, status }: { t: Tender; status: string }) => api(`/favorites/${t.ocid}`, { method: "PUT", body: { status, note: t.note ?? "", my_price: t.my_price ?? null } }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["favs"] }); toast("Movido"); },
    onError: (e) => toast((e as Error).message, "error"),
  });
  return (
    <div className="grid gap-4 overflow-x-auto pb-2 md:grid-cols-5 [&>*]:min-w-[220px]">
      {COLUMNS.map((col) => {
        const rows = items.filter((t) => t.favorite === col);
        const total = rows.reduce((a, t) => a + (t.my_price ?? 0), 0);
        return (
          <section key={col} aria-label={FAV_LABELS[col]} className="flex flex-col gap-2 rounded-2xl bg-stone-100/70 p-2.5">
            <header className="flex items-baseline justify-between px-1.5 pt-1">
              <h2 className="font-display text-[13px] font-semibold">{FAV_LABELS[col]}</h2>
              <span className="text-xs text-stone-600">{rows.length}{total > 0 ? ` · ${money(total)}` : ""}</span>
            </header>
            {rows.map((t) => (
              <article key={t.ocid} className="flex flex-col gap-1.5 rounded-xl border border-stone-200 bg-white p-3">
                <Link to={`/tenders/${t.nog}`} className="text-[13px] font-medium leading-snug text-zinc-900 hover:text-brand-800">{sentenceCase(t.title)}</Link>
                <span className="text-xs text-stone-600">{nameCase(t.buyer_name)}</span>
                <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
                  {t.my_price != null && <b className="text-brand-800">Mi precio {money(t.my_price)}</b>}
                  {t.reference_price != null && <span className="text-stone-600">Ref. {money(t.reference_price)}</span>}
                  {t.is_open && t.days_since_published != null && <span className="text-stone-600">{publishedLabel(t.days_since_published)}</span>}
                </div>
                {t.note && <p className="text-xs text-stone-600">{t.note}</p>}
                <select aria-label="Cambiar etapa" className="input mt-1 min-h-8 py-0 text-xs" value={col} onChange={(e) => move.mutate({ t, status: e.target.value })}>
                  {COLUMNS.map((c) => <option key={c} value={c}>{FAV_LABELS[c]}</option>)}
                </select>
              </article>
            ))}
            {!rows.length && <p className="px-2 py-4 text-center text-xs text-stone-500">Sin concursos</p>}
          </section>
        );
      })}
    </div>
  );
}
