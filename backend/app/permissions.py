"""Roles y permisos: la única fuente de verdad sobre «quién puede qué».

Los endpoints no preguntan «¿es admin?», sino «¿tiene el permiso X?» con `require(Perm.X)`.
Un rol es solo un paquete de permisos (`ROLE_PERMS`); además cada usuario puede tener excepciones
(`app_user.perm_overrides`) para dar o quitar funciones sueltas sin crear roles nuevos.

Para agregar una función controlable: 1) un valor en `Perm`, 2) incluirlo en los roles de
`ROLE_PERMS` que correspondan (los de producto entran solos vía `FEATURE_PERMS`),
3) `Depends(require(Perm.NUEVO))` en sus endpoints y 4) `perm` en su entrada del menú del
frontend (`App.tsx`).
"""
from __future__ import annotations

from enum import Enum

from fastapi import Depends, HTTPException

from .security import current_user


class Role(str, Enum):
    MEMBER = "member"  # usuario normal: toda la plataforma
    ADMIN = "admin"    # administrador: además gestiona usuarios y las operaciones globales


class Perm(str, Enum):
    # Funciones de producto (se pueden dar o quitar por usuario)
    SEARCH = "search"
    RECOMMENDATIONS = "recommendations"
    OPPORTUNITIES = "opportunities"
    FAVORITES = "favorites"
    INVENTORY = "inventory"
    ALERTS = "alerts"
    SUPPLIERS = "suppliers"
    # Administración (solo por rol, nunca por excepción)
    ADMIN = "admin"


FEATURE_PERMS: frozenset[Perm] = frozenset(p for p in Perm if p is not Perm.ADMIN)

ROLE_PERMS: dict[Role, frozenset[Perm]] = {
    Role.MEMBER: FEATURE_PERMS,
    Role.ADMIN: frozenset(Perm),
}

ROLES: tuple[str, ...] = tuple(r.value for r in Role)


def normalize_overrides(raw: dict | None) -> dict[str, list[str]]:
    """Valida y normaliza {"grant": [...], "deny": [...]}. Solo admite permisos de producto."""
    raw = raw or {}
    allowed = {p.value for p in FEATURE_PERMS}
    out: dict[str, list[str]] = {}
    for key in ("grant", "deny"):
        vals = list(raw.get(key) or [])
        bad = [v for v in vals if v not in allowed]
        if bad:
            raise ValueError(f"Permiso desconocido: {bad[0]}")
        out[key] = sorted(set(vals))
    return out


def effective_perms(user: dict) -> set[Perm]:
    """Permisos del rol, más las excepciones propias del usuario."""
    try:
        perms = set(ROLE_PERMS[Role(user["role"])])
    except ValueError:  # rol desconocido en la base: sin permisos
        return set()
    ov = user.get("perm_overrides") or {}
    known = Perm._value2member_map_
    perms |= {Perm(v) for v in ov.get("grant", []) if v in known and Perm(v) in FEATURE_PERMS}
    perms -= {Perm(v) for v in ov.get("deny", []) if v in known}
    return perms


def permission_names(user: dict) -> list[str]:
    return sorted(p.value for p in effective_perms(user))


def require(*perms: Perm):
    """Dependencia de FastAPI: exige sesión válida y todos los permisos; devuelve el usuario."""
    needed = set(perms)

    def dep(user: dict = Depends(current_user)) -> dict:
        if not needed <= effective_perms(user):
            raise HTTPException(status_code=403, detail="No tienes acceso a esta función")
        return user

    return dep
