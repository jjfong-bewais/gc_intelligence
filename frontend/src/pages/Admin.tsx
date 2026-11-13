import { useMutation, useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { api } from "../api";
import { ErrorBox, Kpi, KpiStrip, Loading, Page, Segmented, useFeedback } from "../components/ui";
import { dateTime, num } from "../format";
import Metrics from "./Metrics";
import Users from "./Users";

const TABS = [["usuarios", "Cuentas"], ["uso", "Uso"], ["sistema", "Datos y sistema"]] as const;
type Tab = (typeof TABS)[number][0];

/** Administración: cuentas, métricas de uso y estado de los datos, en un solo lugar. */
export default function Admin() {
  const [sp, setSp] = useSearchParams();
  const raw = sp.get("tab") as Tab | null;
  const tab: Tab = TABS.some(([v]) => v === raw) ? raw! : "usuarios";
  return (
    <div className="flex flex-col gap-6">
      <div className="overflow-x-auto"><Segmented label="Administración" value={tab} options={TABS} onChange={(v) => setSp({ tab: v })} /></div>
      {tab === "usuarios" ? <Users /> : tab === "uso" ? <Metrics /> : <SystemTab />}
    </div>
  );
}

function SystemTab() {
  const { toast, confirm } = useFeedback();
  const st = useQuery({ queryKey: ["admin-status"], queryFn: () => api("/admin/status") });
  const embed = useMutation({
    mutationFn: () => api("/admin/embed", { method: "POST" }),
    onSuccess: () => { toast("Embeddings pendientes procesados"); st.refetch(); },
    onError: (e) => toast((e as Error).message, "error"),
  });
  const alerts = useMutation({
    mutationFn: () => api("/admin/alerts/run", { method: "POST" }),
    onSuccess: () => toast("Alertas enviadas"),
    onError: (e) => toast((e as Error).message, "error"),
  });
  if (st.isLoading) return <Loading rows={3} />;
  if (st.error) return <ErrorBox error={st.error} />;
  const d = st.data;
  const files: any[] = d.files ?? [];
  return (
    <Page title="Datos y sistema" subtitle="Estado de la carga diaria de Guatecompras y acciones de mantenimiento.">
      <KpiStrip>
        <Kpi label="Concursos cargados" value={num(d.tenders)} />
        <Kpi label="Vigentes" value={num(d.open)} />
        <Kpi label="Sin embedding" value={num(d.without_embedding)} hint={d.without_embedding ? "no aparecen en búsqueda por significado" : "todo indexado"} />
        <Kpi label="Modo" value={<span className="text-xl">{d.mode}</span>} hint={`Embeddings: ${d.embeddings} · Correo: ${d.mail}`} />
      </KpiStrip>
      <section className="card flex flex-col gap-3">
        <h2 className="h-section">Acciones</h2>
        <div className="flex flex-wrap gap-2">
          <button className="btn" disabled={embed.isPending} onClick={() => embed.mutate()}>Procesar embeddings pendientes</button>
          <button className="btn" disabled={alerts.isPending} onClick={async () => {
            if (await confirm({ title: "¿Enviar las alertas ahora?", body: "Se envía el correo a todos los usuarios con alertas activas, aunque ya hayan recibido hoy.", confirmLabel: "Enviar" })) alerts.mutate();
          }}>Enviar alertas ahora</button>
        </div>
      </section>
      <section className="card flex flex-col gap-3">
        <h2 className="h-section">Archivos procesados</h2>
        {files.length ? (
          <div className="overflow-x-auto">
            <table className="min-w-[520px]">
              <thead><tr><th>Mes</th><th className="text-right">Registros</th><th className="text-right">Cambiados</th><th className="text-right">Procesado</th></tr></thead>
              <tbody>{files.slice(-12).reverse().map((f) => (
                <tr key={f.key}><td className="font-medium">{f.key}</td><td className="text-right tabular-nums">{num(f.n_records)}</td><td className="text-right tabular-nums text-stone-600">{num(f.n_changed)}</td><td className="whitespace-nowrap text-right text-stone-600">{dateTime(f.processed_at)}</td></tr>))}</tbody>
            </table>
          </div>
        ) : <p className="muted">Todavía no se ha procesado ningún archivo.</p>}
      </section>
    </Page>
  );
}
