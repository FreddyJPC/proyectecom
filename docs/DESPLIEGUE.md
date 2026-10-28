# Guía de despliegue — Railway (backend) + Vercel (frontend)

> Decisión registrada en `PROGRESS.md`, ADR-008: monorepo, backend en
> Railway, frontend en Vercel, ambos con despliegue automático desde GitHub.
>
> Los nombres de menús de Railway y Vercel pueden cambiar con el tiempo; si
> algo no coincide con lo que ves, busca el equivalente y avísame.
> **Nunca pegues valores de secretos en el chat ni en el repo.** Aquí solo
> aparecen nombres de variables.

---

## 0. Antes de empezar

1. **El código debe estar en la rama que conectes.** Las plataformas
   despliegan una rama concreta (normalmente `main`). Los cambios de esta
   etapa (firma del webhook, jobs bajo gunicorn, `gunicorn.conf.py`) viven
   hoy en `claude/nifty-fermi-jry8zu`; hay que llevarlos a `main` (Pull
   Request) o conectar esa rama temporalmente.
2. **Rota las credenciales** que alguna vez se pegaron en un chat
   (Anthropic, token de WhatsApp, contraseña de Supabase, Telegram,
   Rocketfy) y usa las nuevas en producción. Ver `PROGRESS.md`, entrada 0.0.39.
3. **Consigue el App Secret de Meta**: developers.facebook.com → tu app →
   Configuración de la app → Básica → "Clave secreta de la app" → Mostrar.
4. **Supabase**: pasa el proyecto a un plan que no se pause por inactividad
   (pendiente #17 de `PROGRESS.md`) antes de recibir clientes reales.

---

## 1. Backend en Railway

### Crear el servicio
1. Railway → **New Project → Deploy from GitHub repo** → elige `proyectecom`.
2. En el servicio: **Settings**:
   - **Root Directory:** `backend`
   - **Branch:** `main` (o la que decidas)
   - **Start Command:** `gunicorn -c gunicorn.conf.py src.app:app`
   - **Healthcheck Path:** `/health`
   - **Watch Paths:** `/backend/**` (para que un cambio solo en `frontend/`
     no reinicie el backend)
   - **Region:** la más cercana a Supabase (el proyecto está en AWS
     `us-west-2`, Oregón → una región US West).
3. **Settings → Networking → Generate Domain** para obtener la URL pública
   (`https://<algo>.up.railway.app`).

`gunicorn.conf.py` ya fija 1 worker con 4 threads y lee el puerto de la
variable `PORT` que Railway inyecta. La versión de Python se toma de
`backend/.python-version` (3.11).

### Variables de entorno (pestaña Variables)
Los **valores** los pones tú en el panel; no van en el repo.

| Variable | Nota |
|---|---|
| `ROCKETFY_BASE_URL`, `ROCKETFY_API_TOKEN`, `ROCKETFY_ACCOUNT_EMAIL` | Credenciales de Rocketfy |
| `ROCKETFY_WEBHOOK_TOKEN` | Genera uno nuevo para producción: `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `SUPABASE_DB_URL`, `SUPABASE_URL`, `SUPABASE_ANON_KEY` | Del proyecto de Supabase (usar el pooler) |
| `WHATSAPP_API_TOKEN` | Token **permanente** (usuario de sistema), no el de 24 h |
| `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_WABA_ID` | Del número real del negocio |
| `WHATSAPP_WEBHOOK_VERIFY_TOKEN` | Token propio para el handshake GET de Meta |
| **`WHATSAPP_APP_SECRET`** | **Obligatoria en producción**: sin ella el webhook rechaza todo POST (401) |
| `ANTHROPIC_API_KEY`, `LLM_PROVIDER`, `LLM_MODEL` | Cerebro de Victoria |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Avisos de escalada al dueño |
| **`ENABLE_SCHEDULER`** | **`true`**: enciende reconciliación y stock watcher |
| `FRONTEND_ORIGIN` | La URL de Vercel (paso 2), sin `/` final. Es el origen permitido por CORS |
| `LOG_LEVEL`, `BOT_MAX_TURNOS_HERRAMIENTAS`, `BOT_MAX_MENSAJES_HISTORIAL` | Opcionales |

**No** definas `WHATSAPP_SKIP_SIGNATURE` en producción.

### Verificar que quedó bien
```
curl https://<dominio-railway>/health
→ {"scheduler":true,"status":"ok"}
```
Si `scheduler` sale `false`, falta `ENABLE_SCHEDULER=true`.

### Aplicar migraciones a la base
Las 11 migraciones (`backend/migrations/`) ya están aplicadas en tu Supabase
actual. Si usas un proyecto de Supabase nuevo, hay que correr
`backend/tools/apply_migrations.py` contra él.

---

## 2. Frontend en Vercel

1. Vercel → **Add New → Project** → importa `proyectecom`.
2. **Root Directory:** `frontend`. Framework: Next.js (se detecta solo).
3. **Environment Variables:**
   - `NEXT_PUBLIC_API_URL` = URL pública del backend en Railway
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
4. Deploy. Copia la URL resultante y ponla en `FRONTEND_ORIGIN` del backend
   (Railway la redespliega sola al cambiar la variable).
5. En Supabase → Authentication → URL Configuration: pon la URL de Vercel
   como *Site URL* si el login lo requiere.
6. Si quieres evitar builds innecesarios cuando solo cambia `backend/`,
   configura *Ignored Build Step* del proyecto de Vercel.

Prueba: abre la URL de Vercel, inicia sesión y revisa que el indicador de
estado del backend (barra del dashboard) aparezca conectado.

---

## 3. Registrar los webhooks (ya con URLs definitivas)

### Rocketfy
URL: `https://<dominio-railway>/webhooks/rocketfy/<ROCKETFY_WEBHOOK_TOKEN>`
Se registra en el panel de Rocketfy. **Cuidado:** Rocketfy solo tolera 10
fallos acumulados en toda la vida de la URL; registra la URL solo cuando el
backend ya esté estable (`/health` correcto).

### Meta (WhatsApp)
En developers.facebook.com → tu app → WhatsApp → Configuración → Webhook:
- **URL de devolución de llamada:** `https://<dominio-railway>/webhooks/whatsapp`
- **Token de verificación:** el valor de `WHATSAPP_WEBHOOK_VERIFY_TOKEN`
- Suscribirse al campo **messages**.

Meta hace un GET de verificación (lo responde el backend) y a partir de ahí
firma cada POST con el App Secret; el backend descarta los que no tengan
firma válida.

---

## 4. Prueba de punta a punta (poco riesgo)

1. Escríbele al número real desde tu propio teléfono y confirma que Victoria
   responde.
2. Cierra una venta contraentrega de un producto barato y confirma el pedido
   en Rocketfy.
3. Provoca una escalada y confirma el aviso por Telegram y la conversación
   en `/conversaciones`.
4. Responde manualmente desde el dashboard (nunca se ha probado con un envío
   real, pendiente #24).
5. Revisa los logs en Railway: no debe haber errores 401 inesperados en
   `/webhooks/whatsapp` ni fallos de conexión a la base.

## 5. Cosas a tener presentes

- **Reiniciar el backend** (cada despliegue) corta unos segundos el worker de
  Victoria; los mensajes pendientes se recuperan de `cola_mensajes`.
- **Si Supabase está pausado o inaccesible al arrancar**, el backend no
  arranca (al iniciar el worker lee la cola desde la base). Railway lo
  reintentará; la solución es reactivar Supabase.
- **Escalar a más de un worker de gunicorn** duplicaría el bot y los jobs.
  Antes de hacerlo hay que sacarlos a un servicio aparte.
