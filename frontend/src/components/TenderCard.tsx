import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ReactNode } from "react";
import { Link } from "react-router-dom";
import { api, Tender } from "../api";
import { closeLabel, daysLeft, money, nameCase, sentenceCase, supplierName } from "../format";
import { IconBookmark, IconThumbDown, IconThumbUp } from "./icons";

export const FAV_LABELS: Record<string, string> = {
  por_cotizar: "Por cotizar", cotizado: "Cotizado", ganado: "Ganado", perdido: "Perdido", descartado: "Descartado",
};

export function Feedback({ t, context }: { t: Tender; context: string }) {
  const qc = useQueryClient();
  const m = useMutation({
    mutationFn: (signal: number) => api(`/feedback/${t.ocid}`, { method: "PUT", body: { signal: t.feedback === signal ? 0 : signal, context } }),
    onSuccess: () => qc.invalidateQueries(),
  });
  return (
    <>
      <button type="button" aria-label="Me interesa" aria-pressed={t.feedback > 0} title="Me interesa"
        className={`btn-icon ${t.feedback > 0 ? "is-on" : ""}`} onClick={() => m.mutate(1)}><IconThumbUp /></button>
      <button type="button" aria-label="No me interesa" aria-pressed={t.feedback < 0} title="No me interesa"
        className={`btn-icon ${t.feedback < 0 ? "is-on" : ""}`} onClick={() => m.mutate(-1)}><IconThumbDown /></button>
    </>
  );
}

export function FavButton({ t, label }: { t: Tender; label?: boolean }) {
  const qc = useQueryClient();
  const m = useMutation({
    mutationFn: () => t.favorite ? api(`/favorites/${t.ocid}`, { method: "DELETE" }) : api(`/favorites/${t.ocid}`, { method: "PUT", body: { status: "por_cotizar" } }),
    onSuccess: () => qc.invalidateQueries(),
  });
  const on = !!t.favorite;
  if (label) {
    return (
      <button type="button" aria-pressed={on} className={`btn ${on ? "btn-primary" : ""}`} onClick={() => m.mutate()}>
        <IconBookmark filled={on} size={15} />{on ? "En seguimiento" : "Seguir concurso"}
      </button>
    );
  }
  return (
    <button type="button" aria-label={on ? "Dejar de seguir" : "Seguir concurso"} aria-pressed={on} title={on ? "En seguimiento" : "Seguir concurso"}
      className={`btn-icon ${on ? "is-on" : ""}`} onClick={() => m.mutate()}><IconBookmark filled={on} /></button>
  );
}

export function StatusBadge({ t }: { t: Tender }) {
  if (t.is_open) {
    const d = daysLeft(t.deadline_at);
    return <span className="pill-open">{d != null && d >= 0 && d <= 3 ? closeLabel(t.deadline_at) : "Vigente"}</span>;
  }
  return <span className="badge">{t.status_details}</span>;
}

/** Fila de concurso. Úsala dentro de un contenedor `.list`. */
export default function TenderCard({ t, context, extra }: { t: Tender; context: string; extra?: ReactNode }) {
  const meta = t.is_open
    ? closeLabel(t.deadline_at)
    : t.awarded_total != null
      ? `Adjudicado ${money(t.awarded_total)}${t.winners[0] ? ` · ${supplierName(t.winners[0])}` : ""}`
      : t.status_details;
  return (
    <article className="flex flex-wrap items-start gap-x-4 gap-y-3 px-5 py-4 transition-colors hover:bg-stone-50/60">
      {t.score != null && (
        <div className="flex w-11 shrink-0 flex-col items-center pt-0.5">
          <span className="text-[15px] font-semibold tabular-nums text-brand-800">{Math.round(t.score * 100)}%</span>
          <span className="text-[10px] text-stone-600">afinidad</span>
        </div>
      )}
      <div className="flex min-w-0 flex-[1_1_320px] flex-col gap-1">
        <Link to={`/tenders/${t.nog}`} className="text-sm font-medium leading-snug text-zinc-900 hover:text-brand-800">
          {sentenceCase(t.title)}
        </Link>
        <div className="text-[13px] text-stone-600">
          {nameCase(t.buyer_name)}{t.unit_name ? ` · ${nameCase(t.unit_name)}` : ""}{t.department ? ` · ${nameCase(t.department)}` : ""} · NOG {t.nog}
        </div>
        {t.reason && <div className="text-xs text-stone-600">{t.reason.replace(/«([^»]+)»/g, (_, q) => `«${sentenceCase(q)}»`)}</div>}
        {extra}
      </div>
      <div className="flex shrink-0 flex-col items-end gap-2">
        <div className="flex items-center gap-1.5">
          <StatusBadge t={t} />
          <Feedback t={t} context={context} />
          <FavButton t={t} />
        </div>
        {meta && <span className="text-xs text-stone-600">{meta}</span>}
      </div>
    </article>
  );
}
