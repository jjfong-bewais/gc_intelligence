import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api, Tender } from "../api";
import TenderCard, { FAV_LABELS } from "../components/TenderCard";
import { Empty, ErrorBox, Loading, Page } from "../components/ui";

export default function Favorites() {
  const [f, setF] = useState("");
  const q = useQuery({ queryKey: ["favs"], queryFn: () => api<{ items: Tender[] }>("/favorites") });
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorBox error={q.error} />;
  const items = q.data!.items.filter((t) => !f || t.favorite === f);
  return (
    <Page title="Favoritos" actions={
      <select className="input w-auto" value={f} onChange={(e) => setF(e.target.value)}>
        <option value="">Todos</option>{Object.entries(FAV_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select>}>
      {items.length ? <div className="space-y-2">{items.map((t) => (
        <TenderCard key={t.ocid} t={t} context="favorites" extra={<div className="flex gap-2 text-xs"><span className="badge">{FAV_LABELS[t.favorite!]}</span>{t.note && <span className="muted">{t.note}</span>}</div>} />))}</div>
        : <Empty>Marca concursos con ☆ para seguirlos aquí.</Empty>}
    </Page>
  );
}
