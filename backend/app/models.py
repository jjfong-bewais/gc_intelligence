"""Tablas (SQLAlchemy Core). Un solo esquema para SQLite (demo) y Postgres (nube)."""
from __future__ import annotations

import sqlalchemy as sa

from .config import settings
from .db import Vec, utcnow

metadata = sa.MetaData()
DIM = settings.embedding_dim


def _vec() -> sa.Column:
    return sa.Column("embedding", Vec(DIM, settings.pgvector_type))


def _ts(name: str, **kw) -> sa.Column:
    return sa.Column(name, sa.DateTime, **kw)


# ---------------------------------------------------------------- aplicación
organization = sa.Table(
    "organization", metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("name", sa.String(200), nullable=False),
    _ts("created_at", default=utcnow),
)

org_supplier = sa.Table(  # NIT propios de la organización
    "org_supplier", metadata,
    sa.Column("org_id", sa.Integer, primary_key=True),
    sa.Column("supplier_id", sa.String(40), primary_key=True),  # GT-NIT-123456
    sa.Column("label", sa.String(200), nullable=False, default=""),  # nombre de identificación
)

app_user = sa.Table(
    "app_user", metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("org_id", sa.Integer, nullable=False, index=True),
    sa.Column("email", sa.String(200), nullable=False, unique=True),
    sa.Column("name", sa.String(200), nullable=False, default=""),
    sa.Column("password_hash", sa.String(300), nullable=False),
    sa.Column("role", sa.String(20), nullable=False, default="member"),  # member | admin (ver permissions.py)
    sa.Column("active", sa.Boolean, nullable=False, default=True),  # false: no puede entrar ni recibe correos
    sa.Column("must_change_password", sa.Boolean, nullable=False, default=False),  # clave temporal: cambiar al entrar
    sa.Column("perm_overrides", sa.JSON),  # {"grant": [...], "deny": [...]} sobre los permisos del rol
    _ts("created_at", default=utcnow),
)

favorite = sa.Table(
    "favorite", metadata,
    sa.Column("user_id", sa.Integer, primary_key=True),
    sa.Column("ocid", sa.String(40), primary_key=True),
    sa.Column("status", sa.String(20), nullable=False, default="por_cotizar"),
    sa.Column("note", sa.Text, nullable=False, default=""),
    sa.Column("my_price", sa.Float),  # precio que el usuario piensa ofertar (opcional)
    _ts("created_at", default=utcnow),
)

feedback = sa.Table(
    "feedback", metadata,
    sa.Column("user_id", sa.Integer, primary_key=True),
    sa.Column("ocid", sa.String(40), primary_key=True),
    sa.Column("signal", sa.Integer, nullable=False),  # +1 / -1
    sa.Column("reason", sa.String(40), nullable=False, default=""),
    sa.Column("context", sa.String(40), nullable=False, default=""),
    _ts("created_at", default=utcnow),
)

saved_search = sa.Table(
    "saved_search", metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("user_id", sa.Integer, nullable=False, index=True),
    sa.Column("name", sa.String(200), nullable=False),
    sa.Column("q", sa.Text, nullable=False, default=""),
    sa.Column("mode", sa.String(12), nullable=False, default="hybrid"),
    sa.Column("filters", sa.JSON, nullable=False, default=dict),
    sa.Column("frequency", sa.String(12), nullable=False, default="daily"),  # immediate|daily|weekly
    sa.Column("active", sa.Boolean, nullable=False, default=True),  # envía correos
    sa.Column("max_items", sa.Integer, nullable=False, default=5),  # concursos por correo (1-10)
    _ts("last_run_at"),
    _ts("created_at", default=utcnow),
)

alert_delivery = sa.Table(
    "alert_delivery", metadata,
    sa.Column("saved_search_id", sa.Integer, primary_key=True),
    sa.Column("ocid", sa.String(40), primary_key=True),
    _ts("sent_at", default=utcnow),
)

alert_sent = sa.Table(  # concursos enviados por correo a cada usuario (evita repetir en 7 días)
    "alert_sent", metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("user_id", sa.Integer, nullable=False),
    sa.Column("ocid", sa.String(40), nullable=False),
    sa.Column("saved_search_id", sa.Integer),
    _ts("sent_at", default=utcnow),
    sa.Index("ix_alert_sent_user", "user_id", "sent_at"),
)

inventory_item = sa.Table(
    "inventory_item", metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("org_id", sa.Integer, nullable=False, index=True),
    sa.Column("sku", sa.String(80), nullable=False, default=""),
    sa.Column("description", sa.Text, nullable=False),
    sa.Column("unit", sa.String(40), nullable=False, default=""),
    sa.Column("unspsc", sa.String(12), nullable=False, default=""),
    sa.Column("search_text", sa.Text, nullable=False, default=""),
    sa.Column("emb_sig", sa.String(80)),
    _vec(),
)

inventory_alert = sa.Table(
    "inventory_alert", metadata,
    sa.Column("org_id", sa.Integer, primary_key=True),
    sa.Column("ocid", sa.String(40), primary_key=True),
    _ts("sent_at", default=utcnow),
)

# ---------------------------------------------------------------- datos OCDS
party = sa.Table(
    "party", metadata,
    sa.Column("id", sa.String(60), primary_key=True),  # GT-NIT-… | GT-CISP-… | GT-GCUC-…
    sa.Column("kind", sa.String(12), nullable=False),  # supplier | entity | unit
    sa.Column("name", sa.Text, nullable=False),
    sa.Column("name_norm", sa.Text, nullable=False, default=""),
    sa.Column("entity_type", sa.String(120)),
    sa.Column("level", sa.String(120)),
    sa.Column("region", sa.String(120)),
    sa.Column("parent_id", sa.String(60)),
    sa.Index("ix_party_kind", "kind"),
)

tender = sa.Table(
    "tender", metadata,
    sa.Column("ocid", sa.String(40), primary_key=True),
    sa.Column("nog", sa.BigInteger, nullable=False, unique=True),
    sa.Column("title", sa.Text, nullable=False, default=""),
    sa.Column("status", sa.String(20)),  # active | complete | unsuccessful | cancelled…
    sa.Column("status_details", sa.String(60)),  # Vigente | Evaluación | Adjudicado | Desierto…
    sa.Column("method", sa.String(40)),
    sa.Column("method_details", sa.String(200)),
    sa.Column("category", sa.String(40)),  # goods | services | works
    _ts("published_at"),
    _ts("deadline_at"),
    sa.Column("buyer_id", sa.String(60)),
    sa.Column("buyer_name", sa.Text, nullable=False, default=""),
    sa.Column("buyer_norm", sa.Text, nullable=False, default=""),
    sa.Column("unit_name", sa.Text, nullable=False, default=""),
    sa.Column("buyer_region", sa.String(120)),  # departamento de la entidad compradora
    sa.Column("buyer_type", sa.String(120)),  # tipo de entidad (Gobierno Central, Municipalidades…)
    sa.Column("n_tenderers", sa.Integer),
    sa.Column("n_items", sa.Integer, nullable=False, default=0),
    sa.Column("unspsc_main", sa.String(8)),
    sa.Column("release_date", sa.String(40)),
    sa.Column("search_text", sa.Text, nullable=False, default=""),
    sa.Column("embed_text", sa.Text, nullable=False, default=""),
    sa.Column("text_hash", sa.String(40)),
    sa.Column("emb_hash", sa.String(40)),
    sa.Column("emb_sig", sa.String(80)),
    _vec(),
    _ts("first_seen_at", default=utcnow),
    _ts("updated_at", default=utcnow),
    sa.Index("ix_tender_status_pub", "status_details", "published_at"),
    sa.Index("ix_tender_published", "published_at"),
    sa.Index("ix_tender_first_seen", "first_seen_at"),
    sa.Index("ix_tender_region", "buyer_region"),
    sa.Index("ix_tender_buyer_type", "buyer_type"),
    sa.Index("ix_tender_category", "category"),
)

tender_item = sa.Table(
    "tender_item", metadata,
    sa.Column("id", sa.String(80), primary_key=True),  # ocid:item_id
    sa.Column("ocid", sa.String(40), nullable=False, index=True),
    sa.Column("idx", sa.Integer, nullable=False, default=0),
    sa.Column("description", sa.Text, nullable=False, default=""),
    sa.Column("unspsc", sa.String(12), nullable=False, default=""),
    sa.Column("quantity", sa.Float),
    sa.Column("unit", sa.String(80)),
    sa.Column("search_text", sa.Text, nullable=False, default=""),
    sa.Column("embed_text", sa.Text, nullable=False, default=""),
    sa.Column("text_hash", sa.String(40)),
    sa.Column("emb_hash", sa.String(40)),
    sa.Column("emb_sig", sa.String(80)),
    _vec(),
    sa.Index("ix_item_unspsc", "unspsc"),
)

bid = sa.Table(
    "bid", metadata,
    sa.Column("id", sa.String(100), primary_key=True),
    sa.Column("ocid", sa.String(40), nullable=False, index=True),
    sa.Column("supplier_id", sa.String(60), index=True),
    sa.Column("supplier_name", sa.Text, nullable=False, default=""),
    sa.Column("amount", sa.Float),
    sa.Column("currency", sa.String(8)),
    sa.Column("status", sa.String(30)),
    _ts("date"),
)

award = sa.Table(
    "award", metadata,
    sa.Column("id", sa.String(140), primary_key=True),
    sa.Column("ocid", sa.String(40), nullable=False, index=True),
    sa.Column("award_ref", sa.String(60)),
    sa.Column("supplier_id", sa.String(60), index=True),
    sa.Column("supplier_name", sa.Text, nullable=False, default=""),
    sa.Column("amount", sa.Float),
    sa.Column("currency", sa.String(8)),
    sa.Column("status", sa.String(30)),
    sa.Column("status_details", sa.String(60)),
    _ts("date"),
)

contract = sa.Table(
    "contract", metadata,
    sa.Column("id", sa.String(140), primary_key=True),
    sa.Column("ocid", sa.String(40), nullable=False, index=True),
    sa.Column("award_ref", sa.String(60)),
    sa.Column("number", sa.String(80)),
    _ts("signed_at"),
    sa.Column("amount", sa.Float),
    sa.Column("currency", sa.String(8)),
)

document = sa.Table(
    "document", metadata,
    sa.Column("id", sa.String(140), primary_key=True),
    sa.Column("ocid", sa.String(40), nullable=False, index=True),
    sa.Column("doc_type", sa.String(80)),
    sa.Column("title", sa.Text),
    sa.Column("url", sa.Text),
    _ts("published_at"),
)

price_obs = sa.Table(  # precio unitario derivado (solo adjudicaciones de un renglón)
    "price_obs", metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("ocid", sa.String(40), nullable=False, index=True),
    sa.Column("item_id", sa.String(80), nullable=False, index=True),
    sa.Column("unspsc", sa.String(12), nullable=False, default=""),
    sa.Column("quantity", sa.Float),
    sa.Column("unit", sa.String(80)),
    sa.Column("unit_price", sa.Float, nullable=False),
    sa.Column("amount", sa.Float),
    sa.Column("currency", sa.String(8)),
    sa.Column("supplier_id", sa.String(60)),
    sa.Column("supplier_name", sa.Text, nullable=False, default=""),
    _ts("awarded_at"),
    sa.Index("ix_price_unspsc_date", "unspsc", "awarded_at"),
)

ingest_file = sa.Table(
    "ingest_file", metadata,
    sa.Column("key", sa.String(20), primary_key=True),  # 2026-10
    sa.Column("file_timestamp", sa.String(60)),
    sa.Column("n_records", sa.Integer, default=0),
    sa.Column("n_changed", sa.Integer, default=0),
    _ts("processed_at", default=utcnow),
)


# ---------------------------------------------------------------- métricas de uso
# Sesión = actividad de un usuario sin pausas de más de 30 min. Las columnas day/hour/dow ya están en hora
# local (settings.metrics_tz_offset) para agrupar igual en SQLite y Postgres.
usage_session = sa.Table(
    "usage_session", metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("user_id", sa.Integer, nullable=False),
    _ts("started_at", nullable=False),
    _ts("last_seen_at", nullable=False),
    sa.Column("day", sa.String(10), nullable=False),  # AAAA-MM-DD local del inicio
    sa.Column("dow", sa.Integer, nullable=False),  # 0 = lunes
    sa.Column("hour", sa.Integer, nullable=False),
    sa.Column("active_seconds", sa.Integer, nullable=False, default=0),  # tiempo con la pestaña visible y activa
    sa.Column("n_events", sa.Integer, nullable=False, default=0),
    sa.Column("n_pages", sa.Integer, nullable=False, default=0),
    sa.Column("entry_source", sa.String(20), nullable=False, default="direct"),  # direct | alert
    sa.Column("device", sa.String(12), nullable=False, default=""),  # desktop | mobile
    sa.Index("ix_usage_session_user", "user_id", "started_at"),
    sa.Index("ix_usage_session_day", "day"),
)

usage_event = sa.Table(
    "usage_event", metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    _ts("ts", nullable=False),
    sa.Column("day", sa.String(10), nullable=False),
    sa.Column("hour", sa.Integer, nullable=False),
    sa.Column("dow", sa.Integer, nullable=False),
    sa.Column("user_id", sa.Integer),
    sa.Column("session_id", sa.Integer),  # nulo en eventos sin sesión (clics desde el correo)
    sa.Column("kind", sa.String(12), nullable=False),  # api | page | action
    sa.Column("feature", sa.String(40), nullable=False, default=""),
    sa.Column("action", sa.String(40), nullable=False, default=""),
    sa.Column("route", sa.String(120), nullable=False, default=""),
    sa.Column("status", sa.Integer),
    sa.Column("duration_ms", sa.Integer),
    sa.Column("props", sa.JSON),
    sa.Index("ix_usage_event_user", "user_id", "ts"),
    sa.Index("ix_usage_event_feature", "feature", "ts"),
    sa.Index("ix_usage_event_day", "day"),
    sa.Index("ix_usage_event_session", "session_id"),
)
