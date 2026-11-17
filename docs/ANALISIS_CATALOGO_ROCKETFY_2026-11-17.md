# Análisis del catálogo de Rocketfy para elegir el primer producto (2026-11-17)

Pedido de Freddy: «ayúdame a escoger el producto… revisa mis apuntes de la clase». Solo lectura: se bajó el catálogo por la API de
producción (`GET /productos`, 183 páginas) y se filtró en el entorno de Claude. **No se publicó ni se cambió nada.**

## Criterios (salen de los apuntes de la clase «Rocket 2» y de lo ya anotado en el proyecto)
- Nicho **hogar** (mejor tasa de entrega, según la clase) y formato **combo/pack** (sube el valor percibido).
- **Evitar** lo que Meta/WhatsApp restringe (pendiente #80: suplementos, mascotas, dispositivos digitales, imitaciones de marca,
  armas/vigilancia, mejora sexual) y lo cosmético/médico con promesas de salud (más devoluciones). Es un filtro por palabras:
  deja fuera de más y puede dejar pasar algo; **hay que revisar cada finalista a mano**.
- Ganancia neta estimada = precio sugerido − costo Rocketfy − **$5 de envío (estimado; es el valor de «Ajustes de precios», sin confirmar)**.
  Meta de la clase: producto de «estabilidad» $17–20; de «volumen» $14–16 con CPA ≈ $1,50.
- Stock ≥ 200 (para llegar a los 20 pedidos de validación y escalar), precio sugerido $24–60 (ticket cómodo para pagar al recibir),
  peso ≤ 2,5 kg (envío más barato y menos daños).

## Cifras
| Etapa | Productos |
|---|---|
| Catálogo completo | 3 659 |
| Con stock | 3 248 |
| Sin las categorías restringidas | 1 956 |
| Con precio, stock, ganancia y peso dentro de los criterios | 117 |
| …y además de hogar **y** combo | 7 |

## Finalistas (ordenados por mi preferencia para una PRIMERA prueba)
| # | SKU | Producto | Costo → sugerido | Ganancia neta est. | Stock | Peso | Nota |
|---|---|---|---|---|---|---|---|
| 1 | `2067-BOWL-COLADORRALLADOR` | Set 3 en 1: bowl + colador + rallador (acero inox.) | $5,85 → $30,00 | ≈ $19,15 | 2 053 | 0,15 kg | Hogar + combo, muy liviano, poco capital; tiene descripción y 2 fotos extra |
| 2 | `LUZ-LED-SOLA-RECA-X-2` | Luz LED solar recargable ×2 | $6,65 → $29,99 | ≈ $18,34 | 4 999 | 0,35 kg | Pack ×2, problema/solución (ahorro de luz, cortes); **sin descripción** en Rocketfy |
| 3 | `12-CINTA-ANTI-GRIETAS` | Cinta anti grietas impermeable | $3,05 → $25,00 | ≈ $16,95 | 14 924 | 1,0 kg | Demo visual muy clara, stock enorme; $25 por una cinta puede costar convencer; ofrecer pack |
| 4 | `TEND-PARE-INOX` | Tendedero de pared inoxidable | $3,85 → $29,99 | ≈ $21,14 | 450 | 0,95 kg | Margen alto, costo mínimo; stock más corto |
| 5 | `SET-OLLA-13PC` | Set de ollas 13 piezas | $16,03 → $49,99 | ≈ $28,96 | 293 | 1,6 kg | «Producto de estabilidad»: más ganancia pero ticket alto y voluminoso (12×30×26 cm); stock justo para validar |
| 6 | `JUEGOCUBIERTOS24PCS` | Juego de cubiertos 24 piezas (dorado) | $16,70 → $49,99 | ≈ $28,29 | 502 | 1,2 kg | Se vende en cualquier tienda: ojo con el precio de la competencia |
| 7 | `2067-ALMOHADA-SLEEPCARE` | Almohada para parejas | $13,50 → $35,00 | ≈ $16,50 | 2 358 | 1,15 kg | Hogar (cama); tiene variantes parecidas |

Otros con buena cifra pero descartados para la primera prueba: sets de ollas de 12 piezas a $59,99–$79,99 (ticket alto y 2,8–3 kg de peso),
aire acondicionado de pared, hidrolavadora, vaporizador (electrodomésticos: más garantías y devoluciones), edredones (por medidas/variantes).

## Lo que este análisis NO puede decir (importante)
- **Demanda real y tasa de entrega:** la API de Rocketfy no entrega ventas, calificaciones ni % de entrega por producto. La clase propone
  validar con **20 pedidos**; eso solo se sabe vendiendo. Tampoco se pudo usar Kalodata ni mirar creativos de la competencia.
- **Precio de la competencia en Ecuador:** no se verificó. El «precio sugerido» es el de Rocketfy, no el del mercado. Antes de publicar,
  buscar el mismo producto en Mercado Libre / Marketplace.
- **Qué es un producto «Black» en Rocketfy:** no lo sé; hay que revisarlo en el panel o con los apuntes de la clase y cruzarlo con los finalistas.
- **El envío de $5** es un supuesto: el costo real depende de ciudad y peso; confirmarlo con la primera compra de prueba.

## Cuentas rápidas con los números de la clase (producto 1)
- Venta contra entrega a $30,00: costo $5,85 + envío ≈ $5 → ganancia ≈ $19,15; con **$5 de descuento por transferencia**: ≈ $14,15.
- Con CPA de $2–4 por pedido: ganancia ≈ $10–17 por pedido entregado (sin contar devoluciones).
- 20 pedidos de validación ≈ $40–80 de publicidad si el CPA se cumple (**es lo que dice la clase, no está comprobado en este sistema**).

## Recomendación
1. Primer producto de prueba: **#1 (set 3 en 1)**; segundo, para comparar: **#2 (luz solar ×2)**. Un «producto de estabilidad» (#5) para una segunda fase.
2. En la compra de prueba de punta a punta (pendiente #87) **no cancelarla**: recibir la unidad permite ver calidad y empaque (cuesta ≈ $6 + envío).
3. Para ofrecer el pack o el descuento por transferencia, usar «Ofertas y combos» del panel (el código calcula los precios; Victoria no inventa descuentos).

## Anexo: la lista anterior (2026-11-11) y cómo se combina con esta
El 2026-11-11 se hizo otro análisis, con otros criterios (stock ≥ 200, costo $4–25, precio $25–70, peso ≤ 1,5 kg, **ganancia neta ≥ 35 %**).
No quedó escrito en el repositorio; se recuperó del historial de la sesión. El de hoy **partió de cero** con los apuntes de la clase
(hogar + combos) y no se comparó con aquél. Los seis favoritos de entonces (precios/stock de hoy):

| Producto | SKU | Costo → sugerido | Ganancia neta est. | Stock | Estado |
|---|---|---|---|---|---|
| Mega linterna LED recargable | `MEGALINTERNALEDRECARGABLE` | $19,50 → $59,99 | ≈ $35,49 | 968 | Apuesta de **margen**: mayor colchón (con 80 % de entrega y $5 de envío, ≈ $27 por pedido enviado; cierre mínimo ≈ 2,7 %) |
| Depilador de mujer 2 en 1 | `DEPILADORMUJER21` | $6,75 → $29,99 | ≈ $18,24 | 1 684 | Apuesta de **volumen**: 0,15 kg |
| Sellador al vacío | `SELLADORALVACIO` | $6,83 → $29,99 | ≈ $18,16 | 305 | Se explica en 10 s de video; stock justo |
| Mochila impermeable con USB | `MOCHILAIMPERMEABLEUSB` | $8,25 → $29,99 | ≈ $16,74 | 548 | Pocas devoluciones |
| Aspiradora inalámbrica | `10-ASPIR-INALAM` | $9,75 → $29,99 | ≈ $15,24 | 1 323 | Se demuestra bien |
| ~~Cepillo secador para mascotas~~ | — | — | — | — | **Descartado**: productos para animales están en la lista de infracciones de WhatsApp (#80) |

Aquella estrategia proponía **tres productos en paralelo** (la linterna, el depilador y la mochila o el sellador) y escalar solo el ganador.
Los cuatro primeros también aparecen en el análisis de hoy (cumplen los filtros); simplemente no se priorizaron porque hoy se buscó hogar + combo.

---

# Decisión: los 3 productos para la estrategia de prueba (2026-11-17, segunda parte)

Pedido de Freddy: unir las dos listas (11-nov y 17-nov) y elegir **3 productos ganadores** para la estrategia planteada el 11-nov
(piloto con el mejor producto, luego prueba de los tres en paralelo y escalar solo al ganador). Se evaluaron 12 candidatos (los 5 de la lista
anterior sin mascotas + los de hoy + la lámpara solar de pared).

## Método
1. **Economía** con el mismo modelo del 11-nov: ganancia esperada por pedido hecho = `0,8·(venta − costo − envío) − 0,2·envío`
   (el no entregado pierde el envío), envío $5, costo por conversación $0,75 ($0,60 anuncio + $0,15 IA; supuestos, no medidos).
   Se calcula el **cierre mínimo** (% de conversaciones que deben terminar en pedido para no perder) en dos escenarios:
   base y **estrés** (precio −15 %, entrega 70 %, envío +$2).
2. **Cinco criterios calificados 1–5**, con evidencia revisada en la ficha y las fotos reales: riesgo operativo y de devoluciones,
   políticas de Meta y promesas, facilidad de anuncio y de conversación, calidad de la ficha de Rocketfy (descripción, fotos usables, stock)
   y encaje con la clase/portafolio (hogar, combo, ticket).
3. **Cuatro ponderaciones** (balanceada, margen, riesgo y clase) para ver si el resultado depende de mis preferencias.

## Resultado (puntaje /100; entre paréntesis, posición)
| Producto | Cierre mín. base / estrés | Balanceado | Margen | Riesgo | Clase | Rango medio |
|---|---|---|---|---|---|---|
| Set 3 en 1 bowl+colador+rallador | 5,2 % / 11,1 % | 78,2 (1) | 71,3 (5) | 82,1 (1) | 84,1 (1) | **2,00** |
| Lámpara solar de pared decorativa | 4,7 % / 9,2 % | 78,1 (2) | 74,8 (3) | 78,7 (2) | 80,7 (2) | **2,25** |
| Set de ollas 13 pzs | 3,4 % / 6,5 % | 75,9 (3) | 78,1 (2) | 75,2 (4) | 76,2 (4) | 3,25 |
| Tendedero de pared inoxidable | 4,7 % / 9,2 % | 75,1 (4) | 72,8 (4) | 76,7 (3) | 77,7 (3) | 3,50 |
| Mega linterna LED recargable | **2,7 % / 5,0 %** | 72,6 (5) | **81,3 (1)** | 65,7 (8) | 69,7 (7) | 5,25 |
| Cinta anti grietas | 6,0 % / 13,1 % | 69,7 (6) | 60,8 (6) | 73,1 (5) | 75,1 (5) | 5,50 |
| Sellador al vacío | 5,5 % / 12,4 % | 66,6 (7) | 60,0 (7) | 70,4 (6) | 71,4 (6) | 6,50 |
| Luz LED solar ×2 | 5,5 % / 12,1 % | 63,0 (8) | 56,8 (8) | 66,7 (7) | 67,7 (8) | 7,75 |
| Depilador 2 en 1 | 5,5 % / 12,3 % | 51,8 (9) | 48,2 (9) | 54,5 (10) | 50,5 (10) | 9,50 |
| Aspiradora inalámbrica | 6,7 % / 18,7 % | 50,2 (11) | 44,3 (11) | 54,1 (11) | 57,1 (9) | 10,50 |
| Mochila impermeable USB | 6,1 % / 14,8 % | 50,4 (10) | 42,4 (12) | 61,0 (9) | 49,0 (12) | 10,75 |
| Almohada para parejas | 6,1 % / 17,1 % | 47,4 (12) | 44,4 (10) | 49,0 (12) | 50,0 (11) | 11,25 |

Hallazgos que pesaron en el puntaje (verificados en las fichas):
- La foto principal de la **mochila, la aspiradora y la luz solar ×2** es un **banner de Rocketfy con su logo y su teléfono**; no se puede usar en anuncios ni en WhatsApp.
  La mochila y la aspiradora **no tienen descripción**.
- El **depilador** es un producto muy repetido en Latinoamérica (señal débil de precios bajos en otros países: no verificado para Ecuador) y sus anuncios
  chocan con promesas de piel («indolora», «sin irritaciones»).
- Las fotos de la **linterna** muestran un haz retocado: riesgo de «no es como se ve» (devoluciones) y de reclamos engañosos en Meta.
- El **set 3 en 1** declara 0,15 kg: parece poco para tres piezas de acero de 23 cm; **verificar el peso real** (afecta el envío).
- Señal débil de precio: en tiendas de Perú se vio un set 3 en 1 equivalente a ~S/ 39 (≈ $10, conversión mía, sin verificar); el precio de $30 puede
  chocar con la percepción de valor. Probar también $24,99.

## Los 3 ganadores y el orden
| Orden | Producto | SKU | Rol | Precio de partida | Cierre mín. (base) |
|---|---|---|---|---|---|
| **1 (piloto)** | Set 3 en 1 bowl+colador+rallador | `2067-BOWL-COLADORRALLADOR` | Estabilidad/volumen: el de menor riesgo, mejor ficha, hogar + combo | $29,99 (probar $24,99) | 5,2 % |
| **2** | Lámpara solar de pared decorativa | `LAMP-SOLA-PARE-DECO` | Impacto visual: el mejor material para anuncio (3 fotos de calidad); margen alto con costo de $3,87 | $29,99 | 4,7 % |
| **3** | Mega linterna LED recargable | `MEGALINTERNALEDRECARGABLE` | Apuesta de **margen**: sobrevive a un cierre bajo de Victoria; pide cuidado con las promesas | $49,99 (el sugerido es $59,99) | 2,7 % (3,9 % a $49,99) |

De reserva, en este orden: set de ollas 13 pzs (`SET-OLLA-13PC`, solo 1 foto y 293 de stock) y tendedero de pared (`TEND-PARE-INOX`).
Salen de la lista anterior: depilador, mochila y aspiradora (puntajes ≈ 50: ficha pobre, banners de Rocketfy y/o margen más fino); el sellador queda reserva lejana.

## Plan (adaptado del 11-nov) y reglas propuestas
1. **Antes de publicar** (por producto): confirmar que no es «Black» en Rocketfy; precio de la competencia en Ecuador; peso real; subir 3–5 fotos propias
   a la galería (sin banners de Rocketfy); tiempo de entrega, preguntas frecuentes y «Ajustes de precios» confirmados; «Probar con Victoria».
2. **Piloto (3 días, $10 al día, solo el producto 1; ≈ $30):** medir el cierre real de Victoria y arreglar fallos de la conversación.
3. **Prueba (5 días, $15 al día por producto, los 3 a la vez; ≈ $225):** una campaña por producto, 3 anuncios con enfoques distintos.
4. **Reglas propuestas (derivadas de la tabla, no medidas):** parar un producto si tras ≥ 60 conversaciones el cierre es < 3 %; mantenerlo si es ≥ 6 %;
   entre 3 % y 6 %, extender 2 días. Escalar solo al ganador, y solo si el cierre supera su mínimo con holgura.
5. **La tasa de entrega NO se mide en esos 5 días:** a $15 diarios se necesitan ~2 semanas por producto para llegar a 20 pedidos y luego varios días de
   entrega. La prueba mide cierre y costo por pedido; la entrega se valida con el ganador (regla de los 20 pedidos de la clase).

## Lo que sigue sin saberse
Demanda real y tasa de entrega; precios de la competencia en Ecuador; qué es «Black»; el envío real por ciudad y peso; los supuestos de
$0,60 por conversación, 8 % de cierre y 80 % de entrega (la clase habla de un CPA de $2–4, que no se pudo comparar con este modelo).
