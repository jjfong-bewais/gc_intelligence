import { ReactNode } from "react";

export const Page = ({ title, actions, children }: { title: string; actions?: ReactNode; children: ReactNode }) => (
  <div className="space-y-4">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h1 className="text-xl font-semibold">{title}</h1>
      {actions}
    </div>
    {children}
  </div>
);

export const Loading = () => <div className="muted py-8 text-center">Cargando…</div>;
export const Empty = ({ children }: { children: ReactNode }) => <div className="card muted text-center">{children}</div>;
export const ErrorBox = ({ error }: { error: unknown }) => (
  <div className="card border-red-300 text-sm text-red-700 dark:text-red-300">{(error as Error)?.message ?? "Error"}</div>
);

export function Kpi({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <div className="card">
      <div className="muted">{label}</div>
      <div className="text-2xl font-semibold tabular-nums">{value}</div>
      {hint && <div className="muted text-xs">{hint}</div>}
    </div>
  );
}
