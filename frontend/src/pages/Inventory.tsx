import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { api, Tender } from "../api";
import { IconUpload } from "../components/icons";
import TenderCard from "../components/TenderCard";
import { Empty, ErrorBox, Loading, Page, Section } from "../components/ui";
import { sentenceCase } from "../format";

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
  const n = inv.data?.items.length ?? 0;
  return (
    <Page title="Inventario" subtitle="Concursos vigentes que piden productos que ya tienes."
      actions={<>
        <input ref={file} type="file" accept=".csv,text/csv" hidden onChange={(e) => e.target.files?.[0] && up.mutate(e.target.files[0])} />
        <button className="btn btn-primary" onClick={() => file.current?.click()} disabled={up.isPending}><IconUpload size={15} />{up.isPending ? "Importando…" : "Importar CSV"}</button>
        {n > 0 && <button className="btn-ghost" onClick={() => confirm("¿Borrar todo el inventario?") && clear.mutate()}>Vaciar</button>}
      </>}>
      {msg && <div className="rounded-lg border border-stone-200 bg-white px-3 py-2 text-[13px]">{msg}</div>}
      {inv.isLoading ? <Loading /> : inv.error ? <ErrorBox error={inv.error} /> : (
        <>
          {n === 0 ? (
            <Empty icon={<IconUpload size={28} />} action={<button className="btn btn-primary mt-2" onClick={() => file.current?.click()}>Importar CSV</button>}>
              Sube un CSV con las columnas <code className="rounded bg-stone-100 px-1">sku, descripcion, unidad, unspsc</code>. Solo <code className="rounded bg-stone-100 px-1">descripcion</code> es obligatoria; acepta “;” o “,”.
            </Empty>
          ) : (
            <Section title="Coincidencias vigentes">
              {matches.isLoading ? <Loading /> : matches.data?.items.length ? (
                <div className="list">{matches.data.items.map((t) => (
                  <TenderCard key={t.ocid} t={t} context="inventory" extra={
                    <ul className="mt-1.5 flex flex-col gap-1 text-xs text-stone-700">{t.matches!.slice(0, 4).map((m: any, i: number) => (
                      <li key={i}><span className="font-medium">{m.sku || "—"}</span> {m.inventory_description} → <span className="text-stone-600">{sentenceCase(m.item_description)}</span> · {Math.round(m.similarity * 100)}%{m.quantity ? ` · piden ${m.quantity} ${m.unit ?? ""}` : ""}</li>))}</ul>} />
                ))}</div>
              ) : <Empty>Sin coincidencias vigentes por ahora.</Empty>}
            </Section>
          )}
          {n > 0 && (
            <Section title={`Productos (${n})`}>
              <div className="card overflow-x-auto p-0 px-5">
                <table className="min-w-[520px]"><thead><tr><th>SKU</th><th>Descripción</th><th>Unidad</th><th>UNSPSC</th></tr></thead><tbody>
                  {inv.data.items.slice(0, 100).map((i: any) => <tr key={i.id}><td className="text-stone-600">{i.sku}</td><td>{i.description}</td><td>{i.unit}</td><td className="tabular-nums text-stone-600">{i.unspsc}</td></tr>)}
                </tbody></table>
              </div>
            </Section>
          )}
        </>
      )}
    </Page>
  );
}
