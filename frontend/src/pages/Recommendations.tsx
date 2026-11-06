import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, Tender } from "../api";
import TenderCard from "../components/TenderCard";
import { Empty, ErrorBox, Loading, Page } from "../components/ui";

export default function Recommendations() {
  const q = useQuery({ queryKey: ["recs"], queryFn: () => api<{ items: Tender[]; profile_size: number }>("/recommendations?limit=40") });
  return (
    <Page title="Para ti" subtitle={<>Concursos vigentes parecidos a lo que tus NIT han ganado o cotizado y a lo que marcaste como “Me interesa”. Lo que marcas como “No me interesa” baja concursos similares.
      {q.data && q.data.profile_size > 0 && ` Perfil construido con ${q.data.profile_size} concursos.`}</>}>
      {q.isLoading ? <Loading rows={6} /> : q.error ? <ErrorBox error={q.error} /> : q.data!.items.length
        ? <div className="list">{q.data!.items.map((t) => <TenderCard key={t.ocid} t={t} context="recommendation" />)}</div>
        : <Empty action={<Link to="/settings" className="btn mt-2">Configurar NIT</Link>}>Aún no hay perfil. Agrega tus NIT en Ajustes o marca concursos que te interesen.</Empty>}
    </Page>
  );
}
