import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Empty, ErrorBox, Loading, Page } from "../components/ui";
import { money } from "../format";

export default function Opportunities() {
  const q = useQuery({ queryKey: ["opps"], queryFn: () => api("/opportunities") });
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorBox error={q.error} />;
  const d = q.data;
  if (!d.peers.length) return <Page title="Oportunidades"><Empty>Agrega tus NIT en Ajustes para encontrar proveedores semejantes y las clases donde participan.</Empty></Page>;
  return (
    <Page title="Oportunidades">
      <p className="muted">Productos donde participan proveedores parecidos a ti (por mezcla de clases UNSPSC) y donde tú aún no participas.</p>
      <div className="card">
        <h2 className="mb-1 font-medium">Proveedores semejantes</h2>
        <div className="flex flex-wrap gap-2">{d.peers.map((p: any) => <Link key={p.id} to={`/suppliers/${p.id}`} className="badge hover:underline">{p.name} · {Math.round(p.similarity * 100)}%</Link>)}</div>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        {d.opportunities.map((o: any) => (
          <div key={o.unspsc_class} className="card space-y-1">
            <div className="flex items-start justify-between gap-2">
              <div className="font-medium">{o.label}</div>
              <span className="badge shrink-0">UNSPSC {o.unspsc_class}</span>
            </div>
            <div className="muted">{o.examples.join(" · ")}</div>
            <div className="text-sm">{o.n_peers} semejantes participan ({o.peer_participations} veces) · adjudicado a ellos {money(o.peer_awarded_amount)}</div>
            <div className="muted">Ej.: {o.top_peers.join(", ")}</div>
            <Link className="btn mt-1" to={`/search`} state={{ unspsc: o.unspsc_class }}>{o.open_now} vigente(s) ahora</Link>
          </div>
        ))}
      </div>
    </Page>
  );
}
