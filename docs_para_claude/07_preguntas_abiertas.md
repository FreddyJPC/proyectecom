# 07 — Preguntas Abiertas (respondidas contra el código real)

## ¿El proyecto ya tiene algún servidor web (Flask, FastAPI, etc.)?

**Sí.** Flask 3.1.0, patrón *application factory* (`create_app()` en
`backend/src/app.py`). Corre hoy con `flask run` en desarrollo; tiene
`gunicorn` en las dependencias pero no se usa activamente todavía.

## ¿Hay algún endpoint que ya reciba requests externos?

**Sí**, dos tipos:

1. **La API interna del dashboard** (protegida por login de Supabase
   Auth): `/pedidos` (GET/POST/PATCH), `/pedidos/<id>/rechazar`,
   `/productos`, `/productos/monitoreados`, `/catalogos/ubicaciones`,
   `/incidencias/eventos`, `/incidencias/stock`, `/metricas/generales`.
2. **El webhook de Rocketfy**: `POST /webhooks/rocketfy/<token>` — este
   es el único endpoint que ya recibe requests **no autenticados por
   nuestro login**, disparados por un sistema externo sin que nosotros
   iniciemos la llamada. Es el precedente más cercano a lo que sería un
   webhook de WhatsApp Cloud API — mismo problema de fondo (autenticar
   sin depender del proveedor, no fallar nunca, idempotencia).

## ¿Existe alguna lógica de manejo de estado de conversaciones?

**No, no existe en absoluto.** Lo único parecido que existe es una
máquina de estados para el *ciclo de vida de un pedido*
(`pedidos.estado_local`: pendiente_creación → creado → confirmado /
rechazado / error / incompleto) — pero eso es sobre el pedido ya cerrado
frente a Rocketfy, no sobre una conversación con un cliente. No hay
tablas, ni lógica, ni ningún concepto de "lead", "sesión de chat" o
"turno de conversación" en ningún lado del código actual. Esto es 100%
territorio nuevo para el bot (ver `04_base_de_datos.md`, sección 4).

## ¿Hay tests escritos?

**Sí, en el backend: 105 tests con pytest**, organizados en la misma
estructura que `src/` (uno por módulo de dominio). Estrategia:
- Se mockea HTTP hacia Rocketfy con la librería `responses` — nunca se
  llama a la API real en la suite automática.
- Los servicios que tocan base de datos se prueban con repositorios
  falsos en memoria (duck-typing del mismo contrato que el repositorio
  real), no contra Postgres real.
- Existe además un script manual (`backend/tools/rocketfy_order_smoke_test.py`)
  para validar contra Rocketfy real a propósito, fuera de la suite
  automática (no hay sandbox del proveedor).

**En el frontend: no hay tests automatizados todavía** — cada pantalla
se validó manualmente (build/lint limpios + verificación real contra el
backend y Rocketfy, sin herramienta de navegador disponible para
verificación visual automatizada).

## ¿El código está preparado para correr en producción o solo en local?

**Parcialmente, con partes ya probadas contra sistemas reales pero el
conjunto todavía corriendo en local:**
- La integración con Rocketfy (API real) y con Supabase (base de datos
  real, login real) **sí están probadas contra los sistemas de
  producción reales del proveedor**, no contra mocks únicamente.
- Pero el backend y el frontend corren hoy como procesos de desarrollo
  en la máquina del dueño (`flask run`, `next dev`), sin un hosting real
  elegido todavía, y el webhook de Rocketfy no tiene una URL pública
  permanente (se probó una vez con un túnel temporal ya cerrado).
- No está definida la estrategia de arranque de los jobs en background
  bajo un servidor de producción con múltiples workers.

**Conclusión práctica para el diseño del bot:** el *código* de la
integración con el distribuidor es confiable y ya validado end-to-end,
pero **la infraestructura de despliegue todavía no existe** — el bot va
a necesitar su propio hosting (o compartir el que se elija para el
backend) antes de poder operar con clientes reales, no solo escribirse.

---

## Preguntas de arquitectura ya resueltas con el dueño del negocio (2026-09-15)

Estas eran decisiones que el código existente no podía resolver por sí
solo — se le preguntaron directamente al dueño en esta misma conversación
y ya tienen respuesta:

1. **¿Dónde vive el código del bot?** → **Dentro del backend Flask
   actual**, como módulo/blueprint nuevo, con acceso directo en Python a
   `PedidoService` (sin pasar por HTTP), siguiendo el mismo patrón de
   capas ya establecido (`dto.py` / `schemas.py` / `repository.py` /
   `services.py` / `controllers.py`) — no un servicio Python separado.
2. **¿La base de datos del bot (conversaciones, leads) va en qué
   proyecto?** → **El mismo proyecto de Supabase ya existente**
   (`SUPABASE_DB_URL`/`SUPABASE_URL` actuales), con tablas nuevas propias
   del bot — recordatorio: **no** reutilizar ni reestructurar la tabla
   `pedidos` existente, que está moldeada para el contrato con Rocketfy
   (ver `04_base_de_datos.md`, sección 4).
3. **¿Qué LLM usa Sofía?** → **Claude (Anthropic)**, por consistencia con
   el resto del desarrollo del proyecto.

Con esto, la arquitectura de alto nivel queda: **un módulo nuevo dentro
de `backend/src/`, con sus propias tablas en el mismo Postgres de
Supabase, que llama a `PedidoService.crear_y_confirmar()` en Python
directo (no HTTP) cuando el bot cierra una venta, y usa la API de Claude
para la conversación.** El webhook de WhatsApp Cloud API de Meta
(entrante) seguiría el mismo patrón de diseño que ya existe para el
webhook de Rocketfy (`backend/src/routes/webhooks/`): auth propia (Meta
tampoco firma con una cabecera simple, usa verificación por token +
firma HMAC del cuerpo — distinto en detalle a Rocketfy pero mismo
principio), nunca fallar, idempotencia por los IDs que manda Meta.
