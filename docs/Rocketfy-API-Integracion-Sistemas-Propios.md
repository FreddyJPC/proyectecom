# Rocketfy

## API de Integración para Sistemas Propios

**Respuesta técnica al documento «Requerimientos de Integración API – Automatización de Flujo»**

REST · JSON · HTTPS · Ecuador

**Preparado para:** Freddy Paguay · Desarrollador de Software  
**Alcance:** Fase 1 y Fase 2 del documento de requerimientos  
**Versión:** 1.0 · Agosto 2026  
**Tipo:** Documento de referencia técnica

Rocketfy API  
Integración con sistemas propios · Documentación técnica para Sellers  
Rocketfy · Documentación técnica de integración | Confidencial

---

## Contenido

1. Resumen: sus requerimientos y su cobertura actual
2. Puesta en marcha: qué necesita antes de la primera llamada
3. URL base, autenticación y formato de respuesta
4. Fase 1 – Crear pedido
5. Fase 1 – Confirmar pedido
6. Fase 1 – Sincronización de estados: webhook y consulta
7. Fase 2 – Catálogo, precios y stock
8. Fase 2 – Modificar y cancelar pedidos
9. Fase 2 – Métricas de negocio
10. Requerimientos no cubiertos hoy y cómo los resolvemos
11. Flujo recomendado extremo a extremo
12. Buenas prácticas, límites y errores
- A. Anexo: estados del pedido
- B. Anexo: provincias y ciudades de Ecuador
- C. Anexo: ejemplo completo de integración
- D. Anexo: checklist de puesta en marcha

---

## 1. Resumen: sus requerimientos y su cobertura actual

Este documento responde punto por punto al documento de requerimientos remitido. La tabla siguiente resume el estado real de cada petición contra la API de Rocketfy en producción.

| # | Requerimiento | Estado | Endpoint / mecanismo | Sección |
|---|---------------|--------|----------------------|---------|
| 1 | Creación de orden de despacho | Disponible | `POST /api/orders/create` | 4 |
| 2 | Consulta de cobertura y flete por destino | No disponible | Requiere desarrollo. Ver alternativa operativa | 10.1 |
| 3 | Sincronización de estados de guía | Disponible | Webhook push + `POST /api/orders/getInfo/{id}` + consulta en lote | 6 |
| 4 | Consulta de stock por SKU | Disponible | `POST /api/products/list` con parámetro `q` | 7 |
| 5 | Cancelación / edición de órdenes | Disponible | `POST /api/orders/modify` y `POST /api/orders/reject` | 8 |
| 6 | Consultar liquidaciones y saldos | Parcial | Métricas agregadas en `GET /api/statistics/general`. El saldo de wallet y el detalle de liquidaciones requieren desarrollo | 9 y 10.2 |
| 7 | Consulta de catálogo completo y precios | Disponible | `POST /api/products/list` y `POST /api/products/view/{id}` | 7 |

**Resumen ejecutivo.** Cinco de los siete requerimientos se cubren hoy con endpoints ya en producción. El punto 2 (cotizador de cobertura y flete) y la parte de saldos del punto 6 no están expuestos actualmente en la API; la sección 10 explica qué existe internamente, qué alternativa operativa tiene mientras tanto y qué haría falta para publicarlos.

**Nota sobre el punto 2.** Aunque el cotizador no esté expuesto, el destino sí se valida en el momento de confirmar el pedido: si el cantón no tiene cobertura con la transportadora asignada, la confirmación devuelve un error explícito y el pedido no se despacha. Es decir, el riesgo que usted quiere evitar (despachar a zona sin cobertura) está cubierto, aunque la validación ocurra un paso más tarde de lo ideal. Ver sección 5.

---

## 2. Puesta en marcha: qué necesita antes de la primera llamada

La API se consume con las credenciales de su propia cuenta de vendedor. No hay que crear una aplicación ni pasar por un flujo OAuth. Necesita tres cosas:

| # | Requisito | Cómo se obtiene |
|---|-----------|-----------------|
| 1 | Acceso API habilitado | Es un permiso que activa Rocketfy sobre su usuario. Solicítelo a su ejecutivo de cuenta o por ticket de soporte indicando el correo de la cuenta. Sin este permiso todos los endpoints responden `401 Acceso denegado`. |
| 2 | Verificación KYC completada | Su cuenta debe tener la verificación de identidad aprobada en el panel. Es obligatoria para confirmar pedidos y para consultar el catálogo. |
| 3 | Token de API | Es un identificador único y permanente de su cuenta. Rocketfy se lo entregará junto con la activación del punto 1. También aparece en el panel, dentro de la URL de webhook que se muestra al crear o editar una tienda en **Configuración → Tiendas**. |

El token es una credencial. Equivale a la contraseña de su cuenta a efectos de API: permite crear, confirmar y rechazar pedidos en su nombre. Guárdelo en variables de entorno o en un gestor de secretos, nunca en el código fuente ni en el navegador. Si sospecha que se ha filtrado, solicite su rotación de inmediato.

---

## 3. URL base, autenticación y formato de respuesta

### 3.1 URL base

```
https://rocket-e.com/api
```

Todas las llamadas viajan sobre HTTPS. Para operaciones en Chile la base es `https://cl.rocket-e.com/api`; las credenciales no son intercambiables entre países.

### 3.2 Autenticación

Cada petición debe incluir dos cabeceras:

| Cabecera | Contenido |
|----------|-----------|
| `Auth-user` | Hash SHA-256 del correo electrónico de la cuenta, en hexadecimal minúscula |
| `Auth-token` | Token de API de la cuenta, tal cual se lo entregamos |

El servidor localiza al usuario por el token y después comprueba que el hash recibido coincida con el de su correo. Si cualquiera de las dos cabeceras falta o no casa, la respuesta es `400`.

```php
// PHP
$authUser = hash('sha256', 'micorreo@ejemplo.com');
```

```javascript
// Node.js
const authUser = require('crypto').createHash('sha256')
  .update('micorreo@ejemplo.com').digest('hex');
```

```python
# Python
import hashlib
auth_user = hashlib.sha256('micorreo@ejemplo.com'.encode()).hexdigest()
```

**Ojo con el correo.** El hash debe calcularse sobre el correo exactamente como está registrado en Rocketfy, sin espacios y respetando mayúsculas y minúsculas. Un correo con una mayúscula distinta produce un hash distinto y la autenticación falla.

### 3.3 Formato de respuesta

La mayoría de endpoints devuelven esta envoltura JSON:

```json
{
  "ok": 1,
  "code": 200,
  "message": "Texto descriptivo",
  "content": { }
}
```

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `ok` | integer | `1` = éxito, `0` = error |
| `code` | integer | Código de resultado, normalmente igual al código HTTP |
| `message` | string | Mensaje descriptivo, apto para registrar en su log |
| `content` | object | Datos de la respuesta, cuando aplica |

**Dos endpoints son la excepción.** Las consultas de pedido (`/orders/getInfo/{id}` y `/orders/bulk/getInfo`) devuelven una estructura propia, sin el nodo `content`. Está documentada en la sección 6. Programe su cliente para no asumir la envoltura estándar en esos dos casos.

### 3.4 Códigos de error comunes

| Código | Significado |
|--------|-------------|
| 400 | Credenciales inválidas, o recurso no encontrado en algunos endpoints |
| 401 | Acceso API no habilitado, KYC sin verificar, o la operación no es válida en el estado actual del pedido |
| 404 | Pedido o producto inexistente |
| 405 | Error interno al crear el pedido (ver sección 4.4) |
| 500 | Error interno del servidor |

---

## 4. Fase 1 – Crear pedido

**Requerimiento 1: Creación de Orden de Despacho.** Inyecta un pedido en Rocketfy en estado Nuevo. No genera guía todavía: el pedido entra en operación cuando se confirma (sección 5).

```
POST /api/orders/create
```

### 4.1 Parámetros

| Campo | Tipo | Oblig. | Descripción |
|-------|------|--------|-------------|
| `id` | integer | Sí | Identificador del pedido en su sistema. Se guarda como referencia externa y permite localizar el pedido después sin conocer el ID de Rocketfy |
| `name` | string | Sí | Nombre completo del cliente final |
| `phone` | string | Sí | Teléfono del cliente. Se normaliza quitando espacios, guiones, paréntesis y el signo `+` |
| `address` | string | Sí | Dirección de entrega |
| `city` | string | Sí | Cantón de destino. Debe coincidir con el catálogo de Rocketfy (ver 4.2) |
| `province` | string | Sí | Provincia de destino. Debe coincidir con el catálogo de Rocketfy (ver 4.2) |
| `total` | numeric | Sí | Importe a recaudar al cliente final, con impuestos incluidos |
| `order_details` | string JSON | Sí | Líneas del pedido. Es una cadena con un array JSON dentro (ver 4.3) |
| `email` | string | No | Correo del cliente |
| `address_2` | string | No | Referencia, piso, conjunto, etc. |
| `zip` | string | No | Código postal |
| `country_code` | string | No | ISO alpha-2. Si se omite se usa el país de la plataforma (`EC`) |
| `not_COD` | integer | No | `1` = el pedido ya está pagado. `0` u omitido = contra entrega. Un total de `0` se trata siempre como prepagado |
| `carrier_observations` | string | No | Indicaciones para el repartidor. Recomendamos enviarlo siempre (ver aviso en 4.4) |
| `store_id` | integer | No | ID de una de sus tiendas, si desea agrupar los pedidos por origen |
| `ip` | string | No | IP del comprador, útil para analítica antifraude |
| `latitude` / `longitude` | numeric | No | Coordenadas de la dirección |

### 4.2 Provincia y cantón: el punto crítico de la integración

Rocketfy resuelve la provincia y el cantón por nombre contra su catálogo oficial (24 provincias y 832 cantones para Ecuador) en el momento de crear el pedido. La comparación ignora mayúsculas y tildes, pero no corrige nombres distintos.

| Enviado | Resultado | Efecto |
|---------|-----------|--------|
| `"province": "Pichincha"` `"city": "QUITO"` | Resuelto | El pedido queda listo para confirmar |
| `"province": "pichincha"` `"city": "quito"` | Resuelto | Igual: no distingue mayúsculas ni tildes |
| `"province": "Pichincha"` `"city": "Quito Norte"` | No resuelto | El pedido se crea, pero no se podrá confirmar hasta corregir el cantón |

**Esto no falla en la creación, falla en la confirmación.** Si el nombre del cantón o de la provincia no existe en el catálogo, `/orders/create` devuelve `200` igualmente y el pedido queda creado, pero al confirmarlo recibirá «Debe seleccionar una ciudad dentro de las opciones disponibles». Valide el destino en su formulario contra el catálogo que le entregamos (anexo B) en lugar de dejar el cantón como texto libre.

### 4.3 Estructura de `order_details`

Es un string que contiene un array JSON. Cada elemento es una línea del pedido:

```
"order_details": "[{\"sku\":\"PROD-001\",\"name\":\"Reloj deportivo\",\"quantity\":2}]"
```

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `sku` | string | SKU del producto en Rocketfy. También acepta el SKU de un pack: se expande automáticamente en sus componentes |
| `name` | string | Nombre del producto, a efectos de referencia en el pedido |
| `quantity` | integer | Unidades |

**Un SKU inexistente se descarta en silencio.** Si el SKU no existe en el catálogo, esa línea no se crea y la respuesta sigue siendo `200`. Un pedido con todas sus líneas descartadas queda vacío y no se puede confirmar. Compruebe siempre el nodo `products_stock` de la respuesta: debe contener una entrada por cada SKU simple enviado. Los packs no aparecen en ese nodo.

### 4.4 Ejemplo de petición

```bash
curl -X POST https://rocket-e.com/api/orders/create \
  -H "Auth-user: 5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8" \
  -H "Auth-token: 8f14e45f-ceea-467a-9c3a-2b91c93e2f11" \
  -H "Content-Type: application/json" \
  -d '{
    "id": 100245,
    "name": "Maria Fernanda Salazar",
    "email": "maria@ejemplo.com",
    "phone": "0991234567",
    "address": "Av. Amazonas N34-120 y Juan Pablo Sanz",
    "address_2": "Edificio Torre Azul, oficina 502",
    "city": "QUITO",
    "province": "Pichincha",
    "total": 49.90,
    "not_COD": 0,
    "carrier_observations": "Llamar antes de subir, portero no contesta",
    "order_details": "[{\"sku\":\"RLJ-DEP-001\",\"name\":\"Reloj deportivo\",\"quantity\":1}]"
  }'
```

**Respuesta correcta**

```json
{
  "ok": 1,
  "code": 200,
  "message": "El pedido se ha creado correctamente",
  "products_stock": [ { "id": 4821, "stock": 137 } ],
  "id": 9315702
}
```

| Campo | Descripción |
|-------|-------------|
| `id` | ID del pedido en Rocketfy. Guárdelo: es la clave con la que operará el resto de la integración |
| `products_stock` | Stock disponible de cada producto simple en el momento de crear el pedido. Utilice este dato también como comprobante de que la línea se creó |

**El endpoint no es idempotente.** Dos llamadas idénticas crean dos pedidos. Si su petición sufre un timeout, no la reintente a ciegas: registre primero el `id` devuelto, y ante la duda localice el pedido con `/orders/modify` usando `shopify_order_id` (que es el `id` de su sistema) antes de reenviar.

**Dos parámetros que hoy no tienen efecto.** El campo `shipping_method` se ignora: el pedido toma siempre la transportadora por defecto configurada en su cuenta. Y no existe un parámetro para confirmar en la misma llamada: la confirmación es siempre un segundo paso.

Si no envía `carrier_observations`, el pedido se rellena con un texto por defecto heredado de una configuración antigua que no aplica a Ecuador. Envíe siempre el campo, aunque sea con una cadena vacía o con su propia indicación estándar.

Ante un error interno, este endpoint responde con código `405` y `ok: 0`; la transacción se revierte por completo, de modo que no queda un pedido a medias.

---

## 5. Fase 1 – Confirmar pedido

La confirmación es el paso que mete el pedido en operación: valida destino y cobertura, calcula el flete, descuenta el saldo correspondiente y lo envía a bodega para su preparación.

```
POST /api/orders/confirm
```

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `order_id` | integer | ID del pedido en Rocketfy |
| `shopify_order_id` | integer | Alternativa: el `id` de su sistema, si no envía `order_id` |

```bash
curl -X POST https://rocket-e.com/api/orders/confirm \
  -H "Auth-user: {sha256_del_correo}" \
  -H "Auth-token: {su_token}" \
  -H "Content-Type: application/json" \
  -d '{ "order_id": 9315702 }'
```

### 5.1 Por qué puede fallar una confirmación

Es el endpoint con más reglas de negocio de toda la API. Todas las respuestas de error traen `ok: 0` y un `message` legible que conviene registrar y mostrar a su equipo. Los motivos más frecuentes:

| Motivo | Mensaje y cómo resolverlo |
|--------|---------------------------|
| Sin cobertura | «No es posible confirmar este pedido con la transportadora seleccionada ya que no tiene cobertura a: `{canton}`». El cantón no está en la red de la transportadora asignada. Es la validación que cubre su requerimiento 2 |
| Provincia o cantón sin resolver | «Debe seleccionar una provincia / ciudad dentro de las opciones disponibles». El nombre enviado al crear no casa con el catálogo. Ver sección 4.2 |
| Saldo insuficiente | «No dispones de saldo suficiente para confirmar este pedido». Recargue la billetera del panel |
| Pedido sin líneas | Se envió el pedido con SKU inexistentes. Ver sección 4.3 |
| Sin stock | Alguno de los productos no tiene inventario suficiente. Consulte el stock antes de confirmar (sección 7) |
| Recaudo mínimo | «El recaudo mínimo para confirmar un pedido contraentrega es de `{importe}`». Revise que el `total` vaya en la moneda correcta |
| Ya confirmado | «No es posible confirmar un pedido ya confirmado». Es la respuesta segura ante un reintento: no duplica nada |
| Teléfono o nombre inválidos | El nombre debe ser alfanumérico y el teléfono es obligatorio |
| Productos de bodegas distintas | Un pedido no puede mezclar productos de almacenes diferentes. Divida el pedido |
| Servicio en mantenimiento | «El servicio está temporalmente en mantenimiento». Es transitorio: reintente en unos minutos con espera progresiva |

**La confirmación es segura ante reintentos.** Internamente se protege con un bloqueo por pedido, y un pedido ya confirmado responde con un error explícito en lugar de duplicarse. Aun así, trate los errores como definitivos salvo el de mantenimiento, que es el único pensado para reintentar.

---

## 6. Fase 1 – Sincronización de estados: webhook y consulta

**Requerimiento 3.** Hay dos mecanismos y son complementarios: el webhook para reaccionar en tiempo real y la consulta para reconciliar. Recomendamos implementar los dos.

### 6.1 Webhook de cambios de estado (recomendado)

Rocketfy hace un POST a una URL suya cada vez que cambia el estado de uno de sus pedidos. Se configura usted mismo desde el panel, en **Configuración → API Webhooks**, sin intervención de soporte.

**Cuerpo que recibirá**

```json
{
  "order_id": 9315702,
  "event_date": "2026-08-23T19:32:10.000000Z",
  "status_id": 8,
  "status_name": "Entregado",
  "details": "Entregado a Maria Salazar",
  "tracking_code": "CO123456789EC",
  "tracking_url": "https://rastreo.transportadora.com/CO123456789EC",
  "shopify_order_id": 100245,
  "shipping_company": "Servientrega",
  "total": "49.90"
}
```

El campo `shopify_order_id` es el `id` que usted envió al crear el pedido: le permite casar el evento con su registro sin mantener tabla de equivalencias. Las fechas viajan en UTC; Ecuador es UTC−5.

**Reglas de oro del receptor.** Su endpoint debe (1) responder HTTP `200` exacto, no `201` ni `204`; (2) responder también `200` al POST de validación con cuerpo vacío que se lanza al guardar la URL; (3) contestar en menos de 10 segundos; (4) estar publicado antes de darlo de alta; (5) no tener redirecciones. No hay reintentos: un evento no aceptado se pierde. Y tras diez respuestas erróneas acumuladas el webhook se desactiva solo; para reactivarlo basta con volver a guardar la URL en el panel.

Le entregamos junto a este documento la guía «Integrar las notificaciones push de Rocketfy», con el contrato completo del webhook, código de referencia en Node y PHP y una lista de comprobación. Sígalo al implementar el receptor.

### 6.2 Consulta de un pedido

```
POST /api/orders/getInfo/{id}
```

Devuelve la ficha del pedido, su histórico de estados y el detalle de la novedad activa si la hay. El `{id}` es el ID de Rocketfy.

```json
{
  "code": 200,
  "ok": 1,
  "order": {
    "id": 9315702,
    "name": "Maria Fernanda Salazar",
    "order_status": "Entregado",
    "date": "2026-08-20 10:14:02",
    "email": "maria@ejemplo.com",
    "phone": "0991234567",
    "address": "Av. Amazonas N34-120",
    "city": "QUITO",
    "province": "Pichincha",
    "total": "49.90",
    "tracking_code": "CO123456789EC",
    "confirmed_at": "2026-08-20 10:20:41",
    "fulfilled_at": "2026-08-21 08:02:10",
    "delivered_at": "2026-08-23 14:32:10",
    "rejected_at": null,
    "returned_at": null,
    "label_printed_at": "2026-08-21 08:05:00"
  },
  "status_record": [ ... ],
  "incidence_details": null
}
```

Esta respuesta no usa la envoltura estándar: los datos cuelgan de `order`, no de `content`.

### 6.3 Consulta en lote

```
POST /api/orders/bulk/getInfo
```

Devuelve estado, guía e histórico de un rango contiguo de IDs de Rocketfy.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id_start` | integer | ID inicial del rango |
| `id_end` | integer | ID final del rango |

Solo devuelve los pedidos del rango que le pertenecen, de modo que puede pedir el intervalo entre el ID más bajo y el más alto que tenga en curso.

**Use rangos cortos.** El endpoint materializa internamente todos los IDs del intervalo, así que un rango de millones de posiciones es muy costoso aunque solo le pertenezcan diez pedidos. Mantenga los bloques por debajo de unos pocos miles de IDs y pagínelos.

### 6.4 Estrategia recomendada

```
Webhook ---> reacción inmediata: disparar el WhatsApp al cliente final
         | +--> guardar el evento crudo en su base de datos

Consulta ---> cada 30-60 min, reconciliar los pedidos en curso
              (captura cualquier evento que el webhook no haya entregado)
```

---

## 7. Fase 2 – Catálogo, precios y stock

**Requerimientos 4 y 7.** El mismo endpoint resuelve las dos necesidades: sincronizar el catálogo y vigilar el inventario de los SKU que está pautando.

```
POST /api/products/list
```

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `q` | string | Búsqueda por nombre, SKU o descripción. Omítalo para recorrer el catálogo completo |
| `page` | integer | Página a devolver. 20 productos por página |

**Respuesta**

```json
{
  "ok": 1,
  "code": 200,
  "message": "OK",
  "content": {
    "data": [
      {
        "id": 4821,
        "name": "Reloj deportivo",
        "description": "...",
        "sku": "RLJ-DEP-001",
        "stock": 137,
        "price": "18.50",
        "suggested_price": "39.90",
        "provider_code": "...",
        "bar_code": "...",
        "ref": "...",
        "height": "12.00",
        "width": "9.00",
        "length": "4.00",
        "weight": "0.35",
        "image_url": "https://...",
        "extra_images": [ { "size": "...", "url": "https://..." } ],
        "parent_id": null,
        "created_at": "...",
        "updated_at": "..."
      }
    ],
    "pagination": {
      "total": 1840,
      "per_page": 20,
      "current_page": 1,
      "last_page": 92,
      "next_page_url": "...",
      "prev_page_url": null
    }
  }
}
```

| Campo | Uso previsto en su integración |
|-------|--------------------------------|
| `stock` | Inventario disponible. Es el dato con el que puede pausar campañas cuando baje del umbral que defina |
| `price` | Su costo base. Un cambio aquí es el que debe disparar su alerta de margen |
| `suggested_price` | Precio de venta sugerido por el proveedor |
| `weight`, `height`, `width`, `length` | Peso en kg y medidas en cm. Determinan el recargo por sobrepeso del flete |
| `parent_id` | Si viene informado, el producto es una variante (talla, color) del producto padre indicado |

### 7.1 Consulta de un producto concreto

```
POST /api/products/view/{id}
```

Devuelve la misma estructura de un único producto, buscando por su ID de Rocketfy.

### 7.2 Consulta de stock por SKU

Para el caso concreto de vigilar un SKU, use la búsqueda:

```bash
curl -X POST https://rocket-e.com/api/products/list \
  -H "Auth-user: {sha256_del_correo}" -H "Auth-token: {su_token}" \
  -H "Content-Type: application/json" \
  -d '{ "q": "RLJ-DEP-001" }'
```

**Sobre el alcance del catálogo.** Este endpoint devuelve el catálogo público de Rocketfy (productos activos y no privados), que es el que puede vender cualquier vendedor. Si su cuenta tiene productos privados o precios negociados en exclusiva, esos no aparecen aquí; indíquenoslo y le habilitamos el acceso correspondiente. Cuando busca con `q`, la respuesta incluye también las variantes; sin `q` se listan solo los productos padre.

Este endpoint exige la verificación KYC aprobada, además del acceso API.

---

## 8. Fase 2 – Modificar y cancelar pedidos

**Requerimiento 5.** Ambas operaciones existen y responden exactamente al escenario que describe: intervenir antes de que la bodega imprima la guía.

### 8.1 Modificar los datos de entrega

```
POST /api/orders/modify
```

| Campo | Descripción |
|-------|-------------|
| `order_id` | ID del pedido en Rocketfy |
| `shopify_order_id` | Alternativa: el `id` de su sistema |
| `name`, `email`, `phone`, `address`, `address_2`, `city`, `province`, `zip` | Campos a actualizar. Solo se aplican los que envíe; los omitidos se conservan |

Estados en los que se permite: Nuevo, Pendiente de confirmación, Aplazado y Rechazado. Un pedido ya confirmado responde «No es posible modificar los datos de un pedido ya confirmado/preparado».

**Limitaciones a tener en cuenta.** No se pueden modificar las líneas de producto ni el importe total: para eso hay que rechazar el pedido y crear uno nuevo. Y si cambia `city` o `province`, verifique el resultado confirmando el pedido: el cambio de destino por esta vía actualiza el texto, y un cantón mal escrito volverá a bloquear la confirmación.

### 8.2 Cancelar un pedido

```
POST /api/orders/reject
```

| Campo | Descripción |
|-------|-------------|
| `order_id` | ID del pedido en Rocketfy. Obligatorio en este endpoint |

Estados en los que se permite: Nuevo, Pendiente de confirmación, Aplazado, Carrito abandonado, Confirmado y Preparado. Es decir, puede cancelar incluso después de haber confirmado.

**El límite real es la impresión de la guía.** Una vez impresa la etiqueta, el pedido ya no se puede rechazar por API y la respuesta es «No es posible rechazar un pedido con etiqueta YA IMPRESA». A partir de ese punto la cancelación se gestiona con soporte. Si su negocio necesita margen de cancelación, conviene no confirmar el pedido hasta tener la venta cerrada con el cliente.

---

## 9. Fase 2 – Métricas de negocio

```
GET /api/statistics/general
```

Cubre parcialmente el requerimiento 6: da la foto agregada de su operación, aunque no el saldo de la billetera ni el detalle de liquidaciones (ver sección 10.2).

| Campo | Descripción |
|-------|-------------|
| `orders_today` | Pedidos creados hoy |
| `orders_total_amount_today` | Importe total de los pedidos creados hoy |
| `confirmed_today` / `revenue_confirmed` | Pedidos confirmados hoy y su importe |
| `revenue_today` | Importe entregado hoy |
| `revenue_total` | Importe entregado histórico |
| `revenue_transit` | Importe en tránsito (preparado, enviado, en ruta, recogida en agencia) |
| `revenue_incidence` | Importe retenido en pedidos con novedad |
| `transit_products_cost` | Costo de producto comprometido en pedidos con novedad, con impuestos |

---

## 10. Requerimientos no cubiertos hoy y cómo los resolvemos

### 10.1 Cotizador de cobertura y flete (requerimiento 2)

**Situación actual.** El motor de cotización existe y es el mismo que usa el panel: calcula flete, manipulación, comisión de recaudo contra entrega, seguro, recargo por sobrepeso e impuestos por cantón y transportadora. Lo que no existe hoy es un endpoint público que lo exponga con las credenciales de vendedor descritas en la sección 3.

**Datos útiles mientras tanto.** Ecuador tiene 832 cantones en el catálogo, de los cuales 688 tienen tarifa configurada con al menos una transportadora. La cobertura por transportadora activa es:

| Transportadora | Cantones con tarifa | Observación |
|----------------|---------------------|-------------|
| Servientrega | 584 | Mayor cobertura nacional |
| Gintracom | 440 | |

**Alternativa operativa inmediata.** Sin desarrollo adicional, la validación de cobertura la obtiene en la confirmación: si el cantón no tiene red, `/orders/confirm` responde `ok: 0` con el mensaje de falta de cobertura y el pedido no se despacha ni genera costo. Su sistema puede tratar ese error como «destino no servible» y avisar al cliente por WhatsApp antes de recoger el pago. El riesgo económico que usted quiere evitar queda cubierto; lo que no obtiene por esta vía es el importe del flete antes de vender.

**Qué haría falta.** Publicar dos endpoints con la misma autenticación de la sección 3:

- `GET /api/locations` — provincias y cantones con su identificador, para alimentar los desplegables de su landing y evitar el problema de la sección 4.2.
- `POST /api/shipping/quote` — dado un cantón, el importe del pedido y las líneas, devolver la lista de transportadoras con cobertura y el desglose de costo. Una respuesta vacía significa «sin cobertura».

Son endpoints de lectura sobre lógica ya existente. Indíquenos si los necesita para su Fase 1 y los priorizamos.

### 10.2 Liquidaciones y saldos (requerimiento 6)

**Situación actual.** La billetera del vendedor, el detalle de transacciones y las solicitudes de retiro están implementados y disponibles en el panel, pero los endpoints que los sirven están reservados hoy a comunicación interna entre sistemas de Rocketfy y no admiten credenciales de vendedor.

**Lo que sí tiene hoy.** `GET /api/statistics/general` le da entregado histórico, entregado del día, importe en tránsito e importe retenido por novedades (sección 9). Con eso puede construir una aproximación razonable de flujo de caja: lo entregado es lo recaudado, y lo en tránsito es lo pendiente de recaudar.

**Qué haría falta.** Un endpoint `GET /api/wallet/balance` con el saldo disponible, el retenido y el mínimo permitido, y un `GET /api/wallet/transactions` paginado por rango de fechas con el detalle de movimientos y su pedido asociado. Es la vía limpia para automatizar el flujo de caja que describe en su documento.

Ambos bloques son ampliaciones sobre lógica ya existente, no desarrollos desde cero. Si confirma que son necesarios para su puesta en producción, los planificamos y le comunicamos fecha.

---

## 11. Flujo recomendado extremo a extremo

1. **LANDING PAGE**  
   El cliente rellena el formulario. El cantón y la provincia se eligen de una lista cerrada (anexo B), no como texto libre.

2. **CONFIRMACIÓN POR WHATSAPP**  
   Su sistema cierra la venta con el cliente.

3. **VERIFICAR INVENTARIO**  
   `POST /api/products/list { "q": "SKU" }`  
   Si stock insuficiente → no inyectar y avisar al equipo.

4. **CREAR EL PEDIDO**  
   `POST /api/orders/create`  
   Guardar el `id` devuelto. Comprobar que `products_stock` trae una entrada por cada SKU simple enviado.

5. **CONFIRMAR EL PEDIDO**  
   `POST /api/orders/confirm`  
   - `ok: 1` → el pedido entra en operación.  
   - `ok: 0` → leer `message`:  
     - sin cobertura → avisar al cliente, no cobrar  
     - saldo insuficiente → alertar al equipo y recargar  
     - cantón no resuelto → corregir con `/api/orders/modify` y reintentar

6. **SEGUIMIENTO**  
   - Webhook → reacción inmediata: alertas de WhatsApp al cliente final  
   - Consulta → `POST /api/orders/getInfo/{id}` cada 30-60 min para reconciliar

7. **INCIDENCIAS**  
   `status_id` 7 (NOVEDAD) llega por webhook con el motivo en `details`. Es el evento con mayor impacto en su tasa de entrega: gestiónelo el mismo día.

8. **CANCELACIÓN (si aplica)**  
   `POST /api/orders/reject`  
   Posible hasta que se imprime la guía.

---

## 12. Buenas prácticas, límites y errores

| Tema | Recomendación |
|------|---------------|
| Cadencia de llamadas | Los endpoints de pedidos y productos no tienen hoy un límite estricto por minuto, pero se monitoriza el consumo. Mantenga las consultas de reconciliación en intervalos de 30 minutos o más y evite bucles de sondeo por pedido |
| Reintentos | Aplique espera progresiva y solo ante errores 500 o de mantenimiento. Nunca reintente automáticamente `/orders/create` sin comprobar antes si el pedido ya existe |
| Idempotencia | Use su propio `id` como clave y registre el `id` de Rocketfy en cuanto lo reciba. Es su única protección contra pedidos duplicados |
| Registro | Guarde petición y respuesta completas de `/orders/create` y `/orders/confirm` durante al menos 90 días. Agiliza cualquier incidencia con soporte |
| Zona horaria | El webhook entrega fechas en UTC; los endpoints de consulta, en hora local de Ecuador (UTC−5). Normalice al recibir |
| Importes | Viajan como cadena decimal con dos cifras. No los interprete como número en coma flotante para operaciones contables |
| Entorno de pruebas | No hay entorno sandbox público. Recomendamos validar con pedidos reales de importe bajo y rechazarlos antes de la impresión de guía |

---

## A. Anexo: estados del pedido

| `status_id` | Nombre | Significado operativo |
|-------------|--------|------------------------|
| 1 | Pedido nuevo | Creado, aún sin confirmar. No se notifica por webhook |
| 2 | Confirmado - Pendiente de preparación | Validado y en cola de bodega |
| 3 | Rechazado | Anulado antes de salir |
| 4 | Preparado | Empaquetado; a partir de aquí la guía puede imprimirse |
| 5 | Enviado | Entregado a la transportadora. Suele traer ya `tracking_code` |
| 6 | En ruta | En reparto. Momento ideal para el aviso «ten el efectivo listo» |
| 7 | NOVEDAD | Incidencia de reparto. Puede repetirse con distinto `details` |
| 8 | Entregado | Entregado y recaudado |
| 9 | Devuelto - en tránsito | Regresando a bodega |
| 10 | Devuelto - recepcionado en almacén | Devolución cerrada |
| 11 | Pendiente de confirmación | A la espera de cerrar con el cliente |
| 12 | Pedido Aplazado | Reprogramado |
| 13 | Carrito abandonado | No se notifica por webhook |
| 14 | No confirmable | No se pudo contactar al cliente |
| 15 | Duplicado | Detectado como repetido |
| 23 | Recogida en Agencia | Disponible para retiro en oficina |

Programe siempre contra `status_id`, nunca contra `status_name`: el texto puede cambiar. Un pedido puede retroceder (7 → 6 → 7 → 8): no asuma progresión lineal.

---

## B. Anexo: provincias y cantones de Ecuador

Estos son los nombres exactos de provincia que reconoce Rocketfy. La comparación ignora mayúsculas y tildes.

| ID | Provincia | Cantones | ID | Provincia | Cantones |
|----|-----------|----------|----|-----------|----------|
| 1 | Azuay | 47 | 13 | Los Rios | 53 |
| 2 | Bolivar | 28 | 14 | Manabi | 97 |
| 3 | Canar | 21 | 15 | Morona Santiago | 14 |
| 4 | Carchi | 16 | 16 | Napo | 19 |
| 5 | Chimborazo | 21 | 17 | Orellana | 10 |
| 6 | Cotopaxi | 35 | 18 | Pastaza | 8 |
| 7 | El Oro | 41 | 19 | Pichincha | 78 |
| 8 | Esmeraldas | 26 | 20 | Santa Elena | 46 |
| 9 | Galapagos | 3 | 21 | Santo Domingo de los Tsachilas | 23 |
| 10 | Guayas | 101 | 22 | Sucumbios | 15 |
| 11 | Imbabura | 47 | 23 | Tungurahua | 29 |
| 12 | Loja | 37 | 24 | Zamora Chinchipe | 17 |

**Listado de cantones.** Los 832 cantones se entregan junto a este documento en el fichero `rocketfy-cantones-ecuador.csv` (columnas: `city_id`, `canton`, `province_id`, `provincia`). Cargue ese fichero en su sistema y ofrézcalo como lista cerrada en el formulario de su landing: es la forma de eliminar de raíz los fallos de confirmación por destino no reconocido.

---

## C. Anexo: ejemplo completo de integración

```php
<?php
class RocketfyClient
{
    private $base = 'https://rocket-e.com/api';
    private $email;
    private $token;

    public function __construct($email, $token)
    {
        $this->email = $email;
        $this->token = $token;
    }

    private function call($path, array $payload = [], $method = 'POST')
    {
        $ch = curl_init($this->base . $path);
        curl_setopt_array($ch, [
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_CUSTOMREQUEST => $method,
            CURLOPT_TIMEOUT => 30,
            CURLOPT_HTTPHEADER => [
                'Content-Type: application/json',
                'Auth-user: ' . hash('sha256', $this->email),
                'Auth-token: ' . $this->token,
            ],
        ]);
        if ($method === 'POST') {
            curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($payload));
        }
        $raw = curl_exec($ch);
        $code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);
        return ['http' => $code, 'body' => json_decode($raw, true)];
    }

    public function stock($sku)
    {
        $r = $this->call('/products/list', ['q' => $sku]);
        foreach ($r['body']['content']['data'] ?? [] as $p) {
            if (strcasecmp($p['sku'], $sku) === 0) return (int) $p['stock'];
        }
        return 0;
    }

    public function crearPedido(array $pedido, array $lineas)
    {
        $pedido['order_details'] = json_encode($lineas);
        $r = $this->call('/orders/create', $pedido);
        if (($r['body']['ok'] ?? 0) != 1) {
            throw new RuntimeException('Alta fallida: ' . ($r['body']['message'] ?? 'sin detalle'));
        }
        // Comprobacion critica: toda linea simple debe haberse creado.
        $recibidas = count($r['body']['products_stock'] ?? []);
        if ($recibidas < count($lineas)) {
            throw new RuntimeException('Algun SKU no existe en el catalogo. Pedido '
                . $r['body']['id'] . ' creado incompleto: revisar y rechazar.');
        }
        return $r['body']['id'];
    }

    public function confirmar($orderId)
    {
        $r = $this->call('/orders/confirm', ['order_id' => $orderId]);
        if (($r['body']['ok'] ?? 0) != 1) {
            return ['ok' => false, 'motivo' => $r['body']['message'] ?? 'sin detalle'];
        }
        return ['ok' => true];
    }

    public function consultar($orderId)
    {
        // Atencion: este endpoint NO usa la envoltura "content".
        $r = $this->call('/orders/getInfo/' . $orderId);
        return $r['body']['order'] ?? null;
    }

    public function cancelar($orderId)
    {
        $r = $this->call('/orders/reject', ['order_id' => $orderId]);
        return ($r['body']['ok'] ?? 0) == 1;
    }
}

// ---------------------------------------------------------------
$rocket = new RocketfyClient(getenv('ROCKETFY_EMAIL'), getenv('ROCKETFY_TOKEN'));

$lineas = [
    ['sku' => 'RLJ-DEP-001', 'name' => 'Reloj deportivo', 'quantity' => 1],
];

if ($rocket->stock('RLJ-DEP-001') < 1) {
    exit("Sin stock: no se inyecta el pedido.\n");
}

$orderId = $rocket->crearPedido([
    'id' => 100245,
    'name' => 'Maria Fernanda Salazar',
    'phone' => '0991234567',
    'address' => 'Av. Amazonas N34-120 y Juan Pablo Sanz',
    'address_2' => 'Edificio Torre Azul, oficina 502',
    'city' => 'QUITO', // exacto segun catalogo
    'province' => 'Pichincha', // exacto segun catalogo
    'total' => 49.90,
    'not_COD' => 0,
    'carrier_observations' => 'Llamar antes de subir',
], $lineas);

$res = $rocket->confirmar($orderId);
if (!$res['ok']) {
    // "sin cobertura" -> avisar al cliente y no cobrar
    // "saldo" -> alertar al equipo financiero
    error_log("Pedido {$orderId} no confirmado: {$res['motivo']}");
}
```

---

## D. Anexo: checklist de puesta en marcha

| Paso | Acción | Responsable |
|------|--------|-------------|
| 1 | Solicitar la activación del acceso API indicando el correo de la cuenta | Cliente |
| 2 | Activar el permiso y entregar el token de API | Rocketfy |
| 3 | Completar la verificación KYC en el panel | Cliente |
| 4 | Cargar el catálogo de cantones en el formulario de la landing | Cliente |
| 5 | Probar la autenticación con `POST /api/products/list` | Cliente |
| 6 | Crear un pedido de prueba de importe bajo y confirmarlo | Cliente |
| 7 | Rechazar el pedido de prueba antes de la impresión de guía | Cliente |
| 8 | Publicar el receptor de webhook y darlo de alta en el panel | Cliente |
| 9 | Verificar que el webhook recibe los cambios de estado del pedido de prueba | Ambos |
| 10 | Confirmar si se requieren los endpoints de cotización y de saldos (sección 10) | Ambos |

### Soporte

Para dudas técnicas sobre esta documentación, incidencias de integración o la solicitud de los endpoints de la sección 10, contacte con su ejecutivo de cuenta o abra un ticket desde el panel indicando el correo de la cuenta y, si aplica, el id del pedido afectado.

**Documentos que acompañan a este:**

- `Rocketfy-Webhooks-Guia-Integrador.pdf` — contrato completo del webhook de estados
- `rocketfy-cantones-ecuador.csv` — catálogo de los 832 cantones
