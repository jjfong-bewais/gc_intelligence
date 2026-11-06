import { useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";
import { api } from "../api";

export default function Login() {
  const qc = useQueryClient();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setErr("");
    try { qc.setQueryData(["me"], await api("/auth/login", { body: { email, password } })); }
    catch (x) { setErr((x as Error).message); }
    finally { setBusy(false); }
  }
  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="flex w-full max-w-sm flex-col gap-8">
        <div className="flex flex-col items-center gap-3 text-center">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-zinc-900 text-sm font-semibold text-white">GC</div>
          <div>
            <h1 className="text-xl font-semibold tracking-tight">GC Intelligence</h1>
            <p className="mt-1 text-sm text-stone-600">Inteligencia de mercado sobre Guatecompras</p>
          </div>
        </div>
        <form onSubmit={submit} className="card flex flex-col gap-4 p-6 shadow-sm">
          <label className="flex flex-col gap-1.5 text-[13px] font-medium">Correo
            <input className="input min-h-10 font-normal" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} autoFocus required />
          </label>
          <label className="flex flex-col gap-1.5 text-[13px] font-medium">Contraseña
            <input className="input min-h-10 font-normal" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </label>
          {err && <div role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-[13px] text-red-800">{err}</div>}
          <button className="btn btn-primary min-h-10 w-full" disabled={busy}>{busy ? "Entrando…" : "Entrar"}</button>
        </form>
      </div>
    </div>
  );
}
