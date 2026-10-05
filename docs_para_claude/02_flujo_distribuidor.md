# 02 — Flujo con el Distribuidor (Rocketfy)

## 1. Qué es Rocketfy

**Rocketfy** es la plataforma de dropshipping/logística que despacha los
pedidos físicamente (Ecuador). Expone una **API REST propia** (no es
Shopify, no es un BSP, es un proveedor logístico con su propia API):

- Base URL: `https://rocket-e.com/api` (hay variante `cl.rocket-e.com`
  para Chile, no usada acá).
- No tiene sandbox/ambiente de pruebas — todo se prueba contra
  producción real, con pedidos de bajo valor que luego se rechazan.
- No es un mercado/checkout — nuestro sistema le manda pedidos ya
  cerrados (cliente, dirección, productos, total) para que Rocketfy los
  despache contraentrega o prepagados.

## 2. Autenticación contra Rocketfy

Dos headers en cada request, generados por `RocketfyClient`
(`backend/src/integrations/rocketfy/client.py`):

```
Auth-user:  sha256(correo_de_la_cuenta_vendedora)   # hexdigest
Auth-token: <token de API entregado por Rocketfy>
```

Ambos salen de variables de entorno (`ROCKETFY_ACCOUNT_EMAIL`,
`ROCKETFY_API_TOKEN`) — nunca hardcodeados. Si el hash del correo no
coincide con el token, Rocketfy responde 400; si el token en sí es
inválido, 401.

## 3. El flujo paso a paso: crear + confirmar un pedido

Esto es lo que hace `PedidoService.crear_y_confirmar()`
(`backend/src/routes/pedidos/services.py`) — **es el punto exacto donde
el bot debe conectarse al cerrar una venta**:

```
1. Se recibe un CrearPedidoInputDTO (ver 03_input_output_flujo.md)
2. Se valida que el destino (cantón/provincia) exista en el catálogo
   cerrado de 832 cantones de Rocketfy -- ANTES de llamar a la API
   (evita el error "cantón no válido" que si no aparecería recién al
   confirmar, no al crear)
3. Si es pedido contraentrega (no prepagado) y el total < $10, se
   rechaza LOCALMENTE antes de llamar a Rocketfy (ver hallazgos abajo)
4. POST /orders/create  -> Rocketfy responde con un id_rocketfy
   (el pedido queda "creado" en Rocketfy pero SIN confirmar)
5. Se valida que todas las líneas de producto hayan sido aceptadas
   (products_stock en la respuesta) -- un SKU inexistente se descarta
   EN SILENCIO por Rocketfy, hay que detectarlo nosotros
6. POST /orders/confirm -> si Rocketfy acepta, el pedido queda
   confirmado y pasa a producción (Rocketfy asigna transportadora,
   etc.)
7. Todo el resultado se refleja en nuestra tabla `pedidos` (ver
   04_base_de_datos.md) -- Rocketfy sigue siendo la fuente de verdad del
   estado del pedido, nuestra tabla es solo un espejo + control de
   idempotencia
```

Después de la creación existen también:
`PedidoService.modificar()` (`PATCH /orders/modify` — cambiar datos de
contacto/entrega de un pedido ya creado) y `PedidoService.rechazar()`
(`POST /orders/reject` — cancelarlo). Ambos son relevantes si el bot
necesita **modificar o cancelar** un pedido después (ej. cliente escribe
para cambiar la dirección).

## 4. Por qué existe tanta lógica de idempotencia

`POST /orders/create` **no es idempotente** y el proveedor advierte
explícitamente que no se debe reintentar a ciegas si hay un timeout —
podrías terminar creando el mismo pedido dos veces con cobro real
duplicado. Por eso `pedidos.estado_local` es una máquina de estados
local:

| estado_local | Significado |
|---|---|
| `pendiente_creacion` | Se está creando ahora mismo / quedó en un estado ambiguo tras un timeout — **nunca se reintenta solo, requiere revisión manual** |
| `error` | Rocketfy respondió con un error claro (nada se creó) — reintento limpio seguro |
| `incompleto` | Se creó pero algún SKU se descartó en silencio |
| `creado` | Creado en Rocketfy, aún no confirmado (ej. falló la confirmación pero el pedido existe) |
| `confirmado` | Confirmado, en producción |
| `rechazado` | Cancelado |

Si el bot dispara la creación de un pedido y la respuesta es ambigua (se
cae la conexión), **no debe reintentar automáticamente con el mismo ID**
— ese es justamente el caso que este diseño protege.

## 5. Manejo de errores

Tres excepciones tipadas (`backend/src/integrations/rocketfy/exceptions.py`):

- `RocketfyAuthError` — credenciales mal formadas o rechazadas
- `RocketfyRequestError` — problema de red/timeout (reintentable con
  cautela, solo en 500 o mensaje "servicio en mantenimiento", con backoff)
- `RocketfyBusinessError` — Rocketfy respondió con una regla de negocio
  clara (sin stock, sin cobertura, saldo insuficiente, importe mínimo no
  alcanzado, etc.) — **no reintentable tal cual, hay que corregir el dato**

## 6. Hallazgos reales de negocio (importantes para el bot)

Estos se descubrieron probando contra Rocketfy real, no estaban
documentados de antemano:

1. **Recaudo mínimo fijo de $10** para confirmar un pedido contraentrega
   (no aplica a pedidos prepagados). Ya está validado localmente antes de
   crear (`RECAUDO_MINIMO_CONTRAENTREGA` en
   `backend/src/integrations/rocketfy/constants.py`).
2. **Mínimo real dinámico, más estricto:** al confirmar, Rocketfy exige
   que el total cubra "el valor de los productos + el costo del envío",
   calculado internamente por ellos según el destino. Cumplir el mínimo
   fijo de $10 **no garantiza** que la confirmación pase — en una prueba
   real, un pedido de $15 fue rechazado porque el mínimo real era $18.47.
   **No existe forma de consultar este costo de envío de antemano** (no
   hay endpoint de cotización de flete en la API de Rocketfy) — esto es
   relevante si el bot quiere prometerle un precio al cliente antes de
   cerrar la venta: hoy no se puede saber el costo de envío hasta
   intentar confirmar.
3. Rocketfy trata los montos como strings decimales, pero a veces manda
   `0` (número) en vez de `"0.00"` cuando no hay movimiento — hay que
   tratar cualquier campo de dinero como texto siempre, nunca asumir un
   tipo fijo.

## 7. El webhook (avisos de cambio de estado)

Rocketfy puede avisar a un webhook propio cuando el estado de un pedido
cambia (confirmado, en ruta, entregado, novedad, etc.). Puntos clave para
cualquier integración de webhooks futura (incluida la del bot con Meta,
que es un problema análogo):

- **Rocketfy no manda ninguna cabecera de autenticación** — la
  protección la inventamos nosotros (token propio embebido en la URL:
  `/webhooks/rocketfy/<token>`, comparado con `hmac.compare_digest`).
- **Presupuesto de error de 10 fallos DE POR VIDA, sin reset** — si el
  endpoint falla (o tarda) 10 veces acumuladas, Rocketfy deja de avisar
  para siempre sin aviso previo. Por eso el endpoint está diseñado para
  responder 200 pase lo que pase internamente (nunca propaga
  excepciones) y en menos de 2 segundos.
- Al dar de alta la URL en su panel, Rocketfy manda un POST de prueba
  con cuerpo vacío — el endpoint lo detecta y responde 200 sin intentar
  procesarlo como un evento real.
- Clave de idempotencia real: `(order_id, status_id, event_date)`, no
  solo el ID del pedido — un mismo pedido genera múltiples eventos en su
  ciclo de vida (confirmado, luego en ruta, luego entregado, etc.), cada
  uno es un registro legítimo distinto, no una actualización del anterior.
- Como respaldo existe un job de reconciliación
  (`backend/src/jobs/reconciliacion/`) que re-consulta periódicamente los
  pedidos activos por si algún webhook se hubiera perdido.

Este mismo patrón de diseño (auth propia, responder siempre 200,
idempotencia por combinación de campos, no asumir que todo aviso llega)
es el que recomendaríamos replicar para el webhook de WhatsApp Cloud API
del bot, aunque las reglas específicas de Meta sean distintas.
