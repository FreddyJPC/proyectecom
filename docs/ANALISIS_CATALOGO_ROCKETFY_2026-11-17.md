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
