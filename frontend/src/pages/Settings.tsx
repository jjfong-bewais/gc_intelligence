import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api";
import { Page } from "../components/ui";
import { dateTime } from "../format";

export default function Settings({ user }: { user: any }) {
  const qc = useQueryClient();
  const [nits, setNits] = useState((user.supplier_ids as string[]).map((s) => s.replace("GT-NIT-", "")).join("\n"));
  const [ok, setOk] = useState(false);
  const save = useMutation({
    mutationFn: () => api("/org/suppliers", { method: "PUT", body: { supplier_ids: nits.split(/[\s,;]+/).filter(Boolean) } }),
    onSuccess: () => { setOk(true); qc.invalidateQueries(); },
  });
  const status = useQuery({ queryKey: ["admin"], queryFn: () => api("/admin/status"), enabled: user.role === "admin" });
  return (
    <Page title="Ajustes">
      <section className="card space-y-2">
        <h2 className="font-medium">{user.org_name}</h2>
        <p className="muted">NIT de tu empresa (uno por línea). Con ellos se construye tu perfil de recomendaciones y oportunidades.</p>
        <textarea className="input h-24 font-mono" value={nits} onChange={(e) => { setNits(e.target.value); setOk(false); }} placeholder="9000001" />
        <button className="btn btn-primary" onClick={() => save.mutate()}>Guardar</button> {ok && <span className="muted">Guardado ✓</span>}
      </section>
      {status.data && (
        <section className="card space-y-1 text-sm">
          <h2 className="font-medium">Estado del sistema</h2>
          <div>{status.data.tenders} concursos · {status.data.open} vigentes · {status.data.without_embedding} sin embedding</div>
          <div className="muted">Embeddings: {status.data.embeddings} · Correo: {status.data.mail} · Modo: {status.data.mode}</div>
          <table className="mt-2 w-full"><thead><tr><th>Archivo</th><th>Registros</th><th>Cambios</th><th>Última corrida</th></tr></thead><tbody>
            {status.data.files.map((f: any) => <tr key={f.key} className="border-t border-slate-100 dark:border-slate-800"><td>{f.key}</td><td>{f.n_records}</td><td>{f.n_changed}</td><td>{dateTime(f.processed_at)}</td></tr>)}
          </tbody></table>
        </section>
      )}
    </Page>
  );
}
