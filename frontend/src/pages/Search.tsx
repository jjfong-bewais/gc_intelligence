import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useLocation } from "react-router-dom";
import { api, Tender } from "../api";
import TenderCard from "../components/TenderCard";
import { Empty, ErrorBox, Loading, Page } from "../components/ui";

const STATUS = [["all", "Todos"], ["open", "Vigentes"], ["evaluation", "En evaluación"], ["awarded", "Adjudicados"], ["unsuccessful", "Desiertos"]];
const MODES = [["hybrid", "Híbrida"], ["keyword", "Palabras clave"], ["semantic", "Semántica"]];

export default function Search() {
  const qc = useQueryClient();
  const pre = (useLocation().state as { unspsc?: string } | null)?.unspsc ?? "";
  const [form, setForm] = useState({ q: "", mode: "hybrid", status: "open", unspsc: pre, buyer: "", date_from: "", date_to: "", sort: "recent" });
  const [page, setPage] = useState(0);
  const [applied, setApplied] = useState(form);
  const LIMIT = 20;
  const filters = { status: applied.status, unspsc: applied.unspsc, buyer: applied.buyer, date_from: applied.date_from || null, date_to: applied.date_to || null };
  const res = useQuery({
    queryKey: ["search", applied, page],
    queryFn: () => api<{ total: number; items: Tender[] }>("/tenders/search", { body: { q: applied.q, mode: applied.mode, filters, sort: applied.sort, limit: LIMIT, offset: page * LIMIT } }),
  });
  const save = useMutation({
    mutationFn: (name: string) => api("/saved-searches", { body: { name, q: applied.q, mode: applied.mode, filters, frequency: "daily" } }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["saved"] }); alert("Búsqueda guardada. Recibirás alertas por correo con lo nuevo."); },
  });
  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setForm({ ...form, [k]: e.target.value });
  const total = res.data?.total ?? 0;
  return (
    <Page title="Buscar concursos">
      <form className="card grid gap-2 md:grid-cols-6" onSubmit={(e) => { e.preventDefault(); setPage(0); setApplied(form); }}>
        <input className="input md:col-span-4" placeholder="Palabras clave o describe lo que buscas…" value={form.q} onChange={set("q")} />
        <select className="input" value={form.mode} onChange={set("mode")}>{MODES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
        <select className="input" value={form.status} onChange={set("status")}>{STATUS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
        <input className="input" placeholder="UNSPSC (prefijo)" value={form.unspsc} onChange={set("unspsc")} />
        <input className="input" placeholder="Entidad compradora" value={form.buyer} onChange={set("buyer")} />
        <input className="input" type="date" value={form.date_from} onChange={set("date_from")} title="Publicado desde" />
        <input className="input" type="date" value={form.date_to} onChange={set("date_to")} title="Publicado hasta" />
        <select className="input" value={form.sort} onChange={set("sort")} disabled={!!form.q}>
          <option value="recent">Más recientes</option><option value="deadline">Cierre más próximo</option>
        </select>
        <button className="btn btn-primary justify-center">Buscar</button>
      </form>
      <div className="flex items-center justify-between">
        <div className="muted">{res.data ? `${total} resultado(s)` : ""}</div>
        <button className="btn" onClick={() => { const n = prompt("Nombre de la alerta"); if (n) save.mutate(n); }}>🔔 Guardar como alerta</button>
      </div>
      {res.isLoading ? <Loading /> : res.error ? <ErrorBox error={res.error} /> :
        res.data!.items.length ? (
          <div className="space-y-2">{res.data!.items.map((t) => <TenderCard key={t.ocid} t={t} context="search" />)}</div>
        ) : <Empty>Sin resultados. Prueba con otras palabras o amplía los filtros.</Empty>}
      {total > LIMIT && (
        <div className="flex justify-center gap-2">
          <button className="btn" disabled={page === 0} onClick={() => setPage(page - 1)}>← Anterior</button>
          <span className="muted self-center">Página {page + 1} de {Math.ceil(total / LIMIT)}</span>
          <button className="btn" disabled={(page + 1) * LIMIT >= total} onClick={() => setPage(page + 1)}>Siguiente →</button>
        </div>
      )}
    </Page>
  );
}
