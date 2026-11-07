const BASE = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

export async function api<T = any>(path: string, opts: { method?: string; body?: unknown; form?: FormData } = {}): Promise<T> {
  const res = await fetch(`${BASE}/api/v1${path}`, {
    method: opts.method ?? (opts.body || opts.form ? "POST" : "GET"),
    credentials: "include",
    headers: opts.body ? { "Content-Type": "application/json" } : undefined,
    body: opts.form ?? (opts.body ? JSON.stringify(opts.body) : undefined),
  });
  if (!res.ok) {
    let msg = res.statusText;
    try { msg = (await res.json()).detail ?? msg; } catch { /* sin cuerpo */ }
    throw new ApiError(res.status, typeof msg === "string" ? msg : "Error");
  }
  return res.json();
}

export type Tender = {
  ocid: string; nog: number; title: string; status: string; status_details: string; is_open: boolean;
  method: string; category?: string; department?: string | null; entity_type?: string | null; buyer_name: string; unit_name: string; published_at: string | null; deadline_at: string | null;
  n_tenderers: number | null; n_items: number; unspsc: string | null; awarded_total: number | null;
  winners: string[]; favorite: string | null; feedback: number; score: number | null; reason: string;
  portal_url: string; note?: string; matches?: any[];
};
