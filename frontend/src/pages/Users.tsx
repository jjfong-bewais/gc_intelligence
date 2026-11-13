import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";
import { api } from "../api";
import { useMe } from "../auth";
import { Empty, ErrorBox, Loading, Page, useFeedback } from "../components/ui";
import { date } from "../format";

type User = {
  id: number; email: string; name: string; company: string | null; role: "member" | "admin"; active: boolean;
  must_change_password: boolean; n_nits: number; created_at: string | null;
  last_active_at?: string | null; usage_status?: "active" | "at_risk" | "dormant" | "never";
};
type Saved = { user: User; email_sent?: boolean };

const ROLES: [User["role"], string][] = [["member", "Usuario"], ["admin", "Administrador"]];

export default function Users() {
  const qc = useQueryClient();
  const me = useMe().data;
  const { confirm: ask } = useFeedback();
  const list = useQuery({ queryKey: ["users"], queryFn: () => api<{ items: User[] }>("/users") });
  const [creating, setCreating] = useState(false);
  const [msg, setMsg] = useState("");
  const refresh = () => qc.invalidateQueries({ queryKey: ["users"] });
  const patch = useMutation({
    mutationFn: ({ id, ...body }: Partial<User> & { id: number }) => api<Saved>(`/users/${id}`, { method: "PATCH", body }),
    onSuccess: refresh, onError: (e) => setMsg((e as Error).message),
  });
  const reset = useMutation({
    mutationFn: (id: number) => api<{ email_sent: boolean }>(`/users/${id}/reset-password`, { method: "POST" }),
    onSuccess: (r) => setMsg(r.email_sent ? "Enviamos una contraseña temporal nueva por correo." : "No se pudo enviar el correo. Inténtalo de nuevo."),
    onError: (e) => setMsg((e as Error).message),
  });
  const del = useMutation({
    mutationFn: (id: number) => api(`/users/${id}`, { method: "DELETE" }),
    onSuccess: () => { setMsg("Usuario eliminado."); refresh(); }, onError: (e) => setMsg((e as Error).message),
  });
  const items = list.data?.items ?? [];

  return (
    <Page title="Usuarios" subtitle="Cada usuario es su propia empresa. Al crearlo le enviamos por correo una contraseña temporal que deberá cambiar en su primer acceso."
      actions={<button className="btn btn-primary" onClick={() => { setCreating(true); setMsg(""); }}>Nuevo usuario</button>}>
      {creating && <NewUser onClose={() => setCreating(false)} onCreated={(r) => {
        setCreating(false); refresh();
        setMsg(r.email_sent ? `Invitación enviada a ${r.user.email}.` : `Creamos a ${r.user.email}, pero el correo no salió: usa «Reenviar clave».`);
      }} />}
      {msg && <div role="status" className="rounded-lg border border-stone-200 bg-stone-50 px-3 py-2 text-[13px] text-stone-800">{msg}</div>}
      {list.isLoading ? <Loading rows={3} /> : list.error ? <ErrorBox error={list.error} /> : items.length ? (
        <div className="list">
          {items.map((u) => {
            const self = u.id === me?.id;
            return (
              <div key={u.id} className={`flex flex-wrap items-center justify-between gap-4 px-5 py-4 ${u.active ? "" : "opacity-70"}`}>
                <div className="flex min-w-0 flex-[1_1_260px] flex-col gap-0.5">
                  <span className="truncate text-sm font-medium">{u.company || u.email}{self && <span className="ml-2 text-xs font-normal text-stone-500">(tú)</span>}</span>
                  <span className="truncate text-[13px] text-stone-600">{[u.name, u.email].filter(Boolean).join(" · ")}</span>
                  <span className="flex flex-wrap gap-1.5 pt-1 text-xs">
                    <span className="badge">{u.n_nits} NIT</span>
                    {u.created_at && <span className="badge">Desde {date(u.created_at)}</span>}
                    <span className="badge">{u.last_active_at ? `Último acceso ${date(u.last_active_at)}` : "Sin accesos"}</span>
                    {u.usage_status === "at_risk" && <span className="badge bg-amber-50 text-amber-800">En riesgo</span>}
                    {u.usage_status === "dormant" && <span className="badge bg-red-50 text-red-800">Inactivo</span>}
                    {u.must_change_password && <span className="badge bg-amber-50 text-amber-800">Aún no entra</span>}
                    {!u.active && <span className="badge bg-red-50 text-red-800">Desactivado</span>}
                  </span>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <select className="input w-auto" aria-label={`Rol de ${u.email}`} value={u.role} disabled={self || patch.isPending}
                    onChange={(e) => patch.mutate({ id: u.id, role: e.target.value as User["role"] })}>
                    {ROLES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                  </select>
                  <button className="btn" onClick={() => { setMsg(""); reset.mutate(u.id); }} disabled={reset.isPending}>Reenviar clave</button>
                  {!self && <>
                    <button className="btn" onClick={() => { setMsg(""); patch.mutate({ id: u.id, active: !u.active }); }}>{u.active ? "Desactivar" : "Activar"}</button>
                    <button className="action-pill is-danger" onClick={async () => { if (await ask({ title: `¿Eliminar a ${u.email}?`, body: "Se borran también sus NIT, inventario, seguimiento y alertas. No se puede deshacer.", confirmLabel: "Eliminar", danger: true, typeToConfirm: u.company || u.email })) { setMsg(""); del.mutate(u.id); } }}>Eliminar</button>
                  </>}
                </div>
              </div>
            );
          })}
        </div>
      ) : <Empty>Todavía no hay usuarios.</Empty>}
    </Page>
  );
}

function NewUser({ onClose, onCreated }: { onClose: () => void; onCreated: (r: Saved) => void }) {
  const [f, setF] = useState({ email: "", name: "", company: "", role: "member" });
  const create = useMutation({ mutationFn: () => api<Saved>("/users", { body: f }), onSuccess: onCreated });
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  const submit = (e: FormEvent) => { e.preventDefault(); create.mutate(); };
  return (
    <form onSubmit={submit} className="card flex flex-col gap-4 p-6">
      <h2 className="h-section">Nuevo usuario</h2>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="flex flex-col gap-1 text-[13px] text-stone-700">Correo
          <input className="input" type="email" required autoFocus value={f.email} onChange={set("email")} /></label>
        <label className="flex flex-col gap-1 text-[13px] text-stone-700">Empresa
          <input className="input" value={f.company} onChange={set("company")} /></label>
        <label className="flex flex-col gap-1 text-[13px] text-stone-700">Nombre de la persona
          <input className="input" value={f.name} onChange={set("name")} /></label>
        <label className="flex flex-col gap-1 text-[13px] text-stone-700">Rol
          <select className="input" value={f.role} onChange={set("role")}>{ROLES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
      </div>
      {create.error && <p role="alert" className="text-[13px] text-red-700">{(create.error as Error).message}</p>}
      <div className="flex gap-2">
        <button className="btn btn-primary" disabled={create.isPending}>{create.isPending ? "Creando…" : "Crear y enviar invitación"}</button>
        <button type="button" className="btn" onClick={onClose}>Cancelar</button>
      </div>
    </form>
  );
}
