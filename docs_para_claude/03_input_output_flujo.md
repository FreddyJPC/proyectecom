# 03 — Input / Output exacto del flujo de crear pedido

Esta es la interfaz concreta que el bot tendría que llamar (o replicar)
al cerrar una venta. Fuente: `backend/src/routes/pedidos/{dto,schemas,controllers}.py`.

## 1. Cómo se dispara hoy

**HTTP:** `POST /pedidos` en el backend Flask (`http://127.0.0.1:5050/pedidos`
en local). Requiere `Authorization: Bearer <token de Supabase>` — hoy
protegido por el mismo login que usa el dashboard (ver
`05_variables_entorno.md` y la nota de arquitectura en
`06_estado_actual.md` sobre esto).

**Desde Python, dentro del mismo proceso** (si el bot terminara viviendo
en el mismo backend, o importándolo como librería): se puede llamar
directo a `PedidoService(client=get_rocketfy_client()).crear_y_confirmar(dto)`,
sin pasar por HTTP ni por el login — es una función Python normal que
recibe un `CrearPedidoInputDTO` y devuelve un `PedidoDTO`. Esto es
relevante para decidir la arquitectura del bot (ver pregunta abierta en
`07_preguntas_abiertas.md`).

No existe (todavía) una versión "solo Python, sin Flask" pensada para
importarse desde otro servicio — hoy vive dentro del paquete `src` del
backend.

## 2. Input — `POST /pedidos`

Body JSON, camelCase. Definido en `CrearPedidoInputSchema`
(`backend/src/routes/pedidos/schemas.py`):

| Campo | Tipo | Requerido | Notas |
|---|---|---|---|
| `idLocal` | integer | **sí** | ID único que nosotros generamos (no lo asigna Rocketfy). Hoy se genera como epoch en segundos (`int(time.time())`). Es la clave primaria de nuestra tabla `pedidos` — **no se puede reutilizar un mismo idLocal para un pedido distinto** |
| `nombreCliente` | string | sí | |
| `telefono` | string | sí | Se manda tal cual a Rocketfy (ellos normalizan quitando espacios/guiones/+) |
| `direccion` | string | sí | |
| `direccion2` | string | no | Referencia/piso, default `""` |
| `canton` | string | sí | Debe existir en el catálogo cerrado (`GET /catalogos/ubicaciones/<provincia>/cantones`) |
| `provincia` | string | sí | Debe existir en el catálogo (`GET /catalogos/ubicaciones`) |
| `total` | number (2 decimales) | sí | Importe a cobrar. Ver hallazgos del mínimo real en `02_flujo_distribuidor.md` |
| `lineas` | array de `{sku, nombre, cantidad}` | sí, mínimo 1 | `sku` debe existir en el catálogo de Rocketfy (`GET /productos?q=`) — un SKU inexistente se descarta en silencio, no da error |
| `email` | string | no | |
| `codigoPostal` | string | no | |
| `noContraEntrega` | boolean | no, default `false` | `true` = ya pagado (prepagado). `false`/omitido = contraentrega, sujeto al mínimo de $10 |
| `observacionesTransportista` | string | no | Instrucciones para el repartidor |
| `tiendaId` | integer | no | Solo si se usan múltiples tiendas en la cuenta de Rocketfy |
| `ip` / `latitud` / `longitud` | string / float / float | no | Antifraude / geolocalización, opcional |

### Ejemplo real de input válido (usado en pruebas contra producción)

```json
{
  "idLocal": 1788749376,
  "nombreCliente": "Maria Fernanda Salazar",
  "telefono": "0991234567",
  "direccion": "Av. Amazonas N34-120",
  "direccion2": "",
  "canton": "QUITO",
  "provincia": "Pichincha",
  "codigoPostal": null,
  "total": 25.00,
  "noContraEntrega": false,
  "observacionesTransportista": "Llamar antes de subir",
  "lineas": [
    { "sku": "LAMPARASAL", "nombre": "Lampara de sal", "cantidad": 1 }
  ]
}
```

## 3. Output exitoso — HTTP 200

`PedidoResponseSchema`:

```json
{
  "idLocal": 1788749376,
  "idRocketfy": 288928,
  "estadoLocal": "confirmado",
  "statusIdRocketfy": null,
  "mensajeError": null,
  "creadoEn": "2026-09-07T02:49:38.486887+00:00",
  "confirmadoEn": "2026-09-07T02:49:41.174759+00:00",
  "actualizadoEn": "2026-09-07T02:49:41.174759+00:00"
}
```

`estadoLocal` puede volver como `"confirmado"` (éxito total) o
`"creado"` (se creó en Rocketfy pero la confirmación fue rechazada por
una regla de negocio — ver siguiente punto). **No lanza excepción en ese
segundo caso**, HTTP sigue siendo 200 pero conviene revisar `mensajeError`.

Espera, esto último no es exacto — ver el punto de errores abajo: cuando
la confirmación es rechazada, el endpoint SÍ devuelve un código de error
(422/502), pero el pedido queda igual guardado como `creado` con el
`mensajeError` — el estado real solo se ve consultando `GET
/pedidos/<idLocal>` después.

## 4. Output cuando falla

| Código | Cuándo | Cuerpo |
|---|---|---|
| 422 | Cantón/provincia no existe en el catálogo, o total bajo el mínimo fijo de $10 (validado ANTES de llamar a Rocketfy — no se crea nada) | `{"error": "mensaje explicando qué pasó"}` |
| 422 | Rocketfy rechazó la confirmación por una regla de negocio (sin cobertura, sin stock, saldo insuficiente, mínimo real no alcanzado, etc.) — **el pedido SÍ se creó en Rocketfy**, solo falló la confirmación | `{"error": "mensaje de Rocketfy", "codigoRocketfy": <int>}` |
| 409 | El pedido con ese `idLocal` quedó en un estado ambiguo de un intento anterior (timeout) — requiere revisión manual, no se reintenta solo | `{"error": "..."}` |
| 409 | Se creó pero alguna línea de producto se descartó (SKU inexistente) | `{"error": "..."}` |
| 502 | Error de red/autenticación al hablar con Rocketfy | `{"error": "..."}` |
| 422 (validación) | Body mal formado (falta un campo requerido) | `{"error": "Datos inválidos.", "detalle": {...campos con error...}}` |

**Importante para el bot:** cuando la creación "falla" pero en realidad
el pedido sí quedó creado en Rocketfy (fila en estado `creado` con
`mensajeError`), la forma de saberlo es consultar
`GET /pedidos/<idLocal>` después de cualquier error — si existe, hay un
pedido real que necesita atención (ajustar el total y reintentar la
confirmación, por ejemplo), no se debe generar un `idLocal` nuevo y
volver a intentar desde cero.

## 5. Otros endpoints relevantes para el bot

- `GET /pedidos/<idLocal>` — estado y datos completos de un pedido (para
  saber "¿este pedido ya se creó, en qué estado está?").
- `PATCH /pedidos/<idLocal>` — modificar datos de contacto/entrega de un
  pedido ya creado (nombre, teléfono, dirección, cantón/provincia).
- `POST /pedidos/<idLocal>/rechazar` — cancelar un pedido.
- `GET /catalogos/ubicaciones` y `GET /catalogos/ubicaciones/<provincia>/cantones`
  — catálogo cerrado de provincias/cantones, para validar la dirección
  ANTES de intentar crear el pedido (recomendado que el bot lo use
  también, para no descubrir un cantón inválido recién al confirmar).
- `GET /productos?q=<texto>` — buscar en el catálogo real de Rocketfy
  (nombre, SKU, precio, stock) — útil si el bot necesita confirmar
  disponibilidad/precio real de un producto antes de cerrar.
