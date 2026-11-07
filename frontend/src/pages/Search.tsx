import { useQuery } from "@tanstack/react-query";
import { FormEvent, useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { api, Tender } from "../api";
import FilterPanel, { WithFilters } from "../components/FilterPanel";
import { IconSearch, IconX } from "../components/icons";
import TenderCard from "../components/TenderCard";
import { Empty, ErrorBox, Loading, Page, Segmented } from "../components/ui";
import { clean, describe, Filters, fromSaved, SavedCombo, useViewFilters } from "../filters";
import { num } from "../format";

const MODES = [["hybrid", "Inteligente"], ["keyword", "Palabras exactas"], ["semantic", "Por significado"]] as const;
type Mode = (typeof MODES)[number][0];
type Form = { q: string; mode: Mode; sort: string };
const LIMIT = 20;
const DEFAULT_FILTERS: Filters = { status_details: { op: "in", values: ["Vigente"] } };

export default function Search() {
  const st = (useLocation().state ?? {}) as { unspsc?: string; q?: string; focus?: number; filters?: Filters; combo?: SavedCombo };
  const inputRef = useRef<HTMLInputElement>(null);
  const [form, setForm] = useState<Form>({ q: st.combo?.q ?? st.q ?? "", mode: (st.combo?.mode as Mode) ?? "hybrid", sort: "recent" });
  const [applied, setApplied] = useState(form);
  const [filters, setFiltersRaw] = useViewFilters("search", DEFAULT_FILTERS);
  const [page, setPage] = useState(0);

  // Llegar desde Oportunidades / Alertas con filtros o una combinación guardada
  useEffect(() => {
    if (st.combo) setFiltersRaw(fromSaved(st.combo.filters));
    else if (st.filters || st.unspsc) setFiltersRaw({ ...(st.filters ?? filters), unspsc: st.unspsc ?? st.filters?.unspsc });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => { inputRef.current?.focus(); }, [st.focus]);

  const setFilters = (f: Filters) => { setFiltersRaw(f); setPage(0); };
  const apply = (next: Form) => { setForm(next); setApplied(next); setPage(0); };
  const body = clean(filters);
  const res = useQuery({
    queryKey: ["search", applied, body, page],
    queryFn: () => api<{ total: number; items: Tender[] }>("/tenders/search", { body: { q: applied.q, mode: applied.mode, filters: body, sort: applied.sort, limit: LIMIT, offset: page * LIMIT } }),
    placeholderData: (prev) => prev,
  });
  const set = (k: keyof Form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setForm({ ...form, [k]: e.target.value });
  const submit = (e: FormEvent) => { e.preventDefault(); apply(form); };
  const total = res.data?.total ?? 0;
  const summary = describe(filters);

  const panel = <FilterPanel value={filters} onChange={setFilters} q={applied.q} mode={applied.mode}
    onLoad={(c) => apply({ ...form, q: c.q ?? "", mode: (c.mode as Mode) ?? "hybrid" })} />;

  return (
    <Page title="Buscar concursos">
      <WithFilters panel={panel} f={filters}>
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
          {filters.unspsc && (
            <span className="chip">UNSPSC {filters.unspsc}
              <button type="button" aria-label="Quitar filtro UNSPSC" onClick={() => setFilters({ ...filters, unspsc: "" })}><IconX size={14} /></button>
            </span>
          )}
        </div>
      </form>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <span className="text-[13px] text-stone-600">
          {res.data && <><b className="font-semibold text-zinc-900">{num(total)}</b> concurso{total === 1 ? "" : "s"} · </>}
          {applied.q ? "ordenados por relevancia" : (
            <label>ordenar por{" "}
              <select value={form.sort} onChange={(e) => apply({ ...form, sort: e.target.value })} className="cursor-pointer bg-transparent font-medium text-zinc-900 outline-none">
                <option value="recent">más recientes</option><option value="deadline">cierre más próximo</option>
              </select>
            </label>
          )}
        </span>
      </div>
      {summary && <p className="-mt-3 text-xs text-stone-600">{summary}</p>}

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
      </WithFilters>
    </Page>
  );
}
