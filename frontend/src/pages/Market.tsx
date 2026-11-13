import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { IconSearch } from "../components/icons";
import { Empty, Loading, MERCADO_TABS, Page, TabNav } from "../components/ui";
import { nameCase } from "../format";

/** Mercado: entender quién compra y quién vende en el Estado. */
export default function Market() {
  const [q, setQ] = useState("");
  const r = useQuery({
    queryKey: ["buyers-list", q],
    queryFn: () => api<{ total: number; items: { buyer_name: string }[] }>("/tenders/search", { body: { q, mode: "keyword", filters: {}, sort: "recent", limit: 50 } }),
    placeholderData: (p) => p,
    enabled: q.trim().length >= 3,
  });
  const names = Array.from(new Set((r.data?.items ?? []).map((t) => t.buyer_name).filter(Boolean)));
  return (
    <Page title="Mercado" subtitle="Conoce a las entidades que compran y a los proveedores que ganan.">
      <TabNav tabs={MERCADO_TABS} />
      <label className="search-box">
        <IconSearch size={18} className="text-stone-600" /><span className="sr-only">Buscar entidad</span>
        <input className="min-w-0 flex-1 bg-transparent text-[15px] outline-none placeholder:text-stone-500" placeholder="Busca una entidad compradora (mín. 3 letras)…" value={q} onChange={(e) => setQ(e.target.value)} />
      </label>
      {q.trim().length < 3 ? <Empty>Escribe el nombre de un ministerio, municipalidad o institución para ver qué compra, cuánto adjudica y a quién.</Empty>
        : r.isLoading ? <Loading rows={3} /> : names.length ? (
          <div className="list">{names.map((n) => (
            <Link key={n} to={`/buyers?name=${encodeURIComponent(n)}`} className="flex items-center justify-between gap-4 px-5 py-3 text-sm font-medium text-zinc-900 hover:bg-stone-50">{nameCase(n)}<span className="text-xs text-stone-600">Ver perfil →</span></Link>))}</div>
        ) : <Empty>No encontramos entidades con ese nombre.</Empty>}
    </Page>
  );
}
