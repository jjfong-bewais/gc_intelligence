import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, Tender } from "../api";
import FilterPanel, { WithFilters } from "../components/FilterPanel";
import TenderCard from "../components/TenderCard";
import { Empty, ErrorBox, Loading, Page } from "../components/ui";
import { countActive, filterQuery, useViewFilters } from "../filters";

export default function Recommendations() {
  const [filters, setFilters] = useViewFilters("recommendations");
  const fq = filterQuery(filters);
  const q = useQuery({
    queryKey: ["recs", fq],
    queryFn: () => api<{ items: Tender[]; profile_size: number }>(`/recommendations?limit=40${fq ? `&${fq}` : ""}`),
    placeholderData: (p) => p,
  });
  const filtered = countActive(filters) > 0;
  return (
    <Page title="Para ti" subtitle={<>Concursos vigentes parecidos a lo que tus NIT han ganado o cotizado y a lo que marcaste como “Me interesa”. Lo que marcas como “No me interesa” baja concursos similares.
      {q.data && q.data.profile_size > 0 && ` Perfil construido con ${q.data.profile_size} concursos.`}</>}>
      <WithFilters f={filters} panel={<FilterPanel value={filters} onChange={setFilters} lockOpen />}>
        {q.isLoading ? <Loading rows={6} /> : q.error ? <ErrorBox error={q.error} /> : q.data!.items.length
          ? <div className={`list transition-opacity ${q.isFetching ? "opacity-60" : ""}`}>{q.data!.items.map((t) => <TenderCard key={t.ocid} t={t} context="recommendation" />)}</div>
          : filtered && q.data!.profile_size > 0
            ? <Empty action={<button className="btn mt-2" onClick={() => setFilters({})}>Quitar filtros</button>}>Ningún concurso recomendado cumple estos filtros.</Empty>
            : <Empty action={<Link to="/settings" className="btn mt-2">Configurar NIT</Link>}>Aún no hay perfil. Agrega tus NIT en Ajustes o marca concursos que te interesen.</Empty>}
      </WithFilters>
    </Page>
  );
}
