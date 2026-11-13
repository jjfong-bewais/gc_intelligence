import { ReactNode, createContext, useCallback, useContext, useState } from "react";
import { Link, NavLink } from "react-router-dom";

export const Page = ({ title, subtitle, actions, children }: { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode; children: ReactNode }) => (
  <div className="flex flex-col gap-6">
    <header className="flex flex-wrap items-end justify-between gap-4">
      <div className="flex min-w-0 flex-col gap-1">
        <h1 className="text-[26px] font-semibold leading-tight tracking-tight">{title}</h1>
        {subtitle && <p className="max-w-2xl text-sm text-stone-600">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
    {children}
  </div>
);

export const Section = ({ title, more, moreLabel = "Ver todo", children }: { title: ReactNode; more?: string; moreLabel?: string; children: ReactNode }) => (
  <section className="flex flex-col gap-3">
    <div className="flex items-baseline justify-between gap-3">
      <h2 className="h-section">{title}</h2>
      {more && <Link to={more} className="text-[13px] font-medium">{moreLabel} →</Link>}
    </div>
    {children}
  </section>
);

/** Filas grises mientras carga, en lugar de un texto "Cargando…". */
export const Loading = ({ rows = 4 }: { rows?: number }) => (
  <div className="list" aria-busy="true" aria-label="Cargando">
    {Array.from({ length: rows }).map((_, i) => (
      <div key={i} className="flex animate-pulse flex-col gap-2 px-5 py-4">
        <div className="h-3.5 w-3/4 rounded bg-stone-100" />
        <div className="h-3 w-1/3 rounded bg-stone-100" />
      </div>
    ))}
  </div>
);

export const Empty = ({ children, action, icon }: { children: ReactNode; action?: ReactNode; icon?: ReactNode }) => (
  <div className="card flex flex-col items-center justify-center gap-2 py-10 text-center">
    {icon && <div className="text-stone-400">{icon}</div>}
    <div className="max-w-md text-sm text-stone-600">{children}</div>
    {action}
  </div>
);

export const ErrorBox = ({ error }: { error: unknown }) => (
  <div className="card border-red-200 bg-red-50 text-sm text-red-800">{(error as Error)?.message ?? "Ocurrió un error"}</div>
);

export const KpiStrip = ({ children }: { children: ReactNode }) => (
  <section aria-label="Indicadores" className="grid grid-cols-2 gap-px overflow-hidden rounded-2xl border border-stone-200 bg-stone-100 xl:grid-cols-4 [&>*]:bg-white">
    {children}
  </section>
);

export function Kpi({ label, value, hint, action }: { label: string; value: ReactNode; hint?: ReactNode; action?: { to: string; label: string } }) {
  return (
    <div className="flex flex-col gap-1.5 px-5 py-5 sm:px-6">
      <span className="text-[13px] text-stone-600">{label}</span>
      <span className="text-[28px] font-semibold leading-none tracking-tight tabular-nums">{value}</span>
      {action ? <Link to={action.to} className="text-xs font-medium">{action.label} →</Link> : hint && <span className="text-xs text-stone-600">{hint}</span>}
    </div>
  );
}

/** Control segmentado accesible. */
export function Segmented<T extends string>({ value, options, onChange, label }: { value: T; options: readonly (readonly [T, string])[]; onChange: (v: T) => void; label: string }) {
  return (
    <div className="seg" role="group" aria-label={label}>
      {options.map(([v, l]) => (
        <button key={v} type="button" aria-pressed={value === v} className={value === v ? "is-on" : ""} onClick={() => onChange(v)}>{l}</button>
      ))}
    </div>
  );
}

/* ── Avisos (toast) y confirmaciones propias: reemplazan alert()/confirm() del navegador ── */
type Toast = { id: number; text: string; tone: "ok" | "error" };
type ConfirmOpts = { title: string; body?: ReactNode; confirmLabel?: string; danger?: boolean; typeToConfirm?: string };
type Ctx = { toast: (text: string, tone?: Toast["tone"]) => void; confirm: (o: ConfirmOpts) => Promise<boolean> };
const FeedbackCtx = createContext<Ctx>({ toast: () => {}, confirm: async () => false });
export const useFeedback = () => useContext(FeedbackCtx);

export function FeedbackProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [ask, setAsk] = useState<(ConfirmOpts & { resolve: (v: boolean) => void }) | null>(null);
  const [typed, setTyped] = useState("");
  const toast = useCallback((text: string, tone: Toast["tone"] = "ok") => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, text, tone }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4500);
  }, []);
  const confirm = useCallback((o: ConfirmOpts) => new Promise<boolean>((resolve) => { setTyped(""); setAsk({ ...o, resolve }); }), []);
  const close = (v: boolean) => { ask?.resolve(v); setAsk(null); };
  const blocked = !!ask?.typeToConfirm && typed.trim() !== ask.typeToConfirm;
  return (
    <FeedbackCtx.Provider value={{ toast, confirm }}>
      {children}
      <div className="pointer-events-none fixed bottom-20 left-1/2 z-50 flex -translate-x-1/2 flex-col gap-2 md:bottom-6" role="status" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`pointer-events-auto rounded-lg px-4 py-2.5 text-[13px] font-medium text-white shadow-lg ${t.tone === "error" ? "bg-red-700" : "bg-zinc-900"}`}>{t.text}</div>
        ))}
      </div>
      {ask && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" role="dialog" aria-modal="true" aria-label={ask.title}
          onKeyDown={(e) => e.key === "Escape" && close(false)}>
          <div className="card flex w-full max-w-md flex-col gap-4 shadow-xl">
            <h2 className="font-display text-lg font-semibold">{ask.title}</h2>
            {ask.body && <div className="text-sm text-stone-600">{ask.body}</div>}
            {ask.typeToConfirm && (
              <label className="flex flex-col gap-1.5 text-[13px]">
                Para confirmar, escribe <b>{ask.typeToConfirm}</b>
                <input autoFocus className="input" value={typed} onChange={(e) => setTyped(e.target.value)} />
              </label>
            )}
            <div className="flex justify-end gap-2">
              <button type="button" className="btn" onClick={() => close(false)}>Cancelar</button>
              <button type="button" disabled={blocked} onClick={() => close(true)}
                className={`btn ${ask.danger ? "border-red-700 bg-red-700 text-white hover:bg-red-800" : "btn-primary"}`}>{ask.confirmLabel ?? "Confirmar"}</button>
            </div>
          </div>
        </div>
      )}
    </FeedbackCtx.Provider>
  );
}

/** Pestañas de navegación entre pantallas hermanas. */
export function TabNav({ tabs }: { tabs: readonly (readonly [to: string, label: string])[] }) {
  return (
    <nav className="tabs" aria-label="Secciones">
      {tabs.map(([to, label]) => (
        <NavLink key={to} to={to} end className={({ isActive }) => `tab ${isActive ? "is-active" : ""}`}>{label}</NavLink>
      ))}
    </nav>
  );
}

export const CONCURSOS_TABS = [["/search", "Todos"], ["/recommendations", "Para ti"], ["/opportunities", "Oportunidades"]] as const;
export const MERCADO_TABS = [["/market", "Entidades"], ["/suppliers", "Proveedores"]] as const;
