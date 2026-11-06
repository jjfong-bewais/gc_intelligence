export const money = (v: number | null | undefined) =>
  v == null ? "—" : new Intl.NumberFormat("es-GT", { style: "currency", currency: "GTQ", maximumFractionDigits: 0 }).format(v);
export const money2 = (v: number | null | undefined) =>
  v == null ? "—" : new Intl.NumberFormat("es-GT", { style: "currency", currency: "GTQ" }).format(v);
export const num = (v: number | null | undefined) => (v == null ? "—" : new Intl.NumberFormat("es-GT").format(v));
export const date = (s: string | null | undefined) =>
  s ? new Intl.DateTimeFormat("es-GT", { dateStyle: "medium", timeZone: "America/Guatemala" }).format(new Date(s)) : "—";
export const dateTime = (s: string | null | undefined) =>
  s ? new Intl.DateTimeFormat("es-GT", { dateStyle: "medium", timeStyle: "short", timeZone: "America/Guatemala" }).format(new Date(s)) : "—";
export const daysLeft = (s: string | null | undefined) => {
  if (!s) return null;
  return Math.ceil((new Date(s).getTime() - Date.now()) / 86_400_000);
};
/** "Cierra en 3 días", "Cierra hoy", "Cerró", "Sin fecha de cierre". */
export const closeLabel = (s: string | null | undefined) => {
  const d = daysLeft(s);
  if (d == null) return "Sin fecha de cierre";
  if (d < 0) return `Cerró ${date(s)}`;
  if (d === 0) return "Cierra hoy";
  if (d === 1) return "Cierra mañana";
  return d <= 14 ? `Cierra en ${d} días` : `Cierra ${date(s)}`;
};

/* ── Limpieza de textos que vienen de Guatecompras ─────────────────────────── */

const STOP = new Set(["de", "del", "la", "las", "los", "el", "y", "e", "o", "u", "en", "para", "por", "con", "a", "al", "sin", "su", "sus"]);
const KEEP_UPPER = new Set([
  "IGSS", "MSPAS", "INACIF", "EPQ", "NOG", "NIT", "UNSPSC", "ONG", "IVA", "PNC", "MP", "OJ", "USAC", "SAT", "RENAP", "INDE", "EEGSA",
  "CIV", "MAGA", "MINEDUC", "MIDES", "SOSEP", "INAB", "CONAP", "DIDEDUC", "COCODE", "CAMIP", "UPS", "LED", "PVC", "GPS", "TI", "CCTV", "HVAC",
  "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "S.A.", "LCE",
]);

/** Quita HTML (p. ej. "<br />") y espacios repetidos. */
export const stripHtml = (s: string | null | undefined) =>
  (s ?? "").replace(/<[^>]*>/g, " ").replace(/&nbsp;/g, " ").replace(/&amp;/g, "&").replace(/\s+/g, " ").trim();

const isShouting = (s: string) => {
  const letters = s.replace(/[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ]/g, "");
  return letters.length > 3 && letters.replace(/[^a-záéíóúüñ]/g, "").length / letters.length < 0.15;
};

const keepUpper = (word: string) => {
  const core = word.replace(/^[-("«“]+|[-)"»”.,;:]+$/g, "");
  if (!core) return false;
  if (KEEP_UPPER.has(core) || KEEP_UPPER.has(word)) return true;
  if (/\d/.test(core)) return true; // códigos: JSM-6610LV, 2026-ROO-CD-4304
  if (/^[-(].*[-)]$/.test(word)) return true; // -IGSS-, (MSPAS)
  if (core.length >= 2 && !/[AEIOUÁÉÍÓÚ]/.test(core)) return true; // siglas sin vocales
  return false;
};

/** Títulos de concursos: "MANTENIMIENTO DE BOMBA. SOLICITUD" → "Mantenimiento de bomba. Solicitud". */
export function sentenceCase(raw: string | null | undefined) {
  const s = stripHtml(raw);
  if (!isShouting(s)) return s;
  let startOfSentence = true;
  return s
    .split(" ")
    .map((w) => {
      let out = keepUpper(w) ? w : w.toLowerCase();
      if (startOfSentence && !keepUpper(w)) out = out.replace(/\p{L}/u, (c) => c.toUpperCase());
      startOfSentence = /[.:!?]$/.test(w);
      return out;
    })
    .join(" ");
}

/** Nombres de entidades y empresas: "MINISTERIO DE SALUD PÚBLICA" → "Ministerio de Salud Pública". */
export function nameCase(raw: string | null | undefined) {
  const s = stripHtml(raw).replace(/,?\s*SOCIEDAD AN[OÓ]NIMA\b/i, ", S.A.");
  if (!isShouting(s)) return s;
  return s
    .split(" ")
    .map((w, i) => {
      if (keepUpper(w)) return w;
      const lw = w.toLowerCase();
      if (i > 0 && STOP.has(lw)) return lw;
      return lw.replace(/\p{L}/u, (c) => c.toUpperCase());
    })
    .join(" ");
}

/** Personas en formato OCDS "APELLIDO1,APELLIDO2,,NOMBRE1,NOMBRE2" → "Nombre1 Nombre2 Apellido1 Apellido2". */
export function supplierName(raw: string | null | undefined) {
  const s = stripHtml(raw);
  const parts = s.split(",");
  if (parts.length >= 4 && parts.every((p) => !/\s{2,}/.test(p)) && !/S\.?A\.?|SOCIEDAD|LIMITADA/i.test(s)) {
    const [ap1, ap2, ap3, ...names] = parts;
    return nameCase([...names, ap1, ap2, ap3].filter(Boolean).join(" "));
  }
  return nameCase(s);
}

/** Saludo según la hora de Guatemala. */
export function greeting() {
  const h = Number(new Intl.DateTimeFormat("es-GT", { hour: "numeric", hour12: false, timeZone: "America/Guatemala" }).format(new Date()));
  return h < 12 ? "Buenos días" : h < 19 ? "Buenas tardes" : "Buenas noches";
}
export const todayLong = () => {
  const s = new Intl.DateTimeFormat("es-GT", { weekday: "long", day: "numeric", month: "long", timeZone: "America/Guatemala" }).format(new Date());
  return s.charAt(0).toUpperCase() + s.slice(1);
};
