import { ReactNode } from "react";
import { Link } from "react-router-dom";

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
