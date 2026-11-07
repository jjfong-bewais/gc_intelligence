"""Configuración por variables de entorno (o archivo .env en la raíz del repo)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(REPO_ROOT / ".env"), ".env"), extra="ignore"
    )

    # demo | prod. En demo se muestra un aviso de datos sintéticos en la interfaz.
    gc_mode: str = "prod"

    # SQLite para la demo local; en la nube, la cadena de conexión de Neon.
    database_url: str = f"sqlite:///{REPO_ROOT}/demo/demo.db"

    # Sesiones y cookies
    secret_key: str = "dev-insecure-change-me"
    session_days: int = 14
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    cookie_domain: str | None = None
    cors_origins: str = ""  # lista separada por comas
    allow_signup: bool = False

    # Embeddings: "local" (demo, sin red) u "openai"
    embeddings_provider: str = "local"
    embedding_dim: int = 512
    openai_api_key: str = ""
    openai_embedding_model: str = "text-embedding-3-small"
    # "vector" (float32, probado) o "halfvec" (mitad de espacio, requiere pgvector >= 0.7)
    pgvector_type: str = "vector"

    # Umbrales de coincidencia con inventario (depende del modelo de embeddings)
    match_threshold: float = 0.5

    # Correo: console | file | resend
    mail_provider: str = "console"
    resend_api_key: str = ""
    mail_from: str = "GC Intelligence <alertas@example.com>"
    app_url: str = "http://localhost:8000"
    api_url: str = ""  # URL pública de la API (enlaces del correo). Por defecto app_url.
    outbox_dir: str = str(REPO_ROOT / "demo" / "outbox")

    # Datos
    data_year: int = 2026
    data_from: str = "2024-01"  # primer mes a cargar (AAAA-MM)
    guatecompras_base: str = "https://ocds.guatecompras.gt"

    # Frontend compilado servido por la API (útil en la demo local)
    frontend_dist: str = str(REPO_ROOT / "frontend" / "dist")

    @property
    def sqlalchemy_url(self) -> str:
        url = self.database_url.strip()
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        if url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://"):]
        return url

    @property
    def is_sqlite(self) -> bool:
        return self.sqlalchemy_url.startswith("sqlite")

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def public_api_url(self) -> str:
        return (self.api_url or self.app_url).rstrip("/")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
