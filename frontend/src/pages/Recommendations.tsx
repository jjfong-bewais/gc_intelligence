import { useQuery } from "@tanstack/react-query";
import { api, Tender } from "../api";
import TenderCard from "../components/TenderCard";
import { Empty, ErrorBox, Loading, Page } from "../components/ui";

export default function Recommendations() {
  const q = useQuery({ queryKey: ["recs"], queryFn: () => api<{ items: Tender[]; profile_size: number }>("/recommendations?limit=40") });
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorBox error={q.error} />;
  return (
    <Page title="Para ti">
      <p className="muted">Concursos vigentes parecidos a lo que tus NIT han ganado o cotizado y a lo que marcaste con 👍. Los 👎 reducen concursos similares.
        {q.data!.profile_size > 0 && ` Perfil construido con ${q.data!.profile_size} concursos.`}</p>
      {q.data!.items.length ? <div className="space-y-2">{q.data!.items.map((t) => <TenderCard key={t.ocid} t={t} context="recommendation" />)}</div>
        : <Empty>Aún no hay perfil. Agrega tus NIT en Ajustes o dale 👍 a concursos que te interesen.</Empty>}
    </Page>
  );
}
