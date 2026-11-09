import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, Tender } from "../api";
import { IconBell } from "../components/icons";
import TenderCard from "../components/TenderCard";
import { Empty, ErrorBox, Loading, Page } from "../components/ui";
import { describe, fromSaved, SavedCombo } from "../filters";
import { dateTime, num } from "../format";
import { HelpLink } from "./Guide";

const FREQ: Record<string, string> = { immediate: "Cada actualización", daily: "Diario", weekly: "Semanal" };

export default function Alerts() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["saved"], queryFn: () => api<{ items: SavedCombo[] }>("/saved-searches") });
  const [msg, setMsg] = useState("");
  const refresh = () => qc.invalidateQueries({ queryKey: ["saved"] });
  const upd = useMutation({ mutationFn: (s: SavedCombo) => api(`/saved-searches/${s.id}`, { method: "PUT", body: s }), onSuccess: refresh });
  const del = useMutation({ mutationFn: (id: number) => api(`/saved-searches/${id}`, { method: "DELETE" }), onSuccess: refresh });
  const run = useMutation({
    mutationFn: () => api<{ mails: number; tenders: number }>("/alerts/run", { method: "POST" }),
    onSuccess: (r) => { setMsg(r.mails ? `Se enviaron ${r.mails} correo(s) con ${r.tenders} concurso(s).` : "No hay concursos nuevos para enviar: ya recibiste los que coinciden esta semana."); refresh(); },
  });
  const items = q.data?.items ?? [];
  return (
    <Page title={<span className="inline-flex items-center gap-2">Alertas y combinaciones <HelpLink section="alertas" /></span>}
      subtitle="Tus combinaciones de filtros guardadas. Con el correo activo recibes de 1 a 10 concursos vigentes que cumplen la combinación y mejor coinciden contigo; un mismo concurso no se repite en 7 días. Créalas desde el panel de filtros de Buscar, Resumen, Para ti u Oportunidades."
      actions={<button className="btn" onClick={() => run.mutate()} disabled={run.isPending || !items.some((s) => s.active)}>{run.isPending ? "Enviando…" : "Enviar ahora"}</button>}>
      {msg && <div className="rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-[13px] text-green-800">{msg}</div>}
      {q.isLoading ? <Loading rows={3} /> : q.error ? <ErrorBox error={q.error} /> : items.length ? (
        <div className="list">{items.map((s) => <Row key={s.id} s={s} onUpdate={(n) => upd.mutate(n)} onDelete={() => confirm("¿Eliminar esta combinación?") && del.mutate(s.id)} />)}</div>
      ) : <Empty icon={<IconBell size={28} />} action={<Link to="/search" className="btn mt-2">Ir a Buscar</Link>}>No tienes combinaciones guardadas. Elige filtros y usa “Guardar combinación”.</Empty>}
    </Page>
  );
}

function Row({ s, onUpdate, onDelete }: { s: SavedCombo; onUpdate: (s: SavedCombo) => void; onDelete: () => void }) {
  const nav = useNavigate();
  const [preview, setPreview] = useState(false);
  const p = useQuery({
    queryKey: ["saved-preview", s.id, s.filters, s.q, s.max_items],
    queryFn: () => api<{ total: number; items: Tender[] }>(`/saved-searches/${s.id}/preview`),
    enabled: preview,
  });
  const summary = [s.q ? `“${s.q}”` : "", describe(fromSaved(s.filters))].filter(Boolean).join(" · ") || "Sin filtros";
  return (
    <div className={`flex flex-col gap-3 px-5 py-4 ${s.active ? "" : "opacity-80"}`}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex min-w-0 flex-[1_1_320px] flex-col gap-1">
          <span className="text-sm font-medium">{s.name}</span>
          <span className="text-[13px] text-stone-600">{summary}</span>
          <span className="text-xs text-stone-600">{s.active ? `Último envío: ${dateTime(s.last_run_at)}` : "Correo desactivado"}</span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex min-h-9 cursor-pointer items-center gap-2 text-[13px]">
            <input type="checkbox" className="h-4 w-4 accent-zinc-900" checked={s.active} onChange={(e) => onUpdate({ ...s, active: e.target.checked })} />Correo</label>
          <select className="input w-auto" aria-label="Frecuencia" disabled={!s.active} value={s.frequency} onChange={(e) => onUpdate({ ...s, frequency: e.target.value })}>
            {Object.entries(FREQ).map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
          <select className="input w-auto" aria-label="Concursos por correo" disabled={!s.active} value={s.max_items ?? 5} onChange={(e) => onUpdate({ ...s, max_items: Number(e.target.value) })}>
            {Array.from({ length: 10 }, (_, i) => i + 1).map((v) => <option key={v} value={v}>{v} por correo</option>)}</select>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <button className="btn" onClick={() => nav("/search", { state: { combo: s } })}>Abrir en Buscar</button>
        <button className="btn" aria-expanded={preview} onClick={() => setPreview(!preview)}>{preview ? "Ocultar próximo correo" : "Ver próximo correo"}</button>
        <button className="btn-ghost ml-auto text-red-700 hover:bg-red-50" onClick={onDelete}>Eliminar</button>
      </div>
      {preview && (p.isLoading ? <Loading rows={2} /> : p.error ? <ErrorBox error={p.error} /> : (
        <div className="flex flex-col gap-2">
          <p className="text-xs text-stone-600">{num(p.data!.total)} concurso(s) vigentes cumplen la combinación. El próximo correo incluiría:</p>
          {p.data!.items.length
            ? <div className="list">{p.data!.items.map((t) => <TenderCard key={t.ocid} t={t} context="alert" />)}</div>
            : <p className="text-[13px] text-stone-600">Nada nuevo: ya recibiste esta semana todos los que coinciden.</p>}
        </div>
      ))}
    </div>
  );
}
