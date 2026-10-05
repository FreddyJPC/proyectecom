# PROGRESS.md — Integración Rocketfy (Backend Desacoplado)

> Fuente única de verdad del proyecto. Se actualiza en cada sesión de trabajo.
> Última actualización: 2026-09-03
>
> ¿Buscas el panorama general sin entrar en detalle técnico (para
> reorientarte rápido o decidir qué sigue)? Ver `RESUMEN_FASE1.md` en la
> raíz de `PROYECTECOM/` — no reemplaza este archivo, lo complementa.

---

## 0. Objetivo del Proyecto (norte de todo el desarrollo)

Automatizar de extremo a extremo el flujo de venta por WhatsApp con cobro
contra entrega (COD) del negocio de Freddy Paguay, integrándolo con la
plataforma logística Rocketfy, para:

1. **Eliminar la carga manual de pedidos** y reducir el margen de error en
   despachos (inyección directa desde el sistema propio hacia Rocketfy).
2. **Aumentar la tasa de entregas exitosas** mediante notificaciones
   proactivas por WhatsApp al cliente final, basadas en el estado real del
   envío (ej. "tu paquete llega hoy, ten el efectivo listo").
3. **Proteger la inversión publicitaria** (Meta/TikTok) detectando cuándo el
   stock de un producto pautado cae a nivel crítico, para poder pausar
   campañas antes de vender sin inventario.
4. **Dar visibilidad financiera** (liquidaciones, flujo de caja aproximado)
   para decisiones de reinversión en publicidad y retiro de capital.
5. **Servir de base modular y escalable** para futuras automatizaciones y
   orquestaciones de flujo de negocio — la arquitectura se diseña pensando
   en más integraciones futuras, no solo Rocketfy.

**Meta final:** un sistema propio (backend Flask + frontend Next.js, ambos
dentro de `PROYECTECOM/`) que funcione como el "cerebro operativo" del
negocio: minimizar al máximo la intervención manual entre el momento en que
el cliente confirma la compra por WhatsApp y el momento en que el pedido se
entrega y se cobra exitosamente.

Toda decisión técnica de este proyecto debe evaluarse contra este objetivo:
¿reduce intervención manual?, ¿mejora la tasa de entrega?, ¿protege margen o
inversión publicitaria?, ¿deja la puerta abierta a futuras automatizaciones?

---

## 0.1 Resumen funcional y ubicación en disco

Backend desacoplado en Flask que consume, valida y orquesta la API de Rocketfy
(proveedor logístico/COD en Ecuador) para automatizar el flujo:
landing page → confirmación por WhatsApp → creación/confirmación de pedido →
seguimiento de estado → notificación proactiva al cliente → (Fase 2) control
de stock, cancelaciones/ediciones y conciliación financiera.

**Estructura en disco (decidida 2026-09-03):** todo lo nuevo de este proyecto
vive bajo `MASS/PROYECTECOM/`, que es la carpeta madre:

```
MASS/
├── BACKEND/        (proyecto de ejemplo existente — solo referencia, NO se modifica)
├── FRONTEND/        (proyecto de ejemplo existente — solo referencia, NO se modifica)
├── WEBSERVICES/     (proyecto de ejemplo existente — solo referencia, NO se modifica)
└── PROYECTECOM/     (carpeta madre de ESTE proyecto)
    ├── PROGRESS.md  (este archivo)
    ├── docs/        (documentación de negocio/proveedor)
    ├── backend/     (Fase 1 — Flask, en construcción)
    └── frontend/    (Fase 2 — Next.js, pendiente)
```

Fase 2 (frontend): Next.js dentro de `PROYECTECOM/frontend/`, no se rige por
el frontend de ejemplo (`MASS/FRONTEND/`, React CRA legacy) — solo se usó
como referencia de contratos de datos.

Documentos de referencia (no modificar, son la fuente de negocio/proveedor),
ahora en `PROYECTECOM/docs/`:
- `docs/Requerimientos_API.md` — requerimientos originales enviados al proveedor.
- `docs/Rocketfy-API-Integracion-Sistemas-Propios.md` — respuesta técnica del proveedor.
- `docs/rocket-cantones-ecuador.csv` — catálogo cerrado de 832 cantones (copiado
  también a `backend/data/`, que es de donde lo lee la app en tiempo de ejecución).
- `docs/Rocket-Webhooks-Guia-Integrador.md` — contrato detallado del webhook de
  estados. Más estricto y más completo que la sección 6 del doc principal —
  ver directrices 12-16 y ADR-007 más abajo.
- `docs/CONCEPTOS_TECNICOS.md` — glosario/explicaciones didácticas para Freddy
  (connection strings, MCP, configuraciones, etc.), acumulativo. Cuando surja
  un concepto técnico nuevo que valga la pena explicar a fondo, se agrega ahí
  en vez de solo explicarlo en el chat.

---

## 1. Directrices y Reglas Arquitectónicas

1. **Arquitectura por capas por submódulo**, replicando el patrón validado en
   `BACKEND/src/routes/logistica/transportistas`: `dto.py` → `schemas.py`
   (Marshmallow) → `repository.py` (acceso a datos) → `services.py` (lógica
   de negocio, excepciones werkzeug) → `controllers.py` (blueprint delgado).
2. **`repository.py` es la única capa que conoce la fuente de datos.** Para
   la integración con Rocketfy, el equivalente es `integrations/rocketfy/client.py`
   (HTTP externo) en vez de SQLAlchemy.
3. **Ningún secreto en código fuente.** Token y credenciales de Rocketfy
   siempre por variable de entorno / secrets manager. (Antipatrón detectado
   y explícitamente prohibido: `BACKEND/src/netsuite_core/config.py` tiene un
   API key hardcodeado — no se repite ese error aquí.)
4. **Idempotencia obligatoria.** `/orders/create` de Rocketfy NO es idempotente.
   El `id` de Rocketfy se persiste inmediatamente al recibirlo, antes de
   cualquier otro paso. Nunca reintentar `/orders/create` sin antes comprobar
   si el pedido ya existe.
5. **Montos como `Decimal`, nunca `float`.** Rocketfy envía importes como
   string decimal; el proveedor lo advierte explícitamente.
6. **Programar contra `status_id`, nunca contra `status_name`.** El texto
   puede cambiar; el estado puede retroceder (no asumir progresión lineal).
7. **El webhook debe responder HTTP 200 exacto en <10s**, sin redirecciones,
   incluyendo el ping de validación de body vacío. El procesamiento pesado
   (notificaciones, escritura) no debe bloquear esa respuesta.
8. **Validar provincia/cantón contra el catálogo cerrado del proveedor
   ANTES de crear el pedido** (CSV de 832 cantones), nunca como texto libre.
9. **Reintentos solo ante 500 o "servicio en mantenimiento"**, con backoff
   progresivo. Cualquier otro error de negocio se trata como definitivo.
10. **Persistencia mínima en Supabase**, limitada a: mapping pedido_local↔
    pedido_rocketfy, auditoría cruda de eventos de webhook (retención 90 días),
    y locks de jobs de reconciliación. No es una base de datos de negocio/CRM.
11. **Testing:** `pytest` + `responses`/`requests-mock` para mockear Rocketfy
    en unitarias. Ningún módulo se marca completo sin sus tests pasando.
    Integración marcada con `@pytest.mark.integration`, no corre en CI por
    defecto (no existe sandbox del proveedor).

**A partir de `docs/Rocket-Webhooks-Guia-Integrador.md` (2026-09-04):**

12. **Rocket NO manda ninguna cabecera de autenticación al webhook** (ni
    `Authorization`, ni firma HMAC, ni `X-Rocket-*`). La autenticación la
    ponemos nosotros: un token largo y aleatorio embebido en la propia URL
    (`/webhooks/rocketfy/<token>`), comparado con `hmac.compare_digest`
    (tiempo constante). Si el token no cuadra, responder 401/403 — nunca
    404/405 (esos códigos además bloquean el alta del webhook en el panel).
13. **El endpoint del webhook casi nunca debe devolver algo distinto de 200.**
    El presupuesto de error es de **10 fallos acumulados en toda la vida de
    la URL** (nunca se resetea); al superarlo, Rocket desactiva el webhook
    en silencio, sin aviso. Por diseño: persistir el evento crudo primero,
    responder 200 siempre que la autenticación fue válida, y procesar
    después — un fallo de lógica de negocio interno NUNCA debe traducirse
    en una respuesta no-200 a Rocket.
14. **No hay reintentos, nunca.** Un evento no aceptado (por lo que sea) se
    pierde para siempre — no hay forma de recuperarlo salvo la
    reconciliación periódica vía `orders/bulk/getInfo` (resuelve duda #5).
15. **Clave de idempotencia real: `(order_id, status_id, event_date)`**, no
    solo `order_id`. Ver ADR-007 y migración `002_webhook_events_idempotencia.sql`.
16. **`total` del webhook nunca se usa para mover dinero** — es solo
    referencia; se contrasta contra el pedido propio. Y `status_id` 1
    (Nuevo) y 13 (Carrito abandonado) NUNCA llegan por webhook — no hace
    falta manejarlos ahí.
17. **Mínima interacción manual, pero trazabilidad total y visible.**
    Directriz explícita del usuario (2026-09-06): toda automatización futura
    (incluido el bot conversacional de WhatsApp, sección "Fases Futuras")
    debe apuntar a que el dueño del negocio casi no tenga que tocar nada a
    mano. Pero eso NUNCA puede significar una caja negra: cada acción del
    sistema (mensajes del bot, datos recopilados, pedidos creados, errores,
    novedades) debe quedar registrada de forma que el futuro frontend pueda
    mostrarla en un dashboard, para que un humano pueda intervenir rápido
    cuando algo lo requiera. Ningún módulo nuevo debe automatizar sin dejar
    rastro consultable.

---

## 2. Bitácora de Decisiones (ADR ligero)

### ADR-001 — Mantener Marshmallow sobre Pydantic
**Contexto:** el proyecto de ejemplo usa Marshmallow de forma consistente y
madura (camelCase↔snake_case, EXCLUDE unknown, validate.OneOf).
**Decisión:** usar Marshmallow también en el backend nuevo.
**Por qué:** cambiar de librería de validación no aporta valor funcional y
rompe la convención ya interiorizada por el equipo.
**Estado:** ACEPTADO por el usuario (2026-09-03). Stack completo aprobado:
Flask + requests + Marshmallow + Supabase + APScheduler + pytest/responses.

### ADR-002 — Persistencia mínima en Supabase pese al objetivo "sin estado"
**Contexto:** el brief original pedía un backend de consulta/orquestación
sin estado en Fase 1.
**Decisión:** persistir de todas formas el mapping id_local↔id_rocketfy,
auditoría de webhooks y locks de jobs.
**Por qué:** el proveedor advierte que `/orders/create` no es idempotente y
que la única protección contra duplicados es guardar el `id` propio y el de
Rocketfy tan pronto se reciba. Sin esto, cualquier timeout/reintento puede
duplicar pedidos reales con cobro contra entrega.
**Estado:** ACEPTADO por el usuario (2026-09-03), y ampliado. Esquema final
(ver `backend/migrations/001_init.sql`): `pedidos` (mapping id_local↔id_rocketfy
+ cache de estado), `webhook_events` (auditoría cruda, retención 90 días),
`job_locks` (coordinación de jobs), `skus_monitoreados` y `stock_snapshots`
(config y serie de tiempo para el requerimiento 4/7 — pausar ads por stock
bajo, alertar cambio de precio). Sigue sin ser una base de negocio/CRM:
Rocketfy es la fuente de verdad del estado del pedido, catálogo y precios.

### ADR-003 — Requerimiento #2 (cotizador de cobertura/flete) no es construible internamente
**Contexto:** el usuario lo marcó como Fase 1 Prioridad Alta; el proveedor
confirma que el endpoint no existe hoy para vendedores.
**Decisión:** implementar el paliativo (leer el error de "sin cobertura" en
`/orders/confirm`) y dejar el cotizador real como dependencia externa
bloqueada, a gestionar directamente con Rocketfy.
**Estado:** aceptado como limitación conocida. El usuario confirmó (2026-09-03)
que NO se solicitarán a Rocketfy los endpoints faltantes (cotizador ni
saldos/wallet) por ahora — no son impedimento para iniciar el desarrollo ni
para poner en marcha el negocio. La sección 6 (dudas al proveedor) queda
como registro para gestionar más adelante si se vuelve necesario, no como
bloqueo actual.

### ADR-004 — Reutilizar el patrón `NotificationChannel`/`WhatsAppChannel` — CORREGIDO
**Contexto:** ya existe una abstracción Strategy funcionando en
`BACKEND/src/notifications/` que llama a una API interna de notificaciones.
**Decisión original (2026-09-03):** reutilizar esa misma interfaz tal cual,
incluyendo el canal de WhatsApp.
**Corrección (2026-09-04, al implementar Etapa 4):** el patrón (ABC
`NotificationChannel` + `NotificationMessage` + `NotificationService`) SÍ se
reutilizó — es genérico y sirve. Pero el `WhatsAppChannel` original llama a
una API interna de **Massline/Shineray** (el negocio del proyecto de
ejemplo), no a nada que este proyecto tenga acceso. Se implementó
`LoggingNotificationChannel` como default seguro (loguea, no envía nada
real) mientras se define el mecanismo real de envío de WhatsApp para ESTE
negocio.
**Estado:** patrón aceptado y en uso; canal real de WhatsApp PENDIENTE —
requiere que el usuario indique qué mecanismo usar.

### ADR-005 — Reutilizar el patrón de lock de `despacho_dia_actual.py` para reconciliación
**Contexto:** Rocketfy recomienda reconciliar con `bulk/getInfo` cada 30-60 min;
el ejemplo ya resuelve el problema de locks entre instancias con una tabla
de lock + APScheduler.
**Decisión:** replicar el mismo patrón con una tabla de lock en Supabase.
**Estado:** aceptado.

### ADR-007 — Autenticación propia del webhook (token en la URL) + idempotencia por (order_id, status_id, event_date)
**Contexto:** `docs/Rocket-Webhooks-Guia-Integrador.md` aclaró que Rocket no
manda ninguna cabecera de autenticación, y que el presupuesto de error es de
solo 10 fallos acumulados en toda la vida de la URL, sin reset.
**Decisión:** (a) el receptor vive en una ruta con un token secreto propio
(`ROCKETFY_WEBHOOK_TOKEN`, aún por generar) comparado en tiempo constante;
(b) el handler responde 200 a cualquier request autenticada, incluso si el
procesamiento interno falla (solo loguea, nunca propaga el error como
respuesta no-200); (c) `webhook_events` gana columnas `event_date` y
`shopify_order_id`, con índice único en `(id_rocketfy, status_id, event_date)`
para idempotencia real (migración `002_webhook_events_idempotencia.sql`,
aplicada).
**Estado:** aceptado. Falta implementar el receptor en sí (Etapa 4).

### ADR-006 — Mecanismo de acceso a Supabase para Claude
**Contexto:** el usuario preguntó si existe forma de que Claude cree/consulte
tablas directamente en su Supabase, en vez de hacerlo manualmente.
**Opciones evaluadas:**
1. MCP oficial de Supabase (`@supabase/mcp-server-supabase`), vía Personal
   Access Token acotado con `--project-ref` (y opcionalmente `--read-only`).
   Da herramientas interactivas dentro de la sesión de Claude Code.
2. Cadena de conexión directa a Postgres (`SUPABASE_DB_URL` en `.env`) +
   migraciones SQL versionadas en `backend/migrations/` (ya iniciado con
   `001_init.sql`). Reproducible, revisable en git, no depende de MCP.
3. El usuario aplica manualmente el SQL que Claude le entrega.
**Decisión:** propuesta al usuario usar (2) como mecanismo base siempre (el
esquema vive en git, no solo "lo que Claude hizo por chat"), y (1) opcional
como conveniencia adicional para consultas interactivas durante desarrollo.
**Estado:** ACEPTADO por el usuario (2026-09-04) — combinación (1)+(2):
connection string para migraciones versionadas + MCP oficial de Supabase
para consultas interactivas. Pendiente que el usuario entregue
`SUPABASE_DB_URL` (ya con placeholder en `backend/.env`) y registre el MCP
con un Personal Access Token acotado a `--project-ref` de este proyecto.

---

## 3. Plan de Desarrollo y Checklist de Progreso

### Etapa 0 — Scaffolding
- [x] Carpeta creada, entorno virtual (`backend/.venv`), `requirements.txt` inicial
- [x] Estructura de carpetas (`src/`, `tests/`, `tools/`, `migrations/`)
- [x] `.env.example`, `pytest.ini`, `logging_config.py` (JSON estructurado, correlación por order_id)
- [ ] CI básico (lint + pytest) — pendiente, no urgente en solitario
- [x] `/health` responde 200 (`src/app.py`, probado con Flask test_client)

### Etapa 1 — RocketfyClient
- [x] Auth headers (`Auth-user` sha256, `Auth-token`) — `src/integrations/rocketfy/client.py`
- [x] Sin desenvolver "content" genéricamente (ver duda #11 — el ejemplo de
      `/orders/create` no trae `content` pese a la regla general del doc);
      cada método público extrae solo lo que el doc confirma con ejemplo
- [x] Manejo de respuesta bare (`getInfo` sin `content`, datos en `order`)
- [x] Retry con backoff SOLO en 500 (urllib3 Retry) / mensaje "mantenimiento" (manual)
- [x] Excepciones tipadas (`RocketfyAuthError`, `RocketfyRequestError`, `RocketfyBusinessError`)
- [x] Tests unitarios: 12/12 pasando (200 éxito, 401, 405 negocio, timeout,
      no-JSON, mantenimiento con reintento exitoso y con agotamiento)
- [x] Wrappers listos para: crear/confirmar/consultar/consultar-lote/modificar/
      rechazar pedido, listar/ver producto, estadísticas generales (adelantado
      de Etapas 3, 5, 6, 7 — son métodos mecánicos de una línea cada uno,
      sin lógica de negocio todavía)

### Etapa 2 — Catálogo de ubicaciones Ecuador — COMPLETA (2026-09-04)
- [x] Carga del CSV de 832 cantones (`src/catalogs/ecuador_locations.py`, dato en `backend/data/`)
- [x] Normalización mayúsculas/tildes (`_normalizar`, NFKD)
- [x] Endpoint interno de catálogo (`GET /catalogos/ubicaciones`, `GET /catalogos/ubicaciones/<provincia>/cantones`)
- [x] Tests: 6/6 pasando (carga completa, normalización, cantón/provincia inexistente, listado, singleton cacheado)

### Etapa 3 — Crear + confirmar pedido (Requerimiento 1) — COMPLETA (2026-09-04)
- [x] Esquema de tablas diseñado y aplicado (`backend/migrations/001_init.sql`, `002_...sql`)
- [x] Tabla `pedidos` en Supabase, ya en uso real desde `src/routes/pedidos/repository.py`
- [x] Validación de cantón/provincia antes de crear (`EcuadorLocationsCatalog`, bloquea antes de tocar Rocketfy)
- [x] `POST /orders/create` + guardado inmediato de `id` Rocketfy (`PedidoService._crear_en_rocketfy`)
- [x] Verificación de `products_stock` completo → estado `incompleto` si falta alguna línea
- [x] `POST /orders/confirm` + manejo de errores: reintentable limpio si `error` en create (ok=0, Rocketfy
      confirma que no se creó nada); estado ambiguo bloqueado si timeout/red (no reintenta a ciegas, tal
      como advierte el proveedor); reintento de solo-confirmación si el rechazo es en confirm (queda
      `creado` con `mensaje_error`, no se recrea)
- [x] Endpoint `POST /pedidos` (`src/routes/pedidos/controllers.py`), capa completa dto/schemas/repository/services/controllers
- [x] Tests unitarios: 9/9 nuevos pasando (27/27 en total) — flujo exitoso, payload (Decimal→string,
      JSON de líneas), 5 variantes de idempotencia (ya confirmado, estado ambiguo, timeout, error 405
      reintentable, rechazo en confirm reintentable), ubicación no resuelta, products_stock incompleto
- [x] `tools/rocketfy_order_smoke_test.py` — prueba manual contra producción real (pedido de bajo valor,
      confirmar, rechazar), NO automática por diseño (no hay sandbox del proveedor) — pendiente que el
      usuario la corra manualmente cuando quiera validar de punta a punta contra Rocketfy real

### Etapa 4 — Webhook + reconciliación (Requerimiento 3) — COMPLETA (2026-09-04)
- [x] Receptor webhook (`POST /webhooks/rocketfy/<token>`): token propio en la URL (`hmac.compare_digest`,
      nunca 404/405 ante token inválido, 403); tolera cuerpo vacío (ping de validación) → 200 inmediato
- [x] Auditoría cruda del evento en `webhook_events`, idempotente por `(id_rocketfy, status_id, event_date)`
- [x] Traducción `status_id` → evento interno: `EN_RUTA` → notifica al cliente (vía `NotificationService`,
      ver nota de canal pendiente abajo); `NOVEDAD`/`DEVUELTO_EN_TRANSITO` → log de alerta para el equipo
- [x] `WebhookService.procesar_evento` NUNCA propaga excepciones (regla dura de la guía: presupuesto de
      solo 10 fallos de por vida) — cualquier fallo interno se loguea, la respuesta ya fue/será 200
- [x] Job de reconciliación (`src/jobs/reconciliacion/`): lock vía `job_locks` (mismo patrón que
      `despacho_dia_actual.py`), rango `[min, max]` de ids en curso (no terminales), particionado en
      chunks de máximo 5000 ids, parseo defensivo de la respuesta de `bulk/getInfo` (forma no confirmada
      por el proveedor — ver duda #13 nueva), un lote fallido no detiene los demás, lock siempre se libera
- [x] Programado con APScheduler cada 45 min (`start_scheduler()` en `app.py`, arranca solo en el
      proceso `__main__` — pendiente definir el arranque en producción con gunicorn, ver Etapa 8)
- [x] Tests: 24/24 nuevos pasando (51/51 en total) — autenticación del webhook, ping, idempotencia,
      tolerancia a fallos, notificación condicional, lock del job, partición de rangos, resiliencia a
      errores de red por lote

**Pendiente explícito (no bloqueante para el resto):** el canal real de envío de WhatsApp a clientes
finales de ESTE negocio no está definido — el `NotificationChannel` reutilizado de `BACKEND/src/notifications`
llama a una API interna de Massline/Shineray que no aplica aquí. Por ahora `WebhookService` usa
`LoggingNotificationChannel` (loguea qué se habría enviado, no envía nada real). Falta que el usuario
indique qué mecanismo usar (Meta WhatsApp Cloud API directo, Twilio, u otro) para implementar el canal
real — ver pregunta al usuario en el resumen de esta sesión.

### Etapa 5 — Stock y catálogo (Requerimientos 4 y 7) — COMPLETA (2026-09-04)
- [x] Wrapper `/products/list` y `/products/view/{id}` (ya estaban desde Etapa 1, expuestos ahora vía
      `GET /productos` y `GET /productos/<id>` como proxy directo al catálogo de Rocketfy)
- [x] Gestión de SKUs monitoreados: `GET/POST /productos/monitoreados`, `DELETE /productos/monitoreados/<sku>`
      — valida contra el catálogo real de Rocketfy antes de agregar (evita vigilar un SKU mal tipeado
      que nunca va a disparar nada)
- [x] Job `stock_watcher` (`src/jobs/stock_watcher/`) con umbral configurable por SKU, mismo patrón de
      lock que reconciliación (compartido ahora en `src/jobs/_locks.py`, refactor DRY), programado cada
      60 min
- [x] Alerta de cambio de precio (snapshot anterior vs actual en `stock_snapshots`) y de stock bajo umbral
      — ambas por ahora solo van al log (ver pendiente #2 en la sección 6)
- [x] Tests: 17/17 nuevos pasando (68/68 en total)

**Fuera de alcance a propósito:** pausar campañas de Meta/TikTok automáticamente. Este job detecta y deja
constancia del evento; la acción de pausar queda como automatización futura sobre este mismo dato.

### Etapa 6 — Modificar/cancelar pedidos (Requerimiento 5) — COMPLETA (2026-09-04)
- [x] Wrapper `/orders/modify` (ya estaba desde Etapa 1) expuesto como `PATCH /pedidos/<id_local>` —
      solo se validan localmente cosas CIERTAS de antemano (que el pedido exista y tenga id_rocketfy);
      el resto de las reglas de negocio las arbitra Rocketfy, nunca se replican a ciegas localmente
- [x] Si se cambia cantón/provincia, se valida la combinación contra el catálogo ANTES de enviar
      (completando el campo no enviado con el valor ya guardado) — el doc advierte que `/orders/modify`
      no valida el cantón, solo actualiza el texto, así que sin este chequeo se repetiría el mismo
      problema de la sección 4.2 pero en modificación
- [x] Cache local (`payload_creacion`) se actualiza vía merge de jsonb tras un modify exitoso — mantiene
      fresco el teléfono/dirección que usa el webhook para notificar al cliente (Etapa 4)
- [x] Wrapper `/orders/reject` (ya estaba desde Etapa 1) expuesto como `POST /pedidos/<id_local>/rechazar`
      — marca `estado_local='rechazado'` solo si Rocketfy confirma; un rechazo fallido (ej. etiqueta ya
      impresa) no toca el estado local
- [x] Tests: 11/11 nuevos pasando (79/79 en total)

### Etapa 7 — Métricas de negocio (Requerimiento 6, parcial) — COMPLETA (2026-09-04)
- [x] Wrapper `/statistics/general` (ya estaba desde Etapa 1) expuesto vía `GET /metricas/generales`,
      con nombres de campo traducidos (`pedidosHoy`, `ingresoTotal`, etc.) — módulo deliberadamente
      liviano (sin services/dto/repository), mismo criterio que `catalogos`: es un proxy de solo lectura
      sin lógica de negocio ni persistencia
- [x] Los montos viajan como string, nunca se castean a float (consistente con la regla #5 de las
      directrices)
- [x] `avisoImportante` agregado explícitamente en cada respuesta aclarando que esto NO es el saldo real
      de wallet (ver ADR-003 y sección 10.2 del doc del proveedor)
- [x] Refactor DRY de paso: se centralizó la construcción cacheada de `RocketfyClient`, que ya se estaba
      repitiendo en `pedidos`, `productos` y `app.py`, en `src/integrations/rocketfy/factory.py::get_rocketfy_client`
- [x] Tests: 2/2 nuevos pasando (81/81 en total)

**Con esto se completan las 7 etapas del plan maestro original de Fase 1.** Quedan pendientes solo las
etapas transversales (8: Hardening, 9: Documentación) y los 8 puntos de la sección 5.

### Etapa 8 — Hardening — **POSPUESTA por decisión del usuario (2026-09-07)**
> El usuario decidió dejarla pendiente para retomarla más adelante y
> avanzar ahora con la Fase 2 (Frontend). No se pierde de vista: sigue aquí
> tal cual, sin empezar.
- [ ] Logging estructurado (JSON) correlacionado por order_id/shopify_order_id
- [ ] Alerta si el webhook se autodesactiva (10 fallos acumulados)
- [ ] Rate-limit saliente / circuit breaker simple
- [ ] Runbook de incidentes

### Etapa 9 — Documentación — **POSPUESTA por decisión del usuario (2026-09-07)**
> Misma decisión que la Etapa 8: pendiente, no cancelada.
- [ ] README del backend
- [ ] Checklist de puesta en marcha mapeado al Anexo D del proveedor
- [ ] Este archivo mantenido al día

---

## Fase 2 — Frontend (plan maestro propuesto, EN CURSO desde 2026-09-07)

> Con la Fase 1 (backend) construida y validada contra Rocketfy real
> (entradas 0.0.13 a 0.0.15), el usuario decidió posponer las etapas
> transversales 8 y 9 y arrancar la Fase 2. Objetivo de esta fase: dar
> cumplimiento real a la directriz 17 (trazabilidad total visible) y
> resolver el pendiente #2 (alertas internas) con un dashboard, en vez de
> un canal de notificación aparte. El frontend consume la API del backend
> ya construido — no se toca el backend salvo en la Etapa 1 (autenticación).

**Stack DEFINIDO (2026-09-07, corrige la propuesta anterior de este mismo
documento):** el usuario ya había indicado su preferencia de stack al
inicio de esta conversación (Next.js/React/TypeScript/Tailwind/Supabase),
pero esa parte se perdió al resumirse una conversación muy larga y esta
sección llegó a proponer React+Vite+MUI por error. Corregido con el propio
usuario. Stack real:

- **Next.js 16 (App Router) + React 19 + TypeScript** — el usuario ya
  tiene experiencia reciente con estas versiones en otro proyecto propio.
- **Tailwind CSS v4** para estilos.
- **shadcn/ui** (componentes accesibles sobre Radix; trae incluidos
  `class-variance-authority` y `tailwind-merge`, no hace falta agregarlos
  sueltos) + **Lucide React** para iconos.
- **Framer Motion** para transiciones/microinteracciones, **Sonner** para
  notificaciones tipo toast.
- **Supabase Auth** para el login del dashboard — resuelve de forma
  natural el hallazgo/pendiente #11 (el backend no tiene autenticación),
  ya que Supabase ya se usa para la base de datos: el backend Flask solo
  necesita verificar el token que Supabase emite, sin construir un sistema
  de login propio.
- ESLint, npm. Turbopack (bundler propio de Next 16) en vez de configurar
  Webpack aparte.
- Despliegue en Vercel — se retoma en la Etapa 7, no bloquea nada ahora.
- **NO se usa** por ahora (son de otro tipo de proyecto del usuario, no
  aplican a un dashboard operativo): @dnd-kit, Google Gemini, AssemblyAI,
  Creatomate, FFmpeg. `jsPDF`/`xlsx` quedan anotados como candidatos
  futuros (ej. exportar pedidos a Excel) si hace falta más adelante.
- **Diseño:** paleta neutra blanco/negro con acentos a definir por Claude;
  UI/UX es una prioridad explícita del usuario en cada pantalla, no un
  detalle final. El proyecto de ejemplo `MASS/FRONTEND` sirve solo como
  referencia de lógica de componentes y consumo de API — su diseño
  visual NO es una referencia a seguir (palabras del usuario).

### Convenciones de Arquitectura del Frontend
> Definidas el 2026-09-07 a pedido explícito del usuario, ANTES de la
> Etapa 1, para que las Etapas 1-7 no repitan variables/decisiones ni
> diverjan en cómo se organiza el código. Igual que la sección 1 hace para
> el backend, esto es la regla a seguir, no una sugerencia puntual.

- **`src/app/`** — rutas (App Router). Una carpeta = una ruta. Un
  componente usado SOLO por esa página vive junto a ella, en una
  subcarpeta `_components/` (colocación) — no en `src/components/`.
- **`src/components/`** — componentes compartidos por más de una página
  (sidebar, header, `StatusBadge`, etc.). Los primitivos de shadcn viven
  en `src/components/ui/` y se tratan como generados: se regeneran con
  `npx shadcn add <componente>`, no se editan a mano salvo necesidad real.
- **`src/config/`** — metadata/configuración de todo el sitio
  (`site.ts`: nombre, título, navegación). Cualquier texto o dato que
  aparezca en más de un archivo se define acá una sola vez, nunca se
  repite entre `layout.tsx`, sidebar, header, etc.
- **`src/lib/`** — utilidades puras y mapeos de dominio, sin componentes
  React: `api.ts` (cliente HTTP hacia el backend — ninguna página hace
  `fetch` suelto), `estados.ts` (colores/labels de `estado_local` y
  `status_id` de Rocketfy — espejo intencional del backend, ver Etapa 0),
  `utils.ts` (generado por shadcn, `cn()`).
- **`src/hooks/`** — hooks compartidos entre páginas.
- **`src/types/`** — tipos TypeScript del dominio (Pedido, WebhookEvent,
  etc.), creados a medida que cada etapa los necesita, reflejando
  exactamente los `schemas.py` del backend correspondiente para que
  ambos lados nunca diverjan en forma.
- **Diseño:** fuente y colores se definen una sola vez en
  `src/app/globals.css` (tokens de shadcn + paleta de estados semánticos
  success/warning/danger/info/neutral) y `src/lib/estados.ts` (qué estado
  usa qué color). Ninguna página elige un color o una fuente "a mano" —
  siempre a través de estos tokens o de `<StatusBadge />`.

### Etapa 0 — Scaffolding del frontend — COMPLETA (2026-09-07)
- [x] Proyecto Next.js 16.3.4 (App Router) + React 19.2 + TypeScript + Tailwind v4 en `PROYECTECOM/frontend/`
- [x] shadcn/ui inicializado (estilo `radix-nova`, `baseColor: neutral` — blanco/negro por defecto)
- [x] Lucide React, Framer Motion, Sonner instalados; componentes base: sidebar, card, sonner, sheet, tooltip, avatar, dropdown-menu, badge, skeleton, separator, input
- [x] Cliente HTTP mínimo hacia el backend vía `NEXT_PUBLIC_API_URL` (`src/lib/api.ts`)
- [x] Layout base: sidebar colapsable con navegación a las 5 secciones futuras + botón "Nuevo pedido", header con breadcrumb simple
- [x] `.env.example` y `.env.local` propios del frontend
- [x] Página de inicio con indicador de salud del backend en vivo (`src/components/backend-status.tsx`) + tarjetas de acceso a cada sección (con su placeholder "Próximamente")
- [x] `npm run lint` y `npm run build` limpios
- [x] **Sistema de diseño centralizado (2026-09-07, a pedido explícito del usuario antes de la Etapa 1):**
      fuente Poppins (`src/app/layout.tsx`, variable `--font-sans`), paleta
      de estados semánticos success/warning/danger/info/neutral
      (`src/app/globals.css` + `src/lib/estados.ts`, espejo intencional de
      `estado_local` y `RocketfyStatus` del backend), config del sitio
      centralizada (`src/config/site.ts` — nombre, metadata, navegación,
      nada repetido entre `layout.tsx`/sidebar/header), y componente
      reutilizable `<StatusBadge />`. Ver subsección "Convenciones de
      Arquitectura del Frontend" más abajo. De paso se corrigió un bug del
      generador de shadcn: `--font-sans: var(--font-sans)` era
      autorreferente y nunca aplicaba la fuente de `next/font` — Poppins
      quedó nombrada `--font-sans` directamente para que sí conecte.
- [x] **Hallazgo y arreglo en el camino:** `flask-cors` estaba en `requirements.txt` pero nunca se activó en `app.py` — el navegador habría bloqueado silenciosamente las llamadas del frontend por CORS aunque `curl` las mostrara funcionando (curl no aplica esa política, solo el navegador). Se agregó `CORS(app, origins=[settings.frontend_origin])`, con `FRONTEND_ORIGIN` nuevo en `.env`/`.env.example` (default `http://localhost:3000`). Verificado con curl simulando el header `Origin` real: responde `Access-Control-Allow-Origin` correctamente. 84/84 tests del backend siguen pasando.
- [ ] **No verificado visualmente en un navegador real** — Claude no tiene una herramienta de navegador en este entorno; toda la verificación fue con `curl` (código 200 en las 6 rutas, contenido esperado en el HTML) y build/lint limpios. Falta que el usuario confirme abriendo `http://localhost:3000` que el indicador de estado pasa a "Backend conectado" y que el diseño se ve bien.

### Etapa 1 — Autenticación con Supabase Auth — COMPLETA (2026-09-07, pendiente #11 resuelto)
- [x] Pantalla de login en el frontend (`src/app/login/page.tsx`), correo + contraseña, usando `@supabase/ssr` + `@supabase/supabase-js`
- [x] `src/proxy.ts` (Next.js 16 renombró `middleware.ts` → `proxy.ts`, y la función `middleware` → `proxy` — ver `node_modules/next/dist/docs/.../upgrading/version-16.md`) refresca la sesión y redirige a `/login` si no hay usuario, o a `/` si ya hay sesión y se visita `/login`
- [x] Layout reestructurado con un route group `(dashboard)` para que el shell (sidebar/header) NO se muestre en `/login`
- [x] `<UserMenu />` en el header: correo del usuario + botón "Cerrar sesión"
- [x] `src/lib/api.ts` adjunta el token de sesión (`Authorization: Bearer ...`) en cada llamada al backend
- [x] Backend: `src/config/supabase_auth.py::verificar_token()` valida el token contra `${SUPABASE_URL}/auth/v1/user` (sin verificar JWT localmente — una sola llamada HTTP, suficiente para un panel de un solo usuario; documentado como cambiable a JWKS si el volumen lo justifica)
- [x] `before_request` global en `app.py` — 401 si falta el token o Supabase lo rechaza, en TODA ruta interna
- [x] El webhook de Rocketfy (`/webhooks/*`) y `/health` quedan exentos (el webhook sigue con su propio token en la URL — Rocketfy no puede loguearse)
- [x] `flask-cors` actualizado para permitir el header `Authorization`, y para dejar pasar siempre el preflight `OPTIONS` (nunca trae ese header)
- [x] 7 tests nuevos (`tests/unit/config/test_supabase_auth.py`, `tests/unit/test_app_auth.py`) + `tests/conftest.py` con el helper `mock_login_ok()` reutilizable para futuros tests de rutas. 91/91 en total.
- [x] Verificado con curl: sin token → 401; `/health` → 200 sin token; `GET /` sin sesión → redirige a `/login` (307); `/login` → 200 directo.
- [x] Usuario creado por el propio usuario en el dashboard de Supabase y **login confirmado funcionando en el navegador real** (2026-09-07).
- [x] **Decisión consciente, no un olvido:** el login NO restringe por correo específico a nivel de código — solo exige un token válido de Supabase, de quien sea. Hoy la única barrera es que solo el usuario tiene acceso al dashboard de Supabase para crear cuentas nuevas. Se le explicó esta distinción explícitamente y decidió que es suficiente por ahora ("no hay necesidad de que agregues esa validación de solo mi correo"). Si en el futuro se quiere una garantía a nivel de código (rechazar cualquier correo que no sea el admin), es un cambio de dos líneas en `verificar_token`/`before_request` — no se hizo porque el usuario no lo pidió.

### Etapa 2 — Dashboard de Pedidos — COMPLETA (2026-09-07)
- [x] **Backend nuevo** (no existía forma de listar/ver pedidos hasta ahora,
      solo crear/modificar/rechazar): `GET /pedidos` (paginado, filtrable
      por `estado`) y `GET /pedidos/<id_local>` (detalle completo). Nuevos
      `PedidoResumenDTO`/`PedidoDetalleDTO` + schemas + `PedidoRepository.
      listar()/contar()`. Verificado contra la base de datos real (no solo
      el repositorio falso de los tests) con los 2 pedidos de prueba de la
      Etapa 4. 12 tests nuevos, 96/96 en total.
- [x] Listado de pedidos (`/pedidos`): tabla con cliente, teléfono,
      ubicación, total y `<StatusBadge>` de estado; filtro por estado,
      paginación simple (20 por página)
- [x] Vista de detalle (`/pedidos/[idLocal]`): todos los datos de entrega,
      líneas de producto, fechas, estado local Y estado de Rocketfy
      (cuando existe) lado a lado
- [x] **Mensaje de error destacado en rojo cuando el pedido lo tiene**
      (ej. el hallazgo del mínimo de $10 de la Etapa 1 de Fase 1) — es el
      núcleo de la directriz 17: lo primero que se ve es qué necesita
      atención
- [x] Acciones manuales: modificar datos de contacto/entrega (diálogo) y
      rechazar (con confirmación, porque es irreversible contra Rocketfy real)
- [x] `npm run lint`/`build` limpios
- [ ] **No verificado visualmente en un navegador real** (misma limitación
      de siempre: sin herramienta de navegador). Falta que el usuario abra
      `/pedidos` y confirme que la tabla, el filtro, el detalle y las dos
      acciones funcionan como se espera.
- [x] ~~Nota: el diálogo de "Modificar" usaba texto libre para cantón/provincia~~ — **RESUELTO 2026-09-07.** Se agregó `<UbicacionSelector />` (`src/components/ubicacion-selector.tsx`), un selector en cascada Provincia → Cantón reutilizable, consumiendo `GET /catalogos/ubicaciones` (ya existente, respaldado por el CSV del proveedor). **Análisis hecho antes de implementar** (pedido explícito del usuario: CSV vs. subir el catálogo a la base de datos): se descartó migrar a Supabase — es información que casi nunca cambia, se lee mucho (cada creación/modificación de pedido) y nunca se escribe desde el sistema; ese perfil favorece un archivo en memoria sobre una consulta a base de datos, y evita mantener dos copias del mismo catálogo. Coincide con ADR-002 (persistencia mínima). El selector queda listo para reutilizarse también en la Etapa 6 (creación manual de pedido).

### Etapa 3 — Incidencias y Alertas — COMPLETA (2026-09-07, pendiente #2 en gran parte resuelto)
- [x] **Hallazgo real corregido:** `StockWatcherService` detectaba stock
      bajo y cambio de precio desde la Etapa 5 de Fase 1, pero solo lo
      mandaba al log de servidor — nadie fuera de la terminal podía verlo.
      Nueva tabla `alertas_stock` (migración `003_alertas_stock.sql`,
      aplicada localmente y en el historial oficial de Supabase) +
      `StockWatcherRepository.guardar_alerta()`, llamado desde
      `_revisar_uno()` junto al log existente (no se quitó el log).
- [x] **Backend nuevo:** módulo `src/routes/incidencias/` (repository +
      service + schemas + controllers, mismo patrón inyectable que
      `pedidos`/`productos` — no el minimalismo de `catalogos`/`metricas`,
      porque este sí toca nuestra propia base de datos y necesita poder
      probarse con un repositorio falso). `GET /incidencias/eventos`
      (por defecto solo `NOVEDAD`/`DEVUELTO_EN_TRANSITO` — el mismo
      criterio que ya usaba `WebhookService.EVENTOS_PARA_EQUIPO`,
      reutilizado en vez de duplicado; `?todos=true` trae el historial
      completo) y `GET /incidencias/stock` (filtrable por SKU).
- [x] Verificado contra la base de datos real: los 2 eventos reales de la
      Etapa 4 de Fase 1 aparecen correctamente con `?todos=true` (ninguno
      es NOVEDAD/DEVUELTO_EN_TRANSITO, así que el filtro por defecto
      correctamente los excluye).
- [x] 9 tests nuevos, 105/105 en total.
- [x] Frontend `/incidencias`: dos pestañas — **Eventos de pedidos** (con
      casilla para ver todo el historial, no solo lo urgente; el ID del
      pedido enlaza a su detalle) y **Alertas de stock y precio**
      (filtrable por SKU, con debounce). Ambas con paginación.
- [x] `npm run lint`/`build` limpios.
- [ ] **No verificado visualmente en un navegador real** (sin herramienta
      de navegador). Además, como todavía no hay ningún SKU monitoreado
      en producción (Etapa 4 aún no construida), la pestaña de alertas de
      stock estará vacía hasta que eso exista — es el comportamiento
      correcto, no un bug.

### Etapa 4 — Catálogo y Monitoreo de Stock — COMPLETA (2026-09-07)
- [x] **Sin cambios de backend** — a diferencia de las Etapas 2 y 3, todo lo
      necesario ya existía desde la Etapa 5 de Fase 1 (`GET /productos`,
      `GET /productos/<id>`, `GET/POST /productos/monitoreados`,
      `DELETE /productos/monitoreados/<sku>`). Esta etapa fue 100% frontend.
- [x] `/catalogo`, pestaña **Catálogo**: búsqueda con debounce contra el
      catálogo real de Rocketfy (1884 productos), paginada, con botón
      "Monitorear" por fila
- [x] `/catalogo`, pestaña **SKUs monitoreados**: tabla con umbral, último
      stock/precio conocido y estado activo/inactivo; "Editar umbral"
      (reutiliza el mismo endpoint POST, que hace upsert) y "Quitar"
      (soft-delete, `activo=false`)
- [x] Verificado de punta a punta contra Rocketfy y la base de datos real:
      buscar → monitorear → listar → quitar, con un SKU real
      (`MASCARAPROTECCION`) — se dejó desactivado al terminar, no quedó
      nada de prueba activo en el monitoreo real del usuario
- [x] `npm run lint`/`build` limpios; 105/105 tests del backend sin cambios
- [ ] **No verificado visualmente en un navegador real** (sin herramienta
      de navegador). La pestaña de monitoreados mostrará "último stock:
      —" para cualquier SKU nuevo hasta que corra el job `stock_watcher`
      al menos una vez (cada 60 min, o al reiniciar el proceso `__main__`)
      — comportamiento esperado, no un bug.

### Etapa 5 — Métricas de Negocio — COMPLETA (2026-09-07)
- [x] **Sin cambios de backend** — `/metricas/generales` ya existía desde
      la Etapa 7 de Fase 1. 100% frontend, la etapa más chica de la Fase 2.
- [x] `/metricas`: aviso destacado (no es saldo de wallet) siempre visible
      arriba de todo, con el texto exacto que manda el backend; tarjetas
      agrupadas en "Hoy" (pedidos, confirmados, monto total, ingreso) y
      "General" (ingreso confirmado/total/en tránsito/retenido por
      novedad, costo de productos en tránsito)
- [x] **Hallazgo real:** Rocketfy manda `0` (número) en vez de `"0.00"`
      cuando un campo de dinero no tiene movimiento — inconsistencia de su
      propia API, no nuestra (los demás casos sí mandan string con 2
      decimales). No rompe nada (el schema ya trata todo como texto), pero
      se veía "$0" en vez de "$0.00" — se corrigió el formato SOLO para
      mostrar (`Number(valor).toFixed(2)`, nunca para calcular ni guardar,
      respetando la directriz 5 de nunca tratar dinero como float para
      lógica real).
- [x] Verificado contra Rocketfy real: `orders_today=2`,
      `orders_total_amount_today="13.00"` (coincide con los 2 pedidos de
      prueba ya conocidos, $1.00 + $12.00 → total histórico distinto pero
      el de "hoy" cuadra).
- [x] `npm run lint`/`build` limpios.
- [ ] **No verificado visualmente en un navegador real** (sin herramienta de navegador).

### Etapa 6 — Formulario de creación manual de pedido — COMPLETA (2026-09-07)
- [x] **Sin cambios de backend** — `POST /pedidos` ya existía desde la
      Etapa 3 de Fase 1.
- [x] `/pedidos/nuevo`: ID interno generado automáticamente (segundos desde
      época, mismo criterio que `tools/rocketfy_order_smoke_test.py`) — el
      usuario nunca tiene que inventar un identificador
- [x] Reutiliza `<UbicacionSelector />` (Etapa 2) para cantón/provincia —
      evita por diseño el error de la sección 4.2 del doc del proveedor
      (cantón mal escrito que falla recién al confirmar, no al crear)
- [x] Líneas de producto agregadas por búsqueda real contra el catálogo
      de Rocketfy (diálogo reutilizable, mismo patrón que la Etapa 4) en
      vez de escribir el SKU a mano — evita el riesgo documentado de que
      un SKU con typo se descarte en silencio (`PedidoIncompletoError`)
- [x] Aviso del recaudo mínimo COD ($10) en vivo mientras se escribe el total
- [x] **Manejo de errores pensado para no perder al usuario:** si la
      creación falla pero de todas formas quedó un pedido real en
      Rocketfy (confirmación rechazada), el formulario lo detecta
      (reintenta un `GET` del pedido) y lleva al usuario a su detalle en
      vez de dejarlo varado en el formulario sin saber qué pasó
- [x] **Hallazgo real importante durante la verificación:** Rocketfy exige
      un mínimo de confirmación que NO es fijo — es "valor de productos +
      costo de envío", calculado por ellos internamente (con un pedido de
      $15 en un producto de ~$11.50, el mínimo real resultó ser $18.47).
      Cumplir el mínimo fijo de $10 NO garantiza que la confirmación pase.
      Anotado como duda #14 para el proveedor y reforzado en el pendiente
      #5 (sin cotizador de flete, este mínimo real es imposible de
      calcular de antemano). El aviso en pantalla se ajustó para ser
      honesto sobre esto — no promete que $10 alcance.
- [x] Verificado de punta a punta contra Rocketfy real dos veces: (1) un
      pedido de $15 que Rocketfy rechazó por el mínimo real más alto
      (quedó `creado` con el mensaje de error, exactamente el
      comportamiento que el formulario está preparado para manejar); (2)
      un pedido de $25 que se confirmó sin problema. Ambos rechazados
      (limpiados) al terminar la prueba.
- [x] `npm run lint`/`build` limpios.
- [ ] **No verificado visualmente en un navegador real** (sin herramienta de navegador).

### Etapa 7 — Pulido y despliegue conjunto
- [ ] Retomar aquí las Etapas 8 y 9 de la Fase 1 (pospuestas arriba)
- [ ] Elegir hosting real para backend + frontend (con calma, sin apuro — palabras del usuario)
- [ ] Reemplazar la URL temporal del webhook (pendiente #6) por la definitiva

### Fase 3 — Bot Conversacional de WhatsApp (AzoShop / "Victoria") — EN DESARROLLO
> **Nota de nombre:** la asesora virtual se llamaba tentativamente "Sofía"
> en la planificación inicial (`docs/BotPlanifiacion.md`) — el nombre
> definitivo, confirmado por Claude web al entregar los prompts de
> desarrollo de la Etapa 3.1, es **Victoria**. Se actualiza acá; el
> documento de planificación original queda con el nombre viejo, no se
> reescribe.
Anotada como fase futura el 2026-09-06, arrancó formalmente el
2026-09-15. Es una fase completa aparte, posterior al frontend, no una
tarea suelta de la Fase 1:

- Un bot con IA conversa con el cliente final por WhatsApp: da datos del
  producto, responde dudas, y **recopila los datos necesarios para crear el
  pedido** (nombre, teléfono, dirección, cantón/provincia, qué compra).
- Con los datos recopilados, el bot dispara el flujo que ya existe hoy:
  crear pedido → confirmar → pedir confirmación explícita al cliente →
  avisarle de novedades — reutilizando `PedidoService`, no reemplazándolo.
- Depende de dos decisiones aún abiertas: el canal real de envío de
  WhatsApp (pendiente #1 — **ya resuelto en la planificación: WhatsApp
  Cloud API de Meta, directo, sin BSP**) y el mecanismo de alertas
  internas (pendiente #2) — este bot probablemente termine siendo la
  implementación concreta del pendiente #1.
- Sujeta a la directriz 17: toda la actividad del bot (qué preguntó, qué
  respondió el cliente, qué pedido generó, cualquier error) debe quedar
  visible en el dashboard del frontend para intervención humana.

**Flujo de trabajo de esta fase (distinto a las anteriores):** el usuario
está orquestando el diseño de arquitectura del bot con una instancia de
Claude en el chat web ("Claude web"), y usa esta sesión (Claude Code, con
ejecución real) como ejecutor/documentador del lado de PROYECTECOM. El
usuario actúa de intermediario humano entre ambas instancias.

- **2026-09-15:** Claude web pidió, a través del usuario, documentación
  completa del proyecto existente antes de diseñar la arquitectura del
  bot. Se creó `docs_para_claude/` (7 archivos: estructura del proyecto,
  flujo con el distribuidor, contrato de input/output, base de datos,
  variables de entorno, estado actual, preguntas abiertas respondidas
  contra el código real) para que Claude web pueda diseñar sin
  re-descubrir el proyecto ni pisar lo ya construido.
- Se encontró que ya existe `docs/BotPlanifiacion.md` — un documento de
  planificación bastante detallado de una sesión previa (marca AzoShop,
  bot "Sofía", 4 flujos de conversación definidos, decisión ya tomada de
  usar WhatsApp Cloud API directo sin BSP, estructura de datos propuesta
  para pedidos/leads, señales de estado que devolvería la IA). Quedó
  referenciado desde `docs_para_claude/06_estado_actual.md` para no
  duplicar información ni que se pierda de vista.
- Aclaración importante documentada para evitar confusión: la tabla
  `pedidos` ya existente está moldeada específicamente para el contrato
  con Rocketfy — el bot necesita su propio modelo de datos nuevo
  (conversaciones/leads), no debe reutilizar ni reestructurar esa tabla.
- Preguntas abiertas planteadas al usuario (ver entrada de versión
  correspondiente): dónde vive el bot (¿mismo backend Flask o servicio
  aparte?), si usa el mismo proyecto de Supabase, y qué LLM va a usar
  Victoria — resueltas el mismo día: mismo backend Flask (módulo nuevo,
  acceso directo en Python a `PedidoService`), mismo proyecto de Supabase
  (tablas propias, sin tocar `pedidos`), LLM = Claude.

### Etapa 3.1 — Infraestructura base del bot (sin IA todavía) — COMPLETA (2026-09-17 a 2026-09-26)
Encargo detallado recibido de Claude web (prompt de desarrollo completo,
6 tareas). Objetivo explícito: construir el canal de comunicación
completo — webhook, cola en background, cliente de envío — **sin lógica
de IA todavía**, para confirmar que el canal funciona antes de agregar a
Claude encima (eso es la Etapa 3.2).

**Decisiones de arquitectura y su razonamiento:**

- **Worker en background (thread + cola), separado del ciclo
  request/response del webhook.** Igual principio que el webhook de
  Rocketfy (responder rápido, nunca fallar), pero acá el motivo es
  distinto: Meta cancela y reintenta si no recibimos con 200 en ~5
  segundos, y generar+enviar una respuesta (en Fase 3.2, con la llamada a
  Claude de por medio) puede tardar 5-15 segundos. El contrato
  (encolar una tarea, un consumidor la procesa aparte) queda listo para
  migrar a Celery+Redis sin tocar el código que llama a `encolar()`, si
  algún día hace falta escalar a más de un proceso.
- **Tablas nuevas (`conversaciones`, `mensajes`, `leads`) totalmente
  separadas de `pedidos`.** `pedidos` sigue siendo exclusivamente el
  contrato con Rocketfy (Fase 1) — el bot nunca la toca ni la reestructura.
  Solo cuando un lead llega a `estado='listo_para_despacho'` se llama a
  `PedidoService.crear_y_confirmar()` (Etapa 3.2, todavía no implementado)
  y recién ahí se completan `leads.id_pedido_local`/`id_pedido_rocketfy`.
- **`WhatsAppClient` nuevo**, mismo patrón que `RocketfyClient` (cliente
  HTTP dedicado, excepciones tipadas `WhatsAppAuthError`/
  `WhatsAppRequestError`/`WhatsAppBusinessError`) pero **sin reintento
  automático ante 5xx** — a diferencia de Rocketfy, reintentar un envío de
  mensaje a un cliente real podría duplicarlo.
- **Desvío consciente #1 (documentado en el propio código,
  `src/app.py`):** se pidió arrancar el `BotWorker` "igual que APScheduler
  se inicia hoy" — pero `start_scheduler()` solo corre bajo
  `if __name__ == "__main__"`, nunca bajo `flask run`, que es exactamente
  el comando que pide la Tarea 5 para la prueba end-to-end. Arrancarlo
  igual habría dejado el worker sin arrancar nunca durante la prueba. Se
  arrancó en cambio dentro de `create_app()`, con `get_bot_worker()`
  cacheado (`lru_cache`) y `BotWorker.iniciar()` hecho idempotente a
  propósito — necesario además porque `src/app.py` ya ejecuta
  `create_app()` dos veces en el mismo proceso (la línea suelta `app =
  create_app()` al final del archivo, sumada a la que hace el factory de
  Flask), algo preexistente del proyecto, no introducido acá.
- **Desvío consciente #2:** el worker de la Tarea 4 tal como se
  especificó guardaba la respuesta del bot con `conversacion_id=None`
  ("TODO Fase 3.2"). La columna `mensajes.conversacion_id` es NOT NULL —
  guardar con `None` habría roto con un error de base de datos justo en
  la prueba de la Tarea 5. Se resolvió pasando el `conversacion_id` ya
  resuelto (creado o reutilizado) desde `WebhookService` hacia el worker
  en el momento de encolar (`TareaRespuestaDTO`), en vez de dejarlo como
  pendiente — ya no hace falta resolverlo en Fase 3.2, quedó bien desde
  ahora.
- **No se agregaron tests unitarios directos de los repositorios**
  (`ConversacionRepository`/`MensajeRepository`) — mismo patrón que el
  resto del proyecto (ningún repositorio del proyecto tiene tests
  directos; se prueban indirectamente vía tests de servicio con
  repositorios falsos en memoria, y se validan de verdad corriendo contra
  Supabase real). Se hizo esa validación real manualmente (ver abajo).
- **Hallazgo real de seguridad, documentado y NO resuelto a propósito en
  esta etapa:** a diferencia del webhook de Rocketfy (que sí tiene su
  propio token de autenticación), el POST de mensajes de WhatsApp no
  verifica la firma `X-Hub-Signature-256` que Meta manda (HMAC-SHA256 del
  cuerpo con el App Secret) — no se implementó porque el App Secret no
  fue parte de las variables pedidas en la Tarea 1. Hoy cualquiera que
  descubra la URL del webhook podría mandarle un payload falso haciéndose
  pasar por Meta. No es grave mientras la URL sea un túnel temporal que
  cambia todo el tiempo, pero **hay que resolverlo antes de un despliegue
  real** (agregar `WHATSAPP_APP_SECRET` y verificar la firma).

**Variables de entorno agregadas** (`backend/.env` / `.env.example`,
`src/config/settings.py` — ver el detalle completo, sin valores, en
`docs_para_claude/05_variables_entorno.md`):

| Variable | Fail-fast | Para qué |
|---|---|---|
| `WHATSAPP_API_TOKEN` | Sí | Token de acceso a la Cloud API (llamadas salientes) |
| `WHATSAPP_PHONE_NUMBER_ID` | Sí | Identifica el número de WhatsApp desde el que se envía |
| `WHATSAPP_WEBHOOK_VERIFY_TOKEN` | Sí | Token propio para el handshake GET de verificación del webhook |
| `WHATSAPP_WABA_ID` | No | ID de la cuenta de WhatsApp Business |
| `ANTHROPIC_API_KEY` | No | Vacío a propósito — se usa recién en la Etapa 3.2 |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | No | Vacíos a propósito — notificación al dueño, fase posterior |

**Tablas creadas** (migraciones `004_conversaciones.sql`,
`005_mensajes.sql`, `006_leads.sql`, aplicadas local y en el historial
oficial de Supabase — ver esquema completo en
`docs_para_claude/04_base_de_datos.md`):

- **`conversaciones`** — una fila por número de teléfono. Guarda el
  origen (`directo`/`fep`/`web_formulario`), la ventana de 72h si vino de
  un anuncio Click-to-WhatsApp, y el estado de la conversación.
- **`mensajes`** — cada turno (cliente/bot/humano), con índice único
  parcial sobre `wamid` (`where wamid is not null`, ya que los mensajes
  del bot no siempre tienen uno) para garantizar idempotencia.
- **`leads`** — los datos de venta que el bot va recopilando, separada de
  `conversaciones` porque una conversación puede no llegar nunca a
  convertirse en un lead calificado.

**Módulos nuevos:**
- `src/integrations/whatsapp/` — `WhatsAppClient` (enviar_texto,
  enviar_plantilla, marcar_como_leido), excepciones tipadas, factory
  cacheada (mismo patrón que `rocketfy/factory.py`).
- `src/routes/whatsapp/` — blueprint del webhook (`GET`/`POST
  /webhooks/whatsapp`), `WebhookService` (idempotencia por wamid,
  detección de FEP, guardar mensaje, marcar leído best-effort, encolar
  respuesta), `BotWorker` (thread + cola en background), repositorios de
  `conversaciones`/`mensajes`.

**Tests:** 24 nuevos (9 del cliente de WhatsApp con `responses`, 15 del
webhook/servicio con repositorios falsos y sustituyendo `threading.Thread`
por un doble síncrono en los tests del controller). **129/129 tests en
total, todos pasando.**

**Prueba end-to-end (Tarea 5) — resultado real, con varios obstáculos en
el camino que vale la pena dejar anotados:**

1. Túnel público: se usó `cloudflared` en vez de `ngrok` (ya estaba
   instalado de una prueba anterior con el webhook de Rocketfy, sin
   necesidad de cuenta). **Los túneles "quick" de cloudflared no tienen
   garantía de actividad** — se cayeron y hubo que renovarlos varias
   veces a lo largo de esta etapa (a veces el proceso seguía vivo pero
   Cloudflare dejaba de resolver el túnel).
2. **El proyecto de Supabase se pausó por inactividad** (plan gratuito)
   a mitad de esta etapa — hubo que esperar a que el usuario lo
   reactivara desde su dashboard antes de poder aplicar las migraciones.
   Se verificó con `SELECT count(*)` que no se perdió ningún dato de la
   Fase 1 al reactivarlo (4 pedidos de prueba, intactos).
3. **El token de acceso de WhatsApp (`WHATSAPP_API_TOKEN`) se regeneró
   varias veces** durante la prueba — Meta da por defecto un token de
   corta duración (vence en 24h) salvo que se genere uno explícitamente
   marcado como permanente. Cada vez que venció hubo que actualizar
   `.env` y reiniciar el backend.
4. **Bloqueo de red inesperado:** en un momento el túnel dejó de conectar
   por completo (no un problema de propagación, sino que `cloudflared`
   reportaba que la salida UDP/TCP hacia Cloudflare estaba bloqueada). La
   causa: el usuario se había conectado a una red wifi pública de una
   cafetería, que bloquea ese tipo de tráfico por política de seguridad.
   Se resolvió cambiando a otra red.
5. **Hallazgo importante sobre el modo de la app de Meta:** mientras la
   app de Meta no esté publicada, **solo se entregan webhooks de prueba
   disparados desde el propio panel de Meta** — ningún mensaje real
   (incluso de números ya agregados como destinatarios de prueba) llega
   al webhook. Esto explica por qué varios intentos de mandar un mensaje
   real de WhatsApp nunca generaron ningún POST en los logs, pese a tener
   todo lo demás bien configurado (URL verificada, campo `messages`
   suscrito, número en la lista de prueba). Publicar la app requiere
   verificación de negocio + revisión de Meta (días o semanas) — se
   decidió, con el usuario, NO publicarla todavía solo para esta prueba,
   y usar en cambio el botón de prueba del panel de Webhooks.
6. **Resultado real de la prueba de webhook (vía el botón "Probar" del
   panel de Meta):** llegó un `POST /webhooks/whatsapp` real de Meta,
   respondido con 200 de inmediato. El payload de prueba (`wamid
   ABGGFlA5Fpa`, texto `"this is a text message"`, contacto de ejemplo
   `16315551181`) se parseó correctamente. Se verificó en Supabase que
   quedaron guardadas 2 filas reales: la conversación
   (`origen=directo`) y el mensaje del cliente. El bot generó y guardó su
   respuesta placeholder correctamente en `mensajes` (`rol=bot`).
7. **Dos llamadas salientes fallaron, correctamente y sin tumbar nada**
   (`marcar_como_leido` con `(#131009) Parameter value is not valid`, y
   `enviar_texto` con `(#131030) Recipient phone number not in allowed
   list`) — ambas esperables porque el payload de prueba de Meta usa un
   `wamid` y un número de teléfono inventados, no reales. El manejo de
   errores diseñado (try/except alrededor de `marcar_como_leido`, y el
   `try/except` general del worker) funcionó exactamente como se
   pensó: quedó registrado en el log, no se perdió el mensaje del
   cliente ya guardado, y el worker siguió vivo para la siguiente tarea.

**Estado al cerrar la Etapa 3.1:**
- ✅ Funciona al 100%: recepción del webhook, verificación GET,
  idempotencia por wamid, detección de origen FEP, persistencia de
  conversación/mensajes, cola en background, manejo de errores sin
  caídas. Validado con un evento real de Meta (vía el botón de prueba),
  no solo con mocks.
- ⚠️ Parcial a propósito: el envío real de mensajes y el marcado de
  leído solo se probaron contra datos de prueba simulados — no se ha
  confirmado el intercambio con un número de WhatsApp real todavía (
  requiere que el usuario complete la lista de destinatarios de prueba
  permitidos, o publicar la app más adelante).
- 🔴 Pendiente, no es parte de esta etapa: firma `X-Hub-Signature-256`
  sin verificar (ver hallazgo de seguridad arriba). Lógica de IA
  (Claude) — es exactamente el objetivo de la Etapa 3.2.

### Etapa 3.2 — Victoria con un LLM desacoplado como cerebro conversacional — COMPLETA (2026-09-26)
Encargo de 10 tareas recibido de Claude web. Objetivo: reemplazar el
mensaje fijo de prueba de la Etapa 3.1 por Victoria pensando y vendiendo
de verdad con un LLM, resolver la persistencia de la cola (pendiente #18)
y dejar la base de conocimiento de productos + notificaciones de
escalado por Telegram.

**Decisión de arquitectura central: el LLM está desacoplado del resto del
sistema.** Pedido explícito del dueño del negocio: si en el futuro decide
cambiar de proveedor (Claude → Gemini/GPT), el cambio debe limitarse a
escribir un adaptador nuevo y cambiar `LLM_PROVIDER` en `.env` — nunca
tocar la lógica de conversación, las herramientas, el manejo de estado
del lead, o el prompt. Se logra con una interfaz neutral (`LLMProvider`,
ABC) y tipos propios (`MensajeLLM`/`RespuestaLLM`/`HerramientaLLM`/
`LlamadaHerramienta`/`ResultadoHerramienta` en
`src/integrations/llm/contratos.py`) que no exponen nada del SDK de
ningún proveedor. `src/integrations/llm/providers/anthropic_provider.py`
es el ÚNICO archivo de todo el proyecto que importa `anthropic` — traduce
en ambas direcciones ahí adentro y nada más. Esta propiedad queda
protegida hacia adelante con un **test de contención**
(`tests/unit/integrations/llm/test_contencion_anthropic.py`) que recorre
TODO `src/` (no solo los archivos mencionados en el encargo) buscando
`import anthropic` / `from anthropic` fuera de ese único archivo permitido
— si el SDK se filtra alguna vez, este test falla solo. Agregar un
proveedor nuevo en el futuro: escribir `providers/gemini_provider.py`
implementando `LLMProvider`, sumar una rama en `factory.py`, cambiar
`LLM_PROVIDER=gemini`. Nada más del proyecto se toca — y de regalo, los
tests del loop de conversación (Tarea 6) usan un `LLMProvider` falso en
memoria con respuestas guionadas, sin mockear HTTP ni depender del wire
format de ningún proveedor real.

**Otras decisiones de arquitectura ya tomadas antes de programar (por
qué, no solo qué):**
- **El pago por transferencia siempre requiere un humano.** Victoria no
  tiene visión de imágenes todavía (fuera de alcance a propósito de esta
  fase) — no puede verificar una captura de pago. La regla es
  determinista en código (`WebhookService`, no una decisión del LLM): en
  cuanto llega una imagen y el lead está en `estado='esperando_pago'`, se
  escala automático sin pasar por Victoria. El dueño cierra la venta a
  mano con el formulario de creación manual de pedido (Fase 2) una vez
  verificado el comprobante.
- **Detección de cliente con pedido previo, determinista.** Un teléfono
  con algún lead en `estado='despachado'` que vuelve a escribir se
  reconoce ANTES de invocar al LLM y escala directo — versión mínima y
  segura del "Flujo 3 (postventa)" de `docs/BotPlanifiacion.md`, no el
  árbol completo de casos.
- **Tool use en vez de JSON de estado en texto libre.** Victoria llama
  funciones estructuradas (`guardar_datos_cliente`, `registrar_producto`,
  `registrar_metodo_pago`, `cerrar_venta`, `escalar_a_humano`) en vez de
  devolver un JSON parseado a mano — más robusto, y es justo lo que la
  capa `LLMProvider` está pensada para exponer de forma neutral.

**Desvíos conscientes del encargo original, con su razonamiento:**

1. **Manejo de errores de Rocketfy en `cerrar_venta` — colapsado de 2
   categorías a 1.** El encargo describía el manejo como "409 ambiguo" vs
   "422 regla de negocio", pero `PedidoService.crear_y_confirmar()` no
   expone códigos HTTP en esa capa: lanza 5 excepciones tipadas propias
   (`PedidoEnEstadoAmbiguoError`, `PedidoIncompletoError`,
   `UbicacionNoResueltaError`, `RecaudoMinimoNoAlcanzadoError`,
   `RocketfyBusinessError`). Como el propio encargo dice que TODO fallo de
   Rocketfy debe escalar igual a un humano sin importar la categoría, se
   capturan las 5 en un único bloque en `tools.py::_handle_cerrar_venta` y
   se escala siempre con el mensaje de la excepción como `motivo` — las
   dos categorías originales se comportaban idéntico, así que colapsarlas
   no pierde nada.
2. **Fail-fast de `ANTHROPIC_API_KEY` movido de `settings.py` a
   `integrations/llm/factory.py::get_llm_client()`.** El encargo pedía la
   validación condicional dentro de `Settings`/`load_settings()`. Se
   detectó a tiempo que `load_settings()` es una función monolítica que
   TODO el proyecto llama para CUALQUIER cosa (hasta abrir una conexión a
   Postgres vía `get_connection()`) — si fallara ahí por falta de la key
   del LLM, absolutamente nada que dependa de `Settings` arrancaría,
   incluyendo funcionalidad que no tiene nada que ver con el LLM (crear un
   pedido de Rocketfy, por ejemplo). Se movió el fail-fast al único punto
   que de verdad necesita la key (`get_llm_client()`), dejando
   `Settings.anthropic_api_key` opcional como ya estaba. Por el mismo
   motivo, `BotWorker` construye `VictoriaConversationService` de forma
   **perezosa** (recién en el primer mensaje modo='ia' que le toca
   procesar, no en `__init__`) — así el backend entero arranca aunque la
   key todavía no esté configurada, y las rutas de escalado (modo='fijo',
   que no usan LLM) funcionan igual. Verificado manualmente: `flask run`
   arranca limpio con `ANTHROPIC_API_KEY` vacía.
3. **Compatibilidad con Python 3.9:** el proyecto corre en 3.9.6 (`.venv`
   confirmado), que no soporta `X | None` como expresión de tipo en
   tiempo de ejecución (eso es de 3.10, PEP 604) — `contratos.py` usa
   `Optional[X]` en su lugar, igual que el resto del proyecto.
4. **`ResultadoHerramienta.id_llamada` no lo arma el handler.** El encargo
   mostraba a cada handler devolviendo un `ResultadoHerramienta` completo,
   pero también le daba la firma `(lead_id, conversacion_id, entrada)` —
   sin el id de la llamada, que solo conoce quien orquesta el loop. Se
   resolvió así: los métodos privados `_handle_*` de `HerramientasVictoria`
   devuelven solo el texto (`str`); el método público `ejecutar(nombre,
   lead_id, conversacion_id, entrada, id_llamada)` (el que de verdad llama
   `VictoriaConversationService`) arma el `ResultadoHerramienta` completo.
5. **Telegram (Tarea 7) se construyó durante la Tarea 4, no en su propio
   turno.** `tools.py::_handle_escalar_a_humano` lo necesita de verdad
   para poder probarse — construirlo ahí y solo documentar/testear en el
   momento de la Tarea 7 habría significado escribirlo dos veces.

**Tablas nuevas** (migraciones `007_cola_mensajes.sql`,
`008_productos_bot.sql`, `009_anuncios_productos.sql`):
- **`cola_mensajes`** — registro persistente de cada tarea de
  `BotWorker`, resuelve el pendiente #18. `modo` separa 'fijo' (texto ya
  decidido por una regla determinista) de 'ia' (invoca a Victoria).
  `recuperar_pendientes()` repone en la cola en memoria, al arrancar, lo
  que quedó `pendiente` o `procesando` hace más de 5 minutos (huérfano de
  un proceso anterior que murió a medio trabajar).
- **`productos_bot`** — base de conocimiento de VENTAS de Victoria,
  completamente separada del catálogo de Rocketfy (`routes/productos`,
  que es para SKU/stock real). Se carga a mano con
  `tools/cargar_producto_bot.py` (sin panel de administración todavía).
- **`anuncios_productos`** — vincula el `id_anuncio` (referral de un
  Click-to-WhatsApp) con el SKU correspondiente, para que Victoria sepa de
  qué producto hablar sin que el cliente tenga que decirlo.

**Módulos nuevos:**
- `src/integrations/llm/` — contratos neutrales, excepciones, factory
  cacheada, y el único adapter hoy (`providers/anthropic_provider.py`).
- `src/integrations/telegram/` — `TelegramNotifier.notificar_escalado()`,
  best-effort (nunca lanza, ni por credenciales vacías ni por fallo de
  red), mismo patrón de factory cacheada que Rocketfy/WhatsApp.
- `src/routes/whatsapp/tools.py` — las 5 herramientas y sus handlers
  (`HerramientasVictoria`).
- `src/routes/whatsapp/conversation_service.py` —
  `VictoriaConversationService`, el loop de tool use.
- `src/routes/whatsapp/victoria_system_prompt.txt` — personalidad, límites
  y reglas de cuándo escalar, con 3 placeholders (`contexto_producto`,
  `contexto_lead_actual`, `fecha_actual`) rellenados por el servicio.
- `tools/cargar_producto_bot.py` y `tools/chat_con_victoria.py`
  (simulador de terminal — necesario porque la app de Meta sigue sin
  publicar, ver Etapa 3.1).

**El loop de tool use y sus límites de seguridad**
(`VictoriaConversationService.procesar_turno`, `src/config/settings.py`):
hasta `BOT_MAX_TURNOS_HERRAMIENTAS` (default 5) idas y vueltas con el
LLM por turno; si en algún momento se llama `escalar_a_humano`, se
permite exactamente UNA iteración más (para que Victoria redacte la
despedida con el resultado que le llegó) y se corta ahí, nunca más; si se
agota el límite sin llegar a `fin` ni escalar, se escala automáticamente
igual, con un mensaje fijo de disculpa. El historial persistido
(`mensajes`) se recorta a `BOT_MAX_MENSAJES_HISTORIAL` (default 40) filas
más recientes por turno.

**Reglas deterministas de `WebhookService` (ANTES de invocar al LLM
siquiera), en orden:** (1) conversación ya escalada → no hacer nada más;
(2) teléfono con un lead `despachado` → escala (postventa); (3) imagen
con lead `esperando_pago` → escala (comprobante de pago); (4) cualquier
otro caso → Victoria responde.

**Tests:** 41 nuevos (persistencia de cola: 3; `productos_bot` +
repositorio: 1 con Supabase real, autocontenido y con limpieza en
`finally`; capa LLM: 14, incluido el test de contención; Telegram: 3;
herramientas de Victoria: 10, con `PedidoService` real contra Rocketfy
mockeado con `responses`, igual que los tests existentes de Rocketfy;
reglas deterministas de `WebhookService`: 5; loop de conversación: 5;
worker conectado de verdad: 1; más 3 agregados un día después al
verificar la Tarea 8 contra las APIs reales — ver más abajo). **173/173
tests en total, todos pasando**, incluida la confirmación explícita de
que el test de contención pasa (ningún archivo fuera de
`anthropic_provider.py` importa `anthropic`).

**Tarea 8 completada el 2026-09-27, contra la API real de Anthropic** (el
usuario pegó `ANTHROPIC_API_KEY` en `.env` un día después de cerrar el
resto de la etapa). Confirmado sin errores de autenticación — las dos
transcripciones completas están en
`docs_para_claude/09_fase3_etapa32_resultados.md`.

**Tres hallazgos reales, encontrados solo porque se probó contra las APIs
reales (Anthropic + Rocketfy) y no solo contra mocks — exactamente para
esto sirve la Tarea 8:**

1. **El LLM no siempre copia el SKU exacto del catálogo al llamar
   `registrar_producto`** — en intentos reales sucesivos inventó
   `"AUD-BT-001"`, mandó el nombre del producto en vez del SKU, y una vez
   directamente `"N/A"`. Reforzar la instrucción del prompt/herramienta
   ("cópialo exacto") no lo resolvió solo — la corrección real fue en
   código: `tools.py::_handle_registrar_producto` ahora valida el SKU
   recibido contra `productos_bot` y, si no coincide con ninguno real, lo
   corrige buscando por nombre (sin distinguir tildes/mayúsculas,
   `_normalizar_texto`) antes de guardarlo. Nunca debe llegarle un SKU
   inventado a `cerrar_venta`, que se lo pasa tal cual a Rocketfy.
2. **Desajuste de formato de teléfono entre WhatsApp y Rocketfy.**
   WhatsApp entrega el número en formato internacional con código de país
   (`593XXXXXXXXX`, 12 dígitos) — Rocketfy exige formato local
   ecuatoriano sin código de país (9-10 dígitos) y lo rechaza con "El
   número no cumple con el formato válido para EC" si no lo recibe así.
   Nunca se había manifestado porque ningún teléfono real de WhatsApp
   había llegado hasta `PedidoService` (los tests con mocks no lo habrían
   detectado nunca — la propia API real de Rocketfy es la que valida
   esto). Se agregó `tools.py::_telefono_formato_rocketfy()`, que le quita
   el `593` antes de armar `CrearPedidoInputDTO`.
3. **Sin resolver, documentado como pendiente:** ninguna herramienta tiene
   un parámetro para la variante/color del producto (`productos_bot.variantes`
   sí existe y Victoria lo ve en su contexto, así que a veces pregunta por
   el color) — en algunos intentos reales, Victoria escaló a un humano en
   vez de cerrar la venta cuando el color quedaba sin resolver, aunque
   ningún dato requerido por `cerrar_venta` dependa de eso. No es un bug
   de código (el sistema hace exactamente lo que el prompt le dice:
   escalar ante ambigüedad) sino un hueco de diseño en el esquema de las
   herramientas — se deja para que Claude web decida cómo cerrarlo
   (¿agregar un parámetro `variante` a alguna herramienta? ¿instruir a
   Victoria a no tratarlo como bloqueante?).

Las 3 tienen tests nuevos agregados (**173/173 tests en total ahora**,
sube de 170). Cada intento real contra Rocketfy que quedó a medias o se
confirmó de verdad se limpió después con `rechazar_pedido()` (mismo
patrón que `tools/rocketfy_order_smoke_test.py`) — no quedó ningún pedido
de prueba activo en el sistema real del proveedor.

**Pendientes abiertos que deja esta etapa** (además de los que ya estaban
— firma `X-Hub-Signature-256`, número real, publicar la app de Meta, ver
Etapa 3.1): verificación real de comprobantes de pago con visión (Victoria
no puede ver imágenes todavía); panel de administración para
`productos_bot` (hoy solo el script de consola); reactivar conversaciones
escaladas desde el dashboard de Fase 2 (hoy no hay botón para "devolverle"
una conversación a Victoria); Flujo 2 (formulario web) y Flujo 4 completo
de `docs/BotPlanifiacion.md`, no construidos en esta fase; agregar un
segundo proveedor de LLM cuando haga falta (la arquitectura ya está lista
para eso, ver el test de contención arriba).

#### Ajuste posterior (2026-09-27) — variante de producto + resiliencia en `registrar_producto`

Encargo de 4 tareas de Claude web para cerrar el pendiente #23 (hueco de
variante/color). Resuelto agregando `variante` como parámetro **opcional**
de `registrar_producto` (no una herramienta nueva) — nunca motivo para
escalar ni para detener un cierre de venta, tanto en la descripción de la
herramienta como en una sección nueva del system prompt.

- **Columna nueva:** `leads.producto_variante` (migración
  `010_leads_producto_variante.sql`). `LeadRepository.actualizar_producto()`
  la actualiza con `COALESCE` — si una llamada no trae variante, no borra
  una que ya se haya guardado antes.
- **`CrearPedidoInputDTO.lineas` no tiene campo propio para variante**
  (solo sku/nombre/cantidad) — para que llegue de verdad al repartidor y
  no se quede solo en nuestra tabla, `_handle_cerrar_venta` arma el
  `nombre` de la línea como `"{producto_nombre} - {variante}"` cuando hay
  variante, sin tocar el contrato de Rocketfy.
- **Resiliencia nueva en `_handle_registrar_producto`:** si ni el match
  exacto por SKU ni el fuzzy-match por nombre (el que ya se había
  agregado para el bug del SKU alucinado) encuentran ningún producto real
  en `productos_bot`, ya NO se guarda nada — se le devuelve a Victoria la
  lista real de productos disponibles para que le pregunte de nuevo al
  cliente en el mismo turno, en vez de guardar un dato posiblemente
  incorrecto.
- **Documentado en `tools/cargar_producto_bot.py`** (docstring del
  módulo, con la causa raíz del bug original explicada): el SKU cargado
  en `productos_bot` debe ser siempre un SKU real del catálogo de
  Rocketfy, verificable con `RocketfyClient.listar_productos()` o el
  smoke test — nunca inventado ni de demostración. Sigue siendo
  `10-AUDIFONO-INALAM-TIPRO` el único producto real cargado; no se agregó
  ninguno adicional para esta prueba.
- **Verificado contra la API real de Claude** (transcripción completa en
  `docs_para_claude/09_fase3_etapa32_resultados.md`): el cliente responde
  de forma ambigua sobre el color ("cualquiera está bien"), Victoria lo
  registra sin variante y sigue adelante, cierra la venta contraentrega
  normalmente (pedido real confirmado en Rocketfy y luego rechazado como
  limpieza, mismo patrón de siempre) — nunca escala por ese motivo.
- 4 tests nuevos (uno de los tests viejos de "SKU sin match" se reemplazó
  por el nuevo comportamiento de resiliencia, ya no aplicaba tal cual).
  **177/177 tests en total.**

Sin desvíos del encargo — las 4 tareas se implementaron tal como se
especificaron.

### Etapa 3.3 — Módulo de Conversaciones (backend + dashboard) — COMPLETA (2026-09-27)

Por qué existe: el número de WhatsApp del bot no tiene ninguna app de
WhatsApp normal asociada — es un número que solo existe dentro de la
Cloud API. Sin este módulo, cuando Victoria escala no hay ninguna forma
de que un humano le responda al cliente. Encargo de 4 tareas de Claude
web, backend + 2 páginas nuevas del dashboard.

**Backend — `src/routes/conversaciones/`:** mismo patrón de capas que
`routes/pedidos/` (dto/schemas/services/controllers), pero **sin
`repository.py` propio** — reutiliza `ConversacionRepository`/
`LeadRepository`/`MensajeRepository` de `routes/whatsapp/repository.py`
(son las mismas tablas que ya administra el canal del bot; duplicar el
acceso a datos en dos repositorios distintos habría arriesgado que
diverjan). Se le agregaron ahí los métodos nuevos que este módulo
necesita (`listar`, `contar_por_filtro_rapido`, `marcar_vista`,
`actualizar_notas`, `marcar_esperando_pago`, `marcar_escalada`).

- Columnas nuevas: `conversaciones.vista_en` y `conversaciones.notas_internas`
  (migración `011_conversaciones_vista_notas.sql`), más los índices
  `conversaciones_estado_actualizada_idx` y `leads_nombre_cliente_idx`.
- Cálculo de la ventana de mensajería (`ConversacionesService._ventana_abierta`):
  servicio (24h desde el último mensaje del cliente) OR FEP (`fep_expira_en`),
  devuelve también cuál de las dos sigue vigente y cuándo cierra la más
  próxima. `POST /conversaciones/<id>/mensajes` la valida ANTES de tocar
  BD o llamar a WhatsApp — 409 sin efectos secundarios si está cerrada.
- 5 endpoints: `GET /conversaciones` (filtros + `totalesPorFiltroRapido`),
  `GET /conversaciones/<id>` (marca `vista_en` automáticamente si es una
  escalada sin revisar), `POST /conversaciones/<id>/mensajes`,
  `POST /conversaciones/<id>/reactivar`, `PATCH /conversaciones/<id>/notas`.

**Dos extensiones más allá de lo pedido literalmente, ambas necesarias
para que el módulo funcione de verdad (documentadas, no desvíos
silenciosos):**
1. **`conversaciones.estado` nunca se ponía en `esperando_pago`** — solo
   `leads.estado` lo hacía (Fase 3.2). La pestaña "Esperando pago" de
   este módulo filtra sobre `conversaciones.estado`, así que sin este
   cambio esa pestaña siempre habría estado vacía. Se agregó
   `ConversacionRepository.marcar_esperando_pago()`, llamado desde
   `tools.py::_handle_registrar_metodo_pago` cuando el método es
   transferencia.
2. **`marcar_escalada()` (limpia `vista_en`) también se aplicó a
   `WebhookService._escalar()`**, no solo a `tools.py::_handle_escalar_a_humano`
   como decía el encargo literalmente — las 4 reglas deterministas de
   escalado (postventa, imagen de pago) también pasan por ahí, y el
   dashboard necesita "sin revisar" consistente sin importar qué camino
   causó el escalado.

**Frontend — `conversaciones/page.tsx` (lista) y `conversaciones/[id]/page.tsx`
(detalle):** mismo Tailwind v4 + shadcn/ui, mismo `lib/api.ts`, mismo
`StatusBadge`/`lib/estados.ts` (nuevo `ESTADOS_CONVERSACION` — "cerrada"
y "fria" comparten variante "neutral", el sistema de diseño no tiene un
gris más claro aparte). Pestañas de acceso rápido (Escaladas/Esperando
pago/Todas) en vez de un dropdown de estado genérico — las 3 cubren los
casos operativos reales, un dropdown aparte habría sido redundante.
Contador de escaladas sin revisar también en el sidebar (poll cada 30s,
"si es sencillo" del encargo — sí lo fue).

**Prefill del formulario de pedido manual (Fase 2, Etapa 6):** ese
formulario no tenía soporte de querystring antes. Se agregó leyendo
`useSearchParams()` en los `useState` iniciales (lazy initializer) del
mismo archivo `pedidos/nuevo/page.tsx` — no se duplicó el formulario.
Hallazgo de la propia documentación de Next.js 16 (`node_modules/next/dist/docs`,
revisada antes de tocar código por instrucción del propio repo):
`useSearchParams()` exige un límite `<Suspense>` alrededor o `next build`
falla en producción — se envolvió el formulario real en un wrapper
`NuevoPedidoPage` delgado con `<Suspense>`, confirmado con `npm run build`
real (la ruta sigue prerenderizándose como estática).

**Resolución de una ambigüedad del encargo:** el ejemplo JSON de
`lead.total` mostraba un número (`24.99`), pero las convenciones
obligatorias explícitas piden la misma convención de moneda que
`pedidos/` (que es `as_string=True`, nunca float en el wire). Se siguió
la convención explícita, no el ejemplo ilustrativo — `total` sale como
`"24.99"` (string).

**Tests:** 26 nuevos en el backend (16 de servicio con repositorios
falsos — incluye los 3 escenarios de ventana exigidos: cerrada sin
FEP, abierta por servicio, abierta solo por FEP —, 10 de controladores
HTTP con el servicio mockeado). **205/205 tests en total.** Frontend sin
tests automatizados (decisión de alcance del encargo) — `npm run build`
y `npm run lint` limpios, y además se verificó de punta a punta contra
datos reales de Supabase (no solo con mocks): `GET /conversaciones`,
`GET /conversaciones/<id>` (con `marcar_vista` real, confirmado con una
segunda lectura que `sinRevisar` pasó a `false`), y `PATCH /notas`,
los tres a través del cliente de test de Flask real (`create_app()`
real, solo el chequeo de Supabase Auth mockeado) contra la Supabase de
producción.

**No se pudo verificar (necesita al usuario, no es una limitación de
código):** el envío real de un mensaje manual a un teléfono de WhatsApp
de verdad — todos los números de prueba usados en esta fase son
inventados (`593991234...` etc.), y Meta solo entrega/acepta mensajes
hacia números en la lista de prueba de la app (mismo hallazgo que la
Etapa 3.1). Para cerrar esta verificación hace falta que el usuario abra
`/conversaciones` en el navegador con una conversación real (o de un
número de la lista de prueba) con la ventana abierta, escriba una
respuesta, y confirme que llegó. Tampoco hubo confirmación visual del
usuario de las pantallas (sin herramienta de navegador disponible para
Claude, mismo patrón que todas las etapas anteriores del frontend).

---

## 3.1 Credenciales del proveedor (NUNCA en este archivo ni en ningún .md)

- Token de API de Rocketfy: **recibido del usuario el 2026-09-03**, guardado
  en `PROYECTECOM/backend/.env` como `ROCKETFY_API_TOKEN` (archivo excluido
  vía `.gitignore`, NO commitear). No se transcribe aquí a propósito.
- **Pendiente:** el correo de la cuenta vendedora de Rocketfy. Falta para
  poder calcular el header `Auth-user` (`sha256` del correo exacto tal como
  está registrado en Rocketfy — mayúsculas/espacios importan). Sin este dato
  el cliente no puede autenticar ninguna llamada real todavía.
- KYC: no confirmado aún si está aprobado en el panel de Rocketfy (requisito
  obligatorio para confirmar pedidos y consultar catálogo, sección 2 del doc
  del proveedor). Verificar antes de la Etapa 3.

---

## 4. Historial de Versiones y Estado Actual

| Fecha | Versión | Estado | Notas |
|---|---|---|---|
| 2026-09-03 | 0.0.1 | Planeación | Diagnóstico de proyectos de ejemplo completado. Plan maestro y propuesta técnica entregados para validación del usuario. Ninguna línea de código de producción escrita todavía. |
| 2026-09-03 | 0.0.2 | Planeación | Estructura reorganizada: todo el proyecto nuevo vive bajo `MASS/PROYECTECOM/` (docs/backend/frontend). Stack de librerías APROBADO por el usuario (ADR-001). Token de API de Rocketfy recibido y guardado en `backend/.env` (no en este documento). Confirmado que NO se solicitan a Rocketfy los endpoints faltantes por ahora (ADR-003 cerrado). ADR-002 (persistencia mínima) en discusión — pendiente explicación al usuario sobre qué significa "sin estado" y su respuesta. |
| 2026-09-03 | 0.0.3 | Planeación | ADR-002 ACEPTADO y ampliado: esquema de datos diseñado en `backend/migrations/001_init.sql` (pedidos, webhook_events, job_locks, skus_monitoreados, stock_snapshots). Abierto ADR-006: mecanismo de acceso de Claude a Supabase (MCP oficial vs. connection string + migraciones versionadas vs. manual) — pendiente decisión del usuario y credenciales. |

| 2026-09-04 | 0.0.4 | Planeación | ADR-006 resuelto: usuario eligió connection string + MCP. Se creó venv en `backend/.venv`, `tools/apply_migrations.py`, y se guardó `SUPABASE_DB_URL` en `.env`. **Bloqueado:** el host de conexión directa (`db.<ref>.supabase.co:5432`) solo tiene registro DNS AAAA (IPv6); este entorno de trabajo no tiene salida IPv6, así que la migración no pudo aplicarse todavía. Se necesita la connection string del **Connection Pooler** (Supavisor, hostname `*.pooler.supabase.com`, compatible IPv4) desde Project Settings → Database. MCP de Supabase figura "Connected" a nivel de transporte (`claude mcp list`) pero ninguna herramienta suya aparece aún disponible tras varias búsquedas — probablemente requiera reiniciar la sesión de Claude Code. |
| 2026-09-04 | 0.0.5 | Planeación | Usuario entregó connection string del pooler (`aws-0-us-west-2.pooler.supabase.com:5432`, session mode). `001_init.sql` APLICADA exitosamente — verificadas las 6 tablas en Supabase (`pedidos`, `webhook_events`, `job_locks`, `skus_monitoreados`, `stock_snapshots`, `schema_migrations`). Creado `docs/CONCEPTOS_TECNICOS.md` (glosario didáctico acumulativo). Pendiente: usuario va a reiniciar Claude Code para intentar exponer las herramientas MCP de Supabase — verificar en la próxima sesión. |

| 2026-09-04 | 0.0.6 | Planeación → Desarrollo | MCP de Supabase confirmado funcionando tras el reinicio (`list_tables`, `get_advisors`, `apply_migration` probados). Migración `001_init` re-aplicada vía `apply_migration` para quedar registrada en el historial oficial de Supabase (antes solo existía en nuestro `schema_migrations` propio). Dos hallazgos de `get_advisors` documentados (RLS sin políticas — no aplica, no usamos REST/PostgREST; función `rls_auto_enable()` pública preexistente, no creada por nosotros — pendiente de que el usuario la revise si le preocupa). Usuario entregó `ROCKETFY_ACCOUNT_EMAIL`. Smoke test real contra `/api/products/list` → **HTTP 401** "su usuario no tiene permisos". Diagnóstico: el hash del correo coincidió con el token (si no, sería 400 según el doc), por lo que las credenciales están bien formadas — falta que Rocketfy active el **acceso API** y/o que se complete el **KYC** en el panel (sección 2 y checklist Anexo D, pasos 1-3, del doc del proveedor). No es un problema de código. Se decidió avanzar igual con Etapa 0 y Etapa 1 usando tests 100% mockeados, dejando el smoke test real como prueba de integración a repetir cuando Rocketfy active el acceso. Etapa 0 (scaffolding) y Etapa 1 (`RocketfyClient` completo con excepciones tipadas y reintentos) completadas, 12/12 tests unitarios pasando, `/health` verificado. Detectada e incorporada duda #11 para el proveedor (inconsistencia entre la regla general de "content" y el ejemplo de `/orders/create`). |

| 2026-09-04 | 0.0.7 | Desarrollo | **Acceso API de Rocketfy ACTIVADO** — smoke test contra `/products/list` ahora devuelve HTTP 200 con datos reales del catálogo del vendedor (antes 401). Usuario entregó `docs/rocket-cantones-ecuador.csv` y `docs/Rocket-Webhooks-Guia-Integrador.md`. CSV verificado por inspección: 832 cantones, 24 provincias, UTF-8 con BOM, sin duplicados — coincide con el doc principal (resuelve duda #6). Guía de webhooks analizada: reveló que Rocket NO manda autenticación propia al webhook (hay que poner un token en la URL), que el presupuesto de error es de 10 fallos de por vida sin reset, y que la clave de idempotencia real es `(order_id, status_id, event_date)` — no solo `order_id` (nuevo ADR-007). Se corrigió el esquema con `002_webhook_events_idempotencia.sql` (aplicada vía MCP). Etapa 2 (catálogo de ubicaciones) implementada completa: `EcuadorLocationsCatalog`, endpoints `GET /catalogos/ubicaciones` y `/catalogos/ubicaciones/<provincia>/cantones`, 6/6 tests nuevos pasando (18/18 en total). Duda #5 resuelta (no hay recuperación de eventos de webhook perdidos). Nueva duda #12 (no bloqueante): pedir a soporte de Rocket su IP de salida para el firewall cuando se despliegue el webhook. |

| 2026-09-04 | 0.0.8 | Desarrollo | **Etapa 3 completa.** `src/routes/pedidos/` implementado de punta a punta (dto/schemas/repository/services/controllers), con `src/config/database.py` nuevo (pool de conexiones psycopg2 a Supabase para runtime de la app — hasta ahora solo existía la conexión suelta de `tools/apply_migrations.py`). Lógica de idempotencia con 5 estados (`pendiente_creacion`/`error`/`incompleto`/`creado`/`confirmado`) probada exhaustivamente: reintento bloqueado ante ambigüedad de red, reintento limpio ante error definitivo de Rocketfy, reintento de solo-confirmación ante rechazo de negocio. Endpoint `POST /pedidos` registrado. 27/27 tests pasando en total. Se agregó `tools/rocketfy_order_smoke_test.py` (prueba manual contra producción real, no automática) — NO se ejecutó, queda a criterio del usuario correrla cuando quiera. |

| 2026-09-04 | 0.0.9 | Desarrollo | **Etapa 4 completa.** `src/routes/webhooks/` (receptor con auth por token en URL, idempotencia real, tolerancia total a fallos internos) y `src/jobs/reconciliacion/` (lock, rango de ids, chunking, parseo defensivo de `bulk/getInfo`) implementados y probados. Módulo `src/notifications/` migrado del patrón del proyecto de ejemplo, pero se corrigió ADR-004: el `WhatsAppChannel` original apunta a infraestructura de Massline/Shineray, no aplica aquí — se usa `LoggingNotificationChannel` como placeholder seguro hasta que el usuario defina el mecanismo real de envío. Scheduler (APScheduler, cada 45 min) wireado en `app.py`, solo arranca en el proceso `__main__` (pendiente para Etapa 8: estrategia de arranque de jobs con gunicorn multi-worker). 24 tests nuevos, 51/51 en total, incluyendo el primer test que ejercita `create_app()` completo bajo pytest. Nueva duda #13 para el proveedor: forma exacta de la respuesta de `bulk/getInfo`, no documentada con ejemplo. |

| 2026-09-04 | 0.0.10 | Desarrollo | **Etapa 5 completa.** `src/routes/productos/` (proxy a catálogo Rocketfy + gestión de SKUs monitoreados, con validación contra el catálogo real antes de agregar) y `src/jobs/stock_watcher/` (umbral de stock, alerta de cambio de precio, mismo patrón de lock). Refactor DRY: lock de jobs extraído a `src/jobs/_locks.py`, reutilizado por reconciliación y stock_watcher. Programado cada 60 min. 17 tests nuevos, 68/68 en total. Usuario pidió dejar pendiente la decisión del canal de WhatsApp (pendiente #1) y seguir con desarrollo; se creó la sección 5 "Pendientes Transversales" para no perder de vista esto ni lo demás que vaya quedando abierto. |

| 2026-09-04 | 0.0.11 | Desarrollo | **Etapa 6 completa.** `PedidoService.modificar()` y `.rechazar()` agregados sobre el módulo `pedidos` ya existente (mismo dominio, no un módulo nuevo). Nuevos endpoints `PATCH /pedidos/<id_local>` y `POST /pedidos/<id_local>/rechazar`. Validación de cantón/provincia reutilizada al modificar destino. Cache local (`payload_creacion`) se mantiene fresca vía merge jsonb tras modificaciones exitosas. 11 tests nuevos, 79/79 en total. |

| 2026-09-04 | 0.0.12 | Desarrollo | **Etapa 7 completa — Fase 1 del plan maestro original (7 requerimientos) cubierta a nivel de código.** `src/routes/metricas/` (proxy liviano a `/statistics/general`, con aviso explícito de que no es saldo de wallet). Refactor DRY: `get_rocketfy_client()` centralizado en `src/integrations/rocketfy/factory.py`, eliminando 3 copias del mismo código en `pedidos`, `productos` y `app.py`. 2 tests nuevos, 81/81 en total. |
| 2026-09-06 | 0.0.13 | Validación real | **Primera prueba real de punta a punta contra Rocketfy (pendiente #7 resuelto).** Se creó `RESUMEN_FASE1.md` (resumen no técnico para el usuario) y luego se ejecutó `tools/rocketfy_order_smoke_test.py` contra producción real: (1) servidor local levantado, catálogo real (1884 productos) y métricas generales confirmados funcionando con credenciales reales; (2) pedido de prueba creado en Rocketfy (id_rocketfy=288645, SKU `MASCARAPROTECCION`, total $1.00); (3) **confirmación rechazada por Rocketfy con hallazgo nuevo: "El recaudo mínimo para confirmar un pedido contraentrega es de $10.00"** — regla de negocio no documentada en el doc del proveedor; (4) el sistema reaccionó exactamente como estaba diseñado (guardó `estado_local=creado` con el mensaje de error, sin ambigüedad ni caída); (5) pedido rechazado y limpiado vía `POST /pedidos/<id_local>/rechazar`, quedando consistente en Rocketfy y en la base de datos. Validación exitosa del flujo completo de creación/confirmación/rechazo y de la lógica de idempotencia en un caso real. Nuevo pendiente #9 abierto: decidir cómo manejar el mínimo de $10 COD (validación local antes de crear, aviso al usuario, etc.). |

| 2026-09-06 | 0.0.14 | Desarrollo | **Validación del recaudo mínimo COD agregada.** El usuario confirmó que el mínimo de $10 (hallazgo 0.0.13) aplica solo a pedidos contraentrega, no a prepagados — correcto según el doc del proveedor (campo `not_COD`, ya soportado end-to-end como `no_contra_entrega`). Se agregó `RECAUDO_MINIMO_CONTRAENTREGA` (constants.py), `RecaudoMinimoNoAlcanzadoError`, validación en `PedidoService.crear_y_confirmar` (antes de crear, junto a la validación de ubicación) y mapeo a HTTP 422 en el controller. 3 tests nuevos, 84/84 en total. Se agregó también la directriz 17 (mínima interacción manual pero trazabilidad total visible en frontend) y se anotó como fase futura (no iniciar aún) el bot conversacional de IA por WhatsApp que el usuario planea construir después del frontend. |

| 2026-09-07 | 0.0.15 | Validación real | **Webhook probado de punta a punta con eventos reales de Rocketfy (pendiente #6 validado).** Se levantó un túnel temporal (`cloudflared tunnel --url`, sin cuenta) hacia el backend local y se dio de alta esa URL + el token en el panel de Rocketfy. El ping de validación al guardar respondió 200 de inmediato. Luego se creó y confirmó un pedido real (`id_rocketfy=288726`, total $12.00, ya por encima del mínimo COD) y se rechazó: **ambos cambios de estado dispararon un webhook real de Rocketfy en ~2 segundos**, con la autenticación por token, la idempotencia y la actualización del pedido local funcionando correctamente en ambos casos. Hallazgo y arreglo en el camino: las columnas `procesado`/`procesado_en` de `webhook_events` existían en el esquema pero nunca se actualizaban — se agregó `WebhookRepository.marcar_procesado()`, llamado desde `WebhookService._procesar()` tras aplicar el evento (antes de la notificación, que es best-effort). Confirmado además que **rechazar un pedido sí disparó el webhook** (status_id=3), dato que no estaba explícito en la guía del proveedor. 84/84 tests (sin nuevos casos, se extendieron los existentes). El túnel es temporal — la URL registrada en el panel de Rocketfy dejará de responder en cuanto se cierre esta sesión de prueba (ver pendiente #6 actualizado). |

| 2026-09-07 | 0.0.16 | Planeación | **Fase 1 (backend) declarada cerrada a nivel funcional. Arranca la Fase 2 (Frontend).** El usuario decidió posponer explícitamente la Etapa 8 (Hardening) y la Etapa 9 (Documentación) para retomarlas más adelante, y seguir con el frontend. Se agregó el plan maestro propuesto para la Fase 2 (Etapas 0-7, ver sección "Fase 2 — Frontend" más arriba): scaffolding, autenticación mínima, dashboard de pedidos, incidencias/alertas, catálogo/stock, métricas, formulario manual de creación, y pulido+despliegue conjunto al final (donde se retoman las Etapas 8/9 pospuestas). Hallazgo nuevo durante la planeación: **ninguna ruta del backend tiene autenticación hoy** — se anotó como Etapa 1 de la Fase 2, a resolver antes de desplegar el frontend en público, y como pendiente #11. Stack de frontend propuesto (a confirmar): React + Vite + MUI, consistente con `MASS/FRONTEND` (que usa MUI) pero con Vite en vez de Create React App por estar este último descontinuado. |
| 2026-09-07 | 0.0.17 | Planeación | **Corrección del stack de frontend.** El usuario ya había indicado su preferencia real de stack al inicio de esta conversación (Next.js/React/TypeScript/Tailwind/Supabase + un segundo stack de referencia de otro proyecto suyo), pero se perdió al resumirse la conversación y la entrada 0.0.16 propuso React+Vite+MUI por error. Corregido: stack definitivo Next.js 16 (App Router) + React 19 + TypeScript + Tailwind v4 + shadcn/ui + Lucide React + Framer Motion + Sonner, con Supabase Auth para resolver la Etapa 1 (autenticación, pendiente #11). Aclarado explícitamente por el usuario: el proyecto de ejemplo `MASS/FRONTEND` es solo referencia de lógica/consumo de API, NO de diseño visual — paleta propia blanco/negro con acentos, UI/UX como prioridad explícita. Etapas 0 y 1 de la sección "Fase 2 — Frontend" actualizadas con el detalle correcto. |

| 2026-09-07 | 0.0.18 | Desarrollo | **Fase 2, Etapa 0 completa.** Frontend scaffolded en `PROYECTECOM/frontend/` con el stack definitivo (Next.js 16.3.4 + React 19.2 + TypeScript + Tailwind v4 + shadcn/ui + Lucide + Framer Motion + Sonner). Layout con sidebar colapsable, 5 páginas de navegación (una real: Resumen; cuatro placeholder "Próximamente" para las Etapas 2-5), cliente HTTP mínimo (`src/lib/api.ts`), e indicador de salud del backend en vivo. `npm run lint` y `npm run build` limpios (se corrigieron 2 usos de `setState` síncrono dentro de un `useEffect` — uno propio, uno generado por el CLI de shadcn — que la nueva regla de ESLint de React marca como error). **Hallazgo real corregido en el camino:** `flask-cors` estaba declarado en `requirements.txt` desde el principio del proyecto pero nunca se activó en `app.py` — sin esto, el navegador habría bloqueado en silencio toda llamada del frontend al backend por política CORS, un fallo que `curl` no habría revelado nunca (CORS es una restricción exclusiva del navegador). Se agregó `CORS(app, origins=[settings.frontend_origin])` con `FRONTEND_ORIGIN` nuevo en `.env`/`.env.example`, verificado con curl simulando el header `Origin` real. 84/84 tests del backend siguen pasando. **Sin verificar:** no hay herramienta de navegador disponible para Claude en este entorno — toda la validación fue con `curl` (200 en las 6 rutas, contenido esperado) y build/lint limpios; falta que el usuario confirme visualmente abriendo `http://localhost:3000`. |

| 2026-09-07 | 0.0.19 | Desarrollo | **Sistema de diseño centralizado, a pedido explícito del usuario antes de arrancar la Etapa 1.** Usuario confirmó visualmente la Etapa 0 ("se ve bien... Backend conectado"). Se agregó: fuente Poppins como `--font-sans` (corrigiendo de paso un bug del generador de shadcn donde esa variable era autorreferente y nunca se aplicaba); paleta de estados semánticos success/warning/danger/info/neutral en `globals.css`, espejo intencional de `estado_local` (backend) y `RocketfyStatus`; `src/lib/estados.ts` con el mapeo completo de ambos catálogos de estado a {label, color}; `src/config/site.ts` como única fuente de nombre/metadata/navegación (sidebar y header refactorizados para consumirlo, sin duplicar); componente reutilizable `<StatusBadge />`. Se documentó la sección "Convenciones de Arquitectura del Frontend" (estructura de `src/app`, `components`, `config`, `lib`, `hooks`, `types`) para que las Etapas 1-7 no diverjan. `npm run lint`/`build` limpios. |

| 2026-09-07 | 0.0.20 | Desarrollo | **Fase 2, Etapa 1 completa — pendiente #11 resuelto.** Login con Supabase Auth (correo + contraseña, decidido con el usuario) de punta a punta: `/login` sin el shell del dashboard (route group `(dashboard)` nuevo), `src/proxy.ts` (Next.js 16: `middleware.ts`→`proxy.ts`) protegiendo todas las rutas del lado del frontend, `<UserMenu />` con cierre de sesión. Backend: `verificar_token()` valida contra `${SUPABASE_URL}/auth/v1/user` (sin manejar JWT/JWKS localmente, decisión consciente de simplicidad para un panel de un solo usuario), `before_request` global en `app.py` exigiendo el token en toda ruta salvo `/health` y `/webhooks/*`. `flask-cors` ajustado para permitir el header `Authorization` y no bloquear el preflight `OPTIONS`. 7 tests nuevos + `tests/conftest.py` reutilizable, 91/91 en total. Verificado con curl (401 sin token, `/` redirige a `/login` sin sesión). **Falta un paso manual, no de código:** el usuario debe crear su propio usuario en el dashboard de Supabase (Authentication → Users) para poder probar el login real — no se hizo desde aquí para no requerir la `service_role key`. |

| 2026-09-07 | 0.0.21 | Desarrollo | **Etapa 1 confirmada de punta a punta.** El usuario creó su usuario en el dashboard de Supabase y confirmó que el login funciona en el navegador real. Se le explicó una distinción importante que preguntó espontáneamente: el login NO restringe por correo específico en el código, solo exige un token válido de Supabase — la única barrera hoy es el acceso al dashboard para crear cuentas. El usuario decidió explícitamente que eso es suficiente y que NO se agregue una validación de correo específico en el backend. Arranca la Etapa 2 (Dashboard de Pedidos). |

| 2026-09-07 | 0.0.22 | Desarrollo | **Fase 2, Etapa 2 completa.** Se agregó al backend lo que faltaba para poder listar/ver pedidos (`GET /pedidos`, `GET /pedidos/<id_local>` — antes solo existían crear/modificar/rechazar), verificado contra la base de datos real. Frontend: tabla de pedidos con filtro por estado y paginación, vista de detalle con todos los datos de entrega y ambos estados (local y Rocketfy) lado a lado, mensaje de error destacado en rojo cuando existe (directriz 17), y las dos acciones manuales (modificar vía diálogo, rechazar con confirmación). 12 tests nuevos en el backend, 96/96 en total. `lint`/`build` limpios en el frontend. Pendiente de confirmación visual del usuario (sin herramienta de navegador disponible para Claude). |

| 2026-09-07 | 0.0.23 | Desarrollo | **Etapa 2 confirmada por el usuario, y su único pendiente resuelto el mismo día.** El usuario pidió explícitamente reemplazar los campos de texto libre de cantón/provincia del diálogo de "Modificar" por un selector, y que se analizara antes CSV vs. subir el catálogo a Supabase. Análisis: se descartó la base de datos (dato casi estático, lectura intensiva, cero escrituras — el perfil exactamente contrario al que justificaría una tabla; además choca con ADR-002 de persistencia mínima). Se construyó `<UbicacionSelector />` (selector en cascada Provincia→Cantón) consumiendo `GET /catalogos/ubicaciones` ya existente, reutilizable también para la futura Etapa 6. `lint`/`build` limpios. |

| 2026-09-07 | 0.0.24 | Desarrollo | **Fase 2, Etapa 3 completa.** Hallazgo corregido en el camino: `StockWatcherService` detectaba alertas de stock/precio desde la Fase 1 pero solo las logueaba — se agregó la tabla `alertas_stock` (migración 003) y se persisten de verdad. Backend nuevo: `src/routes/incidencias/` (`GET /incidencias/eventos`, `GET /incidencias/stock`), con el mismo patrón repositorio+servicio inyectable que `pedidos` (no el minimalista de `catalogos`/`metricas`, porque este sí toca la base de datos propia). Frontend: `/incidencias` con dos pestañas (eventos de webhook, alertas de stock) reemplazando el placeholder. 9 tests nuevos, 105/105 en total. `lint`/`build` limpios. Pendiente de confirmación visual del usuario. |
| 2026-09-07 | 0.0.25 | Validación real | **Etapa 3 verificada con datos reales por el usuario, con dos preguntas que revelaron el diseño correcto (no bugs).** (1) El usuario notó que el pedido 1788739873 aparece como "Confirmado" en el historial de incidencias pero como "Rechazado" en Pedidos — se confirmó contra la base de datos real que son 2 eventos distintos y consecutivos (confirmado a las 00:11:18, rechazado a las 00:13:15): el módulo de Pedidos muestra el estado ACTUAL, el historial de incidencias es una bitácora cruda de TODOS los eventos, por diseño (auditoría). (2) El usuario notó que el pedido 1788734913 no aparece nunca en el historial — se confirmó que es porque ese pedido se probó ANTES de configurar el túnel/webhook (entrada 0.0.13), cuando Rocketfy todavía no tenía ninguna URL nuestra a la cual avisar; nunca se perdió un evento, nunca se generó. Se anotó como pendiente #12 una mejora de UX (aclarar visualmente que es un historial, posiblemente agrupar por pedido) — el usuario pidió dejarla para después. |

| 2026-09-07 | 0.0.26 | Desarrollo | **Fase 2, Etapa 4 completa — 100% frontend.** Todo lo necesario ya existía en el backend desde la Etapa 5 de Fase 1 (`/productos`, `/productos/monitoreados`). `/catalogo`: pestaña de búsqueda paginada con debounce contra el catálogo real (1884 productos) y botón "Monitorear" por fila; pestaña de SKUs monitoreados con editar umbral (reutiliza el mismo POST, que hace upsert) y quitar (soft-delete). Verificado de punta a punta contra Rocketfy y la base de datos real con un SKU real, dejado desactivado al terminar. `lint`/`build` limpios, 105/105 tests del backend sin cambios. Pendiente de confirmación visual del usuario. |

| 2026-09-07 | 0.0.27 | Desarrollo | **Fase 2, Etapa 5 completa — 100% frontend, la etapa más chica de la Fase 2.** `/metricas/generales` ya existía desde la Etapa 7 de Fase 1. `/metricas`: aviso de "no es tu saldo de wallet" siempre visible arriba, tarjetas agrupadas en "Hoy" y "General". **Hallazgo real:** Rocketfy manda `0` (número) en vez de `"0.00"` cuando un monto no tiene movimiento — inconsistencia de su API, no rompe nada (el schema ya trata todo como texto) pero se corrigió el formato solo para mostrar (`toFixed(2)`, nunca para calcular). Verificado contra datos reales (`orders_today=2`, coincide con los 2 pedidos de prueba conocidos). `lint`/`build` limpios. Pendiente de confirmación visual del usuario. |

| 2026-09-07 | 0.0.28 | Desarrollo | **Fase 2, Etapa 6 completa — última pantalla nueva de la Fase 2.** Sin cambios de backend (`POST /pedidos` ya existía). `/pedidos/nuevo`: ID interno automático, reutiliza `<UbicacionSelector />` y el buscador de catálogo de la Etapa 4 (como diálogo) para armar las líneas sin escribir SKUs a mano, aviso en vivo del recaudo mínimo COD, y manejo de errores que detecta si igual quedó un pedido real creado y lleva al usuario a su detalle en vez de dejarlo perdido en el formulario. **Hallazgo real importante:** el mínimo de confirmación de Rocketfy NO es un número fijo — es "valor de productos + costo de envío" calculado por ellos (un pedido de $15 resultó necesitar $18.47 reales); cumplir el mínimo fijo de $10 no garantiza nada. Sin cotizador de flete (limitación ya conocida, ADR-003), este mínimo real es imposible de calcular de antemano — anotado como duda #14 y reforzado en el pendiente #5. El aviso en pantalla se ajustó para ser honesto al respecto. Verificado dos veces contra Rocketfy real (un rechazo por mínimo real y una confirmación exitosa), ambos pedidos de prueba limpiados. `lint`/`build` limpios. Pendiente de confirmación visual del usuario. |

| 2026-09-15 | 0.0.29 | Planeación | **Arranca la Fase 3 (Bot Conversacional de WhatsApp, AzoShop/"Sofía").** El usuario está orquestando el diseño de arquitectura del bot con una instancia de Claude en el chat web, usando esta sesión (Claude Code) como ejecutor/documentador de PROYECTECOM, con el usuario como intermediario humano entre ambas. A pedido de Claude web, se creó `docs_para_claude/` con 7 documentos verificados contra el código real (no de memoria): estructura del proyecto, flujo con Rocketfy paso a paso, contrato exacto de input/output de `POST /pedidos`, esquema completo de las 6 tablas de la base de datos, variables de entorno (solo nombres, sin valores), estado actual honesto (qué funciona, qué falta, limitaciones conocidas), y preguntas abiertas respondidas contra el código. Se encontró `docs/BotPlanifiacion.md` (documento de planificación previo, ya bastante avanzado: marca AzoShop, bot "Sofía", 4 flujos de conversación, WhatsApp Cloud API directo sin BSP ya decidido, estructura de datos propuesta). Se documentó explícitamente una aclaración importante: la tabla `pedidos` existente está moldeada para el contrato con Rocketfy, el bot necesita su propio modelo de datos nuevo (conversaciones/leads), no debe reutilizarla ni reestructurarla. Se plantearon 3 preguntas de arquitectura al usuario (dónde vive el bot, mismo Supabase o uno nuevo, qué LLM usar) — ninguna resuelta todavía por el código. |

| 2026-09-15 | 0.0.30 | Planeación | **Resueltas las 3 preguntas de arquitectura del bot planteadas al usuario en la entrada anterior.** El bot vive dentro del backend Flask actual (módulo nuevo, acceso directo en Python a `PedidoService`, mismo patrón de capas); usa el mismo proyecto de Supabase (tablas propias nuevas, sin tocar `pedidos`); el LLM es Claude (Anthropic). Actualizado `docs_para_claude/07_preguntas_abiertas.md` con las respuestas y un resumen de la arquitectura de alto nivel que se desprende de ellas (incluye una nota comparando el webhook de WhatsApp Cloud API con el patrón ya usado para el webhook de Rocketfy). Todavía falta que Claude web diseñe el detalle y devuelva prompts de desarrollo concretos. |

| 2026-09-26 | 0.0.31 | Desarrollo | **Fase 3, Etapa 3.1 completa — infraestructura base del bot, sin IA todavía.** Encargo de 6 tareas recibido de Claude web, ejecutado en orden. Variables de entorno nuevas (fail-fast para las de WhatsApp), 3 tablas nuevas (`conversaciones`/`mensajes`/`leads`, separadas de `pedidos` a propósito), `WhatsAppClient` (mismo patrón que `RocketfyClient`), webhook + `BotWorker` en background (cola + thread, para no bloquear la respuesta a Meta). Dos desvíos conscientes del encargo original, documentados en el código y arriba en detalle: el worker se arranca dentro de `create_app()` en vez de solo bajo `__main__` (si no, nunca arrancaría con `flask run`, que es como pide probarlo la propia Tarea 5), y se resolvió `conversacion_id` antes de encolar en vez de dejarlo como `None` (la columna es NOT NULL). 24 tests nuevos, 129/129 en total. **Prueba end-to-end real ejecutada con éxito** vía el botón de prueba del panel de Meta (no fue posible con un mensaje 100% real porque la app de Meta no está publicada — hallazgo documentado en detalle arriba) — webhook recibido, parseado, conversación y mensaje persistidos correctamente en Supabase real; las dos llamadas salientes fallaron de forma esperada (datos de prueba simulados) y el sistema las manejó sin caerse. En el camino: Supabase se pausó por inactividad (se confirmó que no se perdió nada al reactivarlo), el túnel de `cloudflared` se cayó varias veces (incluida una vez por una red wifi pública que bloqueaba el tráfico), y el token de acceso de WhatsApp se regeneró varias veces hasta obtener uno permanente. Hallazgo de seguridad pendiente, documentado y no resuelto a propósito: el webhook no verifica la firma `X-Hub-Signature-256` de Meta (falta `WHATSAPP_APP_SECRET`, no pedido en esta etapa). |

| 2026-09-26 | 0.0.32 | Auditoría | **Repaso pedido explícitamente por el usuario: "no olvides anotar todo lo que estamos llevando en entornos de prueba y que después habrá que hacer distinto para producción."** Se revisó toda la sección de pendientes transversales buscando huecos, y se encontraron 3 reales que no estaban anotados todavía: (1) pendiente #6 solo mencionaba el túnel temporal de Rocketfy — se amplió para dejar explícito que el webhook de WhatsApp tiene EXACTAMENTE el mismo problema (URL temporal, se cae, hay que re-registrarla); (2) pendiente #15 mezclaba dos pasos distintos de Meta que no son lo mismo — se separó "registrar el número de teléfono real del negocio" (rápido, sin revisión de Meta) de "publicar la app para hablar con cualquier número" (revisión + verificación de negocio, días/semanas); (3) se agregó el pendiente #17 (Supabase se pausa solo por inactividad en el plan gratuito — pasó dos veces durante la Fase 3, sería una caída real en producción) y el #18 (la cola del `BotWorker` vive solo en memoria — un reinicio del proceso con mensajes sin procesar los pierde en silencio). Ninguno de estos 3 bloquea seguir desarrollando la Etapa 3.2, pero los tres hay que resolverlos antes de operar con clientes reales. |
| 2026-09-26 | 0.0.33 | Documentación | Creado `docs_para_claude/08_fase3_etapa31_resultados.md` — resultados de la Etapa 3.1 para entregarle a Claude web como archivo (no solo pegado en el chat): qué se construyó, los 2 desvíos conscientes del encargo original con su razonamiento, el resultado real de la prueba end-to-end (payload real de Meta incluido, sin secretos), y la tabla consolidada de los 6 pendientes de producción que salieron de la auditoría de la entrada anterior. Verificado sin secretos reales antes de guardarlo. |
| 2026-09-26 | 0.0.34 | Desarrollo | **Fase 3, Etapa 3.2 completa — Victoria piensa y vende con un LLM, detrás de una interfaz desacoplada (`LLMProvider`).** Encargo de 10 tareas recibido de Claude web, ejecutado en orden (detalle completo, con los 5 desvíos conscientes y su razonamiento, en la sección "Etapa 3.2" arriba). Persistencia de la cola del `BotWorker` agregada (resuelve el pendiente #18). Base de conocimiento de productos (`productos_bot`/`anuncios_productos`) separada del catálogo de Rocketfy. Capa `src/integrations/llm/` con contratos neutrales + adapter único de Anthropic, protegida con un test de contención que barre todo `src/`. Las 5 herramientas de Victoria (`tools.py`) con `PedidoService` real probado contra Rocketfy mockeado. `TelegramNotifier` para avisar al dueño cuando se escala. Simulador de terminal (`tools/chat_con_victoria.py`) listo y verificado hasta el punto exacto donde pide la `ANTHROPIC_API_KEY` real (todavía vacía en `.env` al cerrar esta entrada). 41 tests nuevos, **170/170 en total**. Pendiente inmediato, no bloqueante: pegar la key real y correr las 2 conversaciones de prueba del simulador para completar la Tarea 8. |
| 2026-09-27 | 0.0.35 | Validación real | **Tarea 8 completada contra las APIs reales de Anthropic y Rocketfy — encontró y arregló 2 bugs reales que ningún test con mocks podía haber revelado, y dejó documentado un tercer hallazgo sin resolver.** El usuario pegó `ANTHROPIC_API_KEY` real en `.env`. Al correr las 2 conversaciones de prueba pedidas (venta cerrada por contraentrega, escalada por pregunta fuera de alcance — ambas en la sección "Etapa 3.2" arriba y con transcripción completa en `docs_para_claude/09_fase3_etapa32_resultados.md`), la primera falló 3 veces antes de cerrar limpio: (1) el LLM no copiaba el SKU exacto del catálogo (inventó `AUD-BT-001`, mandó el nombre en vez del SKU, mandó `N/A`) — se agregó autocorrección server-side contra `productos_bot` por nombre (`tools.py::_handle_registrar_producto`); (2) Rocketfy rechazó el teléfono porque WhatsApp lo entrega con código de país (`593XXXXXXXXX`) y Rocketfy exige formato local ecuatoriano — se agregó `_telefono_formato_rocketfy()`. Cada intento real que quedó a medias o se confirmó de verdad en Rocketfy se limpió con `rechazar_pedido()` (mismo patrón que `rocketfy_order_smoke_test.py`), sin dejar pedidos de prueba activos. Tercer hallazgo, sin resolver a propósito (queda para que Claude web decida el diseño): ninguna herramienta tiene un parámetro para la variante/color del producto, y Victoria a veces escala en vez de cerrar cuando ese dato queda sin resolver — no es un bug, es un hueco en el esquema de herramientas (pendiente #23). 3 tests nuevos, **173/173 en total**. Confirmado sin errores de autenticación contra la API real de Claude. |
| 2026-09-27 | 0.0.36 | Desarrollo | **Ajuste posterior a la Etapa 3.2 — resuelve el pendiente #23 (variante/color).** Encargo de 4 tareas de Claude web, ejecutado sin desvíos (detalle completo en la subsección "Ajuste posterior" dentro de "Etapa 3.2" arriba). `leads.producto_variante` (migración 010), `registrar_producto` con parámetro opcional `variante` (nunca motivo de escalar, reforzado en la herramienta y en el system prompt), el nombre de línea que se manda a Rocketfy incluye la variante cuando existe, y nueva resiliencia: si `registrar_producto` no encuentra ningún producto real ni por SKU ni por nombre, ya no guarda nada — le devuelve a Victoria la lista real de productos para que pregunte de nuevo. Documentado en `cargar_producto_bot.py` que el SKU cargado siempre debe ser real de Rocketfy. Verificado contra la API real de Claude: cliente ambiguo sobre el color, Victoria registra sin variante y cierra la venta contraentrega igual (pedido real confirmado y luego rechazado como limpieza). 4 tests nuevos, **177/177 en total**. |
| 2026-09-27 | 0.0.37 | Validación real | **Telegram configurado por el usuario (bot `@AzoShopBot` vía `@BotFather`, `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` en `.env`) y verificado con una escalación real.** De paso, se corrigió un hueco real en `TelegramNotifier.notificar_escalado()`: solo atrapaba `requests.RequestException` y nunca revisaba el cuerpo de la respuesta — Telegram responde HTTP 200 con `ok=false` para varios errores de negocio (chat_id inválido, bot que nunca recibió `/start`, etc.), que antes se habrían dado silenciosamente por enviados sin serlo. Ahora se revisa `ok` en la respuesta: loguea advertencia si falla, info con el `message_id` si tuvo éxito, y el `except` se amplió a `Exception` para que ningún fallo (red, JSON inválido, lo que sea) se escape del best-effort. Verificado disparando una escalación real con `tools/chat_con_victoria.py` ("prefiero hablar con una persona real") contra la API real de Claude: la conversación escaló (`estado='escalada'`) y el log del servidor confirmó `Notificación de escalado enviada a Telegram (message_id=3)`, es decir que Telegram devolvió `ok=true` de verdad — el usuario confirmó además haber visto el mensaje llegar a su Telegram. 1 test nuevo, **178/178 en total**. |
| 2026-09-27 | 0.0.38 | Desarrollo | **Módulo de Conversaciones completo — backend + dashboard (detalle completo en la sección "Etapa 3.3" arriba).** Encargo de 4 tareas de Claude web. Backend nuevo (`src/routes/conversaciones/`) reutilizando los repositorios de `routes/whatsapp` en vez de duplicarlos; ventana de mensajería (24h servicio + 72h FEP) calculada en un solo lugar y validada antes de tocar BD o WhatsApp; 5 endpoints. Dos extensiones necesarias no pedidas literalmente: `conversaciones.estado` ahora sí se marca `esperando_pago` de verdad (antes solo `leads.estado` lo hacía, la pestaña nueva habría estado siempre vacía), y la limpieza de `vista_en` al escalar se aplicó también al camino determinista de `WebhookService`, no solo al de Victoria. Dashboard: 2 páginas nuevas (`/conversaciones`, `/conversaciones/[id]`) con pestañas de acceso rápido, ventana de mensajería visible, notas internas, reactivar, y botón hacia el formulario de pedido manual existente (se le agregó soporte de prefill por querystring, antes no lo tenía). Antes de tocar el frontend se revisó `node_modules/next/dist/docs` por instrucción del propio repo (Next.js 16 con cambios de ruptura) — encontró que `useSearchParams()` exige un límite `Suspense` o `next build` falla, ya resuelto. 26 tests nuevos en el backend, **205/205 en total**; frontend sin tests automatizados (decisión de alcance), `build`/`lint` limpios y verificado de punta a punta contra Supabase real (no solo mocks) vía el cliente de test de Flask. Sin verificar: el envío real a un teléfono de WhatsApp de verdad (todos los números de prueba de esta fase son inventados) y la confirmación visual del usuario en el navegador. |

**Estado actual:** Fase 1 (backend) completa, probada (105/105 tests) y
**validada contra Rocketfy real** de punta a punta. Etapas 8 y 9 quedaron
pospuestas por decisión del usuario (no canceladas). Fase 2 (Frontend):
las 6 pantallas construidas (Etapas 0-6 de 7), falta la Etapa 7
(pulido y despliegue). **Fase 3 (bot de WhatsApp "Victoria"): Etapas 3.1 y
3.2 completas, verificadas de punta a punta contra Anthropic, Rocketfy Y
Telegram reales** (178/178 tests) — Victoria ya piensa y vende de verdad
con Claude detrás de una interfaz de proveedor desacoplada: ventas
contraentrega reales se cerraron de punta a punta (incluida una con una
respuesta ambigua sobre el color, sin escalar innecesariamente), pedidos
de prueba confirmados en Rocketfy y luego rechazados para limpieza, una
conversación fuera de alcance escaló correctamente a un humano, y una
escalación real de prueba confirmó tanto del lado del servidor (Telegram
respondió `ok=true`) como del usuario (confirmó haber recibido el mensaje
en su Telegram) que la notificación de escalado funciona de punta a
punta (bot `@AzoShopBot`, ver entrada 0.0.37). **Módulo de Conversaciones
completo** (entrada 0.0.38): un humano ya puede ver y responder desde el
dashboard cuando Victoria escala — antes de esto, escalar no tenía ningún
efecto práctico posible. Falta: confirmación visual del usuario de las 2
pantallas nuevas, probar el envío de un mensaje manual contra un teléfono
de WhatsApp real, y las decisiones de puesta en producción ya conocidas
(publicar la app de Meta, número real, firma del webhook).

**Próximo paso:** el usuario abre `/conversaciones` en el navegador para
confirmar visualmente las 2 pantallas nuevas, y prueba responder a una
conversación real (o de un número de la lista de prueba de Meta) para
confirmar que el mensaje llega de verdad al teléfono. Claude web revisa
las transcripciones reales de las entradas 0.0.35, 0.0.36, 0.0.37 y
0.0.38, y decide junto con el usuario el siguiente paso: publicar la app
de Meta, migrar al número real, o seguir
afinando el system prompt de Victoria con más pruebas del simulador. En
paralelo, sigue pendiente la Etapa 7 de la Fase 2 (pulido/despliegue) si
el usuario prefiere retomarla
mientras tanto.

**Pendientes transversales que siguen abiertos hoy** (detalle completo en
la sección 5 más abajo — esta lista incluye a propósito TODO lo que hoy
se resuelve "a la manera de entorno de prueba" y que va a necesitar
hacerse distinto antes de operar con clientes reales):
- Alerta *push* al dueño (no solo visible si entras al panel) — se cruza directamente con la necesidad de notificación de escalado del bot (pendiente #2)
- Forma exacta de `bulk/getInfo` sin confirmar con volumen real (pendiente #3)
- Estrategia de jobs en producción con gunicorn multi-worker (pendiente #4, Etapa 8 pospuesta)
- Cotización de flete y saldo de wallet: limitación de Rocketfy, no nuestra — reforzado con el hallazgo del mínimo real (pendiente #5)
- **Las URLs de AMBOS webhooks (Rocketfy y WhatsApp) siguen siendo túneles temporales** — falta elegir hosting real para las dos (pendiente #6)
- KYC nunca confirmado formalmente en el panel, aunque ya funciona (pendiente #8)
- UX del historial de incidencias puede confundir (pendiente #12, el usuario pidió dejarlo para después)
- ~~3 decisiones de arquitectura del bot~~ — **RESUELTO** (pendiente #13, ver entrada 0.0.30)
- El webhook de WhatsApp no verifica la firma `X-Hub-Signature-256` de Meta — falta agregar `WHATSAPP_APP_SECRET` y validarla antes de cualquier despliegue real (pendiente #14)
- No se ha probado con un número de WhatsApp real ni se ha registrado el número real del negocio — la app de Meta sigue sin publicar (pendiente #15, con la aclaración de que registrar el número real es un paso separado y más rápido que publicar la app)
- Confirmar que el token de acceso de WhatsApp sea realmente permanente, y definir cómo renovarlo sin caídas (pendiente #16)
- **Nuevo:** Supabase (plan gratuito) se pausa solo por inactividad — pasó dos veces en esta fase; sería una caída real en producción (pendiente #17)
- ~~La cola del `BotWorker` vive solo en memoria~~ — **RESUELTO 2026-09-26** (Etapa 3.2, Tarea 1): tabla `cola_mensajes` + `recuperar_pendientes()` (pendiente #18)
- **Nuevo (pendiente #16):** `WHATSAPP_API_TOKEN` es un token de acceso que vence — hay que confirmar que el último generado sea realmente permanente (no solo de 24h) o definir el proceso para refrescarlo sin interrumpir el bot en producción
- ~~`ANTHROPIC_API_KEY` real todavía no configurada~~ — **RESUELTO 2026-09-27**: transcripciones reales del simulador corridas y verificadas (pendiente #19, entrada 0.0.35)
- **Nuevo (Etapa 3.2):** Victoria no puede verificar comprobantes de pago (sin visión todavía) — siempre escala a un humano por diseño; visión real queda para más adelante (pendiente #20)
- ~~Sin forma de reactivar desde el dashboard una conversación escalada~~ — **RESUELTO 2026-09-27** (Etapa 3.3). Sigue sin panel de administración para `productos_bot` (solo el script de consola) (pendiente #21)
- **Nuevo (Etapa 3.3):** el módulo de Conversaciones (responder manual) no se probó contra un envío real de WhatsApp, solo contra Supabase real — todos los números de prueba son inventados (pendiente #24)

---

## 5. Pendientes Transversales (retomar más adelante)

> Lista viva de decisiones/credenciales que faltan y que NO bloquean el
> desarrollo actual, pero que sí hay que resolver antes de operar en serio.
> Se actualiza en cada sesión — no se pierde nada de vista aquí.

| # | Pendiente | Bloquea a | Detalle / dónde está anotado |
|---|---|---|---|
| 1 | ~~Canal real de envío de WhatsApp a clientes finales~~ — **EN DESARROLLO desde 2026-09-15** (Fase 3): decidido en la planificación usar WhatsApp Cloud API de Meta, directo, sin BSP (`docs/BotPlanifiacion.md`). Construcción real todavía no empezada — Claude web está diseñando la arquitectura | Que las notificaciones de "tu paquete llega hoy" se envíen de verdad (hoy solo se loguean) | ADR-004, `src/notifications/_log_channel.py`, Fase 3 |
| 2 | ~~Mecanismo de alerta interna~~ — **EN GRAN PARTE RESUELTO 2026-09-07** (Fase 2, Etapa 3): `/incidencias` ya muestra novedades de pedidos y alertas de stock/precio en el dashboard, dejaron de ser solo un log. Lo que falta para cerrarlo del todo: un aviso **push/proactivo** (que el dueño se entere sin tener que abrir el panel) — hoy hay que entrar a mirar. Se puede resolver más adelante con algo simple (un correo, o el futuro bot de WhatsApp) | Reacción inmediata a incidencias (hoy la reacción es "si entro a mirar", no push) | Fase 2, Etapa 3 |
| 3 | Forma exacta de la respuesta de `POST /orders/bulk/getInfo` (sin ejemplo en la doc del proveedor) | Confiabilidad del job de reconciliación con volumen real de pedidos | Duda #13, `src/jobs/reconciliacion/service.py::_extraer_pedidos` |
| 4 | Estrategia de arranque de jobs (reconciliación, stock watcher) en producción con gunicorn multi-worker — hoy solo arranca en el proceso `__main__` de desarrollo | Despliegue a producción | `app.py::start_scheduler`, Etapa 8 |
| 5 | Endpoints de cotización de flete (`/api/shipping/quote`, `/api/locations`) y saldos de wallet no existen en la API — decidido NO solicitarlos por ahora. **Reforzado 2026-09-07:** se confirmó con un pedido real que el mínimo de confirmación no es fijo, incluye el costo de envío calculado por Rocketfy — sin cotizador, ese mínimo real es imposible de saber de antemano (ver duda #14) | Requerimientos 2 y 6 al 100% | ADR-003, sección 6 (dudas al proveedor, #14) |
| 6 | ~~Nunca probado con eventos reales~~ — **VALIDADO** con túneles temporales (`cloudflared`): el webhook de Rocketfy (2026-09-06) y el de WhatsApp (2026-09-26) recibieron y procesaron eventos reales. Queda pendiente la parte que sí sigue abierta, y ahora es **doble**: hay que elegir un hosting real y reemplazar **las dos** URLs temporales por definitivas — mientras sean túneles: (a) dejan de responder en cuanto se cierra la sesión (pasó varias veces durante las pruebas — hay que reabrir el túnel y volver a registrar la URL cada vez), (b) cualquier evento real que Rocketfy intente mandar mientras el túnel esté caído cuenta contra su presupuesto de 10 fallos de por vida, y (c) los túneles "quick" de `cloudflared` no tienen garantía de actividad ni funcionan en redes que bloqueen su tráfico (pasó con una wifi pública) | Operar con clientes reales, en cualquiera de los dos canales (no bloquea seguir desarrollando) | Entrada 0.0.15, sección 8 de `docs/CONCEPTOS_TECNICOS.md`; Fase 3 Etapa 3.1 |
| 7 | ~~Etapa 3 nunca probada contra producción real~~ — **RESUELTO 2026-09-06**: smoke test ejecutado, flujo crear→confirmar→rechazar validado con un pedido real | — | Entrada 0.0.13 |
| 8 | KYC de la cuenta Rocketfy: se infiere aprobado porque `/products/list` ya responde 200, pero nunca se confirmó explícitamente en el panel | Ninguno hoy (ya funciona), pero conviene confirmarlo formalmente | Sección 3.1 |
| 9 | ~~Rocketfy exige un recaudo mínimo de $10.00 para confirmar un pedido contraentrega~~ — **RESUELTO 2026-09-06**: se agregó validación local antes de crear el pedido, aplicable SOLO si `no_contra_entrega=false` (confirmado con el propio usuario y el doc del proveedor: el mensaje de error dice literalmente "pedido contraentrega", y ya existía el campo `not_COD` para marcar un pedido como prepagado) | — | `RECAUDO_MINIMO_CONTRAENTREGA` en `constants.py`, `RecaudoMinimoNoAlcanzadoError`, entrada 0.0.14 |
| 10 | ~~Fase futura del bot conversacional IA por WhatsApp~~ — **EN PLANIFICACIÓN desde 2026-09-15** (Fase 3) — ver subsección "Fase 3" al final de la sección 3 | Requerimiento 1 con mínima intervención manual | Sección 3, "Fase 3 — Bot Conversacional de WhatsApp" |
| 13 | ~~3 decisiones de arquitectura del bot sin resolver~~ — **RESUELTO 2026-09-15**: (1) el bot vive dentro del backend Flask existente, como módulo nuevo con acceso directo en Python a `PedidoService`; (2) usa el mismo proyecto de Supabase, con tablas propias nuevas (no reutiliza `pedidos`); (3) el LLM es Claude (Anthropic). Falta la arquitectura detallada (a cargo de Claude web) y la implementación | — | `docs_para_claude/07_preguntas_abiertas.md`, entrada 0.0.29 |
| 14 | El webhook de WhatsApp (`POST /webhooks/whatsapp`) no verifica la firma `X-Hub-Signature-256` que manda Meta (HMAC-SHA256 del cuerpo con el App Secret) — a diferencia del webhook de Rocketfy, que sí tiene su propio token. No se implementó porque `WHATSAPP_APP_SECRET` no era parte de las variables pedidas en la Etapa 3.1 | Cualquier despliegue real del webhook (hoy no es grave: la URL es un túnel temporal que cambia seguido) | Fase 3, Etapa 3.1, `src/routes/whatsapp/controllers.py` |
| 15 | No se ha probado el envío/recepción con un número de WhatsApp real — la app de Meta sigue sin publicar, y mientras no lo esté, Meta solo entrega webhooks de prueba disparados desde su propio panel (hallazgo confirmado, ver Etapa 3.1). **Dos pasos distintos, no confundir uno con el otro:** (a) registrar el número de teléfono REAL del negocio en la WABA (se pueden agregar hasta 2 números sin verificación de negocio, hasta 20 una vez verificada) — esto es rápido y no requiere revisión de Meta; (b) publicar la app / completar la revisión de Meta para poder hablar con CUALQUIER número (no solo los de la lista de prueba) — esto sí requiere verificación de negocio + revisión de Meta (días/semanas). Se puede avanzar con (a) sin esperar a (b) | Operar con clientes reales por WhatsApp | Fase 3, Etapa 3.1; `docs/BotPlanifiacion.md` sección 13 (checklist de configuración de Meta) |
| 17 | **Riesgo real de producción, confirmado dos veces durante la Fase 3:** el proyecto de Supabase (plan gratuito) se pausa solo por inactividad y hay que reactivarlo a mano desde el dashboard. Si esto pasa en producción con clientes reales, el bot y el backend quedarían caídos hasta que alguien lo note y lo reactive. Hay que decidir: pasar a un plan pago de Supabase (no se pausa), o algún mecanismo que mantenga actividad periódica, antes de operar en serio | Continuidad del servicio en producción (backend Y bot) | Confirmado 2026-09-17 y de nuevo implícitamente durante la Fase 3 |
| 18 | ~~La cola del `BotWorker` vive solo en memoria~~ — **RESUELTO 2026-09-26** (Etapa 3.2, Tarea 1): tabla `cola_mensajes` registra cada tarea antes de encolarla en memoria (`estado` pendiente/procesando/completado/error, `intentos`), y `BotWorker.iniciar()` llama `recuperar_pendientes()` para reponer en la cola en memoria lo que quedó `pendiente` o `procesando` hace más de 5 minutos (huérfano de un proceso anterior) | — | Fase 3, Etapa 3.2, `src/routes/whatsapp/worker.py`, `007_cola_mensajes.sql` |
| 16 | Confirmar que el token de acceso de WhatsApp (`WHATSAPP_API_TOKEN`) generado sea realmente permanente (no uno más de 24h) — se regeneró varias veces durante la Etapa 3.1 antes de obtener el que parece ser el definitivo. Falta además definir el proceso para refrescarlo sin interrumpir el bot el día que corresponda hacerlo (usuario de sistema + token de larga duración es la vía recomendada por Meta) | Continuidad del canal de WhatsApp en producción | Fase 3, Etapa 3.1, `backend/.env` |
| 11 | ~~Ninguna ruta del backend exigía autenticación~~ — **RESUELTO 2026-09-07** (Fase 2, Etapa 1): login con Supabase Auth + verificación en cada request. Nota consciente: no restringe por correo específico a nivel de código (decisión del usuario, ver entrada 0.0.21) — la barrera es el acceso al dashboard de Supabase para crear cuentas | — | Fase 2, Etapa 1, entradas 0.0.20-0.0.21 |
| 12 | **Nuevo (2026-09-07):** UX de la pestaña "Eventos de pedidos" de `/incidencias` con "mostrar todo el historial" activado — el usuario notó, con razón, que un mismo pedido puede aparecer varias veces con estados distintos (es una bitácora de eventos, no el estado actual — explicado en el chat, no es un bug) y que eso puede confundir a simple vista. Mejoras posibles: aclarar visualmente que es un historial, agrupar filas por pedido, o mostrar solo el evento más reciente por pedido con un despliegue para ver el resto. El usuario pidió dejarlo pendiente por ahora | Claridad visual, no funcionalidad (los datos ya son correctos) | `src/app/(dashboard)/incidencias/eventos-tab.tsx` |
| 19 | ~~`ANTHROPIC_API_KEY` real todavía no configurada~~ — **RESUELTO 2026-09-27**: el usuario la pegó en `.env`, las 2 transcripciones reales de la Tarea 8 se corrieron y verificaron (ver entrada 0.0.35) | — | Fase 3, Etapa 3.2, entrada 0.0.35 |
| 23 | ~~Ninguna herramienta de Victoria tenía un parámetro para la variante/color del producto~~ — **RESUELTO 2026-09-27** (ver entrada 0.0.36): `registrar_producto` acepta `variante` (opcional, nunca motivo de escalar), `leads.producto_variante` la guarda, y `cerrar_venta` la incluye en el nombre de la línea que se manda a Rocketfy. Verificado contra la API real de Claude con una variante ambigua sin que escale | — | Fase 3, Etapa 3.2, entrada 0.0.36 |
| 20 | **Nuevo (Etapa 3.2):** Victoria no tiene visión de imágenes — no puede verificar por su cuenta una captura de comprobante de pago. Es una decisión de alcance consciente de esta fase (regla determinista: imagen + lead `esperando_pago` → escala siempre a un humano), no un bug, pero cerrar pedidos por transferencia sigue necesitando intervención manual mientras esto no se resuelva | Automatizar el cierre de ventas por transferencia (hoy solo contraentrega lo cierra Victoria sola) | Fase 3, Etapa 3.2, `src/routes/whatsapp/services.py::_encolar_respuesta` |
| 21 | ~~Sin panel de administración para `productos_bot` ni botón en el dashboard para reactivar una conversación escalada~~ — **la parte de reactivar quedó RESUELTA 2026-09-27** (Etapa 3.3, módulo de Conversaciones: botón "Devolver el control a Victoria" + `POST /conversaciones/<id>/reactivar`). Sigue pendiente solo la parte de `productos_bot`: se carga únicamente con `tools/cargar_producto_bot.py` por consola, sin panel | Cargar/editar productos sin depender de la consola | Fase 3, Etapa 3.2 y 3.3 |
| 22 | **Nuevo (Etapa 3.2):** Flujo 2 (formulario web) y Flujo 4 completo de `docs/BotPlanifiacion.md` no se construyeron en esta fase — solo se cubrió una versión mínima del Flujo 3 (postventa, detección determinista de pedido previo) | Cobertura completa de los 4 flujos de conversación planificados originalmente | `docs/BotPlanifiacion.md`, Fase 3, Etapa 3.2 |
| 24 | **Nuevo (Etapa 3.3):** el módulo de Conversaciones (responder manual desde el dashboard) se verificó de punta a punta contra Supabase real, pero NO contra un envío real de WhatsApp — todos los números de prueba usados son inventados y Meta solo entrega/acepta mensajes hacia números de su lista de prueba (mismo límite que la Etapa 3.1). Falta también la confirmación visual del usuario de las 2 pantallas nuevas (sin herramienta de navegador disponible para Claude) | Confiar en que "responder manualmente" funciona con un cliente real, no solo en teoría | Fase 3, Etapa 3.3 |

---

## 6. Dudas / Peticiones para el Proveedor (Rocketfy)

Además de lo que el propio documento ya señala como pendiente (secciones
10.1 y 10.2), quedan estos puntos abiertos identificados durante el
diseño técnico:

1. ¿El catálogo de cantones (CSV) se mantiene sincronizado? ¿Hay
   notificación de altas/bajas de cantones o cambios de cobertura por
   transportadora?
2. `shipping_method` se ignora y se usa "la transportadora por defecto
   configurada en la cuenta" — ¿dónde/cómo se configura eso? ¿Es por
   `store_id` o global a la cuenta?
3. "Un pedido no puede mezclar productos de bodegas distintas" — ¿cómo se
   identifica a qué bodega pertenece cada SKU antes de crear el pedido? El
   payload de `/products/list` documentado no incluye ese dato.
4. ¿Hay un rate limit real (requests/min) aunque hoy no se aplique
   estrictamente? Necesario para dimensionar los jobs de reconciliación y
   vigilancia de stock.
5. ~~Si el webhook se autodesactiva tras 10 fallos, ¿existe un endpoint para
   reenviar/recuperar eventos perdidos, aparte de la reconciliación manual
   vía `bulk/getInfo`?~~ **RESUELTA** por `Rocket-Webhooks-Guia-Integrador.md`:
   no existe recuperación, los eventos no aceptados se pierden para siempre.
   Único mecanismo de respaldo: reconciliación periódica vía `bulk/getInfo`.
6. ~~Formato exacto del CSV de cantones: delimitador, encoding (UTF-8/Latin1),
   si incluye tildes en los nombres.~~ **RESUELTA** por inspección directa del
   archivo recibido: CSV separado por comas, UTF-8 con BOM (`utf-8-sig`),
   columnas `city_id,canton,province_id,provincia`, con tildes/ñ correctas,
   832 filas de datos + encabezado, 24 provincias, sin `city_id` duplicados
   — coincide exactamente con lo declarado en la sección B del doc principal.
7. Para expansión futura a Chile (base URL y credenciales distintas): ¿el
   mismo `Auth-token` sirve para ambos países o son cuentas 100%
   independientes con activación separada?
8. ¿`revenue_*` en `/statistics/general` incluye o excluye pedidos
   prepagados (`not_COD=1`)?
9. Confirmar que la única vía para corregir líneas de producto/importe es
   rechazar y recrear el pedido (no hay ninguna vía parcial vía `/orders/modify`).
10. ¿Aceptan pruebas de webhook con pedidos reales de bajo valor en
    producción sin que afecte el monitoreo de calidad de servicio de la
    cuenta, dado que no existe entorno sandbox?
11. La sección 3.3 del doc dice que "la mayoría" de endpoints usan la
    envoltura `{ok, code, message, content}`, y solo marca `getInfo`/`bulk
    getInfo` como excepción. Pero el ejemplo de respuesta de
    `/orders/create` (sección 4.4) no trae ningún nodo `content` — trae
    `id` y `products_stock` al mismo nivel que `ok`/`code`/`message`.
    ¿`/orders/create` (y por extensión `/orders/confirm`, `/modify`,
    `/reject`) usan `content` o no? Confirmar la forma exacta de cada
    respuesta de éxito para no romper el parseo en producción.
12. (No bloqueante, para cuando desplememos el webhook) La guía de
    integración sugiere "pedir a soporte de Rocket la IP de salida de su
    servidor" para poder filtrar por IP en el firewall, además del token en
    la URL. Solicitar esa IP a soporte cuando publiquemos el endpoint.
13. La forma exacta del JSON de respuesta de `POST /orders/bulk/getInfo` no
    está documentada con un ejemplo (a diferencia de `getInfo` singular, que
    sí lo tiene). ¿Es `{"orders": [...]}`, `{"data": [...]}`, una lista
    plana, u otra cosa? Necesario para que el job de reconciliación parsee
    correctamente — hoy el código lo intenta de forma defensiva probando
    varias formas, pero convendría confirmarlo antes de depender de esto en
    producción con volumen real de pedidos.
14. **Nuevo (2026-09-07, hallazgo real durante la Etapa 6 de Fase 2):** al
    confirmar, Rocketfy exige un mínimo que NO es un número fijo — es
    "el valor de los productos + el costo del envío", calculado
    internamente por ellos (mensaje real recibido: *"El importe mínimo del
    pedido debe ser el del valor de los productos + el costo del envío
    ($18.47)"*). Esto es más estricto que el mínimo fijo de $10 para
    contraentrega que ya conocíamos (ver `RECAUDO_MINIMO_CONTRAENTREGA`,
    Fase 1 entrada 0.0.13) — cumplir ese mínimo fijo NO garantiza que la
    confirmación pase. Como no existe endpoint de cotización de flete
    (mismo problema ya señalado en el punto de ADR-003 / Requerimiento 2),
    no hay forma de calcular este mínimo real de antemano desde nuestro
    lado. ¿Existe alguna forma de consultarlo antes de confirmar, aunque
    sea de forma aproximada?
