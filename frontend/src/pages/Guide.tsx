import { useQuery } from "@tanstack/react-query";
import { ReactNode, useEffect, useMemo, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { api } from "../api";
import { IconSearch } from "../components/icons";
import { Page } from "../components/ui";
import { date, dateTime, num } from "../format";

/* ── Guía: qué puede hacer el usuario, parámetros y disponibilidad de datos ── */

type Coverage = {
  first_published: string | null; last_published: string | null; updated_at: string | null;
  tenders: number; open: number; accepting: number; awarded: number; buyers: number; demo: boolean;
};

const TOC: [string, string][] = [
  ["inicio", "Primeros pasos"],
  ["datos", "Datos disponibles"],
  ["resumen", "Resumen"],
  ["buscar", "Buscar concursos"],
  ["detalle", "Detalle y precios"],
  ["para-ti", "Para ti"],
  ["oportunidades", "Oportunidades"],
  ["seguimiento", "Seguimiento y 👍/👎"],
  ["alertas", "Alertas por correo"],
  ["proveedores", "Proveedores"],
  ["historial", "Tu historial"],
  ["inventario", "Inventario"],
  ["filtros", "Referencia de filtros"],
  ["privacidad", "Uso de la plataforma"],
  ["faq", "Preguntas frecuentes"],
];

export default function Guide() {
  const { hash } = useLocation();
  // Ir a la sección indicada en la URL (#alertas, #filtros…) al abrir desde un ícono ⓘ.
  useEffect(() => {
    if (!hash) return;
    const t = setTimeout(() => document.getElementById(hash.slice(1))?.scrollIntoView({ behavior: "smooth", block: "start" }), 60);
    return () => clearTimeout(t);
  }, [hash]);

  return (
    <Page title="Guía" subtitle="Todo lo que puedes hacer con GC Intelligence: qué hace cada pantalla, qué significa cada parámetro y qué datos hay disponibles.">
      <div className="flex flex-col gap-6 lg:grid lg:grid-cols-[200px_minmax(0,1fr)] lg:items-start lg:gap-8">
        <nav aria-label="Contenido de la guía" className="hidden lg:sticky lg:top-6 lg:flex lg:flex-col lg:gap-0.5">
          <div className="eyebrow px-2.5 pb-1.5">En esta guía</div>
          {TOC.map(([id, l]) => (
            <a key={id} href={`#${id}`} onClick={(e) => { e.preventDefault(); history.replaceState(null, "", `#${id}`); document.getElementById(id)?.scrollIntoView({ behavior: "smooth" }); }}
              className="rounded-lg px-2.5 py-1.5 text-[13px] text-stone-700 hover:bg-stone-50 hover:text-zinc-900">{l}</a>
          ))}
        </nav>
        <div className="flex min-w-0 flex-col gap-6">
          <FirstSteps />
          <DataSection />
          <Screens />
          <FiltersRef />
          <Faq />
        </div>
      </div>
    </Page>
  );
}

/* ── Piezas ─────────────────────────────────────────────────────────────── */

function Sec({ id, title, to, toLabel, children }: { id: string; title: string; to?: string; toLabel?: string; children: ReactNode }) {
  return (
    <section id={id} className="card flex scroll-mt-6 flex-col gap-3 p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="h-section">{title}</h2>
        {to && <Link to={to} className="text-[13px] font-medium">{toLabel ?? "Abrir"} →</Link>}
      </div>
      <div className="flex flex-col gap-3 text-[13px] leading-relaxed text-stone-700">{children}</div>
    </section>
  );
}

const Ul = ({ children }: { children: ReactNode }) => <ul className="flex list-disc flex-col gap-1.5 pl-5">{children}</ul>;
const B = ({ children }: { children: ReactNode }) => <b className="font-semibold text-zinc-900">{children}</b>;
const Tip = ({ children }: { children: ReactNode }) => <p className="rounded-lg bg-brand-50 px-3 py-2 text-brand-800">{children}</p>;

/** Ícono ⓘ que abre la sección correspondiente de la guía. */
export function HelpLink({ section, label = "Cómo funciona" }: { section: string; label?: string }) {
  return (
    <Link to={`/guide#${section}`} title={label} aria-label={`${label} (abre la guía)`}
      className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-stone-300 align-middle text-[11px] font-semibold not-italic text-stone-600 hover:border-brand-500 hover:text-brand-800">i</Link>
  );
}

/* ── 1. Primeros pasos ──────────────────────────────────────────────────── */

function FirstSteps() {
  const nits = useQuery({ queryKey: ["org-nits"], queryFn: () => api<{ items: unknown[] }>("/org/suppliers") });
  const saved = useQuery({ queryKey: ["saved"], queryFn: () => api<{ items: { active: boolean }[] }>("/saved-searches") });
  const favs = useQuery({ queryKey: ["favs"], queryFn: () => api<{ items: unknown[] }>("/favorites") });
  const steps: { done?: boolean; title: string; text: string; to: string; cta: string }[] = [
    { done: nits.data ? nits.data.items.length > 0 : undefined, title: "Agrega los NIT de tu empresa",
      text: "Con ellos armamos tus recomendaciones, tus oportunidades y tu historial de participación.", to: "/settings", cta: "Ir a Ajustes" },
    { done: saved.data ? saved.data.items.some((s) => s.active) : undefined, title: "Guarda una búsqueda con aviso por correo",
      text: "Elige filtros (y, si quieres, un texto) y usa “Guardar combinación” para recibir los mejores concursos vigentes.", to: "/search", cta: "Ir a Buscar" },
    { done: favs.data ? favs.data.items.length > 0 : undefined, title: "Sigue un concurso",
      text: "Marca con el ícono de marcador los concursos que te interesan para controlar si los cotizaste, ganaste o perdiste.", to: "/recommendations", cta: "Ver Para ti" },
  ];
  return (
    <Sec id="inicio" title="Primeros pasos">
      <p>Tres pasos para sacarle provecho desde el primer día:</p>
      <ol className="flex flex-col gap-2">
        {steps.map((s, i) => (
          <li key={s.title} className="flex items-start gap-3 rounded-xl border border-stone-200 px-4 py-3">
            <span className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${s.done ? "bg-green-100 text-green-800" : "bg-stone-100 text-stone-700"}`}>
              {s.done ? "✓" : i + 1}
            </span>
            <div className="flex min-w-0 flex-1 flex-col gap-0.5">
              <span className="text-sm font-medium text-zinc-900">{s.title}{s.done && <span className="ml-2 text-xs font-normal text-green-700">Listo</span>}</span>
              <span>{s.text}</span>
            </div>
            {!s.done && <Link to={s.to} className="btn shrink-0">{s.cta}</Link>}
          </li>
        ))}
      </ol>
    </Sec>
  );
}

/* ── 2. Datos disponibles ───────────────────────────────────────────────── */

function DataSection() {
  const c = useQuery({ queryKey: ["coverage"], queryFn: () => api<Coverage>("/data-coverage"), staleTime: 10 * 60_000 });
  const d = c.data;
  const fact = (k: string, v: ReactNode, sub?: string) => (
    <div className="flex min-w-0 flex-col gap-1 bg-white px-4 py-3.5">
      <span className="text-xs text-stone-600">{k}</span>
      <span className="text-sm font-semibold tabular-nums text-zinc-900">{v}</span>
      {sub && <span className="text-xs text-stone-600">{sub}</span>}
    </div>
  );
  return (
    <Sec id="datos" title="Datos disponibles">
      <p>
        Toda la información proviene de los <B>datos abiertos que publica Guatecompras</B>: concursos, renglones, oferentes, adjudicaciones y documentos.
        Es la misma información del portal oficial, organizada para que puedas buscarla y compararla.
      </p>
      {d?.demo && <p className="rounded-lg bg-amber-50 px-3 py-2 text-amber-900">Estás en modo demo: las cifras de abajo corresponden a datos de ejemplo.</p>}
      {c.isLoading ? <div className="h-24 animate-pulse rounded-xl bg-stone-100" /> : c.error || !d ? (
        <p className="text-red-700">No se pudo cargar la cobertura de datos.</p>
      ) : (
        <div className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-stone-200 bg-stone-100 md:grid-cols-4">
          {fact("Datos desde", date(d.first_published), "primer concurso publicado")}
          {fact("Última actualización", d.updated_at ? dateTime(d.updated_at) : "—", d.last_published ? `publicaciones hasta ${date(d.last_published)}` : undefined)}
          {fact("Concursos", num(d.tenders), `${num(d.awarded)} adjudicados`)}
          {fact("Vigentes", num(d.open), `${num(d.accepting)} recibiendo ofertas`)}
        </div>
      )}
      <Ul>
        <li><B>Actualización diaria.</B> Los datos se renuevan cada madrugada (alrededor de las 4:00 a. m., hora de Guatemala), poco después de que Guatecompras publica sus archivos del día. Lo publicado durante el día aparece al día siguiente.</li>
        <li><B>Adjudicaciones tardías.</B> Cada día se revisan de nuevo los dos últimos meses, así que una adjudicación que se publica semanas después de la convocatoria también se refleja.</li>
        <li><B>Vigente</B> es el estado que Guatecompras le da al concurso. <B>Recibiendo ofertas</B> significa vigente <i>y</i> con la fecha de cierre aún por venir (o sin fecha de cierre publicada).</li>
        <li><B>Montos en quetzales</B>, tal como aparecen publicados en Guatecompras.</li>
        <li>Cuando un dato no fue publicado (p. ej. fecha de cierre, departamento o número de oferentes) verás “—”, “No publicado” o la opción <B>Sin dato</B> en los filtros.</li>
        <li>Para <B>ofertar</B> o descargar las bases, usa el botón <B>Guatecompras</B> en el detalle del concurso: te lleva a su página oficial.</li>
      </Ul>
    </Sec>
  );
}

/* ── 3. Pantallas ───────────────────────────────────────────────────────── */

function Screens() {
  return (
    <>
      <Sec id="resumen" title="Resumen" to="/" toLabel="Abrir Resumen">
        <p>Tu página de inicio. Muestra de un vistazo:</p>
        <Ul>
          <li><B>Concursos vigentes</B> (y cuántos son nuevos esta semana), <B>En seguimiento</B> y <B>Adjudicado a tus NIT</B>.</li>
          <li><B>Recomendados para ti</B>: los primeros de la pantalla <i>Para ti</i>.</li>
          <li><B>Publicaciones por mes</B> de los últimos 12 meses. El mes en curso aparece más claro porque todavía no termina.</li>
          <li><B>Cierran en los próximos 3 días</B>: vigentes con cierre inminente.</li>
        </Ul>
        <p>Los filtros del panel izquierdo afectan todas las cifras y listas de esta pantalla. El buscador de arriba te lleva a <i>Buscar</i> con tu texto y tus filtros.</p>
      </Sec>

      <Sec id="buscar" title="Buscar concursos" to="/search" toLabel="Abrir Buscar">
        <p>Escribe lo que vendes con tus propias palabras o busca por palabra clave, entidad o número de NOG. Atajo: <kbd className="rounded border border-stone-200 px-1.5 text-[11px]">⌘K</kbd> o <kbd className="rounded border border-stone-200 px-1.5 text-[11px]">Ctrl+K</kbd> desde cualquier pantalla.</p>
        <div className="overflow-x-auto">
          <table className="min-w-[520px]">
            <thead><tr><th>Tipo de búsqueda</th><th>Cuándo usarlo</th><th>Ejemplo</th></tr></thead>
            <tbody>
              <tr><td className="font-medium">Inteligente <span className="text-stone-500">(recomendado)</span></td><td>Combina palabras exactas y significado. Sirve para casi todo.</td><td>“tóner para impresoras HP”</td></tr>
              <tr><td className="font-medium">Palabras exactas</td><td>Cuando buscas un término, marca, código o NOG concreto. Deben aparecer al menos dos tercios de las palabras.</td><td>“27654321”, “glucómetro”</td></tr>
              <tr><td className="font-medium">Por significado</td><td>Cuando los concursos usan otras palabras para lo mismo. Encuentra sinónimos y descripciones parecidas.</td><td>“limpieza de oficinas” → “servicio de conserjería”</td></tr>
            </tbody>
          </table>
        </div>
        <Ul>
          <li><B>Orden:</B> con texto, por relevancia. Sin texto, puedes ordenar por <i>más recientes</i> o <i>cierre más próximo</i>.</li>
          <li>Por defecto, Buscar muestra solo concursos <B>Vigentes</B>. Quita ese filtro en “Estado del concurso” para ver también adjudicados, desiertos, etc.</li>
          <li>Se muestran 20 resultados por página.</li>
          <li>Desde cada resultado puedes marcar 👍/👎, seguir el concurso o abrir su detalle.</li>
        </Ul>
        <Tip>¿Pocos resultados? Prueba “Por significado”, usa menos palabras o revisa si algún filtro está limitando la búsqueda.</Tip>
      </Sec>

      <Sec id="detalle" title="Detalle del concurso y precios de referencia">
        <p>Al abrir un concurso ves sus datos clave (entidad, publicación, cierre, número de oferentes), sus renglones con código UNSPSC y cantidad, los oferentes con sus montos, la adjudicación y los documentos publicados.</p>
        <p><B>¿A qué precio se ha adjudicado esto antes?</B> Para cada renglón buscamos adjudicaciones pasadas de productos parecidos y te mostramos su precio unitario:</p>
        <Ul>
          <li><B>Mediana:</B> el precio del medio; la mitad se adjudicó por debajo y la otra mitad por encima. Es la referencia principal.</li>
          <li><B>P25 – P75:</B> el rango donde quedó la mitad central de las adjudicaciones (la franja sombreada). Ofertar dentro de este rango es lo habitual.</li>
          <li><B>Mín. / Máx.:</B> los extremos. Si un valor queda fuera de escala verás una flecha ‹ o ›.</li>
          <li><B>Mediana por trimestre:</B> cómo ha cambiado el precio en el tiempo.</li>
          <li><B>Tabla de comparables:</B> cada adjudicación usada, con su proveedor, fecha, precio unitario y qué tan parecida es (%).</li>
          <li><B>Concursos adjudicados parecidos · monto total:</B> referencia de cuánto se pagó en total por concursos similares.</li>
        </Ul>
        <Tip>Los precios unitarios solo se calculan con concursos de <b>un solo renglón y una sola adjudicación</b>, para que el precio corresponda sin duda a ese producto. Por eso a veces verás “Sin datos” aunque existan concursos parecidos con varios renglones.</Tip>
        <p>Abajo encontrarás <B>Adjudicados similares</B>: concursos ya resueltos parecidos a este, útiles para ver quién gana y a qué monto.</p>
      </Sec>

      <Sec id="para-ti" title="Para ti (recomendaciones)" to="/recommendations" toLabel="Abrir Para ti">
        <p>Concursos <B>vigentes</B> parecidos a lo que tu empresa ya conoce. Tu perfil se arma con:</p>
        <Ul>
          <li>Los concursos que tus NIT <B>ganaron</B> (cuentan más) y los que <B>cotizaron</B> (cuentan la mitad).</li>
          <li>Los que marcaste con <B>👍 Me interesa</B> (cuentan como si los hubieras ganado).</li>
          <li>Lo reciente pesa más: la importancia de un concurso se reduce a la mitad cada 6 meses.</li>
          <li>Se usan hasta 40 concursos distintos; los casi idénticos se agrupan para dar variedad.</li>
        </Ul>
        <p><B>👎 No me interesa</B> quita ese concurso y baja los que se le parecen. Cada recomendación explica por qué aparece (p. ej. “Parecido a … que ganó”).</p>
        <p><B>% de afinidad:</B> qué tan parecido es al perfil, comparado con la mejor recomendación de la lista (que tiene 100%). Sirve para ordenar, no es una probabilidad de ganar.</p>
        <Tip>Sin NIT ni 👍 todavía no hay perfil. Agrega tus NIT en Ajustes o marca algunos concursos con 👍 y las recomendaciones aparecerán al instante.</Tip>
      </Sec>

      <Sec id="oportunidades" title="Oportunidades" to="/opportunities" toLabel="Abrir Oportunidades">
        <p>Te ayuda a descubrir <B>productos que podrías vender y aún no ofertas</B>.</p>
        <Ul>
          <li>Primero encontramos tus <B>proveedores semejantes</B>: hasta 25 empresas que participan en una mezcla de categorías parecida a la tuya (con al menos 3 participaciones). El % indica qué tanto se parecen a ti.</li>
          <li>Luego mostramos las <B>categorías</B> (clases UNSPSC) donde participan al menos dos de ellos y tú no.</li>
          <li>Cada tarjeta indica cuántos semejantes participan, cuántas veces, cuánto se les ha adjudicado, ejemplos de productos y quiénes son.</li>
          <li><B>Ver vigentes →</B> abre Buscar con los concursos abiertos de esa categoría.</li>
        </Ul>
        <p>Los filtros limitan qué concursos se toman en cuenta (p. ej. solo un departamento o un tipo de entidad). Requiere tener NIT configurados.</p>
      </Sec>

      <Sec id="seguimiento" title="Seguimiento, 👍 y 👎" to="/favorites" toLabel="Abrir Seguimiento">
        <p>Usa el <B>marcador</B> en cualquier concurso para seguirlo. En el detalle puedes cambiar su etapa y agregar una nota:</p>
        <div className="flex flex-wrap gap-1.5">
          {["Por cotizar", "Cotizado", "Ganado", "Perdido", "Descartado"].map((s) => <span key={s} className="badge">{s}</span>)}
        </div>
        <p>En <i>Seguimiento</i> los ves todos y puedes filtrarlos por etapa. Las etapas y notas son tu registro personal; no se envían a Guatecompras.</p>
        <p><B>👍 / 👎</B> mejoran tus recomendaciones y alertas. Vuelve a pulsar el mismo botón para quitar la marca.</p>
      </Sec>

      <Sec id="alertas" title="Alertas por correo y combinaciones guardadas" to="/alerts" toLabel="Abrir Alertas">
        <p>Una <B>combinación</B> es un conjunto de filtros (y, opcionalmente, un texto de búsqueda) que guardas con un nombre. Puedes crearla con <B>Guardar combinación</B> en el panel de filtros de Resumen, Buscar, Para ti u Oportunidades.</p>
        <div className="overflow-x-auto">
          <table className="min-w-[520px]">
            <thead><tr><th>Parámetro</th><th>Opciones</th><th>Qué hace</th></tr></thead>
            <tbody>
              <tr><td className="font-medium">Correo</td><td>Activado / desactivado</td><td>Sin correo, la combinación queda guardada solo para aplicarla rápido.</td></tr>
              <tr><td className="font-medium">Frecuencia</td><td>Diario · Semanal · Cada actualización</td><td>Cada cuánto recibes el correo. Los envíos salen después de la actualización de datos de la madrugada.</td></tr>
              <tr><td className="font-medium">Concursos por correo</td><td>De 1 a 10 (5 por defecto)</td><td>Cuántos concursos incluye cada correo como máximo.</td></tr>
            </tbody>
          </table>
        </div>
        <p><B>Qué concursos llegan:</B></p>
        <Ul>
          <li>Solo concursos que <B>cumplen la combinación</B> y siguen <B>recibiendo ofertas</B>.</li>
          <li>Si guardaste un texto, se ordenan por relevancia y afinidad contigo. Sin texto, por afinidad con tu perfil (o los más recientes si aún no tienes perfil).</li>
          <li><B>Sin repeticiones:</B> un concurso que ya te enviamos no se repite en 7 días, aunque aparezca en otra combinación.</li>
          <li>No se envían los concursos que ya sigues ni los que marcaste con 👎.</li>
          <li>Si no hay nada nuevo, no recibes correo.</li>
        </Ul>
        <p>En <i>Alertas</i> puedes cambiar frecuencia y cantidad, abrir la combinación en Buscar, <B>Ver próximo correo</B> (vista previa) o usar <B>Enviar ahora</B>. Cada correo trae un enlace para darte de baja de esa combinación.</p>
      </Sec>

      <Sec id="proveedores" title="Proveedores" to="/suppliers" toLabel="Abrir Proveedores">
        <p>Busca cualquier proveedor del Estado por nombre o NIT y consulta:</p>
        <Ul>
          <li>Concursos ganados, monto adjudicado, concursos cotizados y <B>tasa de éxito</B> (ganados ÷ cotizados).</li>
          <li>Sus <B>categorías principales</B> y las <B>entidades que más le adjudican</B>.</li>
          <li>Pestañas <B>Ganados</B>, <B>Cotizados</B> y <B>Vigentes parecidos</B> (concursos abiertos parecidos a lo que ese proveedor suele ganar).</li>
        </Ul>
        <Tip>Útil para estudiar a tu competencia o para ver qué concursos le podrían interesar a un proveedor parecido a ti.</Tip>
      </Sec>

      <Sec id="historial" title="Tu historial en Guatecompras" to="/settings" toLabel="Abrir Ajustes">
        <p>En <i>Ajustes</i>, debajo de tus NIT, ves un resumen de todos los concursos en los que tus NIT ofertaron o resultaron adjudicados:</p>
        <Ul>
          <li><B>Participados, adjudicados, no adjudicados y en curso</B> (vigentes o en evaluación).</li>
          <li><B>% de adjudicación</B> = adjudicados ÷ concursos con resultado. Los <B>desiertos o anulados</B> no cuentan.</li>
          <li>Participación por mes, desglose por NIT, entidades, categorías, modalidades y departamentos.</li>
          <li><B>Competidores que te ganaron</B>: quién se llevó los concursos donde ofertaste y no ganaste.</li>
          <li>Lista de concursos (NOG) adjudicados, no adjudicados y en curso, con tu oferta o el monto adjudicado.</li>
        </Ul>
        <p>Puedes registrar varios NIT (por ejemplo, de distintas razones sociales). Sin guiones también funciona y pueden terminar en K. Si un NIT no tiene ofertas ni adjudicaciones en los datos disponibles, verás “Sin registros en Guatecompras”.</p>
      </Sec>

      <Sec id="privacidad" title="Uso de la plataforma y privacidad">
        <p>Para mejorar la herramienta, los administradores de GC Intelligence ven métricas de uso de la plataforma. Registramos <B>qué pantallas visitas, cuánto tiempo estás activo, qué funciones usas y el texto de tus búsquedas</B>.</p>
        <Ul>
          <li>No registramos el contenido de tu inventario, tus notas ni tu contraseña.</li>
          <li>Los registros se conservan <B>90 días</B> y se eliminan automáticamente.</li>
          <li>Solo los administradores pueden consultarlos.</li>
        </Ul>
      </Sec>

      <Sec id="inventario" title="Inventario">
        <p className="flex items-center gap-2"><span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-900">En desarrollo</span>Esta función todavía está en desarrollo. Te avisaremos cuando esté disponible.</p>
      </Sec>
    </>
  );
}

/* ── 4. Referencia de filtros ───────────────────────────────────────────── */

function FiltersRef() {
  const rows: [string, string][] = [
    ["Disponibilidad", "“Solo con recepción de ofertas abierta” (vigentes con cierre por venir) o “Solo adjudicados”. Son excluyentes entre sí."],
    ["Fecha de publicación", "Rango Desde/Hasta, o atajos de los últimos 7 días, 30 días, 3 meses, 6 meses o 1 año (contados desde hoy)."],
    ["Categoría", "Bienes, Servicios, Obras o Consultoría."],
    ["Estado del concurso", "Vigente, Evaluación, Desierto, etc., tal como los publica Guatecompras."],
    ["Entidad / unidad compradora", "Escribe al menos 2 letras y elige una entidad, o pulsa Enter para buscar todas las que contienen ese texto (p. ej. “IGSS”)."],
    ["Departamento", "Departamento de la entidad compradora."],
    ["Tipo de entidad", "Clasificación de la entidad compradora según Guatecompras."],
    ["Modalidad de compra", "Compra directa, cotización, licitación, etc."],
    ["Proveedor adjudicado", "Concursos ganados por los proveedores que elijas (por nombre o NIT)."],
    ["UNSPSC", "Clase de producto. Se aplica al llegar desde Oportunidades y aparece como etiqueta en Buscar."],
  ];
  return (
    <Sec id="filtros" title="Referencia de filtros">
      <p>El panel de filtros está en Resumen, Buscar, Para ti y Oportunidades. Junto a cada opción ves cuántos concursos la tienen en total.</p>
      <div className="overflow-x-auto">
        <table className="min-w-[520px]">
          <thead><tr><th>Filtro</th><th>Qué hace</th></tr></thead>
          <tbody>{rows.map(([k, v]) => <tr key={k}><td className="whitespace-nowrap font-medium">{k}</td><td>{v}</td></tr>)}</tbody>
        </table>
      </div>
      <Ul>
        <li><B>Incluir / Excluir:</B> cada sección puede limitar los resultados a los valores elegidos (Incluir) o quitarlos (Excluir, se muestran tachados en rojo).</li>
        <li>Puedes combinar filtros de varias secciones: los resultados deben cumplirlos todos.</li>
        <li><B>Sin dato</B> agrupa los concursos que no publicaron ese campo.</li>
        <li>Los filtros <B>se recuerdan en cada pantalla</B> de este navegador. “Limpiar todo” los quita.</li>
        <li>En <i>Para ti</i> solo se muestran concursos vigentes, así que “Solo adjudicados” no está disponible allí.</li>
        <li><B>Guardar combinación</B> guarda los filtros (y el texto de búsqueda, si lo hay) para reutilizarlos o recibir alertas.</li>
      </Ul>
    </Sec>
  );
}

/* ── 5. Preguntas frecuentes ────────────────────────────────────────────── */

const FAQ: [string, ReactNode][] = [
  ["¿Por qué no veo recomendaciones?", <>Necesitas al menos un NIT con ofertas o adjudicaciones registradas, o haber marcado algún concurso con 👍. Revisa también que los filtros de <i>Para ti</i> no estén limitando demasiado. <Link to="/settings">Configurar NIT</Link>.</>],
  ["¿Por qué no aparece un concurso que vi hoy en Guatecompras?", "Los datos se actualizan una vez al día, de madrugada. Lo publicado hoy aparecerá mañana."],
  ["¿Cada cuánto se actualiza la información?", "Todos los días, alrededor de las 4:00 a. m. (hora de Guatemala). La fecha exacta de la última actualización está en la sección Datos disponibles."],
  ["¿Desde cuándo hay datos?", "Desde la fecha que aparece en “Datos desde” en la sección Datos disponibles de esta guía."],
  ["¿Qué diferencia hay entre “Vigente” y “Recibiendo ofertas”?", "Vigente es el estado oficial del concurso. Recibiendo ofertas además exige que la fecha de cierre no haya pasado. Un concurso puede seguir vigente unos días después del cierre mientras se evalúa."],
  ["¿Por qué un concurso no tiene fecha de cierre?", "Algunas modalidades o entidades no publican la fecha de cierre en los datos abiertos. En ese caso verás “Sin fecha de cierre”; revisa las bases en Guatecompras."],
  ["¿Por qué dice “Sin datos” el precio de referencia?", "Solo usamos adjudicaciones de un único renglón para calcular precios unitarios confiables. Si no hay suficientes de ese producto, no mostramos un precio. Revisa los “Concursos adjudicados parecidos” como referencia de monto total."],
  ["¿El % de afinidad es mi probabilidad de ganar?", "No. Indica qué tan parecido es un concurso a tu perfil comparado con el mejor de la lista. Sirve para priorizar qué revisar primero."],
  ["¿Por qué no me llegó un correo de alerta?", "Revisa que la combinación tenga el correo activado y su frecuencia. Si no hay concursos nuevos que cumplan la combinación (o ya te los enviamos en los últimos 7 días), no se envía correo. Usa “Ver próximo correo” en Alertas para comprobarlo, y revisa tu carpeta de spam."],
  ["¿Cómo dejo de recibir un correo?", "Desactiva el correo de la combinación en Alertas, elimínala o usa el enlace para darte de baja que viene en cada correo."],
  ["¿Puedo ofertar desde aquí?", "No. Usa el botón “Guatecompras” del concurso para ir a su página oficial, donde se presentan las ofertas y se descargan las bases."],
  ["¿Las etapas de seguimiento o las notas se envían a Guatecompras?", "No, son tu registro personal dentro de la herramienta."],
  ["¿Puedo agregar varios NIT?", "Sí, en Ajustes. Todos se combinan para tus recomendaciones, oportunidades e historial, y el historial muestra también el desglose por NIT."],
  ["¿Cómo cambio mi correo?", "En Ajustes → Correo electrónico. Te pediremos tu contraseña actual. Ese correo se usa para iniciar sesión y para recibir las alertas."],
  ["¿Cuándo estará disponible el inventario?", "La función de inventario está en desarrollo."],
];

function Faq() {
  const [q, setQ] = useState("");
  const norm = (s: string) => s.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();
  const items = useMemo(() => {
    const t = norm(q.trim());
    if (!t) return FAQ;
    return FAQ.filter(([k, v]) => norm(k).includes(t) || (typeof v === "string" && norm(v).includes(t)));
  }, [q]);
  return (
    <Sec id="faq" title="Preguntas frecuentes">
      <label className="flex min-h-10 items-center gap-2 rounded-lg border border-stone-200 px-3 focus-within:border-brand-500">
        <IconSearch size={15} className="text-stone-500" />
        <span className="sr-only">Buscar en preguntas frecuentes</span>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar una pregunta…" className="min-w-0 flex-1 bg-transparent text-[13px] outline-none" />
      </label>
      {items.length ? (
        <div className="divide-y divide-stone-100 rounded-xl border border-stone-200">
          {items.map(([k, v]) => (
            <details key={k} className="group px-4 py-3" open={!!q.trim()}>
              <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-sm font-medium text-zinc-900">
                {k}<span className="text-stone-400 transition-transform group-open:rotate-45">+</span>
              </summary>
              <div className="pt-2">{v}</div>
            </details>
          ))}
        </div>
      ) : <p>No encontramos esa pregunta. Revisa las secciones de arriba.</p>}
    </Sec>
  );
}
