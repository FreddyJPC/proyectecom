# Bitácora del módulo «Inmuebles»

> Bitácora propia del módulo de propiedades (pedido de Freddy, 2026-11-23): todo lo de inmuebles se anota aquí para no mezclarlo
> con la tienda. `PROGRESS.md` solo lleva un resumen (ADR-019, entrada 0.0.173 y pendiente #88) y apunta a este archivo.
> El plan original está en `docs/PLAN_INMUEBLE.md`.

## 1. Qué es y para qué sirve

**Hacemos esto para** que los mensajes de los anuncios de propiedades (hoy, la casa en venta en Guayaquil) los atienda un
asistente automático y Freddy no tenga que contestar a mano lo de siempre: dónde queda, cuánto mide, cuántas habitaciones,
mandar fotos, y anotar quién quiere visitarla.

- **No es Victoria.** Es un asistente aparte, con sus propias instrucciones (`backend/src/routes/inmuebles/asistente_prompt.txt`)
  y herramientas. Informa y toma pedidos de visita. **No vende, no negocia, no da rebajas, no se presenta como asesor**, no crea
  pedidos ni toca Rocketfy, y no le llega el seguimiento automático de la tienda.
- **Pensado para un portafolio**: muchas propiedades, cada una con su ficha, sus fotos y sus anuncios. Cuando se venda la casa,
  queda todo listo para subir la siguiente propiedad.
- **La agenda es manual a propósito**: el asistente solo anota lo que el cliente pidió («el sábado en la mañana») y avisa por
  Telegram. Freddy confirma el día y la hora en la Agenda y decide cuándo avisarle al cliente.

## 2. Estado (2026-11-23)

| Parte | Estado |
|---|---|
| Base de datos (migración 037) | Hecha y probada en la base local. **No aplicada en Supabase** (falta el visto bueno). |
| Backend (asistente, ruteo, agenda, API) | Hecho, 2713 pruebas pasando. **No desplegado.** |
| Panel (Propiedades, ficha, Agenda, conversación) | Hecho: lint, build y accesibilidad SIN VIOLACIONES. **No desplegado.** |
| Datos de la casa | **Faltan** (ver pendientes I-1 a I-4). |
| Conexión del número / anuncio | **Falta decidir** (ver sección 4 y pendiente I-5). |

## 3. Cómo funciona (en palabras simples)

1. **¿Quién atiende?** Cada conversación tiene un «asistente»: `ventas` (Victoria) o `inmuebles`. Se decide al llegar el mensaje:
   - si el cliente llegó por un **anuncio vinculado a una propiedad** (en la ficha → «Anuncios de esta propiedad»), lo atiende el
     asistente de inmuebles y ya sabe de qué propiedad se habla, **aunque el anuncio apunte al número de Victoria**;
   - si escribió a un **número de WhatsApp asignado a inmuebles** (Propiedades → «Números de WhatsApp»), también;
   - en cualquier otro caso, Victoria, como siempre.
   El dueño lo puede cambiar a mano en la conversación («Atiende» → «Cambiar quién atiende»).
2. **Qué sabe el asistente**: solo la ficha de la propiedad. Lo que no está, no lo inventa: pasa la conversación al dueño.
3. **Herramientas**: mandar la **ubicación como pin de WhatsApp** (las coordenadas salen de la ficha), mandar **fotos y videos**
   (sin repetir), **registrar un pedido de visita** (nunca la confirma) y **pasar al dueño** (aviso por Telegram).
4. **Precio**: por propiedad, el dueño decide si se dice y si es conversable. Si no se dice, el asistente responde que lo indica
   el propietario y le pasa la conversación. Nunca acepta ni rechaza ofertas.
5. **Agenda**: Por confirmar → Confirmar (día y hora de Ecuador, quién la enseña) → Avisar al cliente (mensaje editable, solo dentro
   de las 24 h de WhatsApp) → Se realizó / No asistió / Cancelar. También se puede agendar a mano a quien llamó por teléfono.
6. **Varios números**: si una propiedad se atiende por otro número, la respuesta sale de ese mismo número. Una persona que escribe
   a dos números del negocio tiene dos conversaciones (una por número); las conversaciones de siempre no cambiaron.

### Piezas del código
- Migración `backend/migrations/037_inmuebles.sql`: `inmuebles`, `inmuebles_material`, `inmuebles_anuncios`, `visitas`,
  `numeros_whatsapp`; en `conversaciones`: `asistente`, `inmueble_id`, `numero_negocio` y la clave única nueva
  `(canal, id_externo, coalesce(numero_negocio,''))`.
- `backend/src/routes/inmuebles/`: `repository.py`, `logica.py` (fichas, fechas en hora de Ecuador, transiciones de la agenda),
  `ruteo.py`, `herramientas.py`, `asistente.py` + `asistente_prompt.txt`, `servicio.py`, `schemas.py`, `api.py`.
- Cambios fuera del módulo: webhook (`numero_negocio` y ruteo), worker (elige el asistente y el número), registro de canales
  (`para(canal, numero)`, `para_conversacion`, envío de ubicación), seguimiento (excluye inmuebles), conversaciones (asistente en
  detalle y lista, filtro).
- Parámetros nuevos (grupo «Inmuebles»): `inmuebles.activo`, `inmuebles.nombre_asistente`, `inmuebles.como_llamar_al_dueno`,
  `inmuebles.texto_paso_al_dueno`, `inmuebles.texto_confirmacion_visita` (81 parámetros en total).
- Panel: menú «Inmuebles» → Propiedades (`/inmuebles`), ficha (`/inmuebles/[id]`), Agenda de visitas (`/agenda`); en cada
  conversación, la sección «Atiende».

## 4. ¿Se puede el camino A (mismo número de la casa, en el teléfono y en la app)? — Verificado 2026-11-23

**Resultado: hoy NO es viable para AzoShop.** Lo que encontré (solo lectura):

- Meta lo llama **«Coexistencia»** (onboarding de usuarios de la app WhatsApp Business): el mismo número sigue en la app del
  teléfono y además lo atiende la API, con los mensajes sincronizados. Requisitos según la documentación oficial de Meta:
  - ser **Solution Partner o Tech Provider** de Meta (proceso de alta con verificación de empresa y revisión de la app);
  - implementar **Embedded Signup** (el «registro incrustado» de Meta, con su ventana de inicio de sesión) en nuestra app;
  - app WhatsApp Business 2.24.17 o superior; y webhooks extra (`history`, `smb_message_echoes`, `smb_app_state_sync`).
- El conector de WhatsApp que tenemos lo dice explícitamente: **no hace migraciones ni coexistencia**.
- El portafolio AzoShop **no tiene la verificación de empresa** (requisito para ser Tech Provider).

**Conclusión y recomendación:** dejar el camino A como posible mejora futura (si algún día AzoShop se verifica y se hace Tech
Provider) y elegir entre:
- **C — número nuevo solo para propiedades (recomendado):** un chip nuevo registrado en la API (el conector sí puede: agregar →
  verificar → registrar, con confirmación de Freddy), con su nombre visible propio. Se registra en «Números de WhatsApp» con el
  asistente de inmuebles y se cambia el número del anuncio. Ventaja: identidad propia, no se mezcla con AzoShop.
- **B — usar el número de Victoria:** vincular el anuncio a la propiedad en su ficha (ya funciona, sin chip nuevo). Contra: el
  cliente ve «AzoShop» al escribir sobre una casa, y hay que vincular la página de la casa a ese número.

Dato útil: la campaña de la casa («Campaña Casa Guayaquil - Mensajes», cuenta publicitaria personal `853869848927360`) está activa
pero **frenada por el límite de gasto de la cuenta**; trajo 447 conversaciones a $0,34. Reactivarla = subir el límite (al final).

## 5. Pendientes (las dudas de Freddy y lo que falta)

| # | Qué | Quién |
|---|---|---|
| I-1 | **Información de la casa**: dirección o sector, cómo llegar, enlace de Google Maps, metros de terreno y de construcción (frente × fondo), pisos, habitaciones, baños, parqueo, si es zona comercial, servicios, papeles al día, preguntas que siempre hacen y sus respuestas, y fotos o videos (MP4). | Freddy |
| I-2 | **Precio**: ¿el asistente lo dice? ¿dice que es conversable o lo deja a Freddy? (en la ficha: «Que el asistente diga el precio» y «¿Es conversable?»). | Freddy |
| I-3 | **Cómo se presenta**: sin nombre, «el equipo de la casa» u otro nombre (parámetro «Nombre del asistente de inmuebles»), y cómo nombra al dueño («el propietario», «Freddy»…). | Freddy |
| I-4 | **Visitas**: días y horas en que se puede visitar y quién la enseña (en la ficha). Revisar el texto del mensaje de visita confirmada (parámetro). | Freddy |
| I-5 | ~~Decidir B o C~~ **DECIDIDO 2026-11-23: camino B** (el anuncio de la casa apunta al número de Victoria y se vincula a la propiedad en su ficha). A Freddy no le importa que se vea «AzoShop»: el asistente puede saludar como «le habla Freddy». Falta que el anuncio apunte al número de Victoria (hoy apunta al WhatsApp Business del teléfono). | Freddy, con guía |
| I-6 | **Desplegar**: aplicar la migración 037 en Supabase (primero la migración, después el código), PR, fusión, Railway y Vercel. Pide confirmación. | Claude, con visto bueno |
| I-7 | **Cargar la ficha** de la casa en la app, publicarla y vincular el anuncio `120252118114240418` (si es camino B) o registrar el número (camino C). | Freddy o Claude con los datos |
| I-8 | **Probar con la IA real** antes de reactivar: preguntas típicas, «¿dónde queda?», «mándeme fotos», «quiero visitarla», «dígame usted la hora», una oferta de precio, una pregunta que no está en la ficha. Hoy solo hay pruebas con una IA simulada. | Claude |
| I-9 | **Reactivar la campaña** (subir el límite de gasto de la cuenta personal) cuando todo lo anterior esté listo. | Freddy |
| I-11 | **Cómo actúa el asistente (lo dirá Freddy en detalle):** cómo habla y se presenta («Hola, buenos días/tardes/noches, le habla Freddy»), qué decir y qué no, y sobre todo: **cuando necesite a una persona NO debe decir «le paso con un asesor»: se queda callado y marca la conversación para gestión** (hoy, al pasar al dueño, se despide con una frase). Se ajusta en `asistente_prompt.txt` y en la herramienta `pasar_al_dueno`. | Freddy explica; Claude ajusta |
| I-10 | Más adelante: recordatorio de la visita el día anterior (necesita una **plantilla aprobada por Meta**: texto a aprobar por Freddy); instrucciones del asistente editables desde la app (hoy se cambian en el archivo); probar el asistente desde la app como «Probar con Victoria». | Por decidir |

## 6. Historial

| Fecha | Qué |
|---|---|
| 2026-11-23 | Idea asentada (`docs/PLAN_INMUEBLE.md`). Revisado en Meta: campaña de la casa frenada por límite de gasto; coexistencia (camino A) requiere ser Tech Provider + Embedded Signup → no viable hoy. Construido el módulo completo: migración 037, asistente, ruteo por anuncio y por número, respuestas desde el número correcto, agenda manual con aviso al cliente, API y panel. 2713 pruebas; lint, build y accesibilidad sin violaciones. Sin desplegar. |
