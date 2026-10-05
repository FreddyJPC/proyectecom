# Integrar las notificaciones push de Rocket (API Webhooks)

Documento pensado para entregárselo tal cual al desarrollador (o a la IA) del vendedor que quiere recibir en su propio sistema los cambios de estado de sus pedidos de Rocket.

---

## 0. Contexto

Rocket dispara una notificación push (webhook) cada vez que cambia el estado de un pedido tuyo: confirmado, preparado, enviado, en ruta, novedad, entregado, devuelto…

Tu trabajo es montar un endpoint HTTP en tu servidor que reciba esos avisos. Rocket no ofrece un panel de reintentos ni una cola de eventos consultable: **si tu endpoint no contesta bien, ese evento se pierde**. Por eso el contrato de abajo hay que cumplirlo al pie de la letra.

**Dirección del flujo:** Rocket → tu servidor. Siempre POST. Nunca al revés.

---

## 1. Lo que tienes que construir

Un endpoint público que cumpla **TODO** esto:

| Requisito | Detalle |
|-----------|---------|
| Método | `POST` (solo POST; si tu framework responde 405 a POST, el alta ni siquiera se guarda) |
| Respuesta | HTTP **200 exacto**. Ni 201, ni 202, ni 204, ni 301/302 |
| Cuerpo vacío | Debe responder 200 también cuando llega sin cuerpo (ping de validación) |
| Tiempo | Contestar en menos de 10 segundos (límite duro: 10 s de conexión + 25 s totales) |
| TLS | HTTPS con certificado válido y cadena completa (se verifica peer + host) |
| Redirecciones | Ninguna. No se siguen. La URL final tiene que responder ella misma |
| Autenticación | No la aporta Rocket: métela tú en la URL (ver §4.5) |

---

## 2. Contrato exacto de la petición

### Cabeceras que llegan

```
POST /tu/endpoint HTTP/1.1
Content-Type: application/json
```

Eso es todo. No hay `Authorization`, no hay firma HMAC, no hay `X-Rocket-*`, no hay `User-Agent` reconocible. No programes nada que dependa de una cabecera.

### Cuerpo (JSON)

```json
{
  "order_id": 1234567,
  "event_date": "2026-08-23T19:32:10.000000Z",
  "status_id": 8,
  "status_name": "Entregado",
  "details": "Entregado a Juan Pérez",
  "tracking_code": "CO123456789EC",
  "tracking_url": "https://rastreo.transportadora.com/CO123456789EC",
  "shopify_order_id": 5544332211,
  "shipping_company": "Servientrega",
  "total": "49.90"
}
```

| Campo | Tipo | Notas |
|-------|------|-------|
| `order_id` | integer | Id del pedido en Rocket. Es tu clave principal |
| `event_date` | string | Fecha del cambio de estado, ISO-8601 en UTC (`…Z`). Ecuador es UTC-5: réstale 5 h para hora local |
| `status_id` | integer | Nuevo estado. Tabla en §3 |
| `status_name` | string | Nombre del estado en español. Es texto y puede cambiar: no lo uses para decidir lógica, usa `status_id` |
| `details` | string | Texto libre del evento. En novedades (`status_id: 7`) trae el motivo de la transportadora. Puede llegar `""` |
| `tracking_code` | string \| null | Guía de la transportadora. Null hasta que el pedido se envía |
| `tracking_url` | string \| null | URL de rastreo, si la transportadora la da |
| `shopify_order_id` | integer \| null | Id del pedido en TU plataforma de origen (Shopify, WooCommerce, PrestaShop, Magento, Pancake, Chatby…). Se llama así por histórico. `null` si el pedido se creó a mano en Rocket. Úsalo para casar el pedido con el tuyo |
| `shipping_company` | string | Nombre de la transportadora |
| `total` | string | Total del pedido en decimal con dos cifras (`"49.90"`). Llega como string, no como número |

**Lo que NO viene y no vas a poder deducir:** datos del cliente, dirección, líneas de producto, subestado, id de la novedad. Si los necesitas, guárdate el `order_id` y crúzalo con tu propio pedido vía `shopify_order_id`, o pide a Rocket acceso a su API de consulta.

---

## 3. Estados que vas a recibir

| `status_id` | `status_name` | Significado |
|-------------|---------------|-------------|
| 2 | Confirmado - Pendiente de preparación | El pedido entra en operación |
| 3 | Rechazado | Anulado antes de salir |
| 4 | Preparado | Empaquetado en almacén |
| 5 | Enviado | Entregado a la transportadora (aquí suele aparecer `tracking_code`) |
| 6 | En ruta | En reparto |
| 7 | NOVEDAD | Incidencia de reparto. Puede repetirse varias veces con distinto `details` |
| 8 | Entregado | Entregado al cliente final |
| 9 | Devuelto - en tránsito | Vuelve al almacén |
| 10 | Devuelto - recepcionado en almacén | Devolución cerrada |
| 11 | Pendiente de confirmación | A la espera de confirmar con el cliente |
| 12 | Pedido Aplazado | Reprogramado |
| 14 | No confirmable | No se pudo contactar |
| 15 | Duplicado | Detectado como repetido |
| 23 | Recogida en Agencia | Disponible para recoger en oficina |

Nunca llegan **1** (Pedido nuevo) ni **13** (Carrito abandonado): esos dos están excluidos en origen. Cualquier otro `status_id` que no reconozcas: guárdalo y no falles.

Un pedido puede retroceder (7 → 6 → 7 → 8). No asumas progresión lineal.

---

## 4. Las nueve reglas que rompen la integración

Estas no son recomendaciones. Son el comportamiento real del emisor.

### 4.1. Devuelve 200, exactamente 200

El emisor compara `código !== 200`. Un `201 Created` o un `204 No Content` se contabilizan como error. En Laravel: `return response('ok', 200);`. En Express: `res.status(200).json({ ok: true })`.

### 4.2. Al dar de alta la URL, Rocket hace un POST de prueba con el cuerpo vacío

En el momento de pulsar «Guardar» en el panel, Rocket lanza un POST a tu URL con `Content-Type: application/json` y sin cuerpo. Si esa llamada devuelve 0 (inalcanzable / TLS roto / timeout), 404, 405 o 500, la URL no se guarda y verás el mensaje «No se guardaron algunos webhooks por ser inaccesibles».

**Consecuencias prácticas:**

- Publica tu endpoint **ANTES** de darlo de alta. No sirve guardarlo «para luego».
- Tu parser de JSON tiene que tolerar cuerpo vacío. En Express `express.json()` lo hace (deja `req.body = {}`); los parsers estrictos revientan.
- Trata la petición sin `order_id` como un ping: responde 200 y no proceses nada.

### 4.3. No hay reintentos

Si contestas algo distinto de 200, o tardas demasiado, ese evento no se vuelve a enviar. Nunca. No existe reintento con backoff ni cola de reenvío.

Por eso: **persiste el evento crudo lo primero que hagas, responde 200, y procesa después de forma asíncrona**. Si tu lógica de negocio falla, es problema tuyo y lo reintentas tú — no se lo comuniques a Rocket con un 500.

### 4.4. A los 10 errores acumulados, tu webhook se apaga solo

Cada respuesta distinta de 200 deja registrado un error. Cuando ese contador histórico pasa de 10, Rocket pone el webhook en inactivo y deja de enviarte nada, en silencio. No hay aviso por correo.

El contador no se resetea con el tiempo: son 10 fallos en toda la vida de esa URL. Un despliegue chapucero de media hora te puede gastar la cuota entera.

**Cómo revivirlo:** vuelve al panel y guarda otra vez la URL (botón editar → Guardar). Eso crea un registro nuevo con el contador a cero. Es la única forma desde tu lado.

### 4.5. No hay firma ni autenticación: pon el secreto en la URL

Como no llega ninguna cabecera de seguridad, cualquiera que descubra tu URL puede inventarse estados de pedido. Protégete así:

1. Token largo y aleatorio en la ruta o en el query string: `https://tuservidor.com/webhooks/rocketfy/9f2c1a…` — y compáralo con `hash_equals` / `crypto.timingSafeEqual`.
2. Filtra por IP de origen en el firewall si puedes (pide a soporte de Rocket la IP de salida de su servidor y confírmala antes de cerrar nada).
3. Nunca te fíes del `total` que llega para mover dinero: úsalo como referencia y contrasta contra tu propio pedido.
4. Si el token no cuadra, responde **401/403** — no 404 ni 405, que son los códigos que además bloquean el alta.

### 4.6. Responde rápido, procesa luego

Límites: 10 s para conectar, 25 s en total. Si tu handler consulta tu ERP, manda correos o llama a otra API antes de responder, acabarás fuera de tiempo y gastando la cuota de errores de §4.4. Patrón correcto: **guardar evento crudo → 200 → cola**.

### 4.7. Duplicados y desorden: sé idempotente

Los envíos salen por una cola de baja prioridad: no hay garantía de orden de llegada y un mismo estado puede repetirse (sobre todo 7 NOVEDAD).

Clave de idempotencia recomendada: `(order_id, status_id, event_date)`. Y antes de aplicar un estado, comprueba que no estás retrocediendo sobre algo más reciente comparando `event_date`.

### 4.8. Nada de redirecciones ni de certificados a medias

No se siguen redirecciones. Si tu URL es `http://…` y el servidor redirige a `https://`, o de `dominio.com` a `www.dominio.com`, la respuesta será un 301 → contabilizado como error. Da de alta la URL final, canónica y en HTTPS, con certificado válido (se verifica peer y host: los autofirmados fallan).

### 4.9. Una sola URL activa

Hay un webhook por vendedor y por tipo (hoy solo existe el tipo **Actualización de pedido**). Si guardas otra URL, sustituye a la anterior; y si hubiera varias, se usa la última activa. No intentes montar dos destinos: reparte tú desde tu endpoint.

---

## 5. Implementación de referencia

### Node.js / Express

```javascript
const express = require('express');
const crypto = require('crypto');
const app = express();
const TOKEN = process.env.ROCKETFY_WEBHOOK_TOKEN;

function tokenOk(a, b) {
  const A = Buffer.from(String(a)), B = Buffer.from(String(b));
  return A.length === B.length && crypto.timingSafeEqual(A, B);
}

// express.json() tolera cuerpo vacío -> req.body = {}
app.post('/webhooks/rocketfy/:token', express.json({ limit: '256kb' }), async (req, res) => {
  // 1) Autenticación por token en la ruta. 403, nunca 404/405.
  if (!tokenOk(req.params.token, TOKEN)) return res.status(403).json({ error: 'forbidden' });

  const p = req.body || {};

  // 2) Ping de validación del alta: llega sin cuerpo.
  if (!p.order_id) return res.status(200).json({ ok: true, ping: true });

  // 3) Persistir el evento crudo YA, de forma idempotente.
  try {
    await db.rocketfyEvents.upsert({
      where: { order_id_status_id_event_date: {
        order_id: p.order_id, status_id: p.status_id, event_date: p.event_date } },
      create: { payload: p, processed: false },
      update: {}, // duplicado: no hacemos nada
    });
  } catch (e) {
    // Ni siquiera aquí devolvemos 500: perderíamos el evento y gastaríamos cuota.
    console.error('[rocketfy] fallo guardando evento', e, p);
  }

  // 4) 200 inmediato. El trabajo real va en una cola aparte.
  return res.status(200).json({ ok: true });
});
```

### PHP / Laravel

```php
// routes/api.php (api.php NO lleva CSRF; si lo pones en web.php tendrás 419)
Route::post('/webhooks/rocketfy/{token}', function (Request $request, string $token) {
    if (!hash_equals(config('services.rocketfy.webhook_token'), $token)) {
        return response()->json(['error' => 'forbidden'], 403); // 403, no 404
    }

    $p = $request->json()->all();

    // Ping de validación del alta (cuerpo vacío)
    if (empty($p['order_id'])) {
        return response()->json(['ok' => true, 'ping' => true], 200);
    }

    try {
        RocketEvent::firstOrCreate(
            [
                'order_id' => $p['order_id'],
                'status_id' => $p['status_id'] ?? null,
                'event_date' => $p['event_date'] ?? null,
            ],
            ['payload' => $p, 'processed' => 0]
        );
    } catch (\Throwable $e) {
        Log::error('[rocketfy] fallo guardando evento', ['e' => $e->getMessage(), 'p' => $p]);
    }

    return response()->json(['ok' => true], 200); // 200 exacto, siempre
});
```

**Errores clásicos en Laravel que te van a costar la cuota de §4.4:**

- Ruta en `web.php` sin excluir CSRF → 419.
- Método mal registrado y el framework devuelve 405.
- Un middleware de auth colgado del grupo → 302 a login (y encima es una redirección).
- `return response()->json($x, 201)` → cuenta como error.

---

## 6. Alta en el panel de Rocket (lo hace el vendedor)

1. Entra en tu panel: `https://rocket-e.com` (o `https://cl.rocket-e.com` si operas en Chile).
2. Menú **Configuración → API Webhooks** (ruta directa: `/configuration/webhooks`).
3. Campo «URL para Notificaciones de actualizaciones pedido (POST)».
4. Pega la URL completa, final y ya publicada, con `https://` y con tu token: `https://tuservidor.com/webhooks/rocketfy/EL_TOKEN`
5. Pulsa **Guardar webhooks**. En ese instante Rocket llama a tu URL (§4.2).
   - Correcto → «Se guardó el webhook correctamente».
   - «No se guardaron algunos webhooks por ser inaccesibles» → tu endpoint no contestó bien. Revisa §4.2 y §4.8 antes de tocar nada más.
6. El botón «Ver estructura» de esa misma pantalla muestra el JSON que se envía.
7. Para cambiar la URL: icono del lápiz → editar → Guardar. Para quitarla: papelera.

---

## 7. Checklist antes de dar la integración por buena

- ☐ `curl -X POST https://tuservidor.com/webhooks/rocketfy/TOKEN -H "Content-Type: application/json"` (sin `-d`) → 200
- ☐ Mismo curl con el payload de ejemplo de §2 → 200 y el evento aparece guardado
- ☐ Mismo curl con un token incorrecto → 403 (no 404, no 405)
- ☐ `curl -I` no muestra ninguna redirección hacia la URL final
- ☐ `curl -v` no da avisos de certificado (`SSL certificate problem`)
- ☐ El endpoint responde en < 2 s (mídelo con `curl -w "%{time_total}\n"`)
- ☐ Reenviar el mismo payload dos veces no duplica nada en tu sistema
- ☐ Un payload con `status_id` desconocido no revienta: se guarda y responde 200
- ☐ `total` se trata como string («49.90») y `event_date` se convierte de UTC a tu hora local
- ☐ Alta hecha en el panel y estado de un pedido real de prueba movido de punta a punta

---

## 8. Si deja de llegar

Por orden, y antes de escribir a soporte:

1. Mira tus propios logs de acceso. ¿Llegan peticiones? Si llegan y respondes algo que no es 200, el problema es tuyo (§4.1).
2. ¿Se apagó por errores? Es lo más frecuente tras un despliegue fallido (§4.4). Solución desde tu lado: volver a guardar la URL en el panel.
3. ¿Cambió algo en tu infra? Certificado renovado a medias, WAF/Cloudflare bloqueando, una redirección nueva, un rate limit propio devolviendo 429 (≠ 200 → cuenta como error).
4. Escribe a soporte de Rocket pidiendo expresamente esto — tienen una herramienta de diagnóstico para tu cuenta que dice si el webhook está activo, cuántos errores acumula y permite lanzar un envío real de prueba:

> «Por favor, ejecutad el diagnóstico de webhooks de mi cuenta (`command:diagnoseUserWebhooks mi-correo@dominio.com`) y decidme si mi webhook está activo, cuántos errores tiene acumulados y qué código devolvió el último envío. Si podéis, lanzad también un envío real de prueba con `--send`.»

---

## 9. Resumen en una frase

Publica una URL HTTPS final sin redirecciones, que acepte POST con cuerpo vacío o con el JSON de §2, valide un token propio en la ruta, guarde el evento y devuelva 200 en menos de dos segundos — porque no hay reintentos y a los diez fallos Rocket deja de llamarte sin avisar.
