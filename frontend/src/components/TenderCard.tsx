import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, Tender } from "../api";
import { dateTime, daysLeft, money } from "../format";

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
    <span className="inline-flex gap-1">
      <button title="Me interesa" className={`btn ${t.feedback > 0 ? "btn-primary" : ""}`} onClick={() => m.mutate(1)}>👍</button>
      <button title="No me interesa" className={`btn ${t.feedback < 0 ? "btn-primary" : ""}`} onClick={() => m.mutate(-1)}>👎</button>
    </span>
  );
}

export function FavButton({ t }: { t: Tender }) {
  const qc = useQueryClient();
  const m = useMutation({
    mutationFn: () => t.favorite ? api(`/favorites/${t.ocid}`, { method: "DELETE" }) : api(`/favorites/${t.ocid}`, { method: "PUT", body: { status: "por_cotizar" } }),
    onSuccess: () => qc.invalidateQueries(),
  });
  return <button title="Favorito" className={`btn ${t.favorite ? "btn-primary" : ""}`} onClick={() => m.mutate()}>{t.favorite ? "★" : "☆"}</button>;
}

export function StatusBadge({ t }: { t: Tender }) {
  const d = daysLeft(t.deadline_at);
  const cls = t.is_open ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300" : "";
  return <span className={`badge ${cls}`}>{t.is_open ? `Vigente${d != null && d >= 0 ? ` · ${d} d` : ""}` : t.status_details}</span>;
}

export default function TenderCard({ t, context, extra }: { t: Tender; context: string; extra?: React.ReactNode }) {
  return (
    <div className="card flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
      <div className="min-w-0 space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge t={t} />
          <span className="muted">NOG {t.nog}</span>
          {t.score != null && <span className="badge">{Math.round(t.score * 100)}%</span>}
        </div>
        <Link to={`/tenders/${t.nog}`} className="block font-medium hover:underline">{t.title}</Link>
        <div className="muted">{t.buyer_name}{t.unit_name ? ` · ${t.unit_name}` : ""}</div>
        <div className="muted">
          {t.is_open ? `Cierra ${dateTime(t.deadline_at)}` : t.awarded_total != null ? `Adjudicado ${money(t.awarded_total)}${t.winners[0] ? ` a ${t.winners[0]}` : ""}` : ""}
        </div>
        {t.reason && <div className="text-xs text-brand-600 dark:text-brand-100">{t.reason}</div>}
        {extra}
      </div>
      <div className="flex shrink-0 items-center gap-1">
        <Feedback t={t} context={context} />
        <FavButton t={t} />
      </div>
    </div>
  );
}
