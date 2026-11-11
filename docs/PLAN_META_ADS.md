# Plan: cerrar el ciclo de ventas entre WhatsApp y Meta Ads

> Versión 1.0 · 2026-11-11 · Responsable: Freddy · Ejecuta: Claude
> Nace de un plan externo (v1.0 del 11-nov-2026) que se adaptó a lo que PROYECTECOM ya tiene construido.
> Decisión registrada como ADR-016 en `PROGRESS.md`. Pendientes: #68 (envío del evento) y #77 a #79.

## 1. Para qué sirve (en llano)

Hoy Meta sabe que alguien **escribió** por un anuncio, pero no sabe si esa persona **compró**. Por eso solo puede
optimizar por «conversaciones» y no por compradores. La idea es avisarle a Meta, cuando una venta se confirma, qué
clic de qué anuncio la originó. Se hace en dos tiempos:

1. **Medir:** se envía el evento de compra (`Purchase`) mientras la campaña sigue optimizando por conversaciones.
2. **Optimizar:** cuando haya suficientes compras reportadas, se cambia la campaña a «Compras por mensajería».

## 2. Qué ya existe y qué falta

| Pieza | Estado |
|---|---|
| Captura del `ctwa_clid` y de todo el `referral` por cada llegada (`conversacion_anuncios`, único por `wamid`) | **Hecho** (ADR-013, migración 023) |
| Atribución por lead y por venta (`leads.id_anuncio/ctwa_clid`, `ventas.id_anuncio`, ventana de 30 días) | **Hecho** (ADR-015) |
| Vínculo anuncio → producto y pantalla «Anuncios» | **Hecho** |
| Punto de confirmación de cada tipo de venta | **Hecho** (ver §5) |
| Parámetros con interruptor, trabajos automáticos y avisos por Telegram | **Hecho**, se reutilizan |
| Dataset de Meta asociado a la cuenta de WhatsApp | **Falta** (lo crea Freddy / Claude con el token) |
| Token de usuario de sistema con permisos de eventos | **Falta** (lo genera Freddy; va en Railway, nunca en el chat) |
| Bandeja de salida `eventos_meta`, servicio de envío y trabajo con reintentos | **Falta** (Fase 1) |
| Tablero de eventos enviados y costo real por venta | **Falta** (Fase 2) |
| Campaña real que traiga un `referral` de verdad (pendiente #66) | **Falta** |

## 3. Inventario de Meta (revisado con los conectores el 2026-11-11, solo lectura)

| Activo | Lo que se vio |
|---|---|
| Portafolio comercial **AzoShop** (`1152842416600198`) | Único portafolio que ven los conectores. Sin verificación de empresa. Contiene la cuenta de WhatsApp de AzoShop (con su número registrado y listo para enviar) y la cuenta de mensajería «AzoShop» (aprobada). Es el que hay que **reutilizar**: no hay que crear otro. |
| Otra cuenta de WhatsApp dentro del mismo portafolio | Tiene el número personal de Freddy y la cuenta de mensajería sin nombre. No se toca. |
| Páginas de Facebook | `AzoShop` (`1368937172962345`), `Andina Store` (`1371207002741243`) y `Propiedades Ecuador` (`1153068301232084`). Para AzoShop corresponde la Página **AzoShop**. |
| Cuenta publicitaria `853869848927360` | **Activa**, con método de pago, en USD. **No pertenece a ningún portafolio** (sin dueño comercial). Es la misma de la campaña de la casa. |
| Campañas en esa cuenta | «Campaña Casa Guayaquil - Mensajes» (**activa**, 154,03 USD gastados) y un impulso de Marketplace de una chompa (**activo**, 1 USD diario). **No hay ninguna campaña de AzoShop.** |
| Datasets / píxeles | **Cero**, tanto en la cuenta publicitaria como en el portafolio. |
| Catálogos | Cero. |
| Cuentas de Instagram vinculadas a la cuenta publicitaria | Ninguna. |
| Tienda web de AzoShop (otro proyecto en Vercel) | No se ve desde los conectores (no hay píxel registrado). |

**Lectura:** la cuenta publicitaria está mezclada con la campaña de la casa y sin portafolio. Para tener todo de AzoShop por
su lado, la recomendación es **crear una cuenta publicitaria nueva dentro del portafolio AzoShop** (Configuración del negocio →
Cuentas → Cuentas publicitarias → Agregar → Crear), con su propio método de pago, y usarla solo para AzoShop. Las campañas
actuales **no se tocan**. Esto lo hace Freddy en el administrador de Meta; los conectores no crean cuentas publicitarias.

**No verificado:** si existe algún otro portafolio (por ejemplo uno de la casa o de la tienda web) al que la sesión no tenga acceso.
Los conectores solo listan los que la cuenta de Freddy puede ver, y solo aparece AzoShop.

## 4. Decisiones (recomendaciones aprobadas por Freddy el 2026-11-11)

| Decisión | Resolución |
|---|---|
| Cuándo reportar | Al **confirmarse** la venta, nunca solo al «cerrar el pedido». Contra entrega puede cancelarse, y reportar antes entrena a Meta con ventas falsas. |
| Momento por tipo de venta | Rocketfy: pedido confirmado. Transferencia: «Confirmar pago». Producto propio: «Marcar cobrada». Una venta cancelada después **no se puede des-reportar** (Meta no ofrece borrar): por eso se reporta lo más tarde posible dentro de lo razonable. |
| Valor del evento | **Precio de venta** (total cobrado al cliente, como string/`Decimal`, moneda USD). El margen se evalúa más adelante. |
| Atribución | **Último toque** dentro de 30 días (lo que ya hace el lead). |
| Eventos | Solo `Purchase` al inicio. Las señales intermedias (`QualifiedLead`, etc.) quedan para después. |
| Estado de WhatsApp | **No se quita por ahora** (decisión de Freddy). Se mide: si esas llegadas traen `ctwa_clid` o no (pendiente #77). |
| Interruptor | **Apagado de fábrica** hasta que Freddy lo encienda. |

## 5. Fases

### Fase 0 — Preparar Meta (Freddy, con guía de Claude)
1. Crear la cuenta publicitaria nueva dentro del portafolio AzoShop y asociarla a la Página AzoShop (recomendado).
2. Asegurar que la app de Meta tenga los permisos `whatsapp_business_management` y `whatsapp_business_manage_events` (acceso avanzado).
3. Crear/obtener el **dataset de la cuenta de WhatsApp** (`POST /{waba_id}/dataset`; si ya existe devuelve el mismo).
4. Crear un **usuario de sistema** en el portafolio, asignarle la cuenta de WhatsApp, generar su token y guardarlo en Railway
   como `META_CAPI_TOKEN`. **Nunca en el chat, en el repositorio ni en la bitácora.**
5. Confirmar el **identificador de la cuenta de WhatsApp (WABA)**: los conectores devolvieron identificadores distintos según la herramienta;
   hay que usar el mismo que usa nuestro backend (`WHATSAPP_WABA_ID`).

### Fase 1 — Enviar el evento (Claude; sin cambios visibles) — CONSTRUIDA 2026-11-11, sin desplegar y apagada
- Migración **031**: tabla `eventos_meta` (bandeja de salida): tipo, venta, lead, `ctwa_clid`, valor y moneda, estado
  (`pendiente`/`enviado`/`fallido`/`descartado`), intentos, respuesta de Meta, clave única por (tipo, venta) para no duplicar.
- Servicio `integrations/meta_conversiones.py` (único lugar que habla con Meta; fuera de `integrations/llm/`).
- Trabajo `jobs/eventos_meta`: toma lo pendiente, envía, reintenta con espera creciente y avisa por Telegram si falla varias veces.
  Desacoplado de la venta: si Meta falla, la venta no se ve afectada.
- Parámetros nuevos en el catálogo (ADR-011): interruptor (apagado), moneda, intervalo del trabajo, intentos máximos,
  antigüedad máxima del evento. Nada de secretos ahí; el token y el id del dataset viven en variables del servidor.
- Reglas: sin `ctwa_clid` no se envía (queda `descartado` con el motivo); dinero siempre `Decimal`; si hay duda sobre un envío
  ambiguo, no se reintenta a ciegas.
- Tests: construcción del evento, idempotencia, reintentos, apagado, sin `ctwa_clid`, venta cancelada, cero efectos reales en el modo ensayo.

### Fase 2 — Ver lo que pasa
En la pantalla «Anuncios»: eventos enviados, aceptados y fallidos por anuncio; llegadas sin `ctwa_clid`; costo real por venta.

### Fase 3 — Optimizar
Pasar la campaña a «Compras por mensajería» solo cuando haya suficientes eventos reales. **Mínimo de eventos: no verificado**
(la documentación leída no lo indica); se confirmará con el asistente de Meta al crear la campaña.

## 6. Lo verificado en la documentación oficial de Meta (leída el 2026-11-11)

Fuente: *Conversions API for Business Messaging: Onboarding Guide* (developers.facebook.com).

- **Enviar:** `POST https://graph.facebook.com/v27.0/{DATASET_ID}/events`.
- **Dataset de WhatsApp:** `POST/GET .../{WHATSAPP_BUSINESS_ACCOUNT_ID}/dataset` (si ya existe, devuelve ese).
- **Evento:** `event_name` `Purchase`, `event_time` (Unix), `action_source` `business_messaging`, `messaging_channel` `whatsapp`,
  `user_data` con `whatsapp_business_account_id` y `ctwa_clid`, `custom_data` con `currency` y `value`.
- **Sin `ctwa_clid`:** existe un camino con `page_id` y datos personales cifrados (SHA-256), pero atribuye solo a anuncios de los últimos 7 días
  y tiene menos cobertura. **No lo usaremos** (guardaríamos datos personales sin necesidad).
- **Permisos:** `whatsapp_business_management` y `whatsapp_business_manage_events`. Vale un token de usuario de sistema.
- **Deduplicación:** Meta **no ayuda**; hay que evitar duplicados antes de enviar (por eso la clave única).
- **Optimización por compra:** disponible para anuncios a WhatsApp y Messenger (no Instagram).

**La documentación NO dice** (hay que probarlo con datos reales): la ventana máxima entre el clic y el evento cuando se envía `ctwa_clid`,
la antigüedad aceptada de `event_time`, el formato de la respuesta, el máximo de eventos por petición, el mínimo de eventos para optimizar
y si los clics del Estado de WhatsApp traen `ctwa_clid`.

## 7. Riesgos

| Riesgo | Cómo se controla |
|---|---|
| Reportar una venta que luego se cancela | Se reporta en la confirmación, no al cerrar; solo `Purchase` real |
| Duplicar un evento | Clave única en la bandeja de salida + no reintentar a ciegas ante respuesta ambigua |
| Perder ventas por falta de `ctwa_clid` | Medirlo (#77); si es alto, reconsiderar el Estado de WhatsApp |
| Token expuesto | Solo en Railway; Claude nunca lo lee |
| Mezclar AzoShop con la campaña de la casa | Cuenta publicitaria nueva dentro del portafolio AzoShop (§3) |
| Cuenta publicitaria sin entrega previa | La actual está activa; la nueva se probará con un presupuesto mínimo |

## 8. Pendientes de este plan

- **#77** Medir si el Estado de WhatsApp trae `ctwa_clid` (doc de Meta + primer anuncio real). No se quita por ahora.
- **#78** Fase 0 en Meta (cuenta publicitaria nueva, dataset, usuario de sistema, `META_CAPI_TOKEN` en Railway).
- **#79** Verificar con datos reales: ventana del evento, mínimo de eventos y formato de respuesta.
- **#68** Fase 1 (código) — construida y probada; falta desplegar (migración 031 primero).
- **#66** Primer anuncio real de punta a punta — sigue pendiente.
