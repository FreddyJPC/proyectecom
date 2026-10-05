<contexto>

# Módulo de Conversaciones — Backend + Dashboard (versión revisada)

## Nota para ti, CLI

Esta versión **reemplaza** cualquier indicación anterior sobre este módulo — no es un parche, es la especificación completa. Si ya habías empezado con una versión previa, revisa especialmente las Tareas 1 y 3, que tienen lógica nueva de validación que no estaba antes.

## Por qué existe este módulo

El número de WhatsApp del bot (hoy el de prueba, y también el real cuando se migre) **nunca tiene una app de WhatsApp normal asociada** — es un número que solo existe dentro de la Cloud API. Cuando Victoria escala una conversación a atención humana, Telegram avisa que algo pasó, pero sin este módulo no hay ninguna forma de que un humano le responda al cliente. No es una mejora de comodidad: es la pieza que falta para que la intervención humana funcione en absoluto.

## Alcance de esta entrega

Un módulo "Conversaciones" con:
1. Backend: endpoints nuevos, mismo patrón de capas ya establecido.
2. Frontend: dos páginas nuevas en el dashboard existente, reusando componentes y convenciones ya en uso.

## Decisiones de alcance — no las cambies sin avisar

- **No se construye un módulo "Clientes" separado en esta entrega** — ver razonamiento completo en el prompt original de este módulo (queda igual): la lógica de "cliente que compra una segunda vez" no está resuelta todavía en el sistema, así que no se construye una vista de historial de cliente sobre esa base sin resolver primero esa decisión de diseño.
- **"Escaladas" y "Esperando pago" son filtros/pestañas dentro de "Conversaciones", no módulos aparte.**
- **Responder manualmente desde el dashboard es obligatorio, no opcional.**
- **NUEVO — validar la ventana de mensajería es obligatorio, no opcional.** Fuera de la ventana de 24h (o 72h si es FEP), Meta rechaza cualquier mensaje de texto libre — solo acepta plantillas aprobadas. El endpoint de responder debe detectar esto ANTES de intentar enviar, no dejar que falle en Meta de forma confusa. Construir el envío de plantillas desde el dashboard **no** es parte de esta entrega — cuando la ventana esté cerrada, el sistema debe explicarlo claramente, no intentarlo ni fallar en silencio.
- **No se agrega tiempo real (websockets)** — refresco manual o poll simple basta.
- **No se agregan tests automatizados de frontend** — sigue el patrón existente (validación manual, build/lint limpios).
- **Backend sí lleva tests.**

## Convenciones obligatorias del proyecto

- Mismo patrón de capas en todo módulo nuevo del backend.
- SQL crudo con psycopg2, sin ORM.
- Autenticación: mismo login de Supabase Auth que ya protege el resto de la API del dashboard.
- Frontend: mismo Tailwind v4 + shadcn/ui (`radix-nova`), mismo `lib/api.ts`, mismo `config/site.ts`, misma convención de formato de moneda/fechas ya usada en `pedidos/`.
- Documentar en `PROGRESS.md`, con el razonamiento de cada decisión.

</contexto>

---

<requerimientos>

# Tarea 1 — Migraciones: columnas nuevas + índices

## Por qué

Dos necesidades reales de uso diario que no tenían dónde vivir: saber qué escaladas ya revisaste, y poder dejarte notas privadas sobre una conversación.

## Migración

```sql
ALTER TABLE conversaciones ADD COLUMN vista_en timestamptz;
    -- NULL mientras nadie ha abierto el detalle de una escalada nueva.
    -- Se limpia a NULL cada vez que la conversación vuelve a escalar
    -- (ver Tarea 2), así una segunda escalada se vuelve a marcar como
    -- "sin revisar" aunque una escalada anterior ya se hubiera visto.

ALTER TABLE conversaciones ADD COLUMN notas_internas text;
    -- Notas privadas del dueño del negocio. NUNCA se envían al cliente,
    -- ni entran al contexto de Victoria. Son solo para uso humano interno.

CREATE INDEX conversaciones_estado_actualizada_idx ON conversaciones(estado, actualizada_en);
CREATE INDEX leads_nombre_cliente_idx ON leads(lower(nombre_cliente));
```

## Verificación

- Aplica la migración, confirma en Supabase.
- Corre `pytest` — no debe romper nada existente.

</requerimientos>

---

<requerimientos>

# Tarea 2 — Tocar `handle_escalar_a_humano` (Fase 3.2) para limpiar `vista_en`

## Por qué

Si una conversación ya se había escalado antes, se vio, y por algún motivo (aunque hoy sea poco común) vuelve a escalar, debe aparecer de nuevo como "sin revisar" — no seguir marcada como vista de la vez anterior.

## Cambio puntual

En `tools.py`, dentro de `_handle_escalar_a_humano` (Fase 3.2), el `UPDATE conversaciones SET estado='escalada'` pasa a ser:

```sql
UPDATE conversaciones SET estado='escalada', vista_en=NULL, actualizada_en=now()
WHERE id=:conversacion_id
```

## Verificación

- Test: escalar una conversación que ya tenía `vista_en` seteado de una escalada anterior → `vista_en` vuelve a `NULL`.
- Corre `pytest` completo — confirma que los tests existentes de la Fase 3.2 sobre este handler siguen pasando.

</requerimientos>

---

<requerimientos>

# Tarea 3 — Backend: endpoints de conversaciones

## Ubicación

`backend/src/routes/conversaciones/` — mismo patrón de capas que `routes/pedidos/`.

## Lógica compartida — cálculo de la ventana de mensajería

**Por qué:** es lo que evita que "responder manualmente" falle de forma confusa contra Meta. Se calcula así, en un solo lugar reutilizable (ej. un método `_ventana_abierta(conversacion) -> tuple[bool, datetime | None]` en el servicio):

```python
"""
ventana_servicio_abierta = existe algún mensaje con rol='cliente' en esta
    conversación, y (now() - ese último mensaje.creado_en) < 24 horas

ventana_fep_abierta = conversacion.origen == 'fep'
    AND conversacion.fep_expira_en is not None
    AND now() < conversacion.fep_expira_en

ventana_abierta = ventana_servicio_abierta OR ventana_fep_abierta

Devolver también CUÁNDO se cierra (la fecha más próxima entre las dos que
apliquen), para que el frontend pueda mostrar "se cierra en X horas".
"""
```

## Endpoint 1 — `GET /conversaciones`

**Query params:** `estado`, `origen`, `q` (busca por teléfono o nombre del cliente), `page`, `pageSize`.

**Orden por defecto:** `actualizada_en DESC`. Si el filtro `estado=escalada` está activo, ordenar por `creada_en ASC` (cola: la más antigua primero).

**Respuesta por fila:**
```json
{
  "id": 123,
  "telefono": "593987654321",
  "nombreCliente": "Juan Pérez",
  "origen": "fep",
  "estado": "escalada",
  "productoInteres": "Audífonos Bluetooth inalámbricos",
  "sinRevisar": true,
  "ultimoMensaje": {
    "rol": "cliente",
    "contenido": "tengo un problema con mi pedido...",
    "creadoEn": "2026-09-27T15:32:00Z"
  },
  "creadaEn": "2026-09-27T15:00:00Z",
  "actualizadaEn": "2026-09-27T15:32:00Z"
}
```
`sinRevisar` = `estado == 'escalada' AND vista_en IS NULL`.

**Además:** la respuesta debe incluir, junto a los metadatos de paginación, un conteo rápido `totalesPorFiltroRapido`:
```json
{
  "escaladas": 3,
  "escaladasSinRevisar": 2,
  "esperandoPago": 1
}
```
Esto es lo que alimenta los contadores de las pestañas de acceso rápido del frontend (Tarea 4).

## Endpoint 2 — `GET /conversaciones/<id>`

**Comportamiento adicional respecto a antes:** si `conversacion.estado == 'escalada' AND vista_en IS NULL`, este GET debe además hacer `UPDATE conversaciones SET vista_en = now() WHERE id = :id` antes de responder — es la acción de "marcar como vista" simplemente por abrirla.

**Respuesta:**
```json
{
  "conversacion": {
    "id": 123,
    "telefono": "593987654321",
    "origen": "fep",
    "estado": "escalada",
    "idAnuncio": "23847382910",
    "notasInternas": "Cliente ya llamó por teléfono antes, prefiere trato directo.",
    "ventanaAbierta": false,
    "ventanaExpiraEn": null,
    "creadaEn": "...",
    "actualizadaEn": "..."
  },
  "lead": {
    "nombreCliente": "Juan Pérez",
    "direccion": "Av. Amazonas N34-451",
    "canton": "QUITO",
    "provincia": "Pichincha",
    "productoSku": "10-AUDIFONO-INALAM-TIPRO",
    "productoNombre": "Audífonos Bluetooth inalámbricos",
    "productoVariante": null,
    "total": 24.99,
    "metodoPago": "contraentrega",
    "estadoPago": "pendiente",
    "estado": "recopilando_datos",
    "idPedidoLocal": null,
    "idPedidoRocketfy": null
  },
  "mensajes": [
    {"id": 1, "rol": "cliente", "contenido": "Hola...", "tipo": "texto", "creadoEn": "..."}
  ]
}
```
`lead` puede venir `null` si no existe (no debería pasar, pero no debe romper si pasa). Si `producto_sku`/`producto_nombre` vienen vacíos en el lead, el frontend debe mostrar "Sin definir aún" en vez de un campo vacío o roto.

## Endpoint 3 — `POST /conversaciones/<id>/mensajes`

**Body:** `{"contenido": "texto"}`

**Comportamiento — ESTE ES EL CAMBIO IMPORTANTE respecto a la versión anterior de este encargo:**

```python
"""
1. Validar que `contenido` no esté vacío.
2. Obtener la conversación (404 si no existe).
3. Calcular si la ventana de mensajería está abierta (lógica compartida
   de arriba).
4. SI LA VENTANA ESTÁ CERRADA:
   → NO insertar ningún mensaje en BD.
   → NO llamar a WhatsAppClient.
   → Devolver 409 con:
     {"error": "La ventana de mensajería de 24 horas está cerrada y esta conversación no tiene una ventana FEP activa. No se puede enviar texto libre — solo una plantilla aprobada, que todavía no está disponible desde este panel."}

5. SI LA VENTANA ESTÁ ABIERTA (comportamiento igual al ya especificado antes):
   a. Insertar en mensajes: rol='humano', contenido, tipo='texto', wamid=NULL.
   b. Llamar a WhatsAppClient.enviar_texto(telefono=conversacion.telefono, mensaje=contenido)
      — esto NO pasa por BotWorker ni por VictoriaConversationService en
      ningún momento.
   c. UPDATE conversaciones SET actualizada_en=now() WHERE id=:id.
   d. Si el envío falla (WhatsAppRequestError, WhatsAppBusinessError):
      el mensaje YA quedó guardado en el paso (a), pero se debe devolver
      un error claro (502 con {"error": "..."}) — el dueño necesita saber
      que probablemente el cliente no lo recibió.
   e. Si todo sale bien, devolver el mensaje creado.
"""
```

## Endpoint 4 — `POST /conversaciones/<id>/reactivar`

Igual que antes: `UPDATE conversaciones SET estado='activa', actualizada_en=now() WHERE id=:id`. Nota (ya conocida): si el lead está `despachado`, la próxima escritura del cliente lo va a re-escalar automáticamente por la regla determinista de postventa — no es un bug.

## Endpoint 5 — `PATCH /conversaciones/<id>/notas` (nuevo)

**Body:** `{"notasInternas": "texto libre, puede venir vacío para borrar la nota"}`

**Comportamiento:** `UPDATE conversaciones SET notas_internas = :notas WHERE id = :id`. Simple, sin validaciones especiales — es texto libre solo para el dueño.

## Verificación de la Tarea 3

- Tests de cada endpoint con repositorios en memoria y `WhatsAppClient` mockeado.
- Test: `POST /mensajes` con ventana cerrada → 409, NO se llama a `WhatsAppClient`, NO se inserta ningún mensaje.
- Test: `POST /mensajes` con ventana abierta por servicio (24h) → funciona como antes.
- Test: `POST /mensajes` con ventana abierta solo por FEP (fuera de las 24h de servicio pero dentro de las 72h de FEP) → también debe funcionar.
- Test: `GET /conversaciones/<id>` sobre una escalada con `vista_en IS NULL` → después de la llamada, `vista_en` queda seteado.
- Test: `GET /conversaciones` devuelve `sinRevisar` correctamente y los `totalesPorFiltroRapido` correctos.
- Test: `PATCH /notas` guarda y borra correctamente.
- Corre `pytest` completo.

</requerimientos>

---

<requerimientos>

# Tarea 4 — Frontend: páginas del módulo de Conversaciones

## Página de lista — `conversaciones/page.tsx`

- Tabla: Teléfono, Cliente, Producto de interés (o "Sin definir aún"), Estado (`StatusBadge`, agregar los estados de conversación a `lib/estados.ts`: `activa` verde, `esperando_pago` amarillo, `escalada` rojo, `cerrada` gris, `fria` gris claro), Último mensaje (truncado), Actualizado hace X tiempo.
- Filtros: estado, origen, búsqueda por teléfono/nombre.
- **Pestañas de acceso rápido**, con contador en cada una (viene de `totalesPorFiltroRapido`):
  - "Escaladas" (con un sub-contador destacado de cuántas están `sinRevisar` — ej. un punto rojo o número en negrita si hay alguna sin revisar)
  - "Esperando pago"
  - "Todas"
- Fila con `sinRevisar: true` debe verse visualmente distinta (ej. fondo levemente resaltado o un punto indicador) para que salte a la vista sin tener que leer el estado.
- Clic en fila → detalle.
- Paginación simple, consistente con `pedidos/`.

## Página de detalle — `conversaciones/[id]/page.tsx`

- **Transcripción** (columna principal): mensajes en orden, cliente a un lado, bot/humano al otro pero diferenciados entre sí con un label ("Victoria" vs "Tú").
- **Estado de la ventana de mensajería**, visible de forma clara arriba de todo (ej. un banner):
  - Si `ventanaAbierta: true` → "Ventana abierta — puedes responder libremente. Se cierra en X horas." (calcula X en el frontend a partir de `ventanaExpiraEn`, o muéstralo tal cual si el backend ya lo manda calculado)
  - Si `ventanaAbierta: false` → banner de advertencia: "La ventana de mensajería está cerrada. No se puede enviar texto libre hasta que el cliente vuelva a escribir." — y el campo de respuesta (ver abajo) debe estar deshabilitado en este caso, no solo fallar al enviar.
- **Panel lateral de datos del lead:** nombre, dirección, cantón, provincia, producto (+ variante), total, método de pago, estado de pago, estado del lead. Si `idPedidoRocketfy` existe, enlace a la vista de pedido existente.
- **NUEVO — botón "Crear pedido manual con estos datos":** visible cuando el lead tiene al menos nombre, dirección y producto, y `lead.estado != 'despachado'`. Lleva al formulario de creación manual de pedido que ya existe en el dashboard (Fase 2), prefilled con los datos del lead (usa el mecanismo de prefill que ese formulario ya soporte — si hoy no soporta querystring/prefill, agregar esa capacidad al formulario existente es parte de esta tarea, sin duplicar el formulario).
- **NUEVO — campo de notas internas:** textarea con los datos de `notasInternas`, botón "Guardar nota" que llama a `PATCH /conversaciones/<id>/notas`. Dejar claro en la interfaz (un texto pequeño) que estas notas son privadas y nunca se le muestran al cliente.
- **Campo de respuesta:** input + botón "Enviar" → `POST /conversaciones/<id>/mensajes`. Deshabilitado si `ventanaAbierta: false`. Si el backend devuelve 409 (ventana cerrada, condición de carrera con el momento exacto de cierre), mostrar el mismo mensaje de advertencia. Actualización optimista de la transcripción al enviar con éxito.
- **Botón "Devolver el control a Victoria"**, visible solo si `estado === 'escalada'`.

## Nav

Agregar "Conversaciones" a `config/site.ts`. Si es sencillo, mostrar ahí mismo en el sidebar el contador de escaladas sin revisar (mismo dato que ya se pidió en `totalesPorFiltroRapido`).

## Verificación de la Tarea 4

- `npm run build` y `npm run lint` limpios.
- Validar manualmente el flujo completo: lista → filtrar por escaladas → ver el contador de sin revisar → abrir una → confirmar que se marca como vista → revisar el estado de la ventana → si está abierta, responder y confirmar que llega de verdad al teléfono de prueba → guardar una nota interna → si aplica, probar el botón hacia el formulario de pedido manual → reactivar.
- Prueba también el caso de ventana cerrada: usa una conversación de prueba vieja (de hace más de 24h y sin FEP) y confirma que el campo de respuesta aparece deshabilitado con el mensaje correcto, no que falla al intentar enviar.

</requerimientos>

---

<nota_final>

# Resumen final al terminar

1. Resultado de `pytest` completo y confirmación de `npm run build`/`lint` limpios.
2. Confirmación explícita de que probaste el caso de ventana cerrada y el sistema lo bloqueó correctamente en vez de intentar enviar y fallar.
3. Confirmación de que probaste responder a una conversación real con ventana abierta y el mensaje llegó de verdad al teléfono.
4. Cómo quedó conectado el botón de "crear pedido manual" con el formulario existente (si tuviste que agregarle soporte de prefill, explica cómo).
5. Descripción o capturas de las pantallas.
6. Cualquier desvío, con su razonamiento.

</nota_final>
