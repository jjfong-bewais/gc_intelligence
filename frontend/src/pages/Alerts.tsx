import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api";
import { Empty, ErrorBox, Loading, Page } from "../components/ui";
import { dateTime } from "../format";

const FREQ: Record<string, string> = { immediate: "Cada corrida", daily: "Diaria", weekly: "Semanal" };

export default function Alerts() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["saved"], queryFn: () => api("/saved-searches") });
  const [msg, setMsg] = useState("");
  const refresh = () => qc.invalidateQueries({ queryKey: ["saved"] });
  const upd = useMutation({ mutationFn: (s: any) => api(`/saved-searches/${s.id}`, { method: "PUT", body: s }), onSuccess: refresh });
  const del = useMutation({ mutationFn: (id: number) => api(`/saved-searches/${id}`, { method: "DELETE" }), onSuccess: refresh });
  const run = useMutation({ mutationFn: () => api("/alerts/run", { method: "POST" }), onSuccess: (r: any) => { setMsg(`Se enviaron ${r.mails} correo(s) con ${r.tenders} concurso(s) nuevo(s).`); refresh(); } });
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorBox error={q.error} />;
  const items = q.data.items;
  return (
    <Page title="Alertas por correo" actions={<button className="btn" onClick={() => run.mutate()} disabled={run.isPending}>Enviar ahora</button>}>
      {msg && <div className="card text-sm">{msg}</div>}
      <p className="muted">Guarda una búsqueda desde “Buscar” para recibir por correo los concursos nuevos que coincidan. Cada correo trae 👍/👎 y un enlace para pausar.</p>
      {items.length ? items.map((s: any) => (
        <div key={s.id} className="card flex flex-wrap items-center justify-between gap-2">
          <div className="min-w-0">
            <div className="font-medium">{s.name}</div>
            <div className="muted">“{s.q || "sin texto"}” · {s.filters?.status ?? "all"}{s.filters?.unspsc ? ` · UNSPSC ${s.filters.unspsc}` : ""}{s.filters?.buyer ? ` · ${s.filters.buyer}` : ""}</div>
            <div className="muted text-xs">Última corrida: {dateTime(s.last_run_at)}</div>
          </div>
          <div className="flex items-center gap-2">
            <select className="input w-auto" value={s.frequency} onChange={(e) => upd.mutate({ ...s, frequency: e.target.value })}>
              {Object.entries(FREQ).map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
            <label className="flex items-center gap-1 text-sm"><input type="checkbox" checked={s.active} onChange={(e) => upd.mutate({ ...s, active: e.target.checked })} />Activa</label>
            <button className="btn" onClick={() => confirm("¿Eliminar esta alerta?") && del.mutate(s.id)}>Eliminar</button>
          </div>
        </div>
      )) : <Empty>No tienes alertas guardadas.</Empty>}
    </Page>
  );
}
