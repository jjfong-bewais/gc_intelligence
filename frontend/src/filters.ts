import { useEffect, useState } from "react";
import { nameCase, supplierName } from "./format";

/** Selección de una faceta: `in` delimita la búsqueda a los valores, `out` los excluye. */
export type Sel = { op: "in" | "out"; values: string[] };

export type SelKey = "category" | "status_details" | "department" | "entity_type" | "method" | "buyer" | "supplier";

/** Filtros duros. Mismo JSON que acepta la API (`filters` en /tenders/search, `?f=` en las demás vistas). */
export type Filters = Partial<Record<SelKey, Sel>> & {
  date_from?: string | null;
  date_to?: string | null;
  date_preset?: string | null; // 7d | 30d | 3m | 6m | 1y (relativo a hoy)
  open_only?: boolean; // recepción de ofertas abierta
  awarded_only?: boolean;
  unspsc?: string;
  labels?: Record<string, string>; // nombres de proveedores (solo para mostrar)
};

export type SavedCombo = {
  id: number; name: string; q: string; mode: string; filters: Filters; frequency: string; active: boolean;
  max_items: number; last_run_at: string | null;
};

export const NONE = "__none__";
export const SEL_KEYS: SelKey[] = ["category", "status_details", "buyer", "department", "entity_type", "method", "supplier"];

export const SECTION_LABELS: Record<SelKey, string> = {
  category: "Categoría", status_details: "Estado del concurso", buyer: "Entidad / unidad compradora", department: "Departamento",
  entity_type: "Tipo de entidad", method: "Modalidad de compra", supplier: "Proveedor adjudicado",
};

export const DATE_PRESETS: [string, string][] = [["7d", "7 días"], ["30d", "30 días"], ["3m", "3 meses"], ["6m", "6 meses"], ["1y", "1 año"]];

const CATEGORY: Record<string, string> = { goods: "Bienes", services: "Servicios", works: "Obras", consultingServices: "Consultoría" };

/** Texto visible de un valor de faceta. */
export function valueLabel(key: SelKey, v: string, f?: Filters): string {
  if (v === NONE) return "Sin dato";
  if (key === "category") return CATEGORY[v] ?? v;
  if (key === "department") return nameCase(v);
  if (key === "supplier") return supplierName(f?.labels?.[v] ?? v);
  if (key === "buyer") return v;
  return v;
}

export const isActive = (s?: Sel) => !!s && s.values.length > 0;

/** Número de filtros activos (para el botón y "Limpiar todo"). */
export function countActive(f: Filters): number {
  let n = SEL_KEYS.filter((k) => isActive(f[k])).length;
  if (f.date_from || f.date_to || f.date_preset) n++;
  if (f.open_only) n++;
  if (f.awarded_only) n++;
  if (f.unspsc) n++;
  return n;
}

/** Quita valores vacíos para enviar a la API o guardar. */
export function clean(f: Filters): Filters {
  const out: Filters = {};
  for (const k of SEL_KEYS) if (isActive(f[k])) out[k] = f[k];
  if (f.date_preset) out.date_preset = f.date_preset;
  else {
    if (f.date_from) out.date_from = f.date_from;
    if (f.date_to) out.date_to = f.date_to;
  }
  if (f.open_only) out.open_only = true;
  if (f.awarded_only) out.awarded_only = true;
  if (f.unspsc) out.unspsc = f.unspsc;
  if (f.supplier && f.labels) {
    out.labels = Object.fromEntries(f.supplier.values.filter((id) => f.labels![id]).map((id) => [id, f.labels![id]]));
  }
  return out;
}

/** Parámetro `?f=` para las vistas GET. */
export const filterQuery = (f: Filters) => {
  const c = clean(f);
  return countActive(c) ? `f=${encodeURIComponent(JSON.stringify(c))}` : "";
};

/** Resumen corto: "Incluye Bienes · Excluye Desierto · Últimos 30 días". */
export function describe(f: Filters): string {
  const parts: string[] = [];
  for (const k of SEL_KEYS) {
    const s = f[k];
    if (!isActive(s)) continue;
    const vals = s!.values.map((v) => valueLabel(k, v, f));
    const shown = vals.length > 3 ? `${vals.slice(0, 3).join(", ")} y ${vals.length - 3} más` : vals.join(", ");
    parts.push(`${SECTION_LABELS[k]}${s!.op === "out" ? " (excluye)" : ""}: ${shown}`);
  }
  if (f.date_preset) parts.push(`Publicados últimos ${DATE_PRESETS.find(([v]) => v === f.date_preset)?.[1] ?? f.date_preset}`);
  else if (f.date_from || f.date_to) parts.push(`Publicados ${f.date_from ?? "…"} a ${f.date_to ?? "hoy"}`);
  if (f.open_only) parts.push("Recibiendo ofertas");
  if (f.awarded_only) parts.push("Solo adjudicados");
  if (f.unspsc) parts.push(`UNSPSC ${f.unspsc}`);
  return parts.join(" · ");
}

/** Convierte filtros guardados con el formato anterior (`status: "open"`, `buyer: "texto"`). */
export function fromSaved(raw: any): Filters {
  const f: any = { ...(raw ?? {}) };
  const legacy = typeof f.status === "string" ? f.status : "";
  delete f.status;
  if (legacy === "open") f.status_details = { op: "in", values: ["Vigente"] };
  else if (legacy === "evaluation") f.status_details = { op: "in", values: ["Evaluación"] };
  else if (legacy === "unsuccessful") f.status_details = { op: "in", values: ["Desierto"] };
  else if (legacy === "awarded") f.awarded_only = true;
  for (const k of ["buyer", "method"]) if (typeof f[k] === "string") f[k] = f[k] ? { op: "in", values: [f[k]] } : undefined;
  return f as Filters;
}

/** Filtros de una vista, recordados en el navegador. */
export function useViewFilters(view: string, initial: Filters = {}): [Filters, (f: Filters) => void] {
  const key = `gc.filters.${view}`;
  const [f, setF] = useState<Filters>(() => {
    try {
      const raw = localStorage.getItem(key);
      if (raw) return JSON.parse(raw);
    } catch { /* almacenamiento no disponible */ }
    return initial;
  });
  useEffect(() => {
    try { localStorage.setItem(key, JSON.stringify(f)); } catch { /* sin almacenamiento */ }
  }, [key, f]);
  return [f, setF];
}
