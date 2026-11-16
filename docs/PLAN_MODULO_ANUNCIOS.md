# Plan: precios, ofertas y anuncios (módulo «Ventas y Meta»)

> Versión 2.0 — 2026-11-16. Pedidos de Freddy del 2026-11-16: (1) que no haya huecos de venta ni de gestión entre anuncios,
> Victoria y ventas; (2) **control completo por producto**: descuentos (por porcentaje o valor fijo), **regateo con límites**,
> envío gratis, **precio distinto por transferencia**, combos, «si llevo 2…», varios productos en un pedido, ofertas con
> fechas; (3) sin romper lo que ya funciona; luz verde para cambiar base, lógica y flujos.
> Análisis hecho leyendo el código, la base, los permisos reales de la app en Meta (conector Devtools) y la documentación
> oficial de Meta (leída el 2026-11-16). **Nada de este plan está construido todavía.** Pendiente #81.

## 1. Para qué sirve (en llano)

Hoy Victoria vende **un producto a precio fijo de catálogo**, y eso funciona. Pero un negocio real necesita más:

- Anunciar un **combo** («linterna + cargador por $25») o una **promo** con fecha de fin.
- Dejar que Victoria **regatee** dentro de un límite que tú pones («de este producto puede bajar hasta $10»).
- Premiar el pago por **transferencia** («$25 contra entrega, $20 si transfieres»).
- Que el cliente pida **dos productos distintos** en el mismo pedido, o «si llevo 2, ¿a cuánto?».
- Saber **cuánto gastas** en cada anuncio y **que el sistema te avise** (o pause) cuando algo pierde plata.

La idea central: **tú pones las reglas, el código calcula los precios, Victoria solo conversa.** La IA nunca inventa un precio,
y nunca puede bajar de tu precio mínimo, por mucho que el cliente insista.

## 2. Problema urgente encontrado (arreglar primero)

**Un pedido pagado por transferencia se crea en Rocketfy como contra entrega por el total.** En `tools.py::_handle_cerrar_venta`
el pedido siempre se arma con `no_contra_entrega=False` (`not_COD = 0`), aunque el dueño ya haya confirmado el pago. Según la
documentación de Rocketfy, `not_COD = 1` significa «el pedido ya está pagado». **Consecuencia:** el repartidor le cobraría al
cliente **otra vez** el total. Las 4 cuentas para transferir ya están cargadas y Victoria ya ofrece transferencia, así que
puede pasar con la primera venta por transferencia.

**Arreglo propuesto (F0a):** si `metodo_pago = transferencia` y el pago está confirmado, el pedido va con
`no_contra_entrega = True`. No se ha probado con un pedido real de Rocketfy: hay que verificarlo con un pedido de prueba
(crearlo y rechazarlo) antes de la primera venta real por transferencia.

## 3. Lo que ya existe (se conserva)

| Pieza | Qué hace hoy |
|---|---|
| Producto (`productos_bot`) | Precio, variantes, métodos de pago aceptados, envío incluido o aparte (`producto_entregas`), máximo de unidades, stock |
| Total | Lo calcula el código: precio × cantidad (+ envío elegido). Victoria nunca lo fija |
| Piso de margen | `ajustes_negocio.margen_minimo_pct`, calculadora de precios (`productos_bot/calculadora.py`) |
| Pago | Contra entrega o transferencia; cuentas desde `cuentas_bancarias`; el dueño confirma el comprobante |
| Anuncios | Llegadas guardadas, vínculo anuncio → **un** producto, aviso de anuncio nuevo, aviso de ventas a Meta (apagado) |
| Stock | Auto-pausa por agotado (pausa el **producto**) y alerta de margen en riesgo |

## 4. Huecos encontrados

### A. Precios y forma de vender

| # | Hueco |
|---|---|
| H0 | **Transferencia enviada como contra entrega** (ver §2) |
| H1 | Un lead guarda **un** producto; no se puede vender «A + B» ni un producto de otra publicación en el mismo pedido |
| H2 | No existen descuentos: Victoria tiene **prohibido** ofrecerlos (instrucciones y pendiente #57); no hay regateo |
| H3 | No hay precio por cantidad («2 por $45») ni envío gratis condicionado |
| H4 | No hay precio distinto por método de pago (incentivo a transferencia) |
| H5 | No hay ofertas con **fechas**, cupo ni condiciones |
| H6 | La venta no guarda **cuánto descuento** se dio ni por qué: no se puede medir si el regateo conviene |

### B. Anuncios

| # | Hueco |
|---|---|
| H7 | Un anuncio solo se vincula a **un producto** a precio de catálogo |
| H8 | Victoria no ve **el texto del anuncio** que vio el cliente |
| H9 | El vínculo se hace **después** de que llega el primer cliente |
| H10 | Si el cliente tiene un lead abierto con A y vuelve por el anuncio de B, se queda en A |
| H11 | Precio del anuncio ≠ precio del catálogo si este cambia |

### C. Medición

| # | Hueco |
|---|---|
| H12 | No se trae el **gasto** de Meta: no hay costo por venta ni ganancia neta por anuncio |
| H13 | La app «AzoShop Bot» **no tiene la API de Marketing** (solo WhatsApp; verificado el 2026-11-16). La guía de la API de Conversiones para WhatsApp pide además «Marketing API Access Tier»: **podría bloquear el aviso de ventas** (no verificado) |
| H14 | Ventas sin `ctwa_clid` (Estado de WhatsApp, #77) no se atribuyen |
| H15 | Las devoluciones de Rocketfy no restan en los reportes |
| H16 | Dataset llamado «Test WhatsApp Business Account Event Data»: probable `WHATSAPP_WABA_ID` de prueba |

### D. Proteger la inversión

| # | Hueco |
|---|---|
| H17 | La auto-pausa por agotado no pausa **el anuncio** |
| H18 | Stock bajo solo va al log |
| H19 | Sin alertas de gasto sin ventas, costo alto, anuncio rechazado, problema de pago |
| H20 | Ofertas vencidas con anuncio encendido |
| H21 | Sin resumen diario |

## 5. Diseño: el motor de precios

### 5.1 Tres niveles de reglas (del más general al más específico)

| Nivel | Dónde lo controlas | Ejemplos |
|---|---|---|
| **1. Negocio** (valores por defecto) | Ajustes | Margen mínimo (ya existe); descuento por transferencia por defecto; regateo apagado por defecto |
| **2. Producto** | Ficha del producto → «Precios y descuentos» | Precio contra entrega; precio o descuento por transferencia; regateo hasta X % o $X; precios por cantidad; envío gratis desde N unidades o $X |
| **3. Oferta** (promoción o combo) | Pantalla «Ofertas» | Productos y cantidades, precio total, fechas, cupo, quién la ve, si permite regateo y descuento por transferencia |

Lo más específico manda: una oferta pisa al producto, y el producto pisa los valores del negocio. **Encima de todo está el piso:**
ningún descuento, regateo ni oferta puede dejar la venta por debajo de tu **precio mínimo** (costo + envío + margen mínimo,
calculado por el código con la calculadora que ya existe). El panel te muestra ese mínimo en dólares al lado de cada precio.

Todo viene **apagado**: sin reglas nuevas, el sistema vende exactamente como hoy.

### 5.2 Reglas por producto («Precios y descuentos»)

| Control | Cómo se configura | Ejemplo |
|---|---|---|
| Precio por transferencia | Precio fijo **o** descuento (% o $) | Contra entrega $25, transferencia $20 |
| Regateo | Interruptor + límite en % **o** en $ por unidad | Producto de $50 puede bajar hasta $10 → nunca menos de $40 |
| Cómo regatea Victoria | «Acepta lo que pida si está dentro del límite» **o** «Contraoferta primero» | Pide $45: acepta, o contraoferta $48 |
| Precio por cantidad | Tabla de escalas | 1 = $25, 2 = $45, 3 = $60 |
| Envío gratis | Desde N unidades o desde $X (productos con envío aparte) | Envío gratis desde 2 unidades |
| ¿Se suman? | Si el regateo se acumula con el precio por transferencia | Por defecto **no**: se aplica el mejor para el cliente, nunca los dos |
| Ofrecerlo por iniciativa propia | Si Victoria menciona sola el precio por transferencia o la escala | «Si transfiere le queda en $20» |

### 5.3 Ofertas (combos y promociones)

Una **oferta** es «lo que promete un anuncio o una campaña»:

- **Qué incluye:** uno o varios productos con cantidades y variante, opcional. Ejemplos: «A + B», «2 × A», «A + regalo C».
- **Precio total** (`numeric`) y si el envío va incluido.
- **Fechas:** desde y hasta, con hora. Fuera de fecha la oferta no existe para Victoria.
- **Cupo:** máximo de ventas de la oferta (por ejemplo, las primeras 30) y máximo por cliente.
- **Quién la ve:**
  - **Solo quien llega por sus anuncios** (por defecto).
  - **Cualquier cliente**, para que Victoria pueda ofrecerla.
- **Permisos dentro de la oferta:** ¿permite regateo? ¿se le aplica el precio por transferencia?
- **Texto del anuncio y condiciones:** lo que el cliente vio. Victoria lo recibe tal cual.
- **Al vencer o agotarse:** Victoria explica con naturalidad que terminó y ofrece el precio normal (configurable: o pasa al dueño).

Al guardar, el código valida el piso: si el precio de la oferta queda bajo tu mínimo, te lo dice. Puedes guardarla igual,
pero solo marcando a propósito «vender bajo el margen», porque a veces se pierde en una oferta para ganar clientes.

### 5.4 La cotización (la fuente de verdad del precio)

Cada vez que algo cambia en el pedido (productos, cantidades, oferta, método de pago, entrega o regateo), el código arma una
**cotización**:

```
Linterna LED × 2  (escala «2 por $45»)        $45,00
Cargador × 1                                   $12,00
Regateo aceptado                               −$2,00
Envío (gratis desde 2 unidades)                 $0,00
Total contra entrega                           $55,00
Total si transfiere                            $50,00
Precio mínimo permitido (no se muestra al cliente) $48,00
```

Victoria recibe la cotización y comunica **ese** total. El código la guarda en el lead, para que el comprobante de pago se compare
con el total correcto. También la guarda en la venta (`ventas` y `ventas_lineas`) con cada descuento y su motivo (oferta,
escala, transferencia, regateo), para que el reporte diga cuánto margen se fue en descuentos y si valió la pena.

### 5.5 El regateo, paso a paso (ejemplo de Freddy)

Producto de $50 con regateo hasta $10 (mínimo $40):

1. El cliente dice «¿me lo deja en $45?». Victoria usa la herramienta `negociar_precio(45)`. **El código decide**, no ella.
2. Con «acepta si está dentro del límite»: el código acepta $45, actualiza la cotización y Victoria confirma.
3. Con «contraoferta primero»: el código propone el punto medio, $47,50, redondeado a **$48** (redondeo configurable). Si el
   cliente insiste en $45, el código acepta, porque está dentro del límite.
4. El cliente pide $35: el código responde «el mínimo que puedes ofrecer es $40». Victoria nunca ve tu precio mínimo real si no
   hace falta, y no puede pasarlo aunque lo intente.
5. Número de rondas y redondeo: parámetros. Cada paso queda en el historial del lead.

### 5.6 Varios productos en un pedido («carrito»)

- Nueva tabla `lead_items`: producto, variante, cantidad, precio y la oferta de la que viene. El lead conserva sus campos actuales
  (`producto_sku`, `cantidad`, `total`) como **resumen**, para que reportes, seguimiento y pantallas que ya existen sigan
  funcionando sin cambios.
- Victoria puede **agregar** («y también quiero el de la otra publicación»), **cambiar** y **quitar** productos. El código valida
  stock, máximo de unidades y que el producto esté activo, **por cada línea**.
- Rocketfy recibe un pedido con **varias líneas** y un solo total. El contrato ya lo permite, pero no se ha probado con un pedido
  real: hay que verificarlo antes.
- **Mezclas no permitidas en el mismo pedido:** productos de Rocketfy con productos propios, porque se despachan por caminos
  distintos. Victoria lo explica y pasa al dueño; más adelante podrían ser dos pedidos.

### 5.7 Qué cambia para Victoria

- Recibe: la cotización, la oferta del anuncio (con su texto) y las reglas que **puede** ofrecer (escalas y transferencia).
  No recibe tu precio mínimo.
- Herramientas nuevas o cambiadas:
  - `registrar_producto`: agrega o cambia una línea.
  - `quitar_producto`.
  - `aplicar_oferta`.
  - `negociar_precio`.
  - `registrar_metodo_pago`: ahora recalcula el total.
- Sus instrucciones cambian de «nunca ofrezcas descuentos» a «solo los que te da la cotización o `negociar_precio`; nunca
  inventes uno».
- Todo se prueba en «Probar con Victoria» (la simulación que ya existe) antes de encenderlo.

## 6. Diseño: anuncios y Meta

### 6.1 Vínculo anuncio → oferta

`anuncios_ofertas`: un anuncio apunta a una oferta. Una oferta simple es «un producto a su precio normal». Los vínculos de hoy
(`anuncios_productos`) se convierten en ofertas simples, así que nada se rompe. Si un cliente que tiene un lead abierto llega por
el anuncio de **otra** oferta y todavía no dio sus datos de cierre, el lead pasa a la oferta nueva. Si ya estaba cerrando,
Victoria le pregunta qué prefiere.

### 6.2 Lectura de Meta (requiere F0 en Meta)

- **En Meta, una vez:**
  - Agregar a la app el caso de uso de Marketing.
  - Regenerar el token del usuario del sistema con `ads_read` + `ads_management`, además de los de WhatsApp. Debe ser **un
    solo token**: el nivel sin revisión permite un solo usuario del sistema.
  - Asignarle la cuenta publicitaria `1445728047079452`.
  - Para tu propia cuenta basta el acceso estándar, sin revisión de Meta. Sus límites (por cuenta y hora: lecturas
    600 + 400 × anuncios activos) sobran para leer una vez por hora.
- **Trabajo `jobs/meta_anuncios`** (cada hora):
  - Copia campañas, conjuntos y anuncios (nombre, estado, presupuesto, título, texto y miniatura).
  - Guarda el gasto diario y las conversaciones iniciadas por anuncio.
- **Vincular antes de publicar:** eliges la oferta de cada anuncio desde una lista con su miniatura. Así Victoria sabe qué vender
  **desde el primer cliente**.

### 6.3 Tablero

Se ve por anuncio, por oferta y por producto:
- **Gasto:** el que reporta Meta.
- **Embudo:** conversaciones, leads, ventas, entregadas y devueltas.
- **Plata:** ingreso, **descuentos dados por motivo**, costo, costo por venta, **ganancia neta** y ROAS.
- **Control:** conversaciones según Meta comparadas con las que llegaron (para detectar clics perdidos).
- **Resumen diario por Telegram:** con interruptor, apagado de fábrica.

### 6.4 Alertas y acciones automáticas

Al principio **solo avisan**. Pausar el anuncio es un interruptor aparte, apagado de fábrica.

| Regla | Qué detecta |
|---|---|
| R1 | Producto u oferta agotado o pausado, con anuncios activos (→ opcional: pausar esos anuncios) |
| R2 | Oferta vencida o sin cupo, con anuncios activos (→ opcional: pausar) |
| R3 | Stock bajo en un producto con anuncios activos |
| R4 | Anuncio que gastó más de $X sin ventas |
| R5 | Costo por conversación sobre el umbral |
| R6 | Costo por venta mayor que la ganancia por venta (incluye descuentos) |
| R7 | Anuncio activo sin oferta vinculada |
| R8 | Anuncio rechazado o con problemas, o problema de pago de la cuenta |
| R9 | Regateo: demasiadas ventas cerrando en el precio mínimo |

Reglas de seguridad:
- Las decide el **código** con tus umbrales (parámetros).
- Nunca reactiva un anuncio, nunca cambia presupuestos y nunca crea anuncios.
- Cada acción queda en un historial (`meta_acciones`).
- Una respuesta dudosa de Meta no se reintenta a ciegas.

### 6.5 Lo verificado en la documentación de Meta (2026-11-16)

- La app «AzoShop Bot» (`2772513596476010`) solo tiene el caso de uso de WhatsApp. Se puede agregar
  `MARKETING_API_ADS_ANALYTICS` (medir) o `MARKETING_API_ADS_MANAGEMENT` (gestionar).
- Para tu propia cuenta publicitaria bastan `ads_read`/`ads_management` en acceso estándar. El nivel «Limited» permite 1 usuario
  del sistema. El paso a «Full» llega al cumplir 500 llamadas en 15 días con menos del 15 % de errores.
- Con `ctwa_clid`, la documentación no fija un tope de días para el evento (actualiza #79: el `meta.dias_maximos = 7` es nuestro).
  Sin clic se puede atribuir con datos del cliente cifrados (SHA-256) + `page_id`, pero solo 7 días y solo en algunos países
  (opción para #77).
- `GET /{WABA}/dataset` permite consultar el dataset (sirve para verificar la cuenta correcta).

## 7. Cómo no romper lo que funciona

- Migraciones **solo aditivas** (tablas y columnas nuevas). Ninguna migración aplicada se edita.
- Sin reglas configuradas, la cotización da **exactamente** el mismo total que hoy. Un test lo compara caso por caso con el
  cálculo actual antes de cambiar nada.
- El lead conserva sus campos actuales como resumen. Lo que hoy los lee sigue igual.
- Cada capacidad nueva tiene su interruptor. Se enciende producto por producto.
- Se prueba en la simulación y con un pedido real de prueba en Rocketfy (crear y rechazar) antes de usarlo con clientes.

## 8. Fases

| Fase | Qué | Depende de |
|---|---|---|
| **F0a** | **Arreglo urgente:** transferencia confirmada → pedido prepagado en Rocketfy (`not_COD = 1`) + prueba con pedido de prueba | Tu confirmación |
| **F0b** | Meta: corregir `WHATSAPP_WABA_ID` y repetir «Preparar Meta»; agregar el caso de uso de Marketing; token único; asignar la cuenta publicitaria | Tú + yo (te pido confirmación en cada cambio de Meta) |
| **F1** | Motor de precios y cotización: `lead_items`, cotización con `Decimal`, guardada en lead y venta. **Sin cambios visibles**: mismos totales que hoy | — |
| **F2** | Reglas por producto: precio por transferencia, escalas, envío gratis, regateo con `negociar_precio` + sección «Precios y descuentos» + simulación | F1, decisiones P1–P4 |
| **F3** | Varios productos en un pedido + pedido de Rocketfy con varias líneas (probado con pedido de prueba) | F1 |
| **F4** | Ofertas (combos, promos, fechas, cupo, visibilidad) + vínculo anuncio → oferta + Victoria con el texto del anuncio | F2, F3 |
| **F5** | Lectura de Meta + vincular anuncios desde la lista | F0b |
| **F6** | Tablero (con descuentos) + resumen diario | F4, F5 |
| **F7** | Alertas R1–R9 (solo avisar) | F5 |
| **F8** | Pausa automática (R1, R2) con interruptor apagado | F7 probada 2 semanas |
| **F9** | Opcionales: atribuir ventas sin clic con datos cifrados; avisar la compra a Meta al **entregar** | Datos reales (#77, #79) |

Cada fase se entrega con tests, documentación, revisión de pantalla (móvil, accesibilidad) y despliegue (migración primero).

## 9. Decisiones (APROBADAS por Freddy el 2026-11-16: todas las recomendaciones)

> Las reglas quedan registradas como **ADR-017** en `PROGRESS.md` (sección 2), con su porqué. Para cambiar una regla, empezar ahí.

| # | Decisión | Lo decidido |
|---|---|---|
| P1 | Cómo regatea Victoria por defecto | **Contraoferta una vez** (punto medio) y luego acepta lo que pida si está dentro del límite |
| P2 | ¿Se suman regateo y precio por transferencia? | **No**: se aplica el mejor para el cliente |
| P3 | ¿Victoria menciona sola el precio por transferencia? | **Sí**, cuando se habla del pago (para eso existe el incentivo) |
| P4 | ¿Victoria menciona sola el precio por cantidad? | **Sí**, una vez, cuando el cliente ya eligió producto |
| P5 | Pedido que mezcla Rocketfy y producto propio | **No** en el mismo pedido; pasa al dueño |
| P6 | Ofertas: ¿quién las ve? | Por defecto **solo quien llega por su anuncio** |
| P7 | ¿Combos con regateo? | Por defecto **no** (el combo ya es el descuento) |
| D3 | ¿Pausar anuncios solos? | 2 semanas solo avisando; después encender la pausa por agotado |
| D4 | ¿Enviar el teléfono cifrado a Meta para ventas sin clic? | Todavía no; primero medir (#77) |
| D5 | ¿Un solo token de Meta? | Sí |
| D6 | Umbrales de alertas | Con los números del piloto |

## 10. Riesgos

- **Regalar margen:** el piso de margen lo aplica el código en cada cotización, y el reporte de descuentos (R9) muestra si el
  regateo está comiendo la ganancia.
- **Pedido con varias líneas o prepagado mal entendido por Rocketfy:** se prueba con pedidos de prueba antes de usarlo.
- **Victoria confundida con muchas reglas:** recibe solo la cotización y lo que puede ofrecer, no todas las reglas. Cada cambio se
  prueba en la simulación con conversaciones de regateo y de combos.
- **Pausar un anuncio que sí vende:** la pausa viene apagada, solo actúa por hechos (stock 0, oferta vencida) y nunca reactiva sola.
- **Token con más permisos:** solo en Railway; rotarlo si se expone.

## 11. Pendientes que crea o cambia este plan

- **#81** este módulo (F0a–F9).
- **#57** (descuentos y combos): se resuelve con F2 y F4.
- **#77** (sin clic) y **#79** (7 días): actualizados con la documentación (§6.5).
