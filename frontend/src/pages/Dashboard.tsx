import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import TenderCard from "../components/TenderCard";
import { ErrorBox, Kpi, Loading, Page } from "../components/ui";
import { money } from "../format";

export default function Dashboard() {
  const q = useQuery({ queryKey: ["dashboard"], queryFn: () => api("/dashboard") });
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorBox error={q.error} />;
  const d = q.data;
  return (
    <Page title="Resumen">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Kpi label="Concursos vigentes" value={d.kpis.open} hint={`${d.kpis.new_7d} nuevos en 7 días`} />
        <Kpi label="Coincidencias con inventario" value={d.kpis.inventory_matches} hint={`${d.kpis.inventory_items} productos`} />
        <Kpi label="Favoritos" value={d.kpis.favorites} />
        <Kpi label="Adjudicado a tus NIT" value={money(d.kpis.awarded_total)} />
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="card">
          <h2 className="mb-2 font-medium">Concursos publicados por mes</h2>
          <div className="h-48">
            <ResponsiveContainer>
              <BarChart data={d.monthly}>
                <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.3} />
                <XAxis dataKey="month" fontSize={11} /><YAxis fontSize={11} width={36} /><Tooltip />
                <Bar dataKey="count" name="Concursos" fill="#2563eb" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div className="card">
          <h2 className="mb-2 font-medium">Vigentes por clase UNSPSC</h2>
          <div className="h-48">
            <ResponsiveContainer>
              <BarChart data={d.top_classes} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.3} />
                <XAxis type="number" fontSize={11} /><YAxis type="category" dataKey="unspsc" fontSize={11} width={60} /><Tooltip />
                <Bar dataKey="count" name="Concursos" fill="#0d9488" radius={[0, 3, 3, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
      <Section title="Cierran en 3 días" items={d.closing_soon} ctx="dashboard" empty="Nada cierra pronto." />
      <Section title="Recomendados para ti" more="/recommendations" items={d.recommended} ctx="dashboard" empty="Configura tus NIT en Ajustes o dale 👍 a concursos para recibir recomendaciones." />
      <Section title="Coinciden con tu inventario" more="/inventory" items={d.inventory_matches} ctx="inventory" empty="Importa tu inventario para ver coincidencias." />
    </Page>
  );
}

function Section({ title, items, ctx, empty, more }: { title: string; items: any[]; ctx: string; empty: string; more?: string }) {
  return (
    <section className="space-y-2">
      <div className="flex items-center justify-between">
        <h2 className="font-medium">{title}</h2>
        {more && <Link to={more} className="muted hover:underline">Ver todo →</Link>}
      </div>
      {items.length ? items.map((t) => <TenderCard key={t.ocid} t={t} context={ctx} />) : <div className="card muted">{empty}</div>}
    </section>
  );
}
