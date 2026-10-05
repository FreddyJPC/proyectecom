# 01 — Estructura del Proyecto

> Generado por Claude Code (CLI con ejecución) para que Claude web (chat)
> pueda diseñar la arquitectura del bot de WhatsApp sin tener que
> re-descubrir el proyecto existente. Todo lo de aquí está verificado
> contra el código real al momento de escribir esto, no es de memoria.
>
> **Alcance:** solo `MASS/PROYECTECOM/` (carpeta madre del proyecto real).
> `MASS/BACKEND`, `MASS/FRONTEND` y `MASS/WEBSERVICES` son proyectos de
> ejemplo de otro negocio (Massline/Shineray), usados solo como referencia
> de patrones de código durante el desarrollo — no tienen relación
> funcional con AzoShop y probablemente se borren más adelante. Ignóralos.

---

## 1. Panorama general

El proyecto real vive en **`MASS/PROYECTECOM/`** y son dos aplicaciones
independientes que se comunican por HTTP:

```
PROYECTECOM/
├── backend/     ← Flask (Python) — API REST + integración con Rocketfy
├── frontend/    ← Next.js (TypeScript) — dashboard interno del dueño
├── docs/        ← documentación del proveedor Rocketfy + planificación del bot
├── docs_para_claude/  ← este directorio
├── PROGRESS.md       ← bitácora de desarrollo completa (fuente de verdad)
└── RESUMEN_FASE1.md  ← resumen no técnico del backend, para el dueño del negocio
```

No hay todavía un repositorio git a nivel de `PROYECTECOM/` (no es un
repo git). `frontend/` sí tiene su propio git local (inicializado
automáticamente por `create-next-app`), pero solo tiene el commit inicial
— no se ha vuelto a commitear nada desde entonces.

---

## 2. Backend (`PROYECTECOM/backend/`)

**Lenguaje:** Python 3.9.6
**Framework:** Flask 3.1.0, patrón *application factory* (`create_app()`)
**Gestor de dependencias:** `pip` + `requirements.txt` + entorno virtual
en `backend/.venv/`

### `requirements.txt` completo

```
Flask==3.1.0
flask-cors==5.0.1
requests==2.32.3
marshmallow==4.0.1
python-dotenv==1.1.0
psycopg2-binary==2.9.12
APScheduler==3.11.0
gunicorn==23.0.0

# testing
pytest==8.3.4
responses==0.25.3
```

- **marshmallow**: serialización/validación (DTOs de entrada/salida, todo
  en camelCase hacia afuera, snake_case por dentro).
- **psycopg2-binary**: acceso directo a PostgreSQL (Supabase) con SQL
  crudo — no hay ORM.
- **APScheduler**: jobs periódicos en background (reconciliación de
  pedidos, vigilancia de stock).
- **responses**: mockea HTTP en los tests (nunca se llama a Rocketfy real
  en la suite automática).

### Cómo se ejecuta hoy (solo local, ver `06_estado_actual.md`)

```bash
cd PROYECTECOM/backend
source .venv/bin/activate           # o .venv/bin/python directamente
flask run --port 5050               # con FLASK_APP=src.app:create_app y .env cargado
```

No hay Dockerfile, no hay CI, no hay despliegue real todavía — corre como
proceso de desarrollo (`flask run`) en la máquina del dueño. `gunicorn`
está en las dependencias pero no se usa activamente todavía (ver
`06_estado_actual.md`, "estrategia de jobs en producción").

### Árbol completo de `backend/src/`

```
src/
├── app.py                          # create_app(), registro de blueprints, CORS,
│                                    # middleware de login, scheduler de jobs
├── config/
│   ├── settings.py                 # carga de variables de entorno (fail-fast)
│   ├── database.py                 # pool de conexiones psycopg2 (ThreadedConnectionPool)
│   ├── logging_config.py           # logging JSON estructurado
│   └── supabase_auth.py            # verifica el token de sesión del frontend
├── integrations/
│   └── rocketfy/
│       ├── client.py                # RocketfyClient: todas las llamadas HTTP al proveedor
│       ├── constants.py             # enum RocketfyStatus, umbrales de negocio conocidos
│       ├── exceptions.py            # RocketfyAuthError / RequestError / BusinessError
│       └── factory.py               # get_rocketfy_client() — singleton cacheado
├── catalogs/
│   └── ecuador_locations.py        # catálogo cerrado de 832 cantones / 24 provincias (CSV)
├── jobs/
│   ├── _locks.py                    # lock distribuido genérico (tabla job_locks)
│   ├── reconciliacion/              # respaldo del webhook: re-consulta pedidos periódicamente
│   └── stock_watcher/               # vigila stock/precio de SKUs elegidos, genera alertas
├── notifications/                   # capa de notificación — hoy solo loguea (ver pendientes)
└── routes/                          # un paquete por dominio, cada uno con su propio
    ├── pedidos/                     # dto.py / schemas.py / repository.py / services.py / controllers.py
    ├── webhooks/                    # recibe avisos de Rocketfy
    ├── productos/                   # catálogo + SKUs monitoreados
    ├── catalogos/                   # ubicaciones (provincias/cantones)
    ├── incidencias/                 # lectura de eventos/alertas para el dashboard
    └── metricas/                    # agregados de negocio
```

**Convención de capas por módulo de dominio** (ver `PROGRESS.md` sección
1, directriz 1): `dto.py` (dataclasses) → `schemas.py` (marshmallow,
camelCase externo) → `repository.py` (SQL crudo) → `services.py` (lógica
de negocio) → `controllers.py` (rutas Flask, delgadas). Los módulos
puramente de lectura/proxy (`catalogos`, `metricas`) se simplifican y
omiten `dto`/`repository` cuando no hace falta.

`backend/tests/` espeja exactamente la estructura de `src/` — 105 tests
con `pytest`, todos pasando (ver `06_estado_actual.md`).

---

## 3. Frontend (`PROYECTECOM/frontend/`)

**Lenguaje:** TypeScript
**Framework:** Next.js **16.3.4** (App Router), React **19.2.8**
**Estilos:** Tailwind CSS v4 + shadcn/ui (Radix, estilo `radix-nova`,
paleta neutra blanco/negro)
**Autenticación:** Supabase Auth (`@supabase/ssr` + `@supabase/supabase-js`)
**Gestor de dependencias:** `npm`

Es un **dashboard interno** para que el dueño del negocio vea y gestione
pedidos, incidencias, catálogo y métricas — NO es la tienda ni el bot.
Consume la API del backend Flask vía `NEXT_PUBLIC_API_URL`.

### `package.json` — dependencias relevantes

```json
"next": "16.3.4",
"react": "19.2.8",
"@supabase/ssr": "^0.12.6",
"@supabase/supabase-js": "^2.115.0",
"framer-motion": "^13.2.0",
"lucide-react": "^1.41.0",
"sonner": "^2.0.8"
```

### Cómo se ejecuta hoy

```bash
cd PROYECTECOM/frontend
npm run dev      # servidor de desarrollo en http://localhost:3000
```

Requiere `.env.local` con `NEXT_PUBLIC_API_URL`,
`NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` (ver
`05_variables_entorno.md`).

### Árbol relevante de `frontend/src/`

```
src/
├── app/
│   ├── layout.tsx                  # layout raíz (fuente, providers globales)
│   ├── login/page.tsx              # login (correo + contraseña, Supabase Auth)
│   ├── proxy.ts                    # (Next.js 16 renombró middleware.ts -> proxy.ts)
│   │                                # protege rutas, refresca sesión
│   └── (dashboard)/                # route group: todo lo que lleva sidebar
│       ├── page.tsx                # resumen / home
│       ├── pedidos/                # listado, detalle, creación manual
│       ├── incidencias/            # eventos de webhook + alertas de stock
│       ├── catalogo/               # explorador de catálogo + SKUs monitoreados
│       └── metricas/               # agregados de negocio
├── components/                     # compartidos (sidebar, header, StatusBadge, etc.)
│   └── ui/                         # primitivos de shadcn (generados, no editar a mano)
├── config/site.ts                  # nombre del sitio, navegación (única fuente)
├── lib/
│   ├── api.ts                      # cliente HTTP hacia el backend (adjunta el token de sesión)
│   ├── estados.ts                  # mapeo de colores/labels de estados (espejo del backend)
│   └── supabase/                   # clientes de Supabase (browser/server/middleware)
└── types/                          # tipos TS que espejan los schemas del backend
```

**Este frontend es completamente independiente del bot.** El bot no
necesita tocarlo para funcionar — pero probablemente el dashboard sea
donde, más adelante, el dueño quiera ver las conversaciones/leads del
bot (ver `06_estado_actual.md` y `07_preguntas_abiertas.md`).

---

## 4. Cómo se conectan backend y frontend hoy

- CORS restringido a un solo origen (`FRONTEND_ORIGIN`, variable de entorno).
- El frontend adjunta `Authorization: Bearer <token de Supabase>` en cada
  llamada; el backend lo verifica contra la propia API de Supabase Auth
  en cada request (`GET {SUPABASE_URL}/auth/v1/user`) — no hay JWT
  verificado localmente.
- Ambos procesos corren por separado (`flask run` en :5050, `next dev` en
  :3000) — no hay un solo comando que levante todo junto todavía.
