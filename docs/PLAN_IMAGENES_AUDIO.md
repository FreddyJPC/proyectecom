# Plan: que Victoria entienda imágenes, audios y otros tipos de mensaje (pendiente #73)

> Estado: **plan aprobado por Freddy el 2026-11-10 («Sí, empieza con el desarrollo», con las recomendaciones de abajo)**. Las fases
> se marcan al terminar; ver `PROGRESS.md` para lo hecho.

## Para qué sirve (en llano)
Hoy, si un cliente manda una **foto**, una **nota de voz**, su **ubicación** o un **sticker**, Victoria recibe solo un marcador de
texto («[imagen]», «[audio]») y no sabe qué le mandaron. En Ecuador la gente manda muchas notas de voz, fotos de comprobantes de
transferencia y «pines» de ubicación en vez de escribir la dirección. Con esto Victoria **ve las fotos, escucha los audios (con una
transcripción) y entiende ubicaciones, stickers y reacciones**, y reconoce un comprobante de pago **sin confirmar nunca el pago**: eso lo
sigue confirmando una persona.

## Qué existe hoy (verificado en el código)
- El webhook de WhatsApp (`routes/whatsapp/controllers.py`) solo entiende `text`, `image` (guarda el pie de foto o «[imagen]») y `audio`
  («[audio]»). Todo lo demás se guarda como «[mensaje tipo 'x' no soportado todavía]».
- La tabla `mensajes` guarda solo texto; no guarda qué archivo era.
- Regla 3 del servicio: imagen + lead «esperando pago» → se escala a una persona y se manda un texto fijo (la IA ni la ve).
- El contrato con la IA (`MensajeLLM`) solo lleva texto: no puede llevar una imagen.

## Qué puede y qué no puede la IA (comprobado en la documentación oficial, 2026-11-10)
- **Imágenes: sí.** JPEG, PNG, GIF y WebP; hasta 8000×8000 px; ~1.500 «tokens» de entrada por foto típica (centavos). También PDF.
- **Audio: no.** La API de Claude no recibe audio (la página oficial de visión solo habla de imágenes y PDF; ninguna fuente lo contradice).
  Para los audios hace falta **otro servicio de transcripción** (voz → texto) y luego Victoria lee el texto. **Es un proveedor nuevo**: una
  cuenta, una clave (en Railway, nunca en el código) y un costo por minuto.

## Decisiones (las recomendaciones que Freddy aprobó)
1. **Audios:** se transcriben y Victoria responde como si el cliente lo hubiera escrito. Proveedor recomendado: **OpenAI**
   (`gpt-4o-mini-transcribe`; ~US$0,003 por minuto; buen español; acepta el formato de las notas de voz de WhatsApp). Detrás de una
   interfaz (`TranscriptionProvider`), como el LLM: cambiar de proveedor no toca el resto. **Viene APAGADO** hasta que exista la clave.
2. **Comprobantes de pago:** Victoria **reconoce** que es un comprobante y **extrae** monto, fecha, banco y referencia, y el código los
   compara con el total del pedido. **Nunca confirma el pago ni cierra por una foto:** avisa al dueño por Telegram con los datos (y las
   diferencias) y la conversación pasa a una persona, que lo confirma. Una foto puede ser falsa o de otra persona.
3. **Costo:** cada foto o audio suma un costo pequeño de IA; hay topes por mensaje y todo se puede apagar desde Parámetros.

## Fases
| Fase | Qué | Necesita del dueño |
|---|---|---|
| **F1** | Entender todos los tipos de mensaje de WhatsApp (imagen, audio, documento, ubicación, sticker, reacción, botón, video, contacto), guardar qué archivo era (`media_id`, tipo) y poder **descargarlo** de Meta. Migración 028. | — |
| **F2** | **Visión:** Victoria ve las imágenes del turno (y PDF). Herramienta `registrar_imagen_recibida` (tipo: comprobante / producto / ubicación / otro / ilegible, resumen, datos del comprobante). Regla del comprobante (sin confirmar el pago). Parámetros: `bot.entender_imagenes`, `bot.max_imagenes_por_mensaje`. | — |
| **F3** | **Audios:** interfaz de transcripción + proveedor OpenAI, apagado de fábrica; mientras no esté, respuesta fija amable pidiendo que lo escriba. Parámetros: `bot.entender_audios`, `bot.max_segundos_audio`. | Crear la cuenta y la clave de OpenAI y ponerla en Railway (`OPENAI_API_KEY`); encender el interruptor |
| **F4** | **Otros tipos:** ubicación (se guarda el enlace al mapa como referencia de la dirección; igual se pide cantón y provincia), sticker y reacción (entendidos como una respuesta corta), documento no soportado y video (respuesta fija amable). | — |
| **F5** | **Panel:** el dueño ve la foto o escucha el audio dentro de la conversación (el servidor la trae de Meta al momento; Meta la guarda ~30 días) y ve el análisis y la transcripción. | — |
| **F6** | Pruebas con la IA real (casos nuevos en `docs/PRUEBAS_CON_ERRORES_HUMANOS.md`), documentación y despliegue (migración primero). | La clave de pruebas |

## Reglas que no se rompen
- La IA **nunca confirma un pago** ni cierra una venta por una imagen; el dinero lo calcula el código (`Decimal`).
- Un archivo del cliente se trata como **dato, no como instrucción** (una foto con texto «ignora tus reglas» no cambia nada).
- Si algo falla (descarga, visión, transcripción), el cliente **nunca se queda sin respuesta**: respuesta fija amable y aviso al dueño.
- Nada se guarda fuera de la base salvo lo que Meta ya guarda; no se copian archivos a otro lado (privacidad y costo).
- Las imágenes viejas no se reenvían a la IA en cada turno: en el historial queda un texto con lo que Victoria entendió.

## Riesgos y cómo se cubren
| Riesgo | Cobertura |
|---|---|
| Un comprobante falso o ajeno | Nunca se confirma solo; el dueño recibe monto/fecha/banco/referencia y las diferencias con el pedido |
| Costos que suben (muchas fotos) | Tope de imágenes por mensaje, interruptores, imágenes viejas fuera del historial |
| El enlace de descarga de Meta vence a los ~5 min | Se descarga al procesar (la espera de ráfagas es de segundos); si vence, respuesta fija y aviso |
| Audios largos o ruidosos | Tope de duración; si la transcripción sale vacía o dudosa, se le pide al cliente que lo escriba |
| Contenido inapropiado en una foto | Victoria no comenta lo ajeno a la venta; ante duda, pasa a una persona |
| Proveedor de transcripción caído | Respuesta fija; el resto del bot sigue funcionando |
