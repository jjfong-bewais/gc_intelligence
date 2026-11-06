import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api";
import { Page } from "../components/ui";
import { dateTime, num } from "../format";

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
    <Page title="Ajustes" subtitle={user.org_name}>
      <section className="card flex flex-col gap-4 p-6">
        <div>
          <h2 className="h-section">NIT de tu empresa</h2>
          <p className="mt-1 text-[13px] text-stone-600">Uno por línea. Con ellos construimos tu perfil de recomendaciones y oportunidades.</p>
        </div>
        <textarea className="input h-28 max-w-sm py-2 font-mono" aria-label="NIT de tu empresa" value={nits} onChange={(e) => { setNits(e.target.value); setOk(false); }} placeholder="9000001" />
        <div className="flex items-center gap-3">
          <button className="btn btn-primary" onClick={() => save.mutate()} disabled={save.isPending}>Guardar</button>
          {ok && <span className="text-[13px] text-green-700">Guardado</span>}
        </div>
      </section>
      {status.data && (
        <section className="card flex flex-col gap-4 p-6">
          <div>
            <h2 className="h-section">Estado del sistema</h2>
            <p className="mt-1 text-[13px] text-stone-600">{num(status.data.tenders)} concursos · {num(status.data.open)} vigentes · {num(status.data.without_embedding)} sin embedding · Embeddings: {status.data.embeddings} · Correo: {status.data.mail} · Modo: {status.data.mode}</p>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-[520px]"><thead><tr><th>Archivo</th><th className="text-right">Registros</th><th className="text-right">Cambios</th><th className="text-right">Última corrida</th></tr></thead><tbody>
              {status.data.files.map((f: any) => <tr key={f.key}><td>{f.key}</td><td className="text-right tabular-nums">{num(f.n_records)}</td><td className="text-right tabular-nums">{num(f.n_changed)}</td><td className="text-right text-stone-600">{dateTime(f.processed_at)}</td></tr>)}
            </tbody></table>
          </div>
        </section>
      )}
    </Page>
  );
}
