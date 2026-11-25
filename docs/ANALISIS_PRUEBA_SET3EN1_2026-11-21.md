# Análisis de la primera prueba con anuncios: Set 3 en 1 (Black Friday)

**Período:** sábado 21 al miércoles 25 de noviembre de 2026 (hora de Ecuador).
**Hecho el:** 2026-11-25, con datos reales de Supabase (conversaciones, mensajes, pedidos, avisos de Rocketfy), del
Administrador de anuncios de Meta (conector Meta Ads, solo lectura) y de la Biblioteca de anuncios. Ningún dato se escribió ni
se cambió en producción para hacer este análisis.

## Hacemos esto para…

Saber si vale la pena seguir invirtiendo en el Set 3 en 1, qué falló (en el anuncio, en Victoria y en la atención manual) y
cómo tiene que ser la próxima prueba para que su resultado sí sirva para decidir.

---

## 1. En pocas palabras

| Pregunta | Respuesta corta |
|---|---|
| ¿Cuánto se gastó y por qué se detuvo? | **$39,97.** La campaña sigue «activa», pero se detuvo porque la cuenta publicitaria llegó a su **límite de gasto de $40** (lo puso Freddy el 20 de noviembre). No fue falta de saldo en la tarjeta. |
| ¿Cuántos escribieron? | **33 conversaciones** según Meta (**32** según nuestra base, más 2 que escribieron directo sin anuncio). Costo: **$1,21 por conversación**, barato. |
| ¿Cuántos compraron? | **2 clientes** (Rómulo, Naranjito: $25; Ivan, Quito: $62,50 con 3 tablas de picar). En Rocketfy son **3 pedidos vivos** (+1 rechazado). |
| ¿Se ganó o se perdió? | **Se perdió, unos $16** (estimado: ganancia de los pedidos ≈ $23,93 menos $39,97 de anuncios). Eso si los dos clientes retiran y pagan; ninguno ha pagado todavía. |
| ¿Es un mal producto? | **No hay pruebas de eso.** El anuncio atrae barato, y 2 de cada 10 personas que conversaron de verdad compraron. Lo que no cuadra es **el margen**: un set a $25 deja ≈ $8,46 y cada venta costó ≈ $20 en anuncios. |
| ¿Fue una prueba concluyente? | **No.** Dos ventas no alcanzan para decidir (la regla acordada era mirar 60 conversaciones), y la prueba quedó «contaminada»: Victoria cambió a mitad de camino, el seguimiento automático se apagó sin querer y tres clientes interesados se enfriaron esperando respuesta. |
| ¿Hay que hacer video? | **Sí.** El 61 % de las conversaciones vino de **Reels de Facebook** con una imagen fija, y las preguntas de los clientes (litros, grosor, caja, «¿es para inducción?») son justo las que responde un video de 15–25 s. |

**Mi recomendación:** no abandonar el producto todavía, pero tampoco escalarlo. Primero arreglar lo que falló, después una
**segunda prueba de 7 días (~$70)** con video y con la oferta de **2 unidades**. Al final de esa prueba sí se decide
(§10 y §11).

---

## 2. La campaña en Meta

**Campaña:** «BF Set 3 en 1 · WhatsApp · nov 2026» (`120253438840730445`), objetivo interacción → conversaciones de WhatsApp,
del 21 nov 07:00 al 30 nov. Dos conjuntos de $5/día con el **mismo anuncio** (la misma imagen y el mismo texto): por eso esta
prueba comparó **públicos**, no anuncios.

### 2.1 Totales (21 al 25 de noviembre)

| Métrica | Total | A · Cocina y hogar (intereses) | B · Abierto (sin intereses) |
|---|---|---|---|
| Gasto | $39,97 | $21,14 | $18,83 |
| Impresiones | 18 030 | 9 560 | 8 470 |
| Alcance (cuentas) | 12 240 | 7 868 | 5 975 |
| Frecuencia | 1,47 | 1,22 | 1,42 |
| CPM (costo por 1 000 impresiones) | $2,22 | $2,21 | $2,22 |
| CTR (todos los clics) | 1,56 % | 1,34 % | 1,82 % |
| Clics al botón de WhatsApp | 149 | 69 | 80 |
| **Conversaciones iniciadas (Meta)** | **33** | 13 | 20 |
| **Costo por conversación** | **$1,21** | $1,63 | **$0,94** |
| Conversaciones en nuestra base | 32 | 14 | 18 |
| **Ventas** | **2** | **2** | 0 |
| Costo por cliente (anuncios ÷ clientes) | $19,99 | $10,57 | — |

**Cómo leerlo:** el público abierto (B) consiguió conversaciones más baratas, pero las dos ventas salieron del público con
intereses (A). Con solo dos ventas esto **puede ser casualidad**; además, el primer día B recibió las conversaciones que
atendió la versión anterior de Victoria, que presionaba demasiado (§5). No sirve para declarar un ganador.

**Fuga entre el clic y el mensaje:** 149 personas tocaron el botón y solo 33 enviaron el mensaje (22 %). Es normal que se
pierda gente al abrir WhatsApp, pero conviene vigilarlo.

### 2.2 Día por día

| Día | Gasto | Conversaciones | Costo por conversación |
|---|---|---|---|
| Sáb 21 | $8,31 | 16 (13 de B a $0,32) | $0,52 |
| Dom 22 | $12,32 | 8 | $1,54 |
| Lun 23 | $10,42 | 7 | $1,49 |
| Mar 24 | $6,67 | 2 | $3,34 |
| Mié 25 | $2,25 | 0 | — (se topó el límite de $40) |

El primer día fue excepcional y después el costo subió. Meta lo marca como **tendencia mala en B** (CTR −64 %) y **buena en
A** (CTR +31 %). Con una frecuencia de 1,4 no parece cansancio del anuncio; lo más probable es que el algoritmo agotara
rápido a los más dispuestos y que el límite de gasto frenara la entrega los dos últimos días.

### 2.3 Dónde se vio el anuncio

| Ubicación | Gasto | Conversaciones | Costo por conversación |
|---|---|---|---|
| **Reels de Facebook** | $20,85 (52 %) | **20 (61 %)** | $1,04 |
| Feed de Facebook | $14,22 | 11 | $1,29 |
| Instagram (feed, reels, historias) | $3,48 | 2 | $1,74 |
| Historias de Facebook | $0,80 | 0 | — |
| Marketplace | $0,60 | 0 | — |
| Estado de WhatsApp | $0 | 0 | sin entrega |

**La mitad del dinero y 6 de cada 10 conversaciones salieron de Reels, un lugar hecho para video, con una imagen fija.**
Es el argumento más fuerte a favor del video.

### 2.4 Quién escribió (edad y sexo, según Meta)

| Edad | Gasto | Conversaciones |
|---|---|---|
| 25–34 | $6,21 | 6 (mujeres 5 a $0,62; hombres 1 a $3,06) |
| 35–44 | $11,53 | 8 |
| **45–54** | **$20,26** | **17 (52 %)** |
| 55 (el tope era 55) | $1,97 | 2 (mujeres a $0,66) |

Mujeres: 20 conversaciones; hombres: 13. Los dos compradores son hombres de más de 45. **Recomendación:** subir la edad
máxima a 65.

### 2.5 La competencia (Biblioteca de anuncios, Ecuador)

Hay **al menos dos tiendas más vendiendo el mismo set** con anuncios activos: **CompraFácil Ecuador** (4 anuncios desde el
14 nov, «Bowl 3 en 1 Multifuncional - Lava, Ralla y Escurre») e **Importadora Q** (3 anuncios desde el 23 nov, «Set 3 en 1:
lava, escurre y ralla»). Los dos venden **la función** («lava, escurre y ralla»); nosotros vendimos **el precio**. No se ven
sus precios desde la herramienta: Freddy puede abrirlos en
[CompraFácil](https://www.facebook.com/ads/library/?id=1453293283622931) e
[Importadora Q](https://www.facebook.com/ads/library/?id=4747884848831509). Que haya competencia confirma que el producto
se vende, pero también que el cliente puede comparar.

---

## 3. El embudo en WhatsApp (32 conversaciones del anuncio)

| Paso | Personas | % |
|---|---|---|
| Escribieron (casi todos con el mensaje ya escrito del anuncio) | 32 | 100 % |
| **No contestaron la primera respuesta de Victoria** | **22** | **69 %** |
| Contestaron y conversaron | 10 | 31 % (A: 4 de 14; B: 6 de 18) |
| Mostraron intención de compra (pidieron, dieron ciudad o dijeron «ayúdeme») | 4 | 13 % |
| **Compraron** | **2** | **6,3 %** (20 % de los que conversaron) |

- **El agujero más grande es el primer mensaje:** 21 personas mandaron solo «Hola, quiero el Set 3 en 1 de Black Friday» y
  no volvieron. La primera respuesta de Victoria fue casi siempre la misma: precio + descripción + «¿Tiene alguna duda o le
  gustaría ver fotos?». Repite lo que el anuncio ya dijo y no da una razón para seguir.
- **Horas de llegada:** 4 de madrugada (00:00–06:00), 12 en la mañana, 10 en la tarde y 6 en la noche. Victoria cubrió
  bien las horas sin asesor: Rómulo (05:55) dejó todos sus datos en 9 minutos.
- **Seguimiento automático:** salió solo a 5 clientes el sábado (ninguno respondió). **Desde el sábado al mediodía no le salió
  a nadie más** por un efecto secundario de un cambio nuestro (§6, fallo F1): 25 conversaciones se quedaron sin el
  recordatorio. En cambio, el «¿aún le interesa?» que Freddy escribió a mano al día siguiente **recuperó la venta de
  $62,50**.

---

## 4. Las ventas y el dinero

### 4.1 Los pedidos en Rocketfy (según los avisos del webhook)

| Pedido | Cliente | Total | Estado al 25 nov | ¿Unido al sistema? |
|---|---|---|---|---|
| 413585 | Rómulo (Naranjito, retiro en agencia) | $25,00 | En ruta (25 nov 11:22) | Sí (conv. 43, «despachado») |
| 414262 | Ivan (Quito) | $37,50 | **Rechazado** (23 nov 16:02, minutos después de crearlo) | No |
| 414382 | Ivan: el set | $25,00 | **Recogida en agencia** (25 nov 14:36): el paquete ya está en la agencia, esperando que lo retire | **No** |
| 414392 | Ivan: 3 tablas de picar | $37,50 | **Recogida en agencia** (25 nov 14:36) | **No** |

El pedido de Ivan quedó **partido en dos envíos**: el set es de un proveedor (2067) y la tabla de otro (3430). **Dos envíos
= dos veces el costo de logística.** Los pedidos de Ivan no están unidos a su conversación: el sistema no avisa por Telegram
que llegaron a la agencia, y el botón «Ya hice el pedido en Rocketfy» solo acepta **un** pedido por venta (§9, pendiente
nuevo).

### 4.2 Ganancia estimada

Con el costo real que vimos en el pedido de Rómulo (producto $5,85 + logística $10,69 = $16,54) y suponiendo una logística
parecida en Quito (**sin verificar**; la tabla se supone de $6,60, SKU 3430-117136, **a confirmar**):

| Pedido | Cobra | Producto | Logística (est.) | Ganancia (est.) |
|---|---|---|---|---|
| Rómulo, set | $25,00 | $5,85 | $10,69 | $8,46 |
| Ivan, set | $25,00 | $5,85 | $10,69 | $8,46 |
| Ivan, 3 tablas | $37,50 | $19,80 | $10,69 | $7,01 |
| **Total** | **$87,50** | | | **≈ $23,93** |
| Anuncios | | | | −$39,97 |
| **Resultado de la prueba** | | | | **≈ −$16,04** |

Si Ivan hubiera recibido todo en **un solo envío**, la ganancia habría subido ≈ $10,69. Si alguno **no retira** el paquete,
la pérdida crece (envío de ida y vuelta). En Ecuador se habla de devoluciones del 15 al 40 % en contra entrega (cifras de
blogs, no oficiales).

### 4.3 La cuenta que manda

- Un set a $25 deja **≈ $8,46**. Para no perder, cada venta puede costar en anuncios **como máximo $8,46**.
- A $1,21 por conversación, eso exige **1 venta cada 7 conversaciones (14 %)**. Logramos **6 %**.
- **El precio por transferencia de $20** deja ≈ $3,46 (17 %, por debajo del margen mínimo de 25 %). Ivan lo usó para
  regatear («la publicidad dice 20»: falso, la imagen dice $24,99).
- **La palanca más fuerte es vender 2 sets por pedido:** salen del mismo proveedor y en un mismo envío. «2 por $45» deja
  ≈ **$22,61** (45 − 2 × 5,85 − 10,69), casi el triple que uno solo. Con eso, una venta de $20 en anuncios sí es rentable.
  Hoy Victoria solo lo menciona si el cliente pregunta (decisión del 21 nov).

---

## 5. Conversación por conversación

A = conjunto «Cocina y hogar», B = conjunto «Abierto». «Solo el mensaje» = mandó el texto del anuncio y no volvió.

| # | Llegó | Grupo | Qué pasó | Resultado |
|---|---|---|---|---|
| 16 | sáb 07:03 | B | Preguntó la capacidad; Victoria no la tenía y dio medidas | Sin respuesta |
| 17 | sáb 07:26 | B | Versión anterior de Victoria: «¿Lo quiere llevar? ¡Perfecto! Registré su pedido» en un mismo mensaje y pidió datos | Silencio; recordatorio sin respuesta |
| 18 | sáb 08:11 | B | Victoria pidió datos de entrada; «¿Dónde están ubicados?» → «100 % online, sin local» → «Gracias» → «No» | **Perdido por confianza** |
| 19 | sáb 09:18 | B | Versión anterior: pidió el nombre dos veces en el mismo mensaje | Silencio; recordatorio sin respuesta |
| 20 | sáb 09:48 | A | Solo el mensaje | Silencio |
| 21 | sáb 10:39 | B | Solo el mensaje | Silencio; recordatorio sin respuesta |
| 22 | sáb 11:29 | B | Litros + foto: Victoria mandó foto y video y pasó a asesor; Freddy a los 35 min («1,5 a 2 L»); pidió foto de la **caja**; Freddy prometió pedirla a bodega | **Perdido** (la foto nunca llegó) |
| 23 | sáb 14:06 | B | Solo el mensaje | Silencio |
| 24 | sáb 14:42 | directo | Solo el saludo | Silencio; recordatorio sin respuesta |
| 25 | sáb 14:59 | B | «Yo pedí y nunca me llegó» (en otra tienda) → Victoria lo tomó como un pedido nuestro y pasó a asesor; Freddy a los 53 min; la clienta: «Claro que sí, ayúdeme»; Freddy volvió **67 min** después con preguntas de pago | **Perdido** (cliente caliente que se enfrió) |
| 26 | sáb 16:59 | A | Solo el mensaje | Silencio |
| 27 | sáb 17:14 | A | Solo el mensaje | Silencio |
| 28 | sáb 17:29 | B | «¿No son tan delgados?» → asesor (Freddy en 3 min); «¿De dónde envía? Vivo en Cuenca» → Freddy respondió **2 h 18 min** después | **Perdido** (espera) |
| 29 | sáb 19:49 | directo | «¿Qué garantía hay?» → asesor (10 min, 30 días); fotos 45 min después de prometerlas | «Gracias, muy amable»; no compró |
| 30 | sáb 20:29 | B | Solo el mensaje | Silencio |
| 31 | sáb 21:16 | B | Volvió a las 06:32 a preguntar medidas; Victoria respondió | Silencio |
| 32 | dom 08:09 | B | Solo el mensaje | Silencio |
| 33 | dom 10:22 | B | «…gracias por la información» | Silencio |
| 34 | dom 12:10 | A | Solo el mensaje | Silencio |
| **35** | dom 16:25 | A | «Quiero uno»; mandó su **ubicación** (Quito) y Victoria le pidió cantón y provincia **3 veces** («??»); Freddy tomó a los 36 min; al día siguiente «¿aún le interesa?» → sí; agencia Iñaquito; regateó a $20; Freddy le ofreció tablas → **compró 3**; pidió catálogo y cuchillos | **VENTA $62,50** |
| 36 | dom 21:30 | A | Solo el mensaje | Silencio |
| 37 | dom 21:42 | A | Solo el mensaje | Silencio |
| 38 | dom 22:35 | B | Solo el mensaje | Silencio |
| 39 | dom 22:50 | A | Pidió fotos a las 06:56; Victoria mandó foto y video | Silencio |
| 40 | lun 00:22 | A | Solo el mensaje | Silencio |
| 41 | lun 00:56 | A | Solo el mensaje | Silencio |
| 42 | lun 01:05 | A | Solo el mensaje | Silencio |
| **43** | lun 05:55 | A | «¿Esto es en Ecuador?», Naranjito, nombre, retiro en agencia y pago al recibir: **Victoria tomó todo en 9 min**; Freddy siguió a las 08:32 (cédula y agencia) | **VENTA $25** |
| 44 | lun 07:29 | A | Solo el mensaje | Silencio |
| 45 | lun 09:13 | B | Solo el mensaje | Silencio |
| 46 | lun 09:48 | B | Solo el mensaje | Silencio |
| 47 | lun 14:24 | A | «¿Es para inducción?» → no; después un «Perdone la confusión» que sobraba | **Perdido** (buscaba una olla) |
| 48 | mar 16:15 | B | Pidió fotos; Victoria dijo «ya se las envié» **antes** de que llegaran; «¿Tiene más productos de cocina?» → «solo le puedo ayudar con este set» | **Perdido** (no se le ofreció nada más) |
| 49 | mar 17:20 | B | Solo el mensaje | Silencio |

**Escalados a asesor:** 6 (22, 25, 28, 29, 35 y 43). Resultado: **2 ventas**, **3 perdidos por espera o por una promesa sin
cumplir**, 1 sin interés. Tiempos de la primera respuesta de Freddy: 3, 10, 35, 36 y 53 min, y 2 h 28 min (de madrugada);
pero las respuestas **después** de que el cliente mostró interés tardaron 67 min y 2 h 18 min, y ahí se perdieron.

---

## 6. Lo que falló (y en qué quedó)

### En Victoria y en el sistema

| # | Falla | Conversaciones | Estado |
|---|---|---|---|
| F1 | **El seguimiento automático dejó de salir.** Desde el cambio del 21 nov (0.0.167), Victoria ya no registra el producto con el mensaje del anuncio, y el seguimiento solo le escribe a quien tiene producto registrado (`jobs/seguimiento/repository.py`). | 25 conversaciones desde la 20 | **ABIERTO** (fácil: que el lead tome el producto del anuncio vinculado al llegar) |
| F2 | Respuesta pegada y presión: «¿Lo quiere llevar? ¡Perfecto! Registré su pedido», pidió datos de entrada y ofreció precio por cantidad sin que lo pidieran | 17, 18, 19, 21 | Corregido el 21 nov (0.0.167) |
| F3 | No sabía la capacidad | 16, 22 | Corregido (0.0.168: ≈ 1,5 L en la ficha) |
| F4 | Pasaba a asesor la garantía | 29 | Corregido (0.0.170) |
| F5 | **Preguntas de confianza sin buena respuesta:** «¿dónde están ubicados?», «¿de dónde envía?», «¿esto es en Ecuador?», «en otra tienda pedí y nunca me llegó» | 18, 25, 28, 43 | **ABIERTO**: darle a Victoria la respuesta que funcionó con Freddy («despachamos desde nuestra bodega en Guayaquil por Servientrega y usted paga solo cuando lo recibe: no arriesga nada») y que no tome lo de «otra tienda» como un reclamo nuestro |
| F6 | **Ubicación compartida:** pidió cantón y provincia 3 veces a quien ya había mandado el pin | 35 | **ABIERTO**: deducir la ciudad por las coordenadas y confirmarla («¿Es en Quito, Pichincha?») |
| F7 | **Venta cruzada:** «¿tiene más productos de cocina?» → «solo este set» | 48 (y 35 pidió catálogo y cuchillos) | **ABIERTO**: decir que sí, ofrecer el catálogo y pasar a un asesor |
| F8 | Grosor del acero sin dato → pasó a asesor | 28 | **ABIERTO**: agregar peso y grosor a la ficha |
| F9 | «¿Es para inducción?»: la foto se confunde con una olla | 47 | **ABIERTO**: anotar en la ficha que no es olla; el video lo aclara solo |
| F10 | Anunció «ya le envié las fotos» antes de mandarlas | 48 | **ABIERTO** (menor) |
| F11 | Empaque (¿caja o funda?) sin dato ni foto | 22 | **ABIERTO**: preguntar a Rocketfy (ya está en el pendiente #90) |

### En la atención manual

- **Tiempo de respuesta:** los tres clientes que se perdieron después de mostrar interés esperaron más de una hora. Con
  anuncios encendidos, la meta es **menos de 10 minutos** en horario de atención.
- **Promesas sin cumplir:** la foto de la caja (22). Si no se puede cumplir, mejor decir «no la tengo» y seguir.
- **Lo que funcionó:** el «¿aún le interesa?» del día siguiente, ofrecer otro producto (3 tablas) y resumir el pedido
  antes de crearlo.

---

## 7. Lo que tuvimos que agregar durante la prueba

| Cuándo | Qué | Por qué |
|---|---|---|
| sáb 21 | Victoria más humana: sin textos pegados, sin emojis, información de a poco, el mensaje del anuncio no es una compra (0.0.167, PR #50) | Las primeras 3 conversaciones |
| sáb 21 | Capacidad ≈ 1,5 L en la ficha (0.0.168) | Conversaciones 16 y 22 |
| sáb 21 | Recordatorio sin emojis; anuncios vinculados al producto (0.0.169, PR #51) | Recordatorio a quien ya dijo «No» |
| dom 22 | Botón «Enviar fotos y videos» en el panel; regla de garantía (0.0.170, PR #52) | Freddy atendía un chat escalado y no podía mandar fotos |
| lun 23 | Enlaces tocables, ubicación en Google Maps (0.0.171) | La ubicación de Ivan no se podía abrir |
| lun 23 | «Ya hice el pedido en Rocketfy» (0.0.175, PR #55) | El pedido de Rómulo, hecho a mano, no contaba |
| lun 23 | Ver las fotos enviadas y mandar fotos propias (0.0.176, PR #56) | Las tablas de picar para Ivan |
| lun 23 | «Enviar un archivo» (0.0.177, PR #57) y el catálogo de Hogar y Cocina en PDF | Ivan pidió catálogo |

**Efecto secundario a corregir:** el cambio del sábado (no registrar el producto con el mensaje del anuncio) apagó sin querer
el seguimiento automático (F1).

---

## 8. Conclusiones

1. **El producto no está descartado.** Atrae barato ($1,21 por conversación, CTR 1,56 %), hay competencia que lo sigue
   anunciando, 2 de cada 10 personas que conversaron compraron, y un cliente compró 4 productos.
2. **El problema es de margen y de conversión, no de interés.** A $25 con ≈ $10,69 de logística, un set deja ≈ $8,46; con
   6 % de conversión, cada venta costó ≈ $20. Para que cuadre hace falta subir la conversión al **12–15 %**, vender **2
   unidades por pedido**, o las dos cosas.
3. **El mayor hueco es el primer mensaje** (69 % no contesta), seguido de la **espera del asesor**. Las dos cosas se arreglan
   sin gastar más en anuncios.
4. **El video vale la pena**, por datos y no por moda: Reels se llevó la mitad del presupuesto con una imagen fija, el
   producto se entiende viéndolo en uso (rallar, lavar, escurrir, guardar uno dentro del otro) y la competencia vende la
   función. Que alguien lo haya confundido con una olla lo confirma.
5. **El ángulo del precio ya está probado y está gastado** (y Black Friday termina el 30). El siguiente: **demostración** y,
   en diciembre, **regalo de Navidad**, «2 por $45: uno para usted y otro para regalar». En Ecuador el décimo tercer sueldo se
   paga hasta el 24 de diciembre y hay más dinero para regalos.
6. **La prueba no fue concluyente.** Faltó volumen (32 conversaciones de 60) y cambiaron cosas a mitad de camino. Una segunda
   prueba limpia sí sirve para decidir.

---

## 9. Antes de volver a encender los anuncios

**Lo hace Claude (código e instrucciones, con tests):**
1. **F1:** el lead toma el producto del anuncio vinculado al llegar (vuelve el seguimiento automático).
2. **F5, F7, F10:** respuestas de confianza, venta cruzada («sí, tenemos más; le paso el catálogo»), no anunciar fotos antes
   de mandarlas.
3. **F6:** de la ubicación compartida a cantón y provincia (con la lista de cantones de Rocketfy), siempre confirmando con
   el cliente.
4. Ficha: grosor o peso, empaque y «no es olla ni va al fuego» (F8, F9, F11).
5. Primer mensaje más corto, con el video y una sola pregunta fácil; ofrecer «2 por $45» al hablar del precio (lo decide
   Freddy).
6. Unir **más de un pedido de Rocketfy** a la misma venta (pedidos partidos por proveedor, caso Ivan).
7. Costos reales en el sistema (pendiente #90): envío estimado $5 → ≈ $10,69.

**Lo hace Freddy:**
1. Avisar a Ivan que sus dos paquetes **ya están en la agencia de Iñaquito** y confirmar que retire. Seguir el de Rómulo (en
   ruta).
2. Conseguir el **video vertical** (§10).
3. Decidir el **precio por transferencia** ($20 deja casi nada) y si se ofrece «2 por $45».
4. **Subir el límite de gasto** de la cuenta publicitaria cuando todo esté listo (hoy $40).
5. Comprometerse a responder en menos de 10 minutos mientras corran los anuncios (los avisos de Telegram ya existen).

---

## 10. Cómo debe ser el video

- **Vertical 9:16, 15 a 25 segundos**, grabado con celular en una cocina real (se siente cercano, no de catálogo).
- **Los primeros 2 segundos con acción:** rallar zanahoria o queso sobre el colador. Nada de logo al inicio.
- Mostrar los usos: **rallar → lavar y escurrir → servir → guardar uno dentro del otro.**
- **Una mano en la toma** para que se vea el tamaño (responde «¿es delgado?», «¿cuántos litros?») y, si se puede, la caja o
  el empaque.
- Texto grande en pantalla (muchos ven sin sonido): «Lava, escurre y ralla en un solo bowl», «Acero inoxidable», «Envío gratis,
  paga al recibir».
- Cierre: precio, «2 por $45» (si se aprueba) y «Escríbanos por WhatsApp».
- Si no se puede grabar, una versión editada del video del proveedor sirve para empezar, pero la competencia probablemente usa
  ese mismo video.

---

## 11. La segunda prueba (propuesta)

| Qué | Cómo |
|---|---|
| Duración y presupuesto | 7 días, $10/día (≈ $70). Subir el límite de la cuenta a ≈ $80. |
| Estructura | Los mismos 2 públicos (A y B), cada uno con **2 anuncios: la imagen actual y el video**. Edad 25–65. Las ubicaciones, como estaban. |
| Oferta | $24,99 con envío gratis y paga al recibir; **2 por $45**. En diciembre, texto de Navidad. |
| Qué mirar cada día | Costo por conversación (≤ $1,20), % que contesta a Victoria (meta ≥ 40 %), minutos hasta la respuesta del asesor (< 10), ventas ÷ conversaciones, unidades por pedido. |
| Regla para decidir (al llegar a 50 conversaciones) | **7 o más ventas (≥ 14 %) o un costo por venta ≤ $10** → escalar despacio (+20 % cada 3 días). **4 a 6 ventas** → probar otro ángulo o precio. **3 o menos** → cambiar de producto (el análisis del catálogo ya tiene candidatos). |
| También | Medir cuántos pedidos se **entregan y se cobran**: una venta que no se retira cuesta doble. |

---

## 12. Dudas para Freddy

1. **Pedido de Ivan:** ¿por qué quedó en dos pedidos (y uno rechazado)? ¿Rocketfy cobró dos envíos? ¿Cuánto costó cada uno en
   el panel (para reemplazar mis estimaciones)?
2. **La tabla de picar:** ¿cuál fue (SKU y costo)? Supuse la de 29 × 20 cm a $6,60.
3. **Caja o funda:** ¿se supo cómo llega el set? (conversación 22).
4. ¿Volviste a hablar por fuera del panel con las clientas de las conversaciones 25 y 28 (Edith y Rosario)?
5. ¿El «$20 con envío gratis» de Ivan salió de algún lado (un estado, una publicación)? La imagen del anuncio dice $24,99.
6. ¿Puedes grabar el video tú o lo buscamos de otra forma?

---

## Fuentes externas

- Conversión de anuncios a WhatsApp (5–15 %, estimaciones de proveedores, no oficiales):
  [Aurora Inbox, Click-to-WhatsApp](https://www.aurorainbox.com/en/2026/05/13/what-is-click-to-whatsapp-ads/),
  [Aurora Inbox, estadísticas LATAM](https://www.aurorainbox.com/2026/03/04/estadisticas-ecommerce-whatsapp-latam/).
- Video contra imagen en Reels (los datos públicos no coinciden; lo correcto es probar los dos):
  [Stackmatix](https://stackmatix.com/blog/facebook-video-vs-image-ads-performance),
  [Segwise](https://segwise.ai/blog/static-video-ratio-meta-ads),
  [Metricool](https://metricool.com/facebook-reels-ads-guide/).
- Devoluciones en contra entrega en Ecuador (15–40 %, blogs del sector, no oficiales):
  [Andrey Business](https://www.andreybusiness.com/ecuador/blog/que-de-devoluciones-es-sano-en-una-tienda-de-dropshipping-contra-entrega).
