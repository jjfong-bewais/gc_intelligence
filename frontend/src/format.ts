export const money = (v: number | null | undefined) =>
  v == null ? "—" : new Intl.NumberFormat("es-GT", { style: "currency", currency: "GTQ", maximumFractionDigits: 0 }).format(v);
export const money2 = (v: number | null | undefined) =>
  v == null ? "—" : new Intl.NumberFormat("es-GT", { style: "currency", currency: "GTQ" }).format(v);
export const date = (s: string | null | undefined) =>
  s ? new Intl.DateTimeFormat("es-GT", { dateStyle: "medium", timeZone: "America/Guatemala" }).format(new Date(s)) : "—";
export const dateTime = (s: string | null | undefined) =>
  s ? new Intl.DateTimeFormat("es-GT", { dateStyle: "medium", timeStyle: "short", timeZone: "America/Guatemala" }).format(new Date(s)) : "—";
export const daysLeft = (s: string | null | undefined) => {
  if (!s) return null;
  return Math.ceil((new Date(s).getTime() - Date.now()) / 86_400_000);
};
