import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { api, Tender } from "../api";
import TenderCard from "../components/TenderCard";
import { Empty, ErrorBox, Loading, Page } from "../components/ui";

export default function Inventory() {
  const qc = useQueryClient();
  const file = useRef<HTMLInputElement>(null);
  const [msg, setMsg] = useState("");
  const inv = useQuery({ queryKey: ["inv"], queryFn: () => api("/inventory") });
  const matches = useQuery({ queryKey: ["inv-matches"], queryFn: () => api<{ items: Tender[] }>("/inventory/matches") });
  const up = useMutation({
    mutationFn: (f: File) => { const fd = new FormData(); fd.append("file", f); return api("/inventory/import?replace=true", { form: fd }); },
    onSuccess: (r: any) => { setMsg(`${r.imported} productos importados.`); qc.invalidateQueries(); },
    onError: (e: Error) => setMsg(e.message),
  });
  const clear = useMutation({ mutationFn: () => api("/inventory", { method: "DELETE" }), onSuccess: () => qc.invalidateQueries() });
  if (inv.isLoading) return <Loading />;
  if (inv.error) return <ErrorBox error={inv.error} />;
  return (
    <Page title="Inventario" actions={<div className="flex gap-2">
      <input ref={file} type="file" accept=".csv,text/csv" hidden onChange={(e) => e.target.files?.[0] && up.mutate(e.target.files[0])} />
      <button className="btn btn-primary" onClick={() => file.current?.click()}>Importar CSV</button>
      {inv.data.items.length > 0 && <button className="btn" onClick={() => confirm("¿Borrar todo el inventario?") && clear.mutate()}>Vaciar</button>}
    </div>}>
      <p className="muted">CSV con columnas <code>sku, descripcion, unidad, unspsc</code> (solo <code>descripcion</code> es obligatoria; acepta “;” o “,”). Aquí ves los concursos vigentes que piden productos que ya tienes.</p>
      {msg && <div className="card text-sm">{msg}</div>}
      <section className="space-y-2">
        <h2 className="font-medium">Coincidencias vigentes</h2>
        {matches.isLoading ? <Loading /> : matches.data?.items.length ? matches.data.items.map((t) => (
          <TenderCard key={t.ocid} t={t} context="inventory" extra={
            <ul className="mt-1 space-y-0.5 text-xs">{t.matches!.slice(0, 4).map((m: any, i: number) => (
              <li key={i}><b>{m.sku || "—"}</b> {m.inventory_description} → <i>{m.item_description}</i> ({Math.round(m.similarity * 100)}%{m.quantity ? `, piden ${m.quantity} ${m.unit ?? ""}` : ""})</li>))}</ul>} />
        )) : <Empty>{inv.data.items.length ? "Sin coincidencias vigentes por ahora." : "Importa tu inventario para empezar."}</Empty>}
      </section>
      {inv.data.items.length > 0 && (
        <section className="card"><h2 className="mb-1 font-medium">Productos ({inv.data.items.length})</h2>
          <table className="w-full text-sm"><thead><tr><th>SKU</th><th>Descripción</th><th>Unidad</th><th>UNSPSC</th></tr></thead><tbody>
            {inv.data.items.slice(0, 100).map((i: any) => <tr key={i.id} className="border-t border-slate-100 dark:border-slate-800"><td>{i.sku}</td><td>{i.description}</td><td>{i.unit}</td><td>{i.unspsc}</td></tr>)}
          </tbody></table></section>
      )}
    </Page>
  );
}
