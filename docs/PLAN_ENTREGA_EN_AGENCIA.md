# Plan: entrega en agencia de Servientrega («retiro en oficina»)

> Versión 1.0 — 2026-11-16. Pedido de Freddy: que Victoria recomiende enviar el pedido a una **agencia de Servientrega** donde el
> cliente retire con seguridad y a su hora, en vez de a su casa (direcciones difíciles, nadie en casa). Si el cliente prefiere su casa,
> se sigue el flujo de siempre. Regla de oro: **Victoria no inventa agencias ni datos; si algo no lo puede controlar, pasa a GESTIÓN.**
> **Versión 1 construida el 2026-11-16 (entrada 0.0.140, ADR-018), sin desplegar.** Pendientes #83, #84 y #85.
>
> **Decisión de Freddy (2026-11-16):** se hace primero la **versión 1** (§0): Victoria ofrece la agencia, y si el cliente la quiere,
> el dueño define la agencia en GESTIÓN. El catálogo automático de agencias (§3 en adelante) queda como **versión 2**, para el futuro.

## 0. Versión 1: Victoria ofrece la agencia y el dueño la define

**Revisión del flujo actual (2026-11-16):**

| Qué | Cómo está hoy | Hueco |
|---|---|---|
| Datos que pide Victoria | nombre, dirección, cantón, provincia (+ producto, entrega, pago). El teléfono sale de WhatsApp | **No pide referencia** («frente a…», «casa esquinera») |
| Datos que recibe Rocketfy | todos los obligatorios (`name`, `phone`, `address`, `city`, `province`, `total`, `order_details`) | `address_2` (referencia) y `carrier_observations` (indicaciones al repartidor) van **vacíos**; las coordenadas de una ubicación 📍 no se mandan (Victoria la pega como texto en la dirección) |
| Pasar a una persona | `escalar_a_humano` → estado «escalada» + Telegram; Victoria se despide | El motivo es texto libre; no hay un aviso claro de «falta la agencia» |
| Lo que hace el dueño en el panel | Escribe al cliente, «Tomar la conversación», «Que Victoria continúe» (con nota y confirmar pago) | **No puede corregir la dirección del pedido**: los datos de envío se ven pero no se editan. Solo podría dictárselos a Victoria en la nota (ella los copiaría: riesgo de error) |
| Botón «Crear pedido» de la conversación | Abre el formulario manual con los datos | **Riesgo de pedido duplicado:** ese pedido no queda unido al lead; si después se devuelve la conversación a Victoria, ella podría crear otro |
| Estado 23 de Rocketfy «Recogida en Agencia» | Llega por el webhook y se guarda como cualquier estado | Nadie se entera de que un paquete espera retiro (si no lo retiran, vuelve y se pierde el flete) |

**Flujo propuesto (versión 1):**

1. **Victoria ofrece la agencia una sola vez**, cuando ya sabe la ciudad (texto editable como parámetro, interruptor **apagado** de fábrica;
   solo para productos que van por Rocketfy).
2. **Prefiere su casa** → flujo de siempre, y ahora Victoria **pide también una referencia** (va a `address_2`).
3. **Quiere agencia** (lo diga como lo diga: «sí, por el centro», «la de Urdesa», manda un enlace, una foto o su ubicación) → Victoria
   anota «entrega en agencia» y **lo que dijo el cliente, tal cual**, sin confirmar ninguna agencia ni prometer nada. **Sigue tomando el
   resto** (producto, nombre, ciudad, provincia, forma de pago).
4. **Cuando ya tiene todo lo demás**, el **código** (no Victoria) pasa la conversación a gestión: estado «escalada», aviso por Telegram
   «Falta definir la agencia de retiro — el cliente dijo: «…»». Victoria le dice al cliente que en un momento le confirman la agencia exacta.
5. **Tú en el panel:** ves un aviso «Falta definir la agencia» con lo que dijo el cliente. Conversas con él si hace falta. En una tarjeta
   nueva **«Datos de envío»** (editable) escribes la dirección de la agencia, la referencia y las indicaciones para el repartidor (viene
   propuesta: «RETIRO EN AGENCIA SERVIENTREGA … — el cliente retira con cédula»). El código valida ciudad y provincia al guardar.
6. **Pulsas «Que Victoria continúe»** (ya existe) → Victoria le muestra al cliente el **resumen con la agencia**, el cliente confirma y
   ella cierra la venta: el pedido va a Rocketfy con la dirección de la agencia, la referencia y las indicaciones.

**Arreglos que van con la versión 1:**
- Referencia e indicaciones guardadas en el lead y enviadas a Rocketfy; coordenadas de la ubicación 📍 también.
- Si el dueño cambia los datos de envío después de que el cliente confirmó, la confirmación se borra (el cliente vuelve a confirmar).
- El botón «Crear pedido» de la conversación deja el pedido **unido al lead**, y Victoria no puede crear otro (evita duplicados).
- Aviso por Telegram cuando Rocketfy marca un pedido como **«Recogida en Agencia»** (estado 23), para recordarle al cliente que lo retire.

**Antes de usarlo con clientes:** un pedido de prueba con la dirección de una agencia y la indicación de retiro, y preguntar a Rocketfy si
así basta (B1) y si cambia el precio (B2).


## 1. Para qué sirve (en llano)

Muchas entregas fallan porque la dirección es difícil de encontrar o el cliente no está cuando llega el repartidor. Si el paquete va a
una agencia, el cliente lo retira cuando puede, con su cédula, y la entrega casi nunca falla. Menos devoluciones = menos fletes perdidos.

## 2. Lo que averigüé (y lo que NO se pudo confirmar)

| Fuente | Qué dice | Consecuencia |
|---|---|---|
| Documentación de la API de Rocketfy (`docs/Rocketfy-API-Integracion-Sistemas-Propios.md`) | El pedido solo tiene `address`, `address_2` (referencia), `carrier_observations` (indicaciones al repartidor) y `latitude`/`longitude`. **No hay un campo «retiro en oficina».** `shipping_method` se ignora | No sabemos cómo pedirle a Rocketfy que el paquete se quede en una agencia. **Hay que preguntárselo a Rocketfy (bloqueante B1)** |
| Misma documentación, estados | Existe el estado **23 «Recogida en Agencia» — disponible para retiro en oficina** | Rocketfy/Servientrega sí manejan paquetes que esperan en oficina; falta saber cómo se pide desde el inicio |
| Búsqueda en internet (2026-11-16) | **No encontré una API pública de Servientrega Ecuador** con su lista de agencias. Solo hay datos de segunda mano: para retirar se presenta la **cédula**; un tercero necesita **carta de autorización** y copias de cédulas | La lista de agencias la tenemos que **armar y mantener nosotros** en la base. Los requisitos de retiro, Freddy debe confirmarlos con Servientrega antes de que Victoria los diga |
| Código actual | Victoria guarda solo `direccion`, `canton`, `provincia`. No manda referencia, indicaciones ni coordenadas a Rocketfy | Aunque el cliente prefiera su casa, hay mejoras fáciles (§6) |

Fuentes de la búsqueda (secundarias, no oficiales): documento de trámite de Servicios Postales del Ecuador en gob.ec y una guía no oficial
de Servientrega (elyex.com). Ninguna es de Servientrega Ecuador.

## 3. La idea: un catálogo de agencias propio + herramientas que solo leen de ahí

**Por qué no una API ni que la IA busque:** no hay API pública, y si Victoria «buscara» o recordara agencias, podría inventar una que no
existe o que cerró. Con un catálogo nuestro, Victoria **solo puede ofrecer lo que está cargado y verificado**, igual que con las cuentas
bancarias (el código arma el mensaje, Victoria no escribe las direcciones).

**Tabla nueva `agencias_entrega`** (una fila por agencia):
transportadora (servientrega), provincia, **cantón** (el mismo catálogo de cantones de Rocketfy), nombre («Servientrega Urdesa»), dirección,
**zona/sector y palabras clave** («centro», «norte», «Urdesa», «cerca del Mall del Sol»), referencia, horario, teléfono (opcional),
latitud/longitud (opcional), enlace de Google Maps (opcional, solo para mostrar), **activa**, **verificada el / por**, notas internas.

**Pantalla nueva «Agencias de retiro»** (Control): lista por ciudad, agregar/editar/desactivar, importar un CSV. Así Freddy carga las
agencias de las ciudades donde más vende, y agrega una nueva en un minuto cuando un cliente pide una que no está.

**Herramientas nuevas de Victoria** (el código decide, Victoria conversa):
- `elegir_tipo_entrega(agencia | domicilio)`: guarda lo que eligió el cliente.
- `buscar_agencias(zona)`: el **código** busca en el catálogo, **solo en el cantón ya validado** del pedido, y devuelve hasta 3–5 opciones
  numeradas con nombre, dirección y horario. El mensaje con la lista lo arma el código (Victoria no reescribe direcciones).
- `elegir_agencia(numero o id)`: solo acepta una agencia que el código ofreció en esta conversación; vuelve a comprobar que esté activa.
- Al cerrar: se re-comprueba la agencia (como con las ofertas) y el resumen que confirma el cliente dice «Retiro en: agencia X,
  dirección, horario. Lleve su cédula».

## 4. El flujo en la conversación

1. El cliente da la ciudad («a Guayaquil») → el código valida cantón y provincia (ya existe: Guayaquil, Guayas).
2. **Si hay agencias activas cargadas en ese cantón** y el interruptor está encendido, Victoria recomienda la agencia con el texto que
   Freddy definió (parámetro), por ejemplo: «Le recomiendo que el envío llegue a una agencia de Servientrega, donde puede retirarlo con
   seguridad y a la hora que le quede mejor. ¿Qué zona de Guayaquil le queda más cómoda?».
   **Si no hay agencias cargadas en ese cantón, no se ofrece** (se pide la dirección como hoy): nunca se promete algo que no podemos dar.
3. **Prefiere su casa** («no, mejor a mi casa», «envíeme a domicilio nomás», «prefiero que me lo traigan»): se respeta, una sola
   recomendación y no se insiste. Sigue el flujo de siempre (dirección exacta + referencia, §6).
4. **Acepta la agencia** («sí, mándeme a una por el centro»): `buscar_agencias("centro")` → «Por esa zona tenemos estas agencias:
   1) … 2) … 3) … ¿Cuál le queda mejor?». El cliente responde «la 2», «la de la Av. 9 de Octubre» o el nombre → `elegir_agencia`.
5. Resumen y confirmación de datos (ya existe), con la agencia en vez de la dirección.

## 5. Escenarios difíciles y qué hace cada uno

| # | El cliente… | Qué pasa | Por qué |
|---|---|---|---|
| E1 | Acepta agencia sin decir zona («sí, a una agencia») | Victoria pregunta la zona; si dice «cualquiera» o «la más céntrica», el código ofrece las marcadas como «centro» o las primeras del cantón | No adivina dónde vive |
| E2 | Nombra una agencia que **sí** está en el catálogo («la de Urdesa») | El código la busca por nombre/palabras clave; con **una sola coincidencia clara**, Victoria pregunta «¿Se refiere a Servientrega Urdesa, Av. … ?» y espera el sí | Confirmar antes de guardar |
| E3 | Nombra una agencia que **no** está o es ambigua | «No tengo registrada esa agencia; por esa zona tengo estas: …». Si insiste en la suya → **pasa a GESTIÓN** con el texto exacto del cliente («agencia no registrada: …») | Victoria no puede validar una agencia que no conoce |
| E4 | Manda su **ubicación de WhatsApp** (el pin 📍) | El mensaje trae coordenadas reales: el código ofrece las 3 agencias **más cercanas** que tengan coordenadas cargadas. Sin coordenadas en el catálogo → pide la zona | Dato exacto, sin interpretar texto |
| E5 | Manda un **enlace de Google Maps** | Victoria **no lo abre ni lo interpreta**: pide la zona o que mande la ubicación con 📎 → Ubicación. Si igual no se resuelve → GESTIÓN | Los enlaces cortos (maps.app.goo.gl) no dicen nada sin abrirlos y la IA podría inventar |
| E6 | Manda una **foto** de la agencia o del letrero | Si en la foto se lee el nombre, se busca **en el catálogo** como en E2 y se confirma con el cliente. Si no se lee o no está → pide el nombre/zona; si no se resuelve → GESTIÓN | La foto no es prueba de nada por sí sola |
| E7 | Pide una agencia en **otra ciudad** distinta a la que dijo | Se cambia el cantón del pedido (se valida cobertura otra vez) y se busca ahí | El cantón manda en el envío |
| E8 | Pregunta horario, teléfono o si abren el domingo | Solo lo que está en el catálogo; si falta el dato: «No tengo ese dato confirmado» (puede ofrecer el enlace de Maps cargado) | No inventar horarios |
| E9 | Dice que **otra persona** retirará | Victoria da los requisitos **del texto que Freddy confirme** con Servientrega (parámetro). Si no hay texto cargado → «Le confirmo los requisitos» y pasa a GESTIÓN | Los requisitos que encontré son de segunda mano |
| E10 | Primero eligió agencia y luego cambia a casa (o al revés) | Se cambia el tipo de entrega y se vuelve a pedir la confirmación del resumen | El total o el destino cambiaron |
| E11 | La agencia se desactivó entre que la eligió y el cierre | Al cerrar se comprueba; Victoria explica y ofrece otras de la zona | Igual que las ofertas vencidas |
| E12 | Pregunta si es **más barato** en agencia | Solo si Freddy definió una regla de precio (hoy no se sabe si cambia el flete: B2). Sin regla: mismo precio | No prometer descuentos |
| E13 | Está en un cantón **sin agencias cargadas** pero pide agencia | «Por ahora no tengo agencias registradas en su ciudad»; ofrece domicilio o pasa a GESTIÓN si insiste | No inventar |
| E14 | Producto **propio** (cierre manual) | En la primera versión no cambia: los productos propios ya tienen sus propias opciones de entrega (ADR-012). Se puede añadir «retiro en agencia» como otra opción después | Van por otro camino que no es Rocketfy |
| E15 | Escribe la agencia con faltas («urdeza», «sentro») | La búsqueda ignora tildes, mayúsculas y faltas leves (igual que ya hacemos con las ciudades) y siempre confirma con el cliente | Errores humanos normales |

## 6. Mejora aparte (vale también para entrega a domicilio)

Hoy a Rocketfy solo le mandamos la dirección. La API acepta además **referencia** (`address_2`), **indicaciones para el repartidor**
(`carrier_observations`) y **coordenadas**. Propuesta: Victoria pide una referencia («frente a…», «casa esquinera…») y, si el cliente
manda su ubicación 📍, se envían las coordenadas. Ojo: la documentación dice que si no se manda `carrier_observations`, Rocketfy pone
un texto viejo que no aplica a Ecuador; hay que revisar qué estamos mandando hoy.

## 7. Bloqueantes (antes de construir la parte de Rocketfy)

- **B1 — Preguntar a Rocketfy (Freddy):** «¿Cómo creo por API un pedido de Servientrega para **retiro en oficina**? ¿Hay un campo o se
  pone la dirección de la agencia en `address` con una indicación en `carrier_observations`? ¿El repartidor lo deja en la agencia y
  espera al cliente, o intenta entregarlo en esa dirección como si fuera una casa?». Sin esta respuesta no se envía ningún pedido real a
  agencia. Luego, **un pedido de prueba** antes de encender nada.
- **B2 — Precio:** ¿el flete o el recaudo contra entrega cambia si es retiro en oficina? ¿Se paga en la agencia al retirar?
- **B3 — Lista de agencias:** no hay API pública. ¿Rocketfy tiene la lista de oficinas de Servientrega? Si no, se carga a mano desde la
  web de Servientrega, empezando por las ciudades donde más se vende.
- **B4 — Requisitos de retiro y días de espera** en la agencia (cuántos días guarda el paquete antes de devolverlo), confirmados con
  Servientrega: van como texto (parámetro) para Victoria.

## 8. Fases

| Fase | Qué | Depende de |
|---|---|---|
| A0 | Preguntas B1–B4 a Rocketfy/Servientrega | Freddy |
| A1 | Migración `agencias_entrega` + pantalla «Agencias de retiro» + importar CSV | — (se puede construir ya) |
| A2 | Victoria: recomendar agencia, `buscar_agencias`, `elegir_agencia`, escenarios E1–E15, interruptor **apagado** + textos como parámetros, simulación | A1 |
| A3 | Pedido a Rocketfy con agencia (según la respuesta de B1) + pedido de prueba | B1, B2 |
| A4 | Referencia, indicaciones y coordenadas también para domicilio (§6) | — |
| A5 | Medir: entregas fallidas/devoluciones en agencia vs. domicilio (estado 23, devueltos) | Datos reales |

## 9. Reglas propuestas (se anotarán como ADR cuando Freddy las apruebe)

1. Victoria **recomienda** la agencia una sola vez y **respeta** si el cliente prefiere su casa.
2. Solo se ofrecen agencias **activas del catálogo** y del **cantón validado** del pedido. El código arma la lista; Victoria no escribe direcciones.
3. Toda agencia elegida se **confirma con el cliente** antes de guardarla y se **vuelve a comprobar** al cerrar.
4. Enlaces de mapas, fotos dudosas, agencias no registradas o requisitos sin texto confirmado → **GESTIÓN**, nunca una respuesta inventada.
5. Todo viene **apagado**: sin agencias cargadas o con el interruptor apagado, el flujo es exactamente el de hoy.
