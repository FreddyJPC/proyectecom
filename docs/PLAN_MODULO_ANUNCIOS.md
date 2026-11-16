# Plan: módulo de Anuncios y Meta (ofertas, medición y protección de la inversión)

> Versión 1.0 — 2026-11-16. Pedido de Freddy: «que no haya huecos de venta o gestión» entre los anuncios de Meta, Victoria y
> las ventas. Análisis hecho leyendo el código, la base, los permisos reales de la app en Meta (conector Devtools) y la
> documentación oficial de Meta (leída el 2026-11-16). **Nada de este plan está construido todavía.** Pendiente #81.

## 1. Para qué sirve (en llano)

Hoy el sistema sabe **de qué anuncio** llega cada cliente y le avisa a Meta qué clics terminaron en compra. Pero:

- Victoria solo puede saber **un producto** por anuncio, a **precio de catálogo**. Un anuncio de «linterna + cargador por $25»
  o «2×1» no se puede vender bien: Victoria cobraría otro precio o no sabría qué incluye.
- El sistema **no sabe cuánto gastas** en cada anuncio, así que no puede decirte cuánto te cuesta cada venta ni si un anuncio
  está perdiendo plata.
- Cuando un producto se agota, Victoria deja de ofrecerlo, **pero el anuncio sigue gastando** en Meta.

Este módulo cierra esos tres frentes: **qué vende cada anuncio** (ofertas), **cuánto rinde** (medición) y **cuidar la plata**
(alertas y pausas automáticas).

## 2. Lo que ya existe (no se rehace)

| Pieza | Dónde | Qué hace |
|---|---|---|
| Llegadas por anuncio | `conversacion_anuncios` (migración 023) | Guarda cada clic: anuncio, título, texto, imagen, `ctwa_clid` |
| Vínculo anuncio → producto | `anuncios_productos` (009/023), pantalla «Anuncios» | Un anuncio apunta a **un** SKU; Victoria recibe su ficha |
| Aviso de anuncio nuevo | `whatsapp/services.py` | Telegram «Llegó un anuncio nuevo sin vincular» (cuando llega el **primer** cliente) |
| Atribución por lead | `leads.origen/id_anuncio/ctwa_clid` | Último anuncio de los últimos `leads.dias_atribucion` días |
| Reporte de orígenes | `GET /anuncios`, `/anuncios/resumen` | Conversaciones y ventas por anuncio (sin gasto) |
| Aviso de ventas a Meta | `eventos_meta`, `jobs/eventos_meta` (ADR-016) | Envía `Purchase` con el `ctwa_clid`; **apagado** |
| Auto-pausa por agotado | `productos_bot/sincronizacion.py` | Pausa el **producto** (no el anuncio) y avisa por Telegram |
| Vigía de stock | `jobs/stock_watcher` | Solo escribe «considerar pausar campañas» en el log |

## 3. Huecos encontrados

### A. Lo que Victoria sabe del anuncio

| # | Hueco | Consecuencia |
|---|---|---|
| H1 | Un anuncio solo se vincula a **un producto**; no existe el concepto de **oferta** (combo, precio promocional, 2×1, regalo, envío gratis). Victoria tiene **prohibido** ofrecer descuentos (pendiente #57) | Un anuncio de combo o promo se vende mal o a otro precio: cliente molesto o venta perdida |
| H2 | Un lead guarda **un** `producto_sku` + `cantidad`; el total es siempre `precio × cantidad` (`tools.py::_calcular_total`) | No hay forma de registrar «A + B por $25». (Rocketfy y `ventas_lineas` sí aceptan varias líneas) |
| H3 | El vínculo se hace **después** de que llega el primer cliente (el id del anuncio se conoce por el `referral`) | Los primeros clientes de cada anuncio nuevo hablan con una Victoria que no sabe qué se anunció |
| H4 | Victoria no ve **el texto del anuncio** que vio el cliente (título y texto sí se guardan) | Si el anuncio promete algo («envío gratis»), Victoria no lo sabe |
| H5 | Si el cliente ya tiene un lead abierto con el producto A y vuelve por el anuncio del producto B, manda el producto del lead | Victoria insiste con A |
| H6 | El precio del anuncio queda «impreso» en Meta, el del catálogo puede cambiar | Anuncio dice $20, Victoria cobra $22 |

### B. Medición

| # | Hueco | Consecuencia |
|---|---|---|
| H7 | No se trae el **gasto** de Meta | No hay costo por venta, ROAS ni ganancia neta por anuncio |
| H8 | La app «AzoShop Bot» solo tiene el caso de uso de WhatsApp; **no tiene la API de Marketing** (verificado con el conector el 2026-11-16) | El servidor no puede leer resultados ni pausar anuncios. Además, la guía oficial de la API de Conversiones para WhatsApp pide la función «Marketing API Access Tier»: **podría bloquear también el aviso de ventas** (no verificado; se sabrá con la primera prueba) |
| H9 | Ventas sin `ctwa_clid` (Estado de WhatsApp, pendiente #77) no se atribuyen | Meta subestima lo que venden esos anuncios |
| H10 | «Venta» = pedido confirmado; las devoluciones de Rocketfy (`pedidos`) no restan | La ganancia por anuncio sale inflada |
| H11 | El dataset quedó como «Test WhatsApp Business Account Event Data» | Probable cuenta de WhatsApp de **prueba** en `WHATSAPP_WABA_ID` |
| H12 | No se lee la respuesta de Meta (`events_received`) ni las estadísticas del dataset | «Enviado» no garantiza «atribuido» |

### C. Proteger la inversión (objetivo n.º 3 del proyecto)

| # | Hueco | Consecuencia |
|---|---|---|
| H13 | La auto-pausa por agotado pausa el **producto**, no el **anuncio** | Pagas clics de algo que ya no se vende |
| H14 | Stock **bajo** (no cero) solo va al log | Te enteras tarde |
| H15 | Sin alertas de rendimiento: gasto sin ventas, costo por conversación alto, anuncio rechazado por Meta, problema de pago de la cuenta | Se pierde plata sin que nadie lo vea |
| H16 | Sin resumen diario | Hay que entrar a Ads Manager y al panel y cruzar a mano |
| H17 | Una promo vencida sigue con su anuncio encendido | Clientes piden un precio que ya no existe |

## 4. Lo verificado en Meta (2026-11-16)

- **App «AzoShop Bot»** (`2772513596476010`): caso de uso configurado solo `WHATSAPP_BUSINESS_MESSAGING`. Disponibles para
  agregar: `MARKETING_API_ADS_ANALYTICS` (medir) y `MARKETING_API_ADS_MANAGEMENT` (crear, pausar, editar).
- **Permisos:** para manejar **tu propia** cuenta publicitaria bastan `ads_read` y `ads_management` en **acceso estándar** (no
  hace falta revisión de Meta). Fuente: Marketing API › Authorization.
- **Nivel de acceso «Limited» (el que se tiene al agregar el caso de uso):** límites por cuenta publicitaria y por hora:
  lecturas de resultados `600 + 400 × anuncios activos`, cambios `300 + 40 × anuncios activos`. Un trabajo que lee una vez
  por hora usa unos pocos puntos: **alcanza de sobra**. Solo permite **1 usuario del sistema** (+1 administrador): conviene
  **un solo token** para todo. Meta lo describe como «para desarrollo»; el paso a «Full» es automático al cumplir 500
  llamadas en 15 días con menos de 15 % de errores. Fuente: Marketing API › Rate Limiting.
- **Métricas de anuncios de mensajes** disponibles: gasto, impresiones, clics, `messaging_conversation_started_7d`,
  primeras respuestas, costo por conversación, estado (`effective_status`), presupuesto.
- **Ventas sin clic:** la API de Conversiones acepta el evento con datos del cliente **cifrados (SHA-256)** + `page_id`; Meta
  intenta atribuirlo a un anuncio de **los últimos 7 días** y solo en algunos países. Con `ctwa_clid` esos límites **no**
  aplican (la documentación no da otro tope). Esto actualiza el pendiente #79: el límite `meta.dias_maximos = 7` es nuestro,
  no de Meta.
- **Dataset:** se puede **consultar** con `GET /{WABA}/dataset` (útil para verificar la cuenta correcta).

## 5. Propuesta: el módulo «Anuncios y Meta»

### 5.1 Ofertas (lo que vende cada anuncio) — cierra H1–H6, H17

Una **oferta** es «lo que promete un anuncio»: qué productos, cuántos, a qué precio, hasta cuándo y con qué condiciones.

- **Tabla `ofertas`:** nombre, tipo (simple / combo / promoción), **precio total** (`numeric`, nunca `float`), envío incluido
  o no, vigencia (desde/hasta), máximo por cliente, **texto del anuncio** (lo que dice el anuncio, para Victoria),
  condiciones, estado (activa / pausada / vencida).
- **Tabla `oferta_items`:** SKU, variante (opcional), cantidad y el precio asignado a cada línea (para reportes y para el
  pedido de Rocketfy).
- **Tabla `anuncios_ofertas`:** un anuncio → una oferta; una oferta → muchos anuncios. Los vínculos actuales de
  `anuncios_productos` se convierten en ofertas «simples» (mismo producto, precio de catálogo): **nada se rompe**.
- **Reglas que pone el código, nunca la IA:**
  - Al guardar la oferta se valida el **piso de margen**: precio ≥ costo de todos los ítems + envío + margen mínimo. Si no
    llega, no se guarda (o pide confirmación explícita del dueño).
  - El total lo calcula el código desde la oferta. Victoria **no negocia** ni rebaja.
  - Un combo no puede mezclar productos de Rocketfy con productos propios (son dos caminos de cierre distintos).
  - Antes de cerrar se revisa stock de **cada** ítem, que la oferta siga activa y vigente, y que el precio no cambió.
- **Victoria:** recibe la **ficha de la oferta** (qué incluye, precio exacto, condiciones, vigencia y el texto del anuncio que
  vio el cliente). Nueva herramienta `registrar_oferta` (o `registrar_producto` con oferta). Si la oferta venció, lo dice con
  naturalidad y ofrece el precio normal (o pasa al dueño; parámetro). Si el cliente pide otra cosa, sigue el flujo normal
  del catálogo.
- **Lead y venta:** el lead guarda `oferta_id` y sus líneas; el pedido de Rocketfy se crea con **varias líneas** y un solo total;
  `ventas` y `ventas_lineas` guardan la foto con la oferta.
- **Cliente que vuelve por otro anuncio (H5):** si llega por un anuncio de **otra** oferta y su lead abierto aún no tiene datos
  de cierre, el lead cambia a la oferta nueva; si ya estaba a punto de cerrar, Victoria pregunta cuál quiere.
- **Pantalla «Ofertas»** (dentro de Anuncios): crear, editar, pausar, duplicar; ver margen calculado al escribir el precio;
  vincular anuncios; probar con Victoria (la simulación que ya existe).

**Lo que tendrías que llenar tú:** por cada anuncio, su oferta (productos, cantidades, precio, vigencia, condiciones y el
texto del anuncio). Si la oferta es «un producto a precio normal», basta con elegir el producto.

### 5.2 Conexión con la API de Marketing (lectura) — cierra H3, H7, H8

- **En Meta (una vez):** agregar a la app el caso de uso de Marketing; regenerar el token del usuario del sistema con
  `ads_read` + `ads_management` (además de los de WhatsApp) y asignarle la cuenta publicitaria `1445728047079452`. Un solo
  token (límite de 1 usuario del sistema). Se guarda en Railway, nunca en el chat.
- **Trabajo `jobs/meta_anuncios`** (cada 60 min, parámetro): copia campañas, conjuntos y anuncios (nombre, estado, presupuesto,
  título, texto, miniatura) a `meta_anuncios`, y los resultados del día por anuncio a `meta_metricas_diarias` (gasto,
  impresiones, clics, conversaciones iniciadas, costo por conversación). Dinero como `numeric`.
- **Vincular antes de publicar:** como el sistema ya conoce tus anuncios (aunque estén en revisión o sin clientes), puedes
  asignarles la oferta desde una lista con su miniatura. Así Victoria sabe qué vender **desde el primer cliente**.
- Si Meta falla, no pasa nada con las ventas: es solo lectura y se reintenta en la siguiente pasada.

### 5.3 Tablero de rendimiento — cierra H10, H12, H16

Por anuncio, campaña y oferta, en un periodo:

| Dato | De dónde |
|---|---|
| Gasto, conversaciones según Meta | `meta_metricas_diarias` |
| Conversaciones que llegaron, leads, ventas confirmadas | Nuestra base |
| Entregadas, devueltas, canceladas | `pedidos` (Rocketfy) y `ventas` |
| Ingreso, costo de productos y envío | `ventas` (foto congelada) |
| **Costo por venta, tasa de cierre, ganancia neta, ROAS** | Calculado (`Decimal`) |

Además: comparación «conversaciones según Meta» vs «las que llegaron» (detecta clics perdidos), estado del aviso de ventas
(enviados vs atribuidos según el dataset) y un **resumen diario por Telegram** (interruptor; apagado de fábrica).

### 5.4 Alertas y reglas automáticas — cierra H13–H15, H17

Primero **solo avisar** (Telegram + Incidencias). Las que pausan, con interruptor propio, **apagadas de fábrica**.

| Regla | Qué detecta | Acción |
|---|---|---|
| R1 | Producto u oferta agotado o pausado con anuncios activos | Avisar → (opcional) **pausar esos anuncios** |
| R2 | Oferta vencida con anuncios activos | Avisar → (opcional) pausar |
| R3 | Stock bajo (umbral) en un producto con anuncios activos | Avisar antes de que se agote |
| R4 | Anuncio gastó más de X sin ninguna venta | Avisar |
| R5 | Costo por conversación sobre el umbral (tras N conversaciones) | Avisar |
| R6 | Costo por venta mayor que la ganancia por venta | Avisar |
| R7 | Anuncio activo sin oferta vinculada | Avisar (Victoria no sabría qué vender) |
| R8 | Anuncio rechazado o con problemas, cuenta con problema de pago | Avisar |

**Reglas de seguridad:** las decide el **código** con umbrales que tú fijas (parámetros), nunca la IA; el sistema puede
**pausar**, pero **nunca reactiva**, **nunca cambia presupuestos** y **nunca crea anuncios**; cada acción queda en un
historial (`meta_acciones`: qué, por qué, cuándo, resultado); una respuesta ambigua de Meta no se reintenta a ciegas (se lee
el estado primero); tope de acciones por día.

### 5.5 Fuera de alcance (a propósito)

- **Crear anuncios desde la app:** Ads Manager lo hace mejor. Si un día lo quieres, yo puedo crearlos con el conector de Meta,
  con tu confirmación en cada paso.
- Cambiar presupuestos o pujas automáticamente.
- TikTok (la estructura queda lista para sumarlo).

## 6. Fases

| Fase | Qué | Quién | Depende de |
|---|---|---|---|
| **F0** | Corregir `WHATSAPP_WABA_ID` y repetir «Preparar Meta»; agregar caso de uso de Marketing a la app; token con permisos de anuncios; asignar la cuenta publicitaria | Freddy + Claude (yo puedo agregar el caso de uso con tu confirmación) | — |
| **F1** | **Ofertas y combos**: migración, validación de margen, Victoria, pedido con varias líneas, pantalla, simulación, tests | Claude | Tus decisiones D1–D2 |
| **F2** | Sincronizar Meta (lectura) + vincular anuncios desde la lista | Claude | F0 |
| **F3** | Tablero de rendimiento + resumen diario | Claude | F2 |
| **F4** | Alertas R1–R8 en modo «solo avisar» | Claude | F2 (R1–R3 y R7 parcialmente sin F2) |
| **F5** | Pausa automática (R1, R2) con interruptor apagado | Claude | F4 probada 2 semanas |
| **F6** | (Opcional) Atribuir ventas sin clic con teléfono cifrado; avisar la compra al **entregar** en vez de al confirmar | Claude | Datos reales (#77, #79) y decisión D4 |

F1 no depende de Meta: puede empezar ya. Cada fase se entrega con tests, documentación y despliegue (migración primero).

## 7. Decisiones que necesito de Freddy

| # | Decisión | Mi recomendación |
|---|---|---|
| D1 | ¿Se permiten combos y promociones? | **Sí**, como precio fijo por oferta, validado contra el piso de margen. Victoria no regatea |
| D2 | Cuando una oferta vence y llega un cliente | Victoria dice que terminó y ofrece el precio normal |
| D3 | ¿Pausar anuncios solos? | Empezar **solo avisando** 2 semanas; luego encender solo la pausa por agotado |
| D4 | ¿Enviar el teléfono cifrado a Meta para ventas sin clic? | **No por ahora**: primero medir cuántas ventas llegan sin clic (#77) |
| D5 | Un solo token para WhatsApp, ventas y anuncios | **Sí** (el nivel actual solo permite 1 usuario del sistema) |
| D6 | Umbrales de las alertas (gasto sin venta, costo por conversación) | Definirlos con los números del piloto; quedan como parámetros |

## 8. Riesgos

- **Pausar por error un anuncio que sí vende** → empieza apagado, solo pausa por hechos (stock 0, oferta vencida), nunca por
  rendimiento, y nunca reactiva solo.
- **El token con más permisos es más delicado** → solo en Railway; rotarlo si se expone.
- **Datos de Meta con retraso** (los resultados del día se ajustan horas después) → el tablero muestra la hora de la última
  lectura y las alertas de rendimiento usan días cerrados.
- **Combos y Rocketfy:** un pedido con varias líneas no se ha probado contra Rocketfy real → probar con un pedido de prueba
  antes de publicar el primer combo.

## 9. Pendientes que crea este plan

- **#81** este módulo (fases F0–F6).
- Actualiza **#57** (descuentos/combos → se resuelve con F1), **#79** (el tope de 7 días es nuestro), **#77** (camino
  alterno con datos cifrados).
