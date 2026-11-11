import { useQuery } from "@tanstack/react-query";
import { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { api } from "./api";

/** Permisos que entiende la plataforma (espejo de backend/app/permissions.py). */
export type Perm = "search" | "recommendations" | "opportunities" | "favorites" | "inventory" | "alerts" | "suppliers" | "admin";

export type Me = {
  id: number; email: string; name: string; role: "member" | "admin"; org_name: string; supplier_ids: string[];
  demo: boolean; permissions: Perm[]; must_change_password: boolean;
};

export const useMe = () => useQuery<Me>({ queryKey: ["me"], queryFn: () => api("/auth/me"), retry: false });

/** ¿El usuario actual tiene este permiso? Sin permiso indicado, siempre sí. Es solo para mostrar u
 * ocultar opciones: la seguridad real vive en el backend. */
export function useCan(perm?: Perm): boolean {
  const { data } = useMe();
  return !perm || !!data?.permissions.includes(perm);
}

/** Protege una ruta: sin el permiso, vuelve al inicio. */
export function RequirePerm({ perm, children }: { perm?: Perm; children: ReactNode }) {
  return useCan(perm) ? <>{children}</> : <Navigate to="/" replace />;
}
