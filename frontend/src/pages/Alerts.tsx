import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { IconBell } from "../components/icons";
import { Empty, ErrorBox, Loading, Page } from "../components/ui";
import { dateTime } from "../format";

const FREQ: Record<string, string> = { immediate: "Cada actualización", daily: "Diaria", weekly: "Semanal" };
const STATUS: Record<string, string> = { open: "Vigentes", evaluation: "En evaluación", awarded: "Adjudicados", unsuccessful: "Desiertos", all: "Todos" };

export default function Alerts() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["saved"], queryFn: () => api("/saved-searches") });
  const [msg, setMsg] = useState("");
  const refresh = () => qc.invalidateQueries({ queryKey: ["saved"] });
  const upd = useMutation({ mutationFn: (s: any) => api(`/saved-searches/${s.id}`, { method: "PUT", body: s }), onSuccess: refresh });
  const del = useMutation({ mutationFn: (id: number) => api(`/saved-searches/${id}`, { method: "DELETE" }), onSuccess: refresh });
  const run = useMutation({ mutationFn: () => api("/alerts/run", { method: "POST" }), onSuccess: (r: any) => { setMsg(`Se enviaron ${r.mails} correo(s) con ${r.tenders} concurso(s) nuevo(s).`); refresh(); } });
  const items = q.data?.items ?? [];
  return (
    <Page title="Alertas" subtitle="Recibe por correo los concursos nuevos que coincidan con tus búsquedas guardadas. Créalas desde Buscar."
      actions={<button className="btn" onClick={() => run.mutate()} disabled={run.isPending}>{run.isPending ? "Enviando…" : "Enviar ahora"}</button>}>
      {msg && <div className="rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-[13px] text-green-800">{msg}</div>}
      {q.isLoading ? <Loading rows={3} /> : q.error ? <ErrorBox error={q.error} /> : items.length ? (
        <div className="list">{items.map((s: any) => (
          <div key={s.id} className={`flex flex-wrap items-center justify-between gap-4 px-5 py-4 ${s.active ? "" : "opacity-60"}`}>
            <div className="flex min-w-0 flex-col gap-1">
              <span className="text-sm font-medium">{s.name}</span>
              <span className="text-[13px] text-stone-600">“{s.q || "sin texto"}” · {STATUS[s.filters?.status ?? "all"] ?? s.filters?.status}{s.filters?.unspsc ? ` · UNSPSC ${s.filters.unspsc}` : ""}{s.filters?.buyer ? ` · ${s.filters.buyer}` : ""}</span>
              <span className="text-xs text-stone-600">Último envío: {dateTime(s.last_run_at)}</span>
            </div>
            <div className="flex items-center gap-2">
              <select className="input w-auto" aria-label="Frecuencia" value={s.frequency} onChange={(e) => upd.mutate({ ...s, frequency: e.target.value })}>
                {Object.entries(FREQ).map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
              <label className="flex min-h-9 cursor-pointer items-center gap-2 text-[13px]">
                <input type="checkbox" className="h-4 w-4 accent-zinc-900" checked={s.active} onChange={(e) => upd.mutate({ ...s, active: e.target.checked })} />Activa</label>
              <button className="btn-ghost text-red-700 hover:bg-red-50" onClick={() => confirm("¿Eliminar esta alerta?") && del.mutate(s.id)}>Eliminar</button>
            </div>
          </div>
        ))}</div>
      ) : <Empty icon={<IconBell size={28} />} action={<Link to="/search" className="btn mt-2">Ir a Buscar</Link>}>No tienes alertas. Haz una búsqueda y usa “Crear alerta con esta búsqueda”.</Empty>}
    </Page>
  );
}
