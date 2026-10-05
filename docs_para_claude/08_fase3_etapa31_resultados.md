# 08 — Fase 3, Etapa 3.1: Resultados de la Ejecución

> Generado por Claude Code para Claude web, al cerrar el encargo de
> desarrollo de la Etapa 3.1 (infraestructura base del bot, sin IA
> todavía) que Claude web entregó. Los documentos `01` a `07` describen
> el proyecto ANTES de esta etapa — este documento describe **qué pasó al
> construirla y probarla**, para que quede como base al diseñar la
> Etapa 3.2 (integrar a Claude como el cerebro conversacional de
> Victoria).

---

## 1. Qué se construyó

Las 6 tareas del encargo se ejecutaron en orden, cada una verificada con
`pytest` antes de seguir a la siguiente:

1. Variables de entorno nuevas en `backend/.env`/`.env.example` y
   `src/config/settings.py` (fail-fast para las de WhatsApp).
2. Migraciones `004_conversaciones.sql`, `005_mensajes.sql`,
   `006_leads.sql` — tres tablas nuevas, completamente separadas de
   `pedidos` (esa sigue siendo solo el contrato con Rocketfy).
3. `src/integrations/whatsapp/` — `WhatsAppClient` (mismo patrón que
   `RocketfyClient`): `enviar_texto`, `enviar_plantilla`,
   `marcar_como_leido`, excepciones tipadas, factory cacheada.
4. `src/routes/whatsapp/` — blueprint del webhook
   (`GET`/`POST /webhooks/whatsapp`), `WebhookService` (idempotencia por
   `wamid`, detección de origen FEP, guardar mensaje, marcar leído
   best-effort, encolar respuesta), `BotWorker` (thread + cola en
   background, para no bloquear la respuesta a Meta).
5. Prueba end-to-end manual (detalle en la sección 3).
6. Esta documentación + la correspondiente en `PROGRESS.md`.

**Tests:** 24 nuevos (9 del cliente de WhatsApp, 15 del webhook/servicio).
**129 tests en total en el proyecto, 0 fallando.**

---

## 2. Dos desvíos conscientes del encargo original

El encargo pedía dos cosas puntuales que, al implementarlas tal cual,
habrían roto la prueba end-to-end de la propia Tarea 5. Se resolvieron
así, documentados en el código y acá:

### Desvío 1 — dónde y cuándo arranca el `BotWorker`
Se pidió arrancarlo "igual que APScheduler se inicia hoy". En este
proyecto, `start_scheduler()` solo corre bajo `if __name__ ==
"__main__"` — **nunca** bajo `flask run`, que es exactamente el comando
que la Tarea 5 pide usar para la prueba end-to-end. Replicar ese mismo
gate literal habría dejado el worker sin arrancar nunca durante la
prueba.

Se resolvió arrancándolo dentro de `create_app()` en cambio, con
`get_bot_worker()` cacheado (`functools.lru_cache`) y
`BotWorker.iniciar()` hecho idempotente a propósito — necesario además
porque este proyecto ya ejecuta `create_app()` dos veces en el mismo
proceso (una línea suelta `app = create_app()` al final de `app.py`,
sumada a la que hace el factory de Flask), algo preexistente, no
introducido en esta etapa.

### Desvío 2 — `conversacion_id` al encolar la respuesta del bot
El esqueleto de `worker.py` que venía en el encargo guardaba la
respuesta del bot con `conversacion_id=None` ("TODO Fase 3.2: resolver
conversacion_id desde el mensaje"). La columna `mensajes.conversacion_id`
es `NOT NULL` — guardar con `None` habría roto con un error de base de
datos justo en la prueba de la Tarea 5.

Se resolvió pasando el `conversacion_id` ya resuelto (creado o
reutilizado en el paso 2 de `WebhookService._procesar`) hacia el worker
en el momento de encolar, empaquetado en un `TareaRespuestaDTO` propio —
ya no hace falta resolverlo en la Etapa 3.2, quedó bien desde ahora.

---

## 3. Prueba end-to-end — qué se probó de verdad, y qué no

**Hallazgo que cambió el plan de prueba:** mientras la app de Meta no
esté **publicada**, Meta solo entrega webhooks de prueba disparados
desde el propio panel de Meta (botón "Probar" en la sección de
Webhooks) — ningún mensaje real de WhatsApp llega al webhook, ni
siquiera de números ya agregados a la lista de destinatarios de prueba.
Esto no estaba documentado de antemano y se descubrió después de varios
intentos fallidos de mandar un mensaje real (con la URL verificada, el
campo `messages` suscrito, y el número del dueño en la lista de
prueba — nada de eso importa mientras la app no esté publicada).

Publicar la app requiere verificación de negocio + revisión manual de
Meta (días o semanas) — se decidió con el usuario NO publicarla solo
para esta prueba, y usar en cambio el botón de prueba del panel.

### Resultado real de la prueba (vía el botón "Probar" de Meta)

Payload real recibido (tal cual lo manda Meta, dentro del sobre estándar
`entry[].changes[].value`):

```json
{
  "field": "messages",
  "value": {
    "messaging_product": "whatsapp",
    "metadata": { "display_phone_number": "16505551111", "phone_number_id": "123456123" },
    "contacts": [{ "profile": { "name": "test user name" }, "wa_id": "16315551181" }],
    "messages": [{
      "id": "ABGGFlA5Fpa",
      "timestamp": "1504902988",
      "from": "16315551181",
      "type": "text",
      "text": { "body": "this is a text message" }
    }]
  }
}
```

- `POST /webhooks/whatsapp` respondió `200` de inmediato.
- Se confirmó en Supabase real que quedaron guardadas las filas
  correctas: una `conversaciones` (`telefono=16315551181`,
  `origen=directo`) y dos `mensajes` (el del cliente con ese `wamid`, y
  la respuesta placeholder del bot con `rol=bot`, `wamid=null`).
- Dos llamadas salientes fallaron, **de forma esperada** (el payload de
  prueba usa un `wamid` y un número inventados, no reales):
  - `marcar_como_leido` → `WhatsAppBusinessError`: `(#131009) Parameter
    value is not valid`.
  - `enviar_texto` → `WhatsAppBusinessError`: `(#131030) Recipient phone
    number not in allowed list`.
  - Ambas quedaron registradas en el log y **no tumbaron nada** — el
    mensaje del cliente ya estaba guardado antes del primer fallo, y el
    `BotWorker` siguió vivo para la siguiente tarea (el `try/except`
    alrededor de `marcar_como_leido`, y el de `_loop()` en el worker,
    funcionaron exactamente como se diseñaron).

**Lo que esto valida:** el canal completo — recepción, autenticación del
handshake, parseo del payload real de Meta, idempotencia, detección de
origen, persistencia, cola en background, tolerancia a fallos — funciona
de punta a punta contra un evento real de Meta, no solo contra mocks.

**Lo que esto NO valida todavía:** un intercambio de mensajes con un
número de WhatsApp real (cliente real escribiendo, bot real
respondiendo). Eso depende de: (a) registrar un número de teléfono real
del negocio en la WABA (rápido, no requiere revisión de Meta), y/o (b)
publicar la app (si se quiere hablar con cualquier número, no solo los de
prueba).

---

## 4. Hallazgos y pendientes que quedan abiertos

Ya están anotados en `PROGRESS.md` (sección de Pendientes Transversales),
acá el resumen para tenerlos presentes al diseñar la Etapa 3.2:

| # | Pendiente | Urgencia |
|---|---|---|
| Seguridad | El webhook de WhatsApp **no verifica la firma `X-Hub-Signature-256`** que manda Meta (HMAC-SHA256 del cuerpo con el App Secret) — a diferencia del webhook de Rocketfy, que sí tiene su propio token. No se implementó porque `WHATSAPP_APP_SECRET` no era parte de las variables pedidas en esta etapa | Antes de cualquier despliegue real, no bloquea seguir desarrollando |
| Número real | No se ha probado con un número de WhatsApp real. Registrar el número real del negocio en la WABA es un paso rápido y separado de publicar la app | Cuando se quiera probar con un cliente real |
| Publicar la app | Requiere verificación de negocio + revisión de Meta (días/semanas) — necesario solo para hablar con números fuera de la lista de prueba | Decisión de negocio, no urgente hoy |
| Token de acceso | Confirmar que el generado sea realmente permanente (se regeneró varias veces durante esta etapa antes de obtener el que parece definitivo) — y definir el proceso de renovación sin caídas | Antes de producción |
| Supabase se pausa | El proyecto (plan gratuito) se pausó solo por inactividad **dos veces** durante esta etapa — en producción sería una caída real del bot y del backend | Antes de producción |
| Cola en memoria | `BotWorker` usa una `queue.Queue` de Python **solo en memoria** — un reinicio del proceso con mensajes sin procesar los pierde en silencio. El código ya está pensado para migrar a Celery+Redis sin cambiar el contrato de `encolar()`, pero no se hizo todavía | A definir si se resuelve junto con la Etapa 3.2 o después |
| Túnel temporal | La URL del webhook sigue siendo un túnel de `cloudflared` sin garantía de actividad (se cayó varias veces durante las pruebas, incluida una vez por estar en una red wifi pública que bloqueaba el tráfico) | Antes de operar con clientes reales |

Ninguno de estos bloquea el desarrollo de la Etapa 3.2 — son decisiones y
tareas de puesta en producción, no de arquitectura del bot en sí. Se
señalan acá para que, si alguno conviene resolverlo *junto con* la
Etapa 3.2 en vez de después (por ejemplo, la persistencia de la cola), se
pueda decidir con el panorama completo.
