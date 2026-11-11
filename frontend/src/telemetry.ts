import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";
import { BASE } from "./api";

/**
 * Telemetría de uso para el panel de administración: pantallas vistas y tiempo activo.
 * - `page_view` sale casi de inmediato (el servidor mide la permanencia entre pantallas).
 * - El tiempo activo cuenta solo con la pestaña visible y con actividad en el último minuto; se envía cada 30 s
 *   y al ocultar o cerrar la pestaña. `fetch` con `keepalive` (no `sendBeacon`, que haría preflight cruzando de dominio).
 */
type Ev = { type: "page_view" | "heartbeat"; path?: string; src?: string; seconds?: number };

const HEARTBEAT_MS = 30_000;
const IDLE_MS = 60_000;

function send(events: Ev[]) {
  if (!events.length) return;
  try {
    fetch(`${BASE}/api/v1/telemetry`, {
      method: "POST", credentials: "include", keepalive: true,
      headers: { "Content-Type": "application/json" }, body: JSON.stringify({ events: events.slice(0, 50) }),
    }).catch(() => { /* medir nunca debe molestar al usuario */ });
  } catch { /* idem */ }
}

export function useTelemetry(enabled: boolean) {
  const loc = useLocation();
  const queue = useRef<Ev[]>([]);
  const active = useRef(0);
  const lastInput = useRef(Date.now());
  const first = useRef(true);
  const timer = useRef<number | undefined>(undefined);

  const flush = useRef(() => {
    window.clearTimeout(timer.current);
    timer.current = undefined;
    const out = queue.current.splice(0);
    if (active.current > 0) { out.push({ type: "heartbeat", seconds: active.current }); active.current = 0; }
    send(out);
  });

  // Una pantalla vista por cada cambio de ruta (solo la primera lleva ?src=alert si viene de un correo).
  useEffect(() => {
    if (!enabled) return;
    const src = first.current ? new URLSearchParams(window.location.search).get("src") ?? "" : "";
    first.current = false;
    queue.current.push({ type: "page_view", path: loc.pathname, src });
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(flush.current, 800);
  }, [enabled, loc.pathname]);

  // Tiempo activo + latido.
  useEffect(() => {
    if (!enabled) return;
    const touch = () => { lastInput.current = Date.now(); };
    const events = ["mousemove", "keydown", "scroll", "click", "touchstart"] as const;
    events.forEach((e) => window.addEventListener(e, touch, { passive: true }));
    const tick = window.setInterval(() => {
      if (document.visibilityState === "visible" && Date.now() - lastInput.current < IDLE_MS) active.current += 1;
    }, 1000);
    const beat = window.setInterval(() => flush.current(), HEARTBEAT_MS);
    const onHide = () => { if (document.visibilityState === "hidden") flush.current(); };
    document.addEventListener("visibilitychange", onHide);
    window.addEventListener("pagehide", flush.current);
    return () => {
      events.forEach((e) => window.removeEventListener(e, touch));
      window.clearInterval(tick); window.clearInterval(beat);
      document.removeEventListener("visibilitychange", onHide);
      window.removeEventListener("pagehide", flush.current);
      flush.current();
    };
  }, [enabled]);
}
