import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { api, Tender } from "../api";
import { IconBell, IconSearch, IconX } from "../components/icons";
import TenderCard from "../components/TenderCard";
import { Empty, ErrorBox, Loading, Page, Segmented } from "../components/ui";
import { num } from "../format";

const STATUS = [["open", "Vigentes"], ["evaluation", "En evaluación"], ["awarded", "Adjudicados"], ["unsuccessful", "Desiertos"], ["all", "Todos los estados"]] as const;
const MODES = [["hybrid", "Inteligente"], ["keyword", "Palabras exactas"], ["semantic", "Por significado"]] as const;
type Mode = (typeof MODES)[number][0];
type Form = { q: string; mode: Mode; status: string; unspsc: string; buyer: string; date_from: string; date_to: string; sort: string };
const LIMIT = 20;

export default function Search() {
  const qc = useQueryClient();
  const st = (useLocation().state ?? {}) as { unspsc?: string; q?: string; focus?: number };
  const inputRef = useRef<HTMLInputElement>(null);
  const [form, setForm] = useState<Form>({ q: st.q ?? "", mode: "hybrid", status: "open", unspsc: st.unspsc ?? "", buyer: "", date_from: "", date_to: "", sort: "recent" });
  const [applied, setApplied] = useState(form);
  const [page, setPage] = useState(0);
  const [show, setShow] = useState({ buyer: false, unspsc: !!st.unspsc, dates: false });
  const [saving, setSaving] = useState<string | null>(null);
  const [savedMsg, setSavedMsg] = useState("");

  useEffect(() => { inputRef.current?.focus(); }, [st.focus]);

  const apply = (next: Form) => { setForm(next); setApplied(next); setPage(0); };
  const filters = { status: applied.status, unspsc: applied.unspsc, buyer: applied.buyer, date_from: applied.date_from || null, date_to: applied.date_to || null };
  const res = useQuery({
    queryKey: ["search", applied, page],
    queryFn: () => api<{ total: number; items: Tender[] }>("/tenders/search", { body: { q: applied.q, mode: applied.mode, filters, sort: applied.sort, limit: LIMIT, offset: page * LIMIT } }),
    placeholderData: (prev) => prev,
  });
  const save = useMutation({
    mutationFn: (name: string) => api("/saved-searches", { body: { name, q: applied.q, mode: applied.mode, filters, frequency: "daily" } }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["saved"] }); setSaving(null); setSavedMsg("Alerta creada. Te enviaremos por correo los concursos nuevos que coincidan."); },
  });
  const set = (k: keyof Form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setForm({ ...form, [k]: e.target.value });
  const clear = (k: keyof Form, flag?: keyof typeof show) => { apply({ ...form, [k]: "" }); if (flag) setShow({ ...show, [flag]: false }); };
  const submit = (e: FormEvent) => { e.preventDefault(); apply(form); };
  const total = res.data?.total ?? 0;
  const statusLabel = STATUS.find(([v]) => v === applied.status)?.[1] ?? "";

  return (
    <Page title="Buscar concursos">
      <form onSubmit={submit} role="search" className="flex flex-col gap-3">
        <div className="flex flex-wrap gap-2">
          <label className="search-box flex-[1_1_420px]">
            <IconSearch size={18} className="text-stone-600" />
            <span className="sr-only">Qué buscas</span>
            <input ref={inputRef} value={form.q} onChange={set("q")} placeholder="Describe lo que vendes o busca por palabra clave…"
              className="min-w-0 flex-1 bg-transparent text-[15px] outline-none placeholder:text-stone-500" />
          </label>
          <button className="btn btn-primary min-h-[52px] rounded-xl px-6 text-sm">Buscar</button>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Segmented label="Tipo de búsqueda" value={form.mode} options={MODES} onChange={(mode) => apply({ ...form, mode })} />
          <span className="mx-1 hidden h-6 w-px bg-stone-200 sm:block" />

          <label className="chip cursor-pointer">
            <span className="sr-only">Estado</span>
            <select value={form.status} onChange={(e) => apply({ ...form, status: e.target.value })} className="cursor-pointer bg-transparent outline-none">
              {STATUS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </label>

          {show.buyer || applied.buyer ? (
            <span className="chip">
              <input aria-label="Entidad compradora" value={form.buyer} onChange={set("buyer")} onBlur={() => apply(form)} placeholder="Entidad…" autoFocus={!applied.buyer}
                className="w-40 bg-transparent outline-none placeholder:text-brand-800/60" />
              <button type="button" aria-label="Quitar filtro de entidad" onClick={() => clear("buyer", "buyer")}><IconX size={14} /></button>
            </span>
          ) : <button type="button" className="chip-add" onClick={() => setShow({ ...show, buyer: true })}>+ Entidad</button>}

          {show.unspsc || applied.unspsc ? (
            <span className="chip">
              <input aria-label="Categoría UNSPSC" value={form.unspsc} onChange={set("unspsc")} onBlur={() => apply(form)} placeholder="Código UNSPSC…" autoFocus={!applied.unspsc}
                className="w-32 bg-transparent outline-none placeholder:text-brand-800/60" />
              <button type="button" aria-label="Quitar filtro de categoría" onClick={() => clear("unspsc", "unspsc")}><IconX size={14} /></button>
            </span>
          ) : <button type="button" className="chip-add" onClick={() => setShow({ ...show, unspsc: true })}>+ Categoría</button>}

          {show.dates || applied.date_from || applied.date_to ? (
            <span className="chip">
              <input type="date" aria-label="Publicado desde" value={form.date_from} onChange={(e) => apply({ ...form, date_from: e.target.value })} className="bg-transparent outline-none" />
              <span aria-hidden="true">–</span>
              <input type="date" aria-label="Publicado hasta" value={form.date_to} onChange={(e) => apply({ ...form, date_to: e.target.value })} className="bg-transparent outline-none" />
              <button type="button" aria-label="Quitar filtro de fecha" onClick={() => { apply({ ...form, date_from: "", date_to: "" }); setShow({ ...show, dates: false }); }}><IconX size={14} /></button>
            </span>
          ) : <button type="button" className="chip-add" onClick={() => setShow({ ...show, dates: true })}>+ Fecha</button>}
        </div>
      </form>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <span className="text-[13px] text-stone-600">
          {res.data && <><b className="font-semibold text-zinc-900">{num(total)}</b> {statusLabel.toLowerCase()} · </>}
          {applied.q ? "ordenados por relevancia" : (
            <label>ordenar por{" "}
              <select value={form.sort} onChange={(e) => apply({ ...form, sort: e.target.value })} className="cursor-pointer bg-transparent font-medium text-zinc-900 outline-none">
                <option value="recent">más recientes</option><option value="deadline">cierre más próximo</option>
              </select>
            </label>
          )}
        </span>
        {saving == null ? (
          <button type="button" className="btn" onClick={() => { setSavedMsg(""); setSaving(applied.q || "Mi alerta"); }}><IconBell size={15} />Crear alerta con esta búsqueda</button>
        ) : (
          <form className="flex items-center gap-2" onSubmit={(e) => { e.preventDefault(); if (saving.trim()) save.mutate(saving.trim()); }}>
            <input className="input w-56" aria-label="Nombre de la alerta" value={saving} onChange={(e) => setSaving(e.target.value)} autoFocus />
            <button className="btn btn-primary" disabled={save.isPending}>Guardar</button>
            <button type="button" className="btn-ghost" onClick={() => setSaving(null)}>Cancelar</button>
          </form>
        )}
      </div>
      {savedMsg && <div className="rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-[13px] text-green-800">{savedMsg}</div>}

      {res.isLoading ? <Loading rows={6} /> : res.error ? <ErrorBox error={res.error} /> :
        res.data!.items.length ? (
          <div className={`list transition-opacity ${res.isFetching ? "opacity-60" : ""}`}>
            {res.data!.items.map((t) => <TenderCard key={t.ocid} t={t} context="search" />)}
          </div>
        ) : <Empty icon={<IconSearch size={28} />}>Sin resultados. Prueba con otras palabras, el modo “Por significado” o quita algún filtro.</Empty>}

      {total > LIMIT && (
        <nav aria-label="Paginación" className="flex items-center justify-center gap-3">
          <button className="btn" disabled={page === 0} onClick={() => setPage(page - 1)}>Anterior</button>
          <span className="text-[13px] text-stone-600">Página {page + 1} de {Math.ceil(total / LIMIT)}</span>
          <button className="btn" disabled={(page + 1) * LIMIT >= total} onClick={() => setPage(page + 1)}>Siguiente</button>
        </nav>
      )}
    </Page>
  );
}
