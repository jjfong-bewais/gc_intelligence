import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";
import { api } from "../api";

/** Formulario de cambio de contraseña. Se usa en Ajustes y, a pantalla completa, en el primer acceso. */
export function PasswordForm({ onDone, submitLabel = "Guardar" }: { onDone?: () => void; submitLabel?: string }) {
  const qc = useQueryClient();
  const [cur, setCur] = useState("");
  const [next, setNext] = useState("");
  const [again, setAgain] = useState("");
  const [localErr, setLocalErr] = useState("");
  const save = useMutation({
    mutationFn: () => api("/auth/password", { method: "PUT", body: { current_password: cur, new_password: next } }),
    onSuccess: (u) => { qc.setQueryData(["me"], u); qc.invalidateQueries({ predicate: (q) => q.queryKey[0] !== "me" }); onDone?.(); },
  });
  const submit = (e: FormEvent) => {
    e.preventDefault(); setLocalErr("");
    if (next.length < 8) return setLocalErr("La contraseña nueva necesita al menos 8 caracteres");
    if (next !== again) return setLocalErr("Las contraseñas nuevas no coinciden");
    save.mutate();
  };
  const err = localErr || (save.error as Error | null)?.message;
  return (
    <form onSubmit={submit} className="flex max-w-sm flex-col gap-3">
      <label className="flex flex-col gap-1 text-[13px] text-stone-700">Contraseña actual
        <input className="input" type="password" required autoComplete="current-password" value={cur} onChange={(e) => setCur(e.target.value)} /></label>
      <label className="flex flex-col gap-1 text-[13px] text-stone-700">Contraseña nueva
        <input className="input" type="password" required minLength={8} autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} />
        <span className="text-xs text-stone-500">Mínimo 8 caracteres.</span></label>
      <label className="flex flex-col gap-1 text-[13px] text-stone-700">Repite la contraseña nueva
        <input className="input" type="password" required autoComplete="new-password" value={again} onChange={(e) => setAgain(e.target.value)} /></label>
      {err && <p role="alert" className="text-[13px] text-red-700">{err}</p>}
      <div><button className="btn btn-primary" disabled={save.isPending}>{save.isPending ? "Guardando…" : submitLabel}</button></div>
    </form>
  );
}

/** Pantalla que bloquea la plataforma hasta que el usuario cambia su contraseña temporal. */
export default function ChangePassword({ onLogout }: { onLogout: () => void }) {
  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="card flex w-full max-w-md flex-col gap-5 p-6 shadow-sm">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Crea tu contraseña</h1>
          <p className="mt-1 text-sm text-stone-600">Entraste con una contraseña temporal. Por seguridad, elige una nueva para continuar.</p>
        </div>
        <PasswordForm submitLabel="Guardar y entrar" />
        <button type="button" className="self-start text-[13px] text-stone-600 hover:text-zinc-900" onClick={onLogout}>Cerrar sesión</button>
      </div>
    </div>
  );
}
