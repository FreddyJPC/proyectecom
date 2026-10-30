# CLAUDE.md — directrices para trabajar en PROYECTECOM

> Este archivo lo lee Claude al empezar cada sesión. Es el "manual de
> operación": qué es el proyecto, cómo trabajar con Freddy, qué reglas no se
> rompen y qué puede (y qué no puede) controlar Claude hoy. Si algo cambia,
> se actualiza aquí. Para el detalle técnico e histórico, la fuente de
> verdad es `PROGRESS.md`.

## 1. Qué es el proyecto
**PROYECTECOM** es el sistema operativo de **AzoShop** (dropshipping en
Ecuador, venta por WhatsApp con cobro contra entrega, logística con
Rocketfy). Tres piezas en un **monorepo** (ADR-008):

| Carpeta | Qué es | Producción |
|---|---|---|
| `backend/` | API Flask + webhooks + jobs + bot Victoria (Claude) | Railway |
| `frontend/` | Dashboard Next.js (pedidos, incidencias, catálogo, métricas, conversaciones) | Vercel |
| `docs/`, `docs_para_claude/` | Documentación del proveedor y del proyecto | — |

Base de datos: **Supabase** (Postgres). Migraciones en `backend/migrations/`.

## 2. Qué leer al retomar el contexto (en este orden)
1. Este archivo.
2. `PROGRESS.md`: sección 5 (pendientes), sección 4 (últimas entradas del
   historial) y la sección de la fase que se esté tocando.
3. `docs/DESPLIEGUE.md` si el tema es producción.
4. `frontend/AGENTS.md` antes de tocar el frontend (esta versión de Next.js
   tiene cambios incompatibles; leer la guía en `node_modules/next/dist/docs/`).
5. `RESUMEN_FASE1.md` para una visión general en lenguaje llano.

## 3. Cómo trabajar con Freddy
- **Hablar en español.** Freddy retoma el proyecto después de tiempos largos:
  **explicar siempre qué es cada cosa y para qué sirve** antes de proponer
  cambios. Sin jerga sin explicar.
- Ir **paso a paso**, una cosa a la vez, y dar una recomendación clara en
  vez de listas de opciones.
- Los conceptos nuevos se anotan en `docs/CONCEPTOS_TECNICOS.md`.
- Las decisiones se anotan en `PROGRESS.md` (ADR en la sección 2, fila nueva
  en el historial de la sección 4, pendientes en la sección 5).
- Ser honesto sobre lo que no se pudo verificar o probar.
- Pronombres: neutros si no están dados.

## 4. Reglas que no se rompen
**Seguridad**
- Nunca escribir valores de secretos en el repo, en commits, en la bitácora
  ni en el chat. Solo nombres de variables. `backend/.env` está ignorado por
  git; la plantilla es `backend/.env.example`.
- Si Freddy pega un secreto en el chat, avisarle y recomendar rotarlo.
- Los secretos de producción viven en Railway/Vercel/Supabase, no en el código.

**Dominio (Rocketfy / pedidos)**
- **Nunca duplicar pedidos reales.** Ante duda sobre si Rocketfy creó un
  pedido, detenerse y pedir revisión manual (idempotencia, ADR-007).
- **El dinero es siempre `Decimal`/string**, nunca `float`.
- **Validar la dirección (ciudad/cantón) antes** de enviar a Rocketfy.
- El webhook de Rocketfy **siempre responde 200** a una petición autenticada
  (más de 10 fallos acumulados y Rocketfy deja de avisar para siempre).
- El webhook de WhatsApp exige la firma `X-Hub-Signature-256`
  (`WHATSAPP_APP_SECRET`); falla cerrado.
- Un solo worker de gunicorn (el bot y los jobs viven en el mismo proceso).

**Código**
- Cambios con tests. Seguir el patrón de capas existente
  (`dto/schemas/services/controllers/repository`) y el estilo de comentarios
  del código vecino (en español, explicando el *por qué*).
- Migraciones: archivos nuevos y numerados en `backend/migrations/`. **No
  editar nunca una migración ya aplicada.**
- Proveedor del LLM detrás de la interfaz `LLMProvider`; no importar el SDK
  de Anthropic fuera de `src/integrations/llm/` (hay un test que lo vigila).

## 5. Entorno de trabajo (sesión en la nube)
- Desarrollar en la rama que indique la sesión; **commit + push al terminar**
  (el contenedor es efímero). **No crear Pull Requests sin que se pida.**
- Mensajes de commit en español, descriptivos.
- Archivos temporales en el directorio scratchpad de la sesión.

**Correr los tests del backend**
Los tests importan `src.app`, que al crearse se conecta a Postgres (el worker
del bot lee `cola_mensajes`). Hace falta una base real; **nunca apuntar los
tests al Supabase de producción**. En el contenedor hay binarios de
PostgreSQL 16 (`/usr/lib/postgresql/16/bin`):
1. Crear un venv e instalar `backend/requirements.txt`.
2. Levantar un Postgres desechable (no corre como root: usar un usuario
   normal, p. ej. `useradd -m pgtest`, `initdb`, `pg_ctl start -o '-p 5433'`).
3. Variables dummy: `ROCKETFY_BASE_URL`, `ROCKETFY_ACCOUNT_EMAIL`,
   `ROCKETFY_API_TOKEN`, `ROCKETFY_WEBHOOK_TOKEN`, `SUPABASE_URL`,
   `SUPABASE_ANON_KEY`, `WHATSAPP_API_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`,
   `WHATSAPP_WEBHOOK_VERIFY_TOKEN=token-secreto-de-prueba`, y
   `SUPABASE_DB_URL=postgresql://postgres@localhost:5433/postgres`.
4. `python tools/apply_migrations.py` y luego `python -m pytest -q`
   desde `backend/`. Estado actual: **221 tests pasando**.

**Interfaz (frontend)** — sistema de diseño definido en ADR-009
- Colores y estados **solo con tokens** de `src/app/globals.css` (`bg-primary`,
  `bg-status-*-soft` + `text-status-*-ink`…). Nunca colores a mano. Los estados
  de pedidos/conversaciones salen de `src/lib/estados.ts` y se muestran con
  `StatusBadge`.
- Reutilizar `src/components/app/*` (PageHeader, StatCard, SectionCard,
  EmptyState, FilterChips, PaginationBar, AvatarInitials, ListSkeleton) y el
  hook `useApi` para cargar datos (maneja carga, error, reintento y refresco).
  Formato de dinero, teléfono y fechas: `src/lib/format.ts`.
- **Mobile-first siempre:** toda pantalla nueva debe verse y usarse bien a
  390 px. Listas = tarjetas en móvil y tabla desde `md`; objetivos táctiles
  ≥ 40 px; nada puede quedar fuera de pantalla; respetar la barra inferior
  (`pb-28`) y el área segura.
- Todo texto visible en **español**; dinero siempre como string (nunca `float`).
- Cada pantalla necesita estados de carga, vacío y error (con "Reintentar").
- Antes de entregar cambios de UI: `npm run lint`, `npx next build` y la
  auditoría de accesibilidad de `frontend/tools/ui-preview/` (`node axe.mjs`)
  debe dar **SIN VIOLACIONES**; revisar capturas en escritorio y móvil, claro y
  oscuro (ver el README de esa carpeta). Antes de tocar Next.js, leer
  `frontend/AGENTS.md`.

## 6. Control de producción: qué puedo hacer hoy y qué falta
La meta de Freddy es trabajar desde cualquier lugar y que Claude opere el
ciclo completo (código, GitHub, Railway, Vercel, base de datos). Estado real
(verificado el 2026-10-29):

| Área | Hoy | Para ampliarlo |
|---|---|---|
| **Código y git** | Sí: editar, probar, commit, push a la rama de la sesión | — |
| **GitHub** (ramas, PR, issues, CI) | Sí, con las herramientas de GitHub, solo en este repo y con la app de Claude instalada en la cuenta | Crear PR solo si se pide |
| **Railway** | **Conectado y verificado (2026-10-30).** Puedo crear proyectos y servicios, cambiar su configuración (carpeta raíz, comando de arranque, healthcheck, región), fijar variables, generar dominios, leer logs y estado, y desplegar (`accept-deploy`, `redeploy`). Requiere un plan de pago activo. Los valores de las variables no los puedo leer (el conector entrega solo nombres) | — |
| **Vercel** | **Conectado y verificado (2026-10-29).** Más de 200 herramientas: crear proyectos, variables de entorno, despliegues, logs y errores en producción, dominios, etc. La primera vez pide autorizar el equipo (`authorize_team_access`: genera un enlace que Freddy abre y aprueba). Ojo: `create_git_project` puede devolver una respuesta ambigua aunque haya creado el proyecto: verificar antes de reintentar | — |
| **Base de datos (Supabase)** | **Conectado y verificado (2026-10-29).** Puedo listar proyectos y tablas, ejecutar SQL (`execute_sql`, solo lectura salvo que se pida otra cosa), aplicar migraciones, ver logs y advisors, y pausar/reactivar proyectos. La lista de migraciones del conector no refleja las de `tools/apply_migrations.py` (esas están en `public.schema_migrations`) | Para cambios de esquema: archivo nuevo en `backend/migrations/` y confirmación antes de aplicar |
| **Meta / Rocketfy** (paneles web) | No hay conector. Se configuran a mano por Freddy con mi guía | — |

Los tres conectores ya están conectados y la tabla refleja lo comprobado.
Un conector nuevo debe verificarse al conectarlo, mirando las herramientas
que realmente expone. No asumir.

**Cómo conectar (preferido):**
1. claude.ai → Personalizar → Conectores (https://claude.ai/customize/connectors).
2. Agregar Railway, Vercel y Supabase y autorizar cada uno con la cuenta de
   Freddy (normalmente OAuth). Empezar por Railway y Vercel.
3. **Iniciar una sesión nueva**: los conectores se leen al arrancar la sesión.

**Alternativa: token de API como secreto del entorno.** En la sesión, menú
del entorno en la nube → *Edit* → secretos de red / variables de entorno
(nombres previstos: `RAILWAY_API_TOKEN`, `VERCEL_TOKEN`, `SUPABASE_DB_URL`) y
red permitida para los dominios necesarios. Un token nuevo se ve en sesiones
**nuevas**. Menos cómodo que el conector y deja un secreto guardado en el
contenedor.

**Sobre los secretos y el `.env` real:** Claude **no necesita leer** los
valores para gestionarlos.
- Conocer los **nombres** de las variables (`backend/.env.example`) basta
  para programar; los tests usan valores falsos y una base local.
- Con un conector o token de plataforma, Claude puede **actuar** sobre las
  variables guardadas en Railway/Vercel sin ver ni pegar sus valores en el chat.
- **No guardar el `.env` de producción en el contenedor.** Si algún día se
  necesitan datos reales para reproducir un bug: base de **staging** o rol
  de Supabase de solo lectura, nunca el `.env` completo.

**Quién actualiza qué cuando algo cambia:**

| Qué cambia | Quién | Cómo |
|---|---|---|
| Nombres de variables nuevas, rutas del código | Claude, siempre | Editar código y `.env.example`, y documentarlo |
| Valores en Railway/Vercel (rotar un token, cambiar una URL) | Claude, **si hay conector o token de plataforma** y la herramienta lo permite | Cambiar la variable en la plataforma, **pidiendo confirmación antes** (suele implicar redespliegue) |
| Tokens que nacen en paneles de terceros (Meta, Rocketfy, Anthropic, Telegram) | Freddy, a mano | Freddy genera el valor y lo pone **en Railway/Vercel, nunca en el chat**; Claude verifica después que la variable exista y que `/health` responda |

Los valores que solo Freddy puede crear (p. ej. el App Secret de Meta) no
los puede inventar ni descubrir Claude; sí puede avisar cuando falten.

**Nunca pegar tokens en el chat.** Usar tokens con el mínimo alcance
posible y rotarlos.

**Reglas de operación en producción** (cuando exista el acceso):
- "Control total" no significa actuar sin preguntar. Antes de acciones
  difíciles de revertir (borrar datos, cambiar variables de producción,
  redesplegar en horario de ventas, registrar/cambiar URLs de webhooks,
  correr migraciones destructivas) **pedir confirmación**.
- Preferir cambios por git + despliegue automático antes que ediciones
  directas en la plataforma, para que todo quede en el historial.
- Registrar cada cambio de infraestructura en `PROGRESS.md`.

## 7. Estado de producción (actualizar al avanzar)
- Hecho (2026-10-29): código fusionado en `main` (PR #1); proyecto de Vercel
  `proyectecom-dashboard` creado y enlazado (sin desplegar); reactivación de
  Supabase solicitada (el proyecto estaba pausado).
- Los conectores de Railway, Vercel y Supabase están conectados. Vercel pide
  autorizar el equipo la primera vez (herramienta `authorize_team_access`).
- Railway: proyecto `proyectecom` (id `da0b3ffa-fc68-4859-b2e9-0506333e08cb`),
  servicio `backend` (carpeta `/backend`, healthcheck `/health`, región
  `us-west2`), dominio `backend-production-3e43.up.railway.app`. Repositorio
  conectado, **backend desplegado y sano** (2026-10-30; `/health` →
  `scheduler: true`). Los despliegues nuevos salen solos al hacer push a
  `main` si cambia algo en `backend/`.
- Vercel: `proyectecom-dashboard` **desplegado en producción**
  (`https://proyectecom-dashboard.vercel.app`, 2026-10-30). Tiene *Vercel
  Authentication* **desactivada** (2026-10-30, a pedido de Freddy): el dashboard
  se protege con su propio login de Supabase.
  Rediseño de UI (PR #2) **en producción** desde 2026-10-30; despliegue anterior
  `dpl_CnBrKTfkEWvBhHVukppr2T11cxnz` disponible para volver atrás.
- Dominio `azoshopec.com` (Spaceship, DNS básico): `www` y `@` son la tienda
  pública (Vercel, otro proyecto) y el correo se reenvía por Spaceship: **no
  tocar esos registros**. Para el panel: `app.azoshopec.com` → Vercel y
  `api.azoshopec.com` → Railway (en configuración, ver `PROGRESS.md` 0.0.50).
  **Vence el 2026-11-27 sin renovación automática** (pendiente #26).
- Spaceship: herramientas `dns_records_get/save/delete` y `domains_list`.
  Antes de escribir DNS, leer la zona; solo *agregar*, nunca borrar sin pedirlo.
- El proxy de la sesión de Claude **bloquea `*.up.railway.app`**: desde aquí no
  se puede hacer `curl` al backend; verificar con los logs/estado de Railway.
- Una respuesta ambigua de una herramienta de escritura (p. ej. "outcome
  unknown") **no se reintenta a ciegas**: se verifica el estado real primero.
- Código listo para desplegar: firma del webhook de WhatsApp, jobs bajo
  gunicorn (`ENABLE_SCHEDULER`), `gunicorn.conf.py`, `/health`.
- **Pendiente:** crear el servicio en Railway y cargar variables, desplegar el
  frontend con sus variables, registrar webhooks definitivos en Meta y
  Rocketfy, rotar credenciales, plan de Supabase que no se pause, prueba de
  punta a punta con un número real. Ver `docs/DESPLIEGUE.md`.
