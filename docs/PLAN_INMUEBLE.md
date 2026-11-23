# Plan: atender con el bot los mensajes del anuncio de la casa (módulo «Inmueble»)

> Estado: **desplegado** (2026-11-23, camino B). Lo que se hizo, lo verificado en Meta y los pendientes: `docs/BITACORA_INMUEBLES.md`.
> (Este plan queda como referencia de la idea original.) Pedido de Freddy: que los mensajes del anuncio de la casa en venta
> lleguen a la app y los atienda un asistente que **informa y toma pedidos de visita**, sin vender, sin negociar y sin
> presentarse como asesor de ventas. Además, un panel de agendamientos para ver quién va a ver la casa y cuándo.

## 1. Lo que hay hoy (verificado en Meta el 2026-11-23, solo lectura)

- Campaña **«Campaña Casa Guayaquil - Mensajes»** (`120252118114230418`), en la cuenta publicitaria **personal**
  `853869848927360` (no la de AzoShop; no pertenece a ningún portafolio). Objetivo: mensajes por WhatsApp.
- Grupo «Inversionistas Guayaquil - WhatsApp.» (`120252118114250418`), **$2,50 al día**, anuncio «Video Casa Guayaquil 1»
  (`120252118114240418`).
- Desde el 2026-08-09: **447 conversaciones por $154,03 → $0,34 cada una** (muy barato).
- Campaña, grupo y anuncio figuran como **activos**, pero **no están saliendo**: la cuenta llegó a su **límite de gasto**
  (`account_spend_limit_reached`). «Reactivar» = subir o reiniciar el límite de gasto de esa cuenta; no hace falta
  rehacer nada.
- Los mensajes llegan al número de WhatsApp Business (app del teléfono) que Freddy atiende a mano. Ese número **no está**
  conectado a nuestra app (la app solo atiende el número de Victoria, por la API de WhatsApp).

## 2. La decisión de fondo: ¿por qué número llegan los mensajes?

La app solo puede leer y contestar mensajes de un número conectado a la **API de WhatsApp** (WhatsApp Cloud API). Hay
tres caminos:

| Camino | Qué implica | A favor | En contra |
|---|---|---|---|
| **A. Conectar el número de la casa a la API en modo «coexistencia»** | El mismo número sigue en la app del teléfono **y** además lo atiende la API (Meta sincroniza los mensajes). | No cambia el anuncio, ni el número, ni los contactos de antes; Freddy puede seguir mirando y contestando desde el teléfono. | Hay que verificar que Meta lo permita para esta cuenta (es un alta especial). La app debe aprender a manejar **dos números**. |
| B. Apuntar el anuncio al número de Victoria (AzoShop) | El anuncio de la casa manda al número de la tienda. | Lo más rápido: la app ya lo atiende. | El cliente ve «AzoShop» al escribir sobre una casa (confunde y mezcla marcas); hay que vincular la página de la casa al número de AzoShop. |
| C. Número nuevo solo para la casa, en la API | Un chip nuevo registrado en la API con su propio nombre visible. | Identidad propia, separado de la tienda. | Cambiar el número del anuncio; nombre visible a aprobar por Meta; se pierde el historial del número actual. |

**Recomendación: A.** Es la única que deja todo como está para el cliente y para Freddy. **Primer paso (F0):** comprobar
en Meta, sin cambiar nada, si el número de la casa se puede conectar en coexistencia. Si no se puede, ir por **C**.

## 3. Cómo se separa de Victoria sin rehacer nada

Se reutiliza todo el «motor» (webhook, cola, junta de mensajes seguidos, audios e imágenes, panel de conversaciones,
Telegram). Lo que cambia es **quién contesta y con qué herramientas**:

- Cada conversación tiene un **modo**: `ventas` (Victoria, como hoy) o `inmueble` (el asistente de la casa). El modo se
  decide **por el número** que recibió el mensaje (camino A o C) o **por el anuncio** de llegada (camino B), y queda fijo
  en la conversación. El dueño puede cambiarlo a mano desde el panel.
- **Asistente de la casa** = instrucciones propias + ficha del inmueble + herramientas propias. Victoria no se entera de
  la casa y la casa no se entera de los productos.
- **Lo que NO hace el asistente de la casa:** vender, negociar el precio, ofrecer descuentos, presentarse como asesor,
  crear pedidos, Rocketfy, cuentas para transferir, seguimiento automático (empujones), aviso de ventas a Meta. Esas
  conversaciones no cuentan en ventas, leads ni métricas de la tienda.

### Herramientas del asistente de la casa

| Herramienta | Qué hace |
|---|---|
| `enviar_ubicacion` | Manda la **ubicación nativa de WhatsApp** (el pin con el mapa, no un texto) y una referencia de cómo llegar. Las coordenadas salen de la ficha, nunca de la IA. |
| `enviar_material` | Fotos y videos de la casa (misma lógica que los productos). |
| `solicitar_visita` | Registra que el cliente quiere ir: nombre, día y hora que prefiere (o «cuando ustedes digan»), cuántas personas, nota. Le dice al cliente que **se le confirma en breve**: el asistente **nunca confirma** una visita. Avisa a Freddy por Telegram. |
| `pasar_al_dueno` | Para lo que no esté en la ficha, una oferta de precio, financiamiento, papeles o cualquier cosa delicada. |

### Ficha del inmueble (la escribe Freddy una vez)

Título, dirección o sector y referencia para llegar, **coordenadas**, precio (y si se puede decir o no), metros de
terreno y de construcción (largo × ancho), pisos, habitaciones, baños, parqueo, uso (residencial o comercial), servicios,
papeles al día, qué está incluido, preguntas frecuentes, fotos y videos, **horarios en que se puede visitar** y temas que
el asistente no debe tocar.

## 4. Agenda de visitas (pantalla nueva)

- Lista por día: cliente, teléfono, hora pedida, hora confirmada, estado y nota.
- Estados: **solicitada** (la pidió el cliente) → **confirmada** (Freddy acordó día y hora con quien enseña la casa) →
  **realizada** / **no asistió** / **cancelada**.
- Botones: «Confirmar» (con día y hora) y «Avisar al cliente» (le manda la confirmación por WhatsApp; dentro de las 24 h
  es texto libre, después hace falta una plantilla aprobada por Meta).
- Más adelante: recordatorio el día anterior (plantilla) y compartir la agenda con la persona que enseña la casa.

## 5. Fases

| Fase | Qué | Depende de |
|---|---|---|
| F0 | Comprobar en Meta (sin cambiar nada) si el número de la casa se puede conectar en coexistencia; decidir A o C. | Freddy elige el negocio en el conector de WhatsApp |
| F1 | Datos: ficha del inmueble, modo de la conversación, visitas (migración nueva). Envío de ubicación nativa en el cliente de WhatsApp. | — |
| F2 | Asistente de la casa: instrucciones, herramientas y pruebas con conversaciones simuladas (preguntas típicas, pedir visita, «dígame usted la hora», preguntas fuera de la ficha). | Ficha llena por Freddy |
| F3 | Panel: ficha editable, agenda de visitas, filtro «Inmueble» en conversaciones, aviso por Telegram. | — |
| F4 | Conectar el número (A o C), probar con un mensaje real, y recién entonces subir el límite de gasto de la cuenta y reactivar la campaña. | F0–F3 |

**Orden importante:** la campaña se reactiva **al final**. Si se reactiva antes, los mensajes siguen llegando al teléfono
como hoy (eso también vale si Freddy quiere reactivarla ya y atenderla a mano mientras se construye).

## 6. Lo que falta que decida o entregue Freddy

1. Toda la información de la casa (lista del punto 3) y sus fotos o videos.
2. ¿El asistente dice el precio? ¿Dice que es negociable o lo deja para Freddy?
3. ¿Cómo se presenta? (sin nombre, «el equipo de la casa», otro nombre…). No será Victoria.
4. Días y horas en que se puede visitar la casa, y quién la enseña.
5. Visto bueno para el paso F0 en Meta.
