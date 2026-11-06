# Despliegue en la nube (MVP)

Orden recomendado. Todo el código viene del repo en GitHub.

## 1. Base de datos — Neon
1. Crea un proyecto Postgres 16 en neon.tech y copia la cadena **pooled** (`...-pooler...?sslmode=require`).
2. pgvector viene disponible; la app ejecuta `CREATE EXTENSION vector` al iniciar (`python -m app.cli init-db` también).

## 2. API — Fly.io
```bash
fly launch --no-deploy --copy-config      # cambia `app` en fly.toml por un nombre único
fly secrets set DATABASE_URL='postgresql://…' SECRET_KEY="$(python3 -c 'import secrets;print(secrets.token_urlsafe(48))')" \
  OPENAI_API_KEY=sk-… RESEND_API_KEY=re_…
fly secrets set MAIL_FROM='GC Intelligence <alertas@tudominio.com>' APP_URL=https://app.tudominio.com \
  API_URL=https://api.tudominio.com CORS_ORIGINS=https://app.tudominio.com COOKIE_DOMAIN=.tudominio.com
fly deploy
fly certs add api.tudominio.com
```
Web y API deben estar en subdominios del **mismo sitio** (`app.` y `api.`) para que la cookie de sesión httpOnly funcione.

Primer usuario:
```bash
fly ssh console -C "python -m app.cli create-user tu@correo.com 'contraseña-larga' --org 'Tu Empresa' --nit 1234567"
```

## 3. Web — Cloudflare Pages
Proyecto conectado al repo: root `frontend`, build `npm run build`, salida `dist`, variable `VITE_API_URL=https://api.tudominio.com`. Dominio `app.tudominio.com`. `public/_redirects` ya incluye el fallback SPA.

## 4. Ingesta y alertas — GitHub Actions
En *Settings → Secrets*: `DATABASE_URL`, `OPENAI_API_KEY`, `RESEND_API_KEY`, `SECRET_KEY` (el mismo que la API: firma los enlaces de los correos), `FLY_API_TOKEN`. En *Variables*: `MAIL_FROM`, `APP_URL`, `API_URL`.
Primera carga: Actions → "Ingesta y alertas" → Run workflow con `months_back = 0` (todo 2026; descarga ~230 MB por mes). Luego corre solo cada día.
> No verificado: que los servidores de GitHub puedan descargar de `ocds.guatecompras.gt`. Si los bloquea, ejecuta `python -m app.cli ingest` desde otra máquina (misma `DATABASE_URL`) o en un cron propio.

## 5. Correo — Resend
Verifica tu dominio y usa un remitente de ese dominio en `MAIL_FROM`.

## Notas
- Neon duerme tras inactividad: la primera petición puede tardar ~1 s (la app usa `pool_pre_ping`).
- `PGVECTOR_TYPE=halfvec` (mitad de espacio) requiere pgvector ≥ 0.7 y **no está probado**; el predeterminado `vector` sí.
- Cambiar de proveedor/dimensión de embeddings requiere recalcularlos (`EMBEDDING_DIM`; vaciar columnas y `python -m app.cli embed`).
