import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api, Tender } from "../api";
import { IconBookmark } from "../components/icons";
import TenderCard, { FAV_LABELS } from "../components/TenderCard";
import { Empty, ErrorBox, Loading, Page, Segmented } from "../components/ui";

export default function Favorites() {
  const [f, setF] = useState("");
  const q = useQuery({ queryKey: ["favs"], queryFn: () => api<{ items: Tender[] }>("/favorites") });
  const all = q.data?.items ?? [];
  const count = (s: string) => all.filter((t) => !s || t.favorite === s).length;
  const opts = [["", `Todos ${count("")}`], ...Object.entries(FAV_LABELS).map(([v, l]) => [v, `${l} ${count(v)}`])] as [string, string][];
  const items = all.filter((t) => !f || t.favorite === f);
  return (
    <Page title="Seguimiento" subtitle="Los concursos que sigues y en qué etapa va cada uno.">
      <div className="overflow-x-auto"><Segmented label="Filtrar por estado" value={f} options={opts} onChange={setF} /></div>
      {q.isLoading ? <Loading /> : q.error ? <ErrorBox error={q.error} /> : items.length ? (
        <div className="list">{items.map((t) => (
          <TenderCard key={t.ocid} t={t} context="favorites" extra={
            <div className="mt-1 flex flex-wrap items-center gap-2 text-xs"><span className="badge">{FAV_LABELS[t.favorite!]}</span>{t.note && <span className="text-stone-600">{t.note}</span>}</div>} />))}</div>
      ) : <Empty icon={<IconBookmark size={28} />}>Usa el ícono de marcador en cualquier concurso para seguirlo aquí.</Empty>}
    </Page>
  );
}
