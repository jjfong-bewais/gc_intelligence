import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ReactNode, useEffect, useState } from "react";
import { api } from "../api";
import {
  clean, countActive, DATE_PRESETS, fromSaved, Filters, NONE, SavedCombo, SECTION_LABELS, Sel, SelKey, valueLabel,
} from "../filters";
import { num } from "../format";
import { IconBell, IconX } from "./icons";

type Facet = { value: string; count: number };
type Facets = Record<"category" | "status_details" | "department" | "entity_type" | "method", Facet[]>;

const FREQ: [string, string][] = [["daily", "Diario"], ["weekly", "Semanal"], ["immediate", "Cada actualización"]];

/**
 * Panel de filtros duros. Cada sección puede **incluir** (delimitar) o **excluir** valores.
 * Permite guardar la combinación y recibir por correo los mejores concursos vigentes que la cumplan.
 */
export default function FilterPanel({ value, onChange, lockOpen, q = "", mode = "hybrid", onLoad }: {
  value: Filters; onChange: (f: Filters) => void;
  lockOpen?: boolean; // la vista muestra solo vigentes (Para ti)
  q?: string; mode?: string; // texto de búsqueda que se guarda con la combinación
  onLoad?: (c: SavedCombo) => void;
}) {
  const facets = useQuery({ queryKey: ["facets"], queryFn: () => api<Facets>("/catalogs/facets"), staleTime: 15 * 60_000 });
  const f = value;
  const set = (patch: Partial<Filters>) => onChange({ ...f, ...patch });
  const setSel = (k: SelKey, s: Sel | undefined) => onChange({ ...f, [k]: s && s.values.length ? s : s ? { ...s, values: [] } : undefined });
  const n = countActive(f);

  return (
    <aside aria-label="Filtros" className="card flex flex-col gap-0 p-0 text-[13px]">
      <div className="flex items-center justify-between px-4 pb-3 pt-4">
        <h2 className="text-sm font-semibold">Filtros{n ? <span className="ml-1.5 font-normal text-stone-500">({n})</span> : null}</h2>
        <button type="button" className="text-[13px] font-medium text-brand-800 disabled:text-stone-400" disabled={!n}
          onClick={() => onChange({})}>Limpiar todo</button>
      </div>

      <SavedCombos f={f} q={q} mode={mode} onLoad={(c) => { onChange(fromSaved(c.filters)); onLoad?.(c); }} />

      <Block title="Disponibilidad">
        <Toggle label="Solo con recepción de ofertas abierta" on={!!f.open_only} onChange={(v) => set({ open_only: v, awarded_only: v ? false : f.awarded_only })} />
        <Toggle label="Solo adjudicados" on={!!f.awarded_only} disabled={lockOpen} onChange={(v) => set({ awarded_only: v, open_only: v ? false : f.open_only })} />
      </Block>

      <Block title="Fecha de publicación">
        <div className="grid grid-cols-2 gap-2">
          <label className="flex flex-col gap-1 text-xs text-stone-600">Desde
            <input type="date" className="input px-2 text-[13px]" value={f.date_preset ? "" : f.date_from ?? ""}
              onChange={(e) => set({ date_from: e.target.value || null, date_preset: null })} />
          </label>
          <label className="flex flex-col gap-1 text-xs text-stone-600">Hasta
            <input type="date" className="input px-2 text-[13px]" value={f.date_preset ? "" : f.date_to ?? ""}
              onChange={(e) => set({ date_to: e.target.value || null, date_preset: null })} />
          </label>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {DATE_PRESETS.map(([v, l]) => (
            <button key={v} type="button" aria-pressed={f.date_preset === v}
              className={`pill ${f.date_preset === v ? "is-on" : ""}`}
              onClick={() => set({ date_preset: f.date_preset === v ? null : v, date_from: null, date_to: null })}>{l}</button>
          ))}
        </div>
      </Block>

      <FacetBlock k="category" f={f} facets={facets.data?.category} onSel={setSel} chips />
      <FacetBlock k="status_details" f={f} facets={facets.data?.status_details} onSel={setSel}
        note={lockOpen ? "Esta vista muestra solo concursos vigentes." : undefined} />
      <SearchBlock k="buyer" f={f} onSel={setSel} placeholder="Entidad o unidad, p. ej. IGSS, Roosevelt"
        source={(t) => api<{ items: { name: string; count: number }[] }>(`/catalogs/buyers?q=${encodeURIComponent(t)}`)
          .then((r) => r.items.map((i) => ({ id: i.name, label: i.name, hint: num(i.count) })))} freeText />
      <FacetBlock k="department" f={f} facets={facets.data?.department} onSel={setSel} />
      <FacetBlock k="entity_type" f={f} facets={facets.data?.entity_type} onSel={setSel} />
      <FacetBlock k="method" f={f} facets={facets.data?.method} onSel={setSel} />
      <SearchBlock k="supplier" f={f} onSel={setSel} placeholder="Nombre o NIT del proveedor"
        onLabel={(sel, id, label) => onChange({ ...f, supplier: sel, labels: { ...(f.labels ?? {}), [id]: label } })}
        source={(t) => api<{ items: { id: string; name: string }[] }>(`/suppliers?q=${encodeURIComponent(t)}`)
          .then((r) => r.items.map((i) => ({ id: i.id, label: i.name, hint: i.id.replace("GT-NIT-", "NIT ") })))} last />
      {facets.error ? <p className="px-4 pb-4 text-xs text-red-700">No se pudieron cargar las opciones de filtro.</p> : null}
    </aside>
  );
}

/* ── Piezas ─────────────────────────────────────────────────────────────── */

function Block({ title, right, children, last }: { title: string; right?: ReactNode; children: ReactNode; last?: boolean }) {
  return (
    <section className={`flex flex-col gap-2.5 border-t border-stone-100 px-4 py-4 ${last ? "pb-5" : ""}`}>
      <div className="flex items-center justify-between gap-2">
        <h3 className="eyebrow">{title}</h3>
        {right}
      </div>
      {children}
    </section>
  );
}

function Toggle({ label, on, onChange, disabled }: { label: string; on: boolean; onChange: (v: boolean) => void; disabled?: boolean }) {
  return (
    <label className={`flex cursor-pointer items-start gap-2.5 ${disabled ? "cursor-not-allowed opacity-50" : ""}`}>
      <button type="button" role="switch" aria-checked={on} disabled={disabled} onClick={() => onChange(!on)}
        className={`mt-0.5 inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors ${on ? "bg-zinc-900" : "bg-stone-300"}`}>
        <span className={`h-4 w-4 rounded-full bg-white shadow transition-transform ${on ? "translate-x-[18px]" : "translate-x-0.5"}`} />
      </button>
      <span className="text-stone-800">{label}</span>
    </label>
  );
}

/** Incluir / Excluir + estado de la sección. */
function OpSwitch({ k, s, onSel }: { k: SelKey; s?: Sel; onSel: (k: SelKey, s: Sel | undefined) => void }) {
  const op = s?.op ?? "in";
  const n = s?.values.length ?? 0;
  return (
    <div className="flex items-center justify-between gap-2">
      <div className="seg" role="group" aria-label={`${SECTION_LABELS[k]}: incluir o excluir`}>
        {(["in", "out"] as const).map((o) => (
          <button key={o} type="button" aria-pressed={op === o} className={`!min-h-[28px] !px-2.5 !text-xs ${op === o ? "is-on" : ""}`}
            onClick={() => onSel(k, { op: o, values: s?.values ?? [] })}>{o === "in" ? "Incluir" : "Excluir"}</button>
        ))}
      </div>
      <span className={`text-xs ${n ? (op === "out" ? "font-medium text-red-700" : "font-medium text-brand-800") : "text-stone-500"}`}>
        {n ? `${n} ${op === "out" ? "excluido" : "incluido"}${n > 1 ? "s" : ""}` : "Sin filtro"}
      </span>
    </div>
  );
}

function FacetBlock({ k, f, facets, onSel, chips, note }: {
  k: "category" | "status_details" | "department" | "entity_type" | "method"; f: Filters; facets?: Facet[];
  onSel: (k: SelKey, s: Sel | undefined) => void; chips?: boolean; note?: string;
}) {
  const s = f[k];
  const [more, setMore] = useState(false);
  const chosen = new Set(s?.values ?? []);
  const out = s?.op === "out";
  const toggle = (v: string) => {
    const next = new Set(chosen);
    next.has(v) ? next.delete(v) : next.add(v);
    onSel(k, { op: s?.op ?? "in", values: [...next] });
  };
  const all = facets ?? [];
  // los valores elegidos siempre visibles aunque estén fuera de los primeros
  const visible = more || all.length <= 8 ? all : all.filter((x, i) => i < 7 || chosen.has(x.value));
  return (
    <Block title={SECTION_LABELS[k]}>
      <OpSwitch k={k} s={s} onSel={onSel} />
      {note && <p className="text-xs text-stone-500">{note}</p>}
      {!facets ? <div className="h-16 animate-pulse rounded-lg bg-stone-100" /> : chips ? (
        <div className="flex flex-wrap gap-1.5">
          {visible.map((x) => (
            <button key={x.value} type="button" aria-pressed={chosen.has(x.value)} onClick={() => toggle(x.value)}
              className={`pill ${chosen.has(x.value) ? (out ? "is-out" : "is-on") : ""}`}>
              {valueLabel(k, x.value)} <span className="tabular-nums opacity-60">{num(x.count)}</span>
            </button>
          ))}
        </div>
      ) : (
        <ul className={`flex flex-col ${more && all.length > 12 ? "max-h-72 overflow-y-auto pr-1" : ""}`}>
          {visible.map((x) => (
            <li key={x.value}>
              <label className="flex min-h-8 cursor-pointer items-start gap-2.5 rounded-md px-1 py-1 hover:bg-stone-50">
                <input type="checkbox" className={`mt-px h-4 w-4 shrink-0 ${out ? "accent-red-700" : "accent-zinc-900"}`}
                  checked={chosen.has(x.value)} onChange={() => toggle(x.value)} />
                <span className={`min-w-0 flex-1 leading-snug ${chosen.has(x.value) && out ? "text-red-800 line-through decoration-red-300" : ""}`}
                  title={valueLabel(k, x.value)}>{valueLabel(k, x.value)}</span>
                <span className="shrink-0 text-xs tabular-nums text-stone-500">{num(x.count)}</span>
              </label>
            </li>
          ))}
        </ul>
      )}
      {facets && (
        <div className="flex gap-3 text-xs">
          <button type="button" className="font-medium text-brand-800" onClick={() => onSel(k, { op: s?.op ?? "in", values: all.map((x) => x.value) })}>Seleccionar todo</button>
          <button type="button" className="font-medium text-brand-800" onClick={() => onSel(k, undefined)}>Ninguno</button>
          {all.length > 8 && <button type="button" className="ml-auto text-stone-600 hover:text-zinc-900" onClick={() => setMore(!more)}>{more ? "Ver menos" : `Ver ${all.length} opciones`}</button>}
        </div>
      )}
    </Block>
  );
}

type Option = { id: string; label: string; hint?: string };

/** Sección con autocompletado (entidades, proveedores). */
function SearchBlock({ k, f, onSel, source, placeholder, freeText, onLabel, last }: {
  k: "buyer" | "supplier"; f: Filters; onSel: (k: SelKey, s: Sel | undefined) => void;
  source: (t: string) => Promise<Option[]>; placeholder: string; freeText?: boolean;
  onLabel?: (sel: Sel, id: string, label: string) => void; last?: boolean;
}) {
  const s = f[k];
  const [text, setText] = useState("");
  const [term, setTerm] = useState("");
  const [open, setOpen] = useState(false);
  useEffect(() => { const t = setTimeout(() => setTerm(text.trim()), 250); return () => clearTimeout(t); }, [text]);
  const sugg = useQuery({ queryKey: ["filter-suggest", k, term], queryFn: () => source(term), enabled: term.length >= 2, staleTime: 60_000 });
  const values = s?.values ?? [];
  const out = s?.op === "out";
  const add = (o: Option) => {
    if (!values.includes(o.id)) {
      const next = { op: s?.op ?? "in", values: [...values, o.id] } as Sel;
      if (onLabel) onLabel(next, o.id, o.label); // proveedor: guarda el nombre para el chip
      else onSel(k, next);
    }
    setText(""); setOpen(false);
  };
  return (
    <Block title={SECTION_LABELS[k]} last={last}>
      <OpSwitch k={k} s={s} onSel={onSel} />
      <div className="relative">
        <input className="input text-[13px]" value={text} placeholder={placeholder} aria-label={SECTION_LABELS[k]}
          onChange={(e) => { setText(e.target.value); setOpen(true); }} onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              const first = sugg.data?.[0];
              if (freeText && text.trim()) add({ id: text.trim(), label: text.trim() });
              else if (first) add(first);
            }
          }} />
        {open && term.length >= 2 && (sugg.data?.length || freeText) ? (
          <ul role="listbox" className="absolute z-20 mt-1 max-h-64 w-full overflow-y-auto rounded-lg border border-stone-200 bg-white py-1 shadow-lg">
            {freeText && text.trim() && (
              <li><button type="button" className="w-full px-3 py-1.5 text-left hover:bg-stone-50" onMouseDown={(e) => e.preventDefault()}
                onClick={() => add({ id: text.trim(), label: text.trim() })}>Contiene “{text.trim()}”</button></li>
            )}
            {sugg.data?.map((o) => (
              <li key={o.id}><button type="button" className="flex w-full items-baseline gap-2 px-3 py-1.5 text-left hover:bg-stone-50"
                onMouseDown={(e) => e.preventDefault()} onClick={() => add(o)}>
                <span className="min-w-0 flex-1 truncate">{valueLabel(k, o.id, { labels: { [o.id]: o.label } })}</span>
                {o.hint && <span className="shrink-0 text-xs text-stone-500">{o.hint}</span>}
              </button></li>
            ))}
          </ul>
        ) : null}
      </div>
      {values.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {values.map((v) => (
            <span key={v} className={`pill ${out ? "is-out" : "is-on"} max-w-full`}>
              <span className="truncate">{valueLabel(k, v, f)}</span>
              <button type="button" aria-label={`Quitar ${valueLabel(k, v, f)}`} onClick={() => onSel(k, { op: s!.op, values: values.filter((x) => x !== v) })}><IconX size={12} /></button>
            </span>
          ))}
        </div>
      )}
    </Block>
  );
}

/** Combinaciones guardadas: aplicar una y guardar la actual (con correo opcional). */
function SavedCombos({ f, q, mode, onLoad }: { f: Filters; q: string; mode: string; onLoad: (c: SavedCombo) => void }) {
  const qc = useQueryClient();
  const saved = useQuery({ queryKey: ["saved"], queryFn: () => api<{ items: SavedCombo[] }>("/saved-searches") });
  const [form, setForm] = useState<null | { name: string; email: boolean; frequency: string; max_items: number }>(null);
  const [msg, setMsg] = useState("");
  const save = useMutation({
    mutationFn: (b: NonNullable<typeof form>) => api<SavedCombo>("/saved-searches", {
      body: { name: b.name, q, mode, filters: clean(f), frequency: b.frequency, active: b.email, max_items: b.max_items },
    }),
    onSuccess: (_r, b) => {
      qc.invalidateQueries({ queryKey: ["saved"] });
      setForm(null);
      setMsg(b.email ? `Guardada. Recibirás hasta ${b.max_items} concursos vigentes por correo, sin repetir en la semana.` : "Combinación guardada.");
    },
  });
  const items = saved.data?.items ?? [];
  return (
    <section className="flex flex-col gap-2 border-t border-stone-100 px-4 py-3">
      {items.length > 0 && (
        <select className="input text-[13px]" aria-label="Aplicar combinación guardada" value=""
          onChange={(e) => { const c = items.find((x) => String(x.id) === e.target.value); if (c) { onLoad(c); setMsg(`Aplicada: ${c.name}`); } }}>
          <option value="">Combinaciones guardadas…</option>
          {items.map((c) => <option key={c.id} value={c.id}>{c.name}{c.active ? " ✉" : ""}</option>)}
        </select>
      )}
      {form == null ? (
        <button type="button" className="btn w-full" disabled={!countActive(f) && !q}
          title={!countActive(f) && !q ? "Elige al menos un filtro" : undefined}
          onClick={() => { setMsg(""); setForm({ name: q || "Mi combinación", email: true, frequency: "daily", max_items: 5 }); }}>
          <IconBell size={15} />Guardar combinación
        </button>
      ) : (
        <form className="flex flex-col gap-2.5 rounded-lg bg-stone-50 p-3" onSubmit={(e) => { e.preventDefault(); if (form.name.trim()) save.mutate(form); }}>
          <label className="flex flex-col gap-1 text-xs text-stone-600">Nombre
            <input className="input text-[13px]" value={form.name} autoFocus onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </label>
          {q && <p className="text-xs text-stone-600">Incluye el texto “{q}”.</p>}
          <label className="flex items-start gap-2 text-[13px]">
            <input type="checkbox" className="mt-0.5 h-4 w-4 accent-zinc-900" checked={form.email} onChange={(e) => setForm({ ...form, email: e.target.checked })} />
            Enviarme por correo los concursos vigentes que mejor coincidan conmigo
          </label>
          {form.email && (
            <div className="grid grid-cols-2 gap-2">
              <label className="flex flex-col gap-1 text-xs text-stone-600">Frecuencia
                <select className="input px-2 text-[13px]" value={form.frequency} onChange={(e) => setForm({ ...form, frequency: e.target.value })}>
                  {FREQ.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </select>
              </label>
              <label className="flex flex-col gap-1 text-xs text-stone-600">Concursos por correo
                <select className="input px-2 text-[13px]" value={form.max_items} onChange={(e) => setForm({ ...form, max_items: Number(e.target.value) })}>
                  {Array.from({ length: 10 }, (_, i) => i + 1).map((v) => <option key={v} value={v}>{v}</option>)}
                </select>
              </label>
            </div>
          )}
          {save.error && <p className="text-xs text-red-700">{(save.error as Error).message}</p>}
          <div className="flex gap-2">
            <button className="btn btn-primary flex-1" disabled={save.isPending || !form.name.trim()}>Guardar</button>
            <button type="button" className="btn-ghost" onClick={() => setForm(null)}>Cancelar</button>
          </div>
        </form>
      )}
      {msg && <p className="text-xs text-green-800">{msg}</p>}
    </section>
  );
}

/** Columna de filtros + contenido. En móvil el panel se abre con un botón. */
export function WithFilters({ panel, f, children }: { panel: ReactNode; f: Filters; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const n = countActive(f);
  return (
    <div className="flex flex-col gap-4 lg:grid lg:grid-cols-[264px_minmax(0,1fr)] lg:items-start lg:gap-6">
      <button type="button" className="btn self-start lg:hidden" aria-expanded={open} onClick={() => setOpen(!open)}>
        {open ? "Ocultar filtros" : "Filtros"}{n ? ` · ${n}` : ""}
      </button>
      <div className={`${open ? "block" : "hidden"} lg:sticky lg:top-6 lg:block lg:max-h-[calc(100vh-3rem)] lg:overflow-y-auto lg:rounded-2xl`}>{panel}</div>
      <div className="flex min-w-0 flex-col gap-6">{children}</div>
    </div>
  );
}

export { NONE };
