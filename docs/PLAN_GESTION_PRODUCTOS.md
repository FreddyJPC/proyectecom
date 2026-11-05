# Plan: gestión de productos desde la app

> **Estado: PROPUESTA (2026-11-05), pendiente de tu aprobación.** Nada de esto
> está construido. Cuando lo apruebes se registra como ADR en `PROGRESS.md`
> (sección 2) y se empieza por la Fase A. Escrito por Claude a partir de
> `PROGRESS.md`, `backend/src/routes/whatsapp/*`, `backend/src/routes/productos/*`
> y el dashboard (`frontend/src/app/(dashboard)/catalogo`), leídos el 2026-11-05.

## 1. Hacemos esto para…

Que puedas llevar un producto desde **"tengo una idea"** hasta **"Victoria lo
está vendiendo"** sin terminal, sin SQL y sin pedirme que cargue datos a mano,
con **control tuyo en cada paso**: el sistema y el LLM *proponen*, tú
*decides*. De paso cerramos los huecos de seguridad de ventas que encontramos
al revisar el flujo actual (precio, cantidad, stock, pausa).

## 2. Punto de partida (cómo es hoy)

### 2.1 Dos catálogos que no se hablan

| | Catálogo de Rocketfy | Base de conocimiento de Victoria (`productos_bot`) |
|---|---|---|
| Qué es | Lo que Rocketfy tiene para tu cuenta: nombre, SKU, **costo**, precio sugerido, stock, peso, imágenes | Lo que Victoria sabe para **vender**: descripción, **precio de venta**, variantes, tiempo de entrega, pagos, preguntas frecuentes |
| Quién lo llena | Rocketfy | Hoy: tú por script interactivo (necesita terminal y la clave de la base) o yo por SQL |
| Dónde se ve | Dashboard → Catálogo (solo nombre, SKU, costo y stock) | En ningún lado del dashboard |

Que Rocketfy tenga un producto **no** lo vuelve vendible por WhatsApp.
Hoy hay **1** producto cargado para Victoria y **0** SKUs vigilados.

### 2.2 Huecos encontrados en el flujo actual

| # | Hueco | Dónde está en el código |
|---|---|---|
| H1 | **El total del pedido lo escribe el LLM**, no sale del precio cargado. Solo el SKU está protegido. | `tools.py::_handle_registrar_producto` toma `entrada["total"]` |
| H2 | **Siempre 1 unidad por pedido.** | `tools.py::_handle_cerrar_venta` fija `cantidad=1` |
| H3 | **Nadie revisa el stock** antes de vender. El vigilante solo registra alertas de SKUs vigilados. | Ningún archivo de `routes/whatsapp` consulta stock |
| H4 | **Variantes = texto libre.** El pedido lleva el SKU del producto y la variante solo como sufijo del nombre; no sabemos si Rocketfy maneja el color como producto aparte. | `productos_bot.variantes`, `tools.py` |
| H5 | **Victoria no envía fotos**, solo texto. | No existe herramienta de imagen |
| H6 | **Pausar no pausa del todo.** `obtener_por_sku` y `obtener_por_id_anuncio` no filtran por `activo`: un cliente con el producto ya elegido (o un anuncio vinculado) lo sigue pudiendo comprar. | `repository.py::ProductoBotRepository` |
| H7 | **Con varios productos, Victoria solo ve nombre, SKU y precio** hasta que registra el producto; la ficha completa recién aparece en el turno siguiente del cliente. | `conversation_service.py::_formatear_contexto_producto` |
| H8 | **El simulador actual usa las herramientas reales:** un cierre de venta simulado crearía un pedido real en Rocketfy y avisaría por Telegram. | `tools/chat_con_victoria.py` |

## 3. El flujo en la app (lo que verás)

**Entrada:** *Catálogo* → en cada producto el botón **"Preparar para vender"**
(o la pestaña nueva **"Mis productos"** → "Nuevo desde Rocketfy").

**Estados de un producto** (insignia de color, siempre los mismos nombres):

`borrador` → `listo` → **`activo`** ⇄ `pausado` · `agotado` (pausa automática por
stock) · `archivado`. **Solo `activo` lo ve Victoria.**

**La ficha del producto, en 5 secciones** (guardas y vuelves cuando quieras; en
el teléfono se ven como acordeón, en pantalla grande como pasos):

1. **Datos de Rocketfy** (solo lectura, con botón *Actualizar*): nombre, SKU,
   costo, precio sugerido, stock, peso, imagen y variantes si las hay.
2. **Precio**: la app calcula tres niveles (mínimo, recomendado, premium) y te
   muestra cuánto ganas por unidad. Tú eliges uno o escribes el tuyo.
3. **Contenido de ventas**: botón **"Redactar con IA"**. Tú le das tus notas
   (a quién va dirigido, qué destacar, qué evitar); devuelve un borrador que
   editas campo por campo.
4. **Reglas de venta**: unidades máximas por pedido, métodos de pago, tiempo de
   entrega y mínimo de stock a vigilar.
5. **Probar y publicar**: conversas con Victoria en modo simulación (sin tocar
   nada real), ves la lista de verificación y pulsas **Publicar**.

Desde la lista de *Mis productos* también: **Pausar, Reanudar, Archivar** y ver
el **historial de cambios** (quién cambió qué y cuándo).

## 4. Reglas de diseño (no se negocian)

1. **Tú apruebas.** Nada llega a Victoria sin que pulses *Publicar*. La IA nunca
   publica ni cambia precios sola.
2. **Los números los calcula código, no el LLM.** Dinero siempre `Decimal`/texto,
   nunca `float` (regla del proyecto). El LLM redacta y explica.
3. **Cada afirmación del contenido lleva su fuente:** *Rocketfy*, *tus notas* o
   *sugerido por IA (verifica)*. Lo que la IA añade por su cuenta se marca.
4. **La simulación no toca el mundo real:** ni pedidos en Rocketfy, ni Telegram,
   ni WhatsApp, ni filas en conversaciones o leads.
5. **Todo cambio queda registrado** (usuario, fecha, qué cambió).
6. **Mobile-first, en español, con estados de carga/vacío/error**, solo tokens
   de color y componentes existentes (reglas de `CLAUDE.md` §5).
7. **Cada fase se entrega sola:** su PR, sus tests, su migración confirmada por
   ti, su despliegue verificado. Nunca se edita una migración ya aplicada.

## 5. Fases

| Fase | Qué entrega | Cierra | Tamaño | Depende de |
|---|---|---|---|---|
| **0** | Decisiones tuyas (sección 12) | — | — | — |
| **A** | **Ventas seguras** (solo backend) | H1, H2, H3, H6, H7 | M | 0 |
| **B** | **"Mis productos"**: lista, ficha manual, estados, publicar/pausar | Carga sin terminal | L | A |
| **C** | **Precio recomendado** y ajustes de negocio | — | M | B |
| **D** | **Redactar con IA** | — | M | B |
| **E** | **Probar con Victoria** (simulación) + lista de verificación | H8 | M | B, D |
| **F** | **Operación continua**: sincronizar stock y costo, auto-pausa, alertas de margen | — | M | B |
| **G** | Extras opcionales: variantes reales, fotos por WhatsApp, publicar en la tienda | H4, H5 | S–M c/u | B |

Tamaños relativos (S < M < L), no horas. **Primer hito útil: al terminar la
Fase B ya cargas productos desde el teléfono.** Orden recomendado: A → B → C → D
→ E → F, con G cuando lo necesites.

### Fase A — Ventas seguras (backend)

*Para qué:* que Victoria no pueda cobrar un monto equivocado, ni vender lo que
no hay, ni vender lo que pausaste. Se puede hacer antes de cualquier pantalla.

- **H1 — total desde la base:** `registrar_producto` calcula
  `total = precio del producto × cantidad` (Decimal). Lo que escriba el LLM se
  ignora; si difiere se deja un aviso en el log para detectarlo.
- **H2 — cantidad:** parámetro nuevo `cantidad` (de 1 al máximo del producto,
  `productos_bot.max_unidades_por_pedido`, por defecto 1). `leads.cantidad`
  nuevo; `cerrar_venta` lo usa en la línea del pedido.
- **H3 — stock:** antes de registrar y justo antes de cerrar, se consulta el
  stock del SKU exacto en Rocketfy (caché de ~5 minutos). Si no alcanza,
  Victoria se lo dice al cliente (ofrece menos unidades o avisa) y queda
  alerta. Si Rocketfy no responde **no se bloquea la venta** (Rocketfy igual la
  rechazaría al confirmar y se escala), pero queda en el log.
- **H6 — pausar de verdad:** `registrar_producto`, `cerrar_venta` y el contexto
  por anuncio verifican que el producto siga `activo`. Si se pausó a mitad de
  conversación, Victoria lo explica y escala.
- **H7 — ficha bajo demanda:** herramienta nueva `ver_ficha_producto(sku)` que
  devuelve la ficha completa **en el mismo turno**, para poder responder dudas
  antes de que el cliente "elija".
- **Captura de mínimos de Rocketfy:** cuando Rocketfy rechaza una confirmación
  con *"el importe mínimo debe ser … ($18.47)"*, se guarda ese monto con el
  producto y el destino (`rocketfy_minimos_observados`). Es la única forma de
  aprender el costo real de envío sin cotizador (alimenta la Fase C).
- Prompt de Victoria: aclara que "el total lo calcula el sistema".

*Listo cuando:* tests demuestran que (a) con precio $24.99 y 2 unidades el pedido
sale por $49.98 sin importar lo que diga el LLM, (b) sin stock suficiente no se
crea el pedido, (c) un producto pausado no se puede registrar ni cerrar.

### Fase B — "Mis productos" (backend + app)

*Para qué:* reemplazar el script y el SQL. Con esta fase ya puedes dejar un
producto activo desde el teléfono, aunque el precio y el texto los escribas tú.

- **Migración 014:** columnas nuevas en `productos_bot` (estado, costo y precio
  sugerido de Rocketfy, stock último, imagen, peso, notas internas, quién y
  cuándo publicó) y tabla `productos_bot_historial`. El producto actual
  (audífonos) pasa a `activo`. `activo` y `estado` se mantienen sincronizados
  por una única función de transición.
- **Backend** (módulo nuevo `routes/productos_bot/`, mismas capas
  `dto/schemas/services/controllers/repository`): listar, ver, crear borrador
  desde un SKU de Rocketfy (valida SKU exacto y copia costo/stock), editar,
  publicar, pausar, reanudar, archivar. Al publicar se agrega el SKU a
  *Vigilados* automáticamente.
- Ampliar `GET /productos` (descripción, precio sugerido, imagen, peso, id del
  padre) y agregar `GET /productos/<sku>`.
- **App:** pestaña *Mis productos* en Catálogo, botón *Preparar para vender* en
  cada fila, página de la ficha con las secciones 1, 3 (manual), 4 y 5.
- El script `cargar_producto_bot.py` queda como respaldo.

*Listo cuando:* creas, publicas, pausas y reanudas un producto real desde el
teléfono, y la siguiente conversación de Victoria lo refleja.

### Fase C — Precio recomendado

*Para qué:* que fijar el precio deje de ser adivinar. Ver la sección 7.

- Pantalla **Ajustes de precios**: margen mínimo y objetivo, costo de envío
  estimado, otros costos (porcentaje y fijos), tipo de redondeo.
- **Calculadora** en el backend (Decimal, con tests) y sección *Precio* con
  tres niveles, comparación con el precio sugerido de Rocketfy, un campo
  opcional para el **precio de la competencia que tú mires** y la ganancia por
  unidad.
- **Calibración del envío:** con los mínimos observados (Fase A) la app te dice
  "tu envío real parece rondar $X"; tú decides si lo adoptas.
- El LLM, si quieres, solo **explica** el resultado en lenguaje llano.
- No se puede publicar por debajo del piso (ver 7).

### Fase D — Redactar con IA

*Para qué:* que el contenido de ventas salga en minutos y sin inventar.

- Se amplía el contrato `LLMProvider` con un parámetro opcional
  `forzar_herramienta` (el adaptador de Anthropic lo traduce a `tool_choice`)
  para recibir **JSON estructurado** y no texto libre. La regla de no importar
  el SDK fuera de `src/integrations/llm/` se mantiene y se prueba.
- **Entrada:** datos de Rocketfy + tus notas + reglas de la casa (tono de
  Victoria, "no prometer", política de entrega y pago). **Salida (campos):**
  nombre comercial, resumen corto (1–2 líneas), descripción para WhatsApp,
  puntos fuertes, variantes detectadas, tiempo de entrega propuesto (de tus
  ajustes), preguntas frecuentes (5 a 8), temas que Victoria no debe responder y
  **alertas de revisión** (afirmaciones que no salen de Rocketfy ni de tus notas).
- **Honestidad por diseño:** cada dato lleva su fuente; lo "sugerido por IA" se
  resalta; el texto de Rocketfy se trata como dato no confiable (podría traer
  instrucciones); nunca se publica solo.
- **Control de uso:** tope diario de redacciones (ajustable) y registro en
  `generaciones_ia`.
- **App:** panel *Redactar con IA* → borrador por campo con *Aceptar / Editar /
  Regenerar*, contador de caracteres (todo va al prompt de cada turno, conviene
  que sea corto).
- Si vendes productos de salud o suplementos, la regla de la casa evita
  promesas médicas o de resultados; **la revisión final es tuya**.

### Fase E — Probar con Victoria + lista de verificación

*Para qué:* ver cómo se comporta antes de que hable con un cliente real.

- **Modo simulación:** el mismo `VictoriaConversationService` (el cerebro real)
  pero con repositorios **en memoria**, un ejecutor de herramientas en
  **modo ensayo** (`cerrar_venta` no llama a Rocketfy: devuelve la **vista
  previa del pedido** que se habría enviado; `escalar_a_humano` no avisa por
  Telegram) y el producto en borrador como único producto disponible.
- **App:** chat de prueba con escenarios rápidos (*Quiero comprarlo*, *¿Cuánto
  cuesta el envío?*, *Pago por transferencia*, *Pregunta fuera de la ficha — debe
  escalar*, *Quiero 2 unidades*), vista del pedido simulado y de las
  herramientas que usó. Topes de mensajes y de pruebas por día.
- **Lista de verificación al publicar** (sección 9), con la simulación como
  recomendación fuerte.

*Listo cuando:* un test comprueba que una compra simulada completa no genera
**ninguna** llamada a Rocketfy, Telegram o WhatsApp ni filas nuevas reales.

### Fase F — Operación continua

*Para qué:* que lo publicado se mantenga correcto sin que lo vigiles.

- **Sincronización** (en el job del vigilante, cada 60 minutos): actualiza costo,
  precio sugerido y stock de cada producto activo.
- **Auto-pausa por agotado:** estado `agotado`, aviso por Telegram y en
  *Incidencias*. Reanudar es manual por defecto (ajustable).
- **Alerta de margen en riesgo:** si el costo sube y el margen cae del mínimo,
  insignia y aviso; **no cambia el precio solo**.
- En la lista: pedidos creados por producto (últimos 30 días) e historial.

### Fase G — Extras opcionales

- **G1 Variantes reales:** primero un descubrimiento en tu catálogo (¿Rocketfy
  usa productos hijos con `parent_id` y SKU propio?). Si es así, `variantes`
  pasa a ser una lista estructurada con el SKU de cada una, y el pedido lleva
  el SKU correcto. Hasta entonces, la primera venta de un producto con
  variantes la revisas tú.
- **G2 Fotos por WhatsApp:** herramienta `enviar_foto_producto` y envío de
  imagen por enlace con la Cloud API (usando la imagen de Rocketfy o una que
  subas).
- **G3 Publicar también en la tienda web** (repo `AzoShop_FrontEnd`): hoy la
  tienda tiene su propia base de productos y su propio precio. Hay que decidir
  si se unifican; mientras no, el precio de la tienda y el de Victoria pueden
  diferir.
- **G4 Descuentos o combos**, si algún día decides ofrecerlos (hoy Victoria
  tiene prohibido ofrecerlos).

### Fuera de este plan: automatización de anuncios (versión siguiente)

Conectar las cuentas de anuncios, vincular cada anuncio con su producto,
medir su rendimiento contra las ventas reales, pausar o dar de baja anuncios
(por stock bajo o margen), etc. Es la **versión 2** del proyecto
(`PROGRESS.md`, pendiente #50). Este plan es su base: sin una ficha de producto
bien gestionada no hay a qué conectar un anuncio. La tabla `anuncios_productos`
y la captura del `referral` de Meta ya existen.

## 6. Datos nuevos (migraciones numeradas; nunca se edita una aplicada)

| Migración | Contenido |
|---|---|
| 013 (Fase A) | `leads.cantidad`; `productos_bot.max_unidades_por_pedido`; `rocketfy_minimos_observados` (sku, cantón, provincia, mínimo, mensaje, fecha) |
| 014 (Fase B) | `productos_bot`: `estado`, `rocketfy_product_id`, `costo_rocketfy`, `precio_sugerido_rocketfy`, `stock_ultimo`, `stock_actualizado_en`, `peso_kg`, `imagen_url`, `notas_internas`, `resumen_corto`, `publicado_en`, `publicado_por`; tabla `productos_bot_historial` |
| 015 (Fase C) | `ajustes_negocio` (una sola fila: margen mínimo y objetivo, envío estimado, otros costos, redondeo, topes de uso de IA, auto-pausa) |
| 016 (Fase D) | `generaciones_ia` (producto, usuario, tipo, modelo, fecha) para topes y auditoría |

Todas con RLS activado y sin policies, como la tabla `latido`.

## 7. Cómo se calcula el precio recomendado (Fase C)

Entradas: `costo` (precio base de Rocketfy), `envío` (estimado en ajustes),
`otros_fijos`, `otros_%`, margen mínimo y objetivo. *Margen = ganancia ÷ precio
de venta.*

- **Piso** = el mayor entre `costo + envío` y **$10.00** (mínimo de contraentrega
  de Rocketfy). *Por debajo del piso no se puede publicar.*
- **Precio para un margen m** = `(costo + envío + otros_fijos) ÷ (1 − m − otros_%)`,
  redondeado hacia arriba al siguiente precio terminado en **.99** (configurable).
- **Tres niveles:** *Mínimo* (margen mínimo), *Recomendado* (margen objetivo) y
  *Premium* (el mayor entre el recomendado y el precio sugerido del proveedor).
  Si tu margen objetivo exige un precio **por encima del sugerido**, la app lo
  avisa: puede costarte competitividad.

**Ejemplo con números inventados, solo para ilustrar:** costo $10.00, envío
estimado $5.00, margen mínimo 25 %, objetivo 35 %, sugerido $29.90.

| Nivel | Cálculo | Precio | Ganancia por unidad |
|---|---|---|---|
| Piso | máx($15.00, $10.00) | $15.00 | — |
| Mínimo | 15 ÷ 0.75 = 20.00 → .99 | $20.99 | $5.99 (28.5 %) |
| Recomendado | 15 ÷ 0.65 = 23.08 → .99 | $23.99 | $8.99 (37.5 %) |
| Premium | máx(23.99, 29.90) | $29.90 | $14.90 (49.8 %) |

**Límites honestos:**

- Rocketfy **no tiene cotizador de flete** (pendiente #5): el envío real solo se
  conoce al confirmar. Por eso el envío es un *estimado* que tú ajustas y que la
  app calibra con los mínimos que Rocketfy rechaza. Antes de abrir un producto
  conviene un pedido de prueba.
- **No conozco precios de la competencia ni de tu mercado.** Los puedes anotar a
  mano; el LLM no inventa cifras.

## 8. Endpoints nuevos (todos exigen login, como el resto)

| Método y ruta | Para qué |
|---|---|
| `GET /productos/<sku>` | Ficha de Rocketfy de un producto (en vivo) |
| `GET /productos-bot` · `GET /productos-bot/<sku>` | Lista y detalle (con historial) |
| `POST /productos-bot` | Crear borrador desde un SKU de Rocketfy |
| `PATCH /productos-bot/<sku>` | Editar campos (registra historial) |
| `POST /productos-bot/<sku>/precio/recomendar` | Calculadora |
| `POST /productos-bot/<sku>/contenido/generar` | Borrador con IA (no guarda hasta que aceptes) |
| `POST /productos-bot/<sku>/probar` | Un turno de la simulación |
| `POST /productos-bot/<sku>/publicar` · `/pausar` · `/reanudar` · `/archivar` | Transiciones de estado |
| `GET/PUT /ajustes/negocio` | Ajustes de precios y topes |

## 9. Lista de verificación para publicar

Bloquean (no se puede publicar si falla):
1. El SKU existe **exactamente** igual en Rocketfy (consulta en vivo).
2. Hay stock.
3. El precio no está bajo el **piso**.
4. Están completos nombre, descripción, tiempo de entrega y métodos de pago.
5. Las unidades máximas por pedido están definidas.

Avisan (puedes publicar igual, con confirmación):
6. Margen por debajo del mínimo.
7. Incluye *transferencia*: Victoria **no ve imágenes**, así que escalará a una
   persona para verificar el comprobante.
8. No hubo una simulación completa.
9. Tiene variantes (se sigue el criterio de la G1).
10. Contenido con "alertas de revisión" sin resolver.

Al confirmar se muestra el resumen: *"Victoria empezará a vender X a $Y"*.

## 10. Riesgos y cómo se mitigan

| Riesgo | Mitigación |
|---|---|
| El costo de envío es desconocido, el precio recomendado es aproximado | Estimado ajustable, calibración con datos reales, piso duro, pedido de prueba |
| La IA inventa características | Fuente por dato, alertas de revisión, tú apruebas, nada se publica solo |
| El texto de Rocketfy trae instrucciones ocultas | Se trata como dato no confiable, salida con esquema fijo, revisión humana |
| La simulación crea un pedido real | Ejecutor en modo ensayo + repos en memoria + test que lo comprueba (H8) |
| Pausar no detiene una conversación en curso | Se verifica `activo` al registrar y al cerrar (H6) |
| Dos fuentes de verdad (`activo` y `estado`) | Una sola función de transición + test de consistencia |
| Gasto de IA | Topes diarios y registro de usos |
| Cualquiera con sesión puede publicar | Hoy el panel es de un solo usuario (pendiente #11); si se suma gente, hay que agregar roles |
| Despliegue del backend es manual (pendiente #48) | Tras cada fusión se reconecta la fuente y se verifica en los logs |
| La lista de productos que ve Victoria crece | Con muchos productos, pasar a búsqueda por herramienta (la base ya queda preparada con `ver_ficha_producto`) |

## 11. Cómo se verifica cada fase

- **Backend:** pruebas unitarias nuevas y toda la suite en verde (hoy 237) contra
  un Postgres local desechable; migración probada ahí y luego aplicada a
  Supabase **con tu confirmación**.
- **App:** `npm run lint`, `npx next build`, auditoría de accesibilidad
  (`node axe.mjs`, SIN VIOLACIONES) y capturas a 390 px y en escritorio, claro y
  oscuro (reglas de `CLAUDE.md` §5).
- **Producción:** PR y fusión con tu OK; el frontend se despliega solo en Vercel,
  el backend reconectando Railway; verificación por logs. Para lo que toca a
  Victoria, una conversación real de prueba desde tu teléfono.

## 12. Decisiones que necesito de ti (Fase 0)

| # | Decisión | Mi propuesta de partida |
|---|---|---|
| 1 | Margen mínimo y objetivo | 25 % y 35 % (de ganancia sobre el precio de venta) |
| 2 | Costo de envío estimado | Que lo saques de tus envíos reales en el panel de Rocketfy (Quito/Guayaquil y resto) |
| 3 | Unidades por pedido | 1 por defecto, configurable por producto |
| 4 | Métodos de pago al inicio | Solo **contraentrega** (transferencia obliga a una persona a verificar) |
| 5 | Al agotarse un producto | Pausa automática sí; reanudar manual |
| 6 | Tope diario de IA | 20 redacciones y 10 pruebas por día |
| 7 | ¿Productos de salud o suplementos? | Si sí, reglas de contenido más estrictas y revisión tuya obligatoria |
| 8 | ¿Unificar algún día con la tienda web? | Dejarlo para la G3 |
