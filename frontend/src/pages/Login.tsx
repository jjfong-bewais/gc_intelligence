import { useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";
import { api } from "../api";

export default function Login() {
  const qc = useQueryClient();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  async function submit(e: FormEvent) {
    e.preventDefault();
    try { qc.setQueryData(["me"], await api("/auth/login", { body: { email, password } })); }
    catch (x) { setErr((x as Error).message); }
  }
  return (
    <div className="mx-auto mt-24 max-w-sm px-4">
      <form onSubmit={submit} className="card space-y-3">
        <h1 className="text-lg font-semibold">GC Intelligence</h1>
        <p className="muted">Inteligencia de mercado sobre Guatecompras.</p>
        <input className="input" type="email" placeholder="Correo" value={email} onChange={(e) => setEmail(e.target.value)} autoFocus required />
        <input className="input" type="password" placeholder="Contraseña" value={password} onChange={(e) => setPassword(e.target.value)} required />
        {err && <div className="text-sm text-red-600">{err}</div>}
        <button className="btn btn-primary w-full justify-center">Entrar</button>
      </form>
    </div>
  );
}
