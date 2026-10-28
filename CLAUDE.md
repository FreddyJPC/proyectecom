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

## 6. Control de producción: qué puedo hacer hoy y qué falta
La meta de Freddy es trabajar desde cualquier lugar y que Claude opere el
ciclo completo (código, GitHub, Railway, Vercel, base de datos). Estado real:

| Área | Hoy | Para ampliarlo |
|---|---|---|
| **Código y git** | Sí: editar, probar, commit, push a la rama de la sesión | — |
| **GitHub** (ramas, PR, issues, CI) | Sí, con las herramientas de GitHub, solo en este repo y con la app de Claude instalada en la cuenta | Crear PR solo si se pide |
| **Railway** | No hay conector. Puedo preparar la configuración y guiar | Guardar un token de API de Railway **de alcance limitado** como secreto del entorno de la sesión (variable `RAILWAY_API_TOKEN`) y permitir el acceso de red a Railway; así podría usar su CLI/API (ver logs, variables, redespliegues) |
| **Vercel** | No hay conector. Igual que Railway | Token `VERCEL_TOKEN` como secreto del entorno + acceso de red a Vercel |
| **Base de datos (Supabase)** | Puedo escribir migraciones y aplicarlas si hay `SUPABASE_DB_URL` en el entorno | Guardar `SUPABASE_DB_URL` como secreto del entorno. Ideal: un rol de solo lectura para consultar y la cadena con permisos de escritura solo para migraciones |
| **Meta / Rocketfy** (paneles web) | No: se configuran a mano por Freddy con mi guía | — |

Cómo dar acceso: en la sesión, menú del entorno en la nube → *Edit* →
secretos de red / variables de entorno, y red permitida para los dominios
necesarios. Un token nuevo se ve en sesiones **nuevas**. **Nunca pegar
tokens en el chat.** Usar tokens con el mínimo alcance posible y rotarlos.

**Reglas de operación en producción** (cuando exista el acceso):
- Antes de acciones difíciles de revertir (borrar datos, cambiar variables
  de producción, redesplegar en horario de ventas, registrar/cambiar URLs de
  webhooks, correr migraciones destructivas) **pedir confirmación**.
- Preferir cambios por git + despliegue automático antes que ediciones
  directas en la plataforma, para que todo quede en el historial.
- Registrar cada cambio de infraestructura en `PROGRESS.md`.

## 7. Estado de producción (actualizar al avanzar)
- Código listo para desplegar: firma del webhook de WhatsApp, jobs bajo
  gunicorn (`ENABLE_SCHEDULER`), `gunicorn.conf.py`, `/health`.
- **Pendiente:** desplegar en Railway y Vercel, registrar webhooks definitivos
  en Meta y Rocketfy, rotar credenciales, plan de Supabase que no se pause,
  prueba de punta a punta con un número real. Ver `docs/DESPLIEGUE.md`.
