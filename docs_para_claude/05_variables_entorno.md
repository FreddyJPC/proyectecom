# 05 — Variables de Entorno

Regla del proyecto: los secretos reales **nunca** se escriben en archivos
`.md` ni se comparten por chat — viven solo en archivos `.env`
(git-ignorados). Este documento solo lista **nombres y para qué sirve
cada una**, nunca valores reales.

## 1. Backend — `backend/.env` (real) / `backend/.env.example` (plantilla versionada)

| Variable | Para qué sirve |
|---|---|
| `ROCKETFY_BASE_URL` | URL base de la API de Rocketfy (`https://rocket-e.com/api`) |
| `ROCKETFY_API_TOKEN` | Token de API entregado por Rocketfy (header `Auth-token`) |
| `ROCKETFY_ACCOUNT_EMAIL` | Correo exacto de la cuenta vendedora en Rocketfy (se hashea con SHA-256 para el header `Auth-user`) |
| `ROCKETFY_WEBHOOK_TOKEN` | Token propio (no lo da Rocketfy) para autenticar su webhook — va embebido en la URL `/webhooks/rocketfy/<token>`. Generado con `secrets.token_urlsafe(32)` |
| `SUPABASE_DB_URL` | Connection string de Postgres (vía el Connection Pooler, no la conexión directa) — la única que permite crear/alterar tablas |
| `SUPABASE_URL` | URL del proyecto de Supabase (`https://<project_ref>.supabase.co`) |
| `SUPABASE_SERVICE_KEY` | Llave de servicio (admin) de Supabase — **existe como variable pero está vacía/sin usar hoy**, nadie la ha necesitado todavía |
| `SUPABASE_ANON_KEY` | Llave pública (anon/publishable) de Supabase — se usa para verificar el token de sesión de un usuario del dashboard contra `/auth/v1/user`. NO es la de servicio, no da acceso administrativo |
| `NOTIFICATIONS_API_URL` / `NOTIFICATIONS_API_KEY` | Reservadas para un futuro canal de notificaciones — **no están implementadas ni conectadas a nada todavía** (ver `06_estado_actual.md`) |
| `FLASK_ENV` | `development` en local |
| `LOG_LEVEL` | Nivel de logging (default `INFO`) |
| `FRONTEND_ORIGIN` | Origen permitido para CORS desde el frontend Next.js (`http://localhost:3000` en local) |

## 2. Frontend — `frontend/.env.local` (real) / `frontend/.env.example` (plantilla versionada)

| Variable | Para qué sirve |
|---|---|
| `NEXT_PUBLIC_API_URL` | URL del backend Flask que consume el dashboard (`http://127.0.0.1:5050` en local) |
| `NEXT_PUBLIC_SUPABASE_URL` | Igual que la del backend — mismo proyecto de Supabase |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Llave pública de Supabase para el login desde el navegador |

Nota: en Next.js, cualquier variable con prefijo `NEXT_PUBLIC_` queda
embebida en el código que llega al navegador — por diseño solo se ponen
ahí llaves públicas, nunca secretos reales.

## 3. Lo que todavía no existe (relevante para el bot)

No hay ninguna variable de entorno relacionada con WhatsApp, Meta,
ningún LLM (Claude/OpenAI/Gemini), ni ningún servicio de mensajería —
porque nada de eso está construido todavía. Cuando se decida el
proveedor de LLM y se complete la configuración de Meta (ver
`docs/BotPlanifiacion.md`, sección 13), van a hacer falta variables
nuevas del estilo:

- Credenciales de la API de LLM elegida
- Token de acceso de WhatsApp Cloud API (Meta), ID del número de
  teléfono (WABA), token de verificación del webhook
- Posiblemente credenciales propias si el bot usa un servicio o base de
  datos distinta a la ya existente (a decidir, ver
  `07_preguntas_abiertas.md`)
