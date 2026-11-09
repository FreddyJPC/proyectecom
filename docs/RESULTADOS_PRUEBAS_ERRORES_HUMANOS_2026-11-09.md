# Resultados — pruebas de Victoria con errores humanos (IA real)

**Fecha:** 2026-11-09 · **Pendiente que cierra (en parte):** #74 de `PROGRESS.md` · **Lista de casos:**
[`PRUEBAS_CON_ERRORES_HUMANOS.md`](PRUEBAS_CON_ERRORES_HUMANOS.md) · **Salida cruda completa, sin tocar:**
[`RESULTADOS_PRUEBAS_ERRORES_HUMANOS_2026-11-09_SALIDA_COMPLETA.txt`](RESULTADOS_PRUEBAS_ERRORES_HUMANOS_2026-11-09_SALIDA_COMPLETA.txt)

## Para qué sirve este documento
Dejar escrito, para que no dependa de ninguna conversación, **qué se probó, cómo, qué contestó Victoria en cada caso y qué
conclusiones salen**. Así, cuando se retome el tema, se puede comparar contra esta corrida (por ejemplo después de cambiar las
instrucciones de Victoria) sin repetir el trabajo.

## Resumen
**11 de 11 casos sin fallos observados** (10 pasaron completos; S11 pasó en lo que el guion permite comprobar). Los cuatro casos que
el pendiente pedía mirar con más cuidado —S1 (ciudad mal escrita), S5 (corrección y vuelta a confirmar), S6 (ciudad y provincia que no
cuadran) y S10 (mensajes ambiguos)— salieron bien. Nunca cerró una venta sin el «sí» del cliente al resumen.

| Caso | Situación | Resultado |
|---|---|---|
| S1 | Compra completa con faltas y ciudad mal escrita | Pasó |
| S2 | No sabe el nombre del producto | Pasó (despedida doble al escalar) |
| S3 | Palabras pegadas, letras comidas | Pasó (pregunta doble) |
| S4 | Mensajes en pedacitos | Pasó (asumió 1 unidad, y lo dijo) |
| S5 | Confirmaciones informales y correcciones | Pasó |
| S6 | Ciudad y provincia que no cuadran | Pasó (no guardó ni nombre ni dirección) |
| S7 | Pide una persona, con errores | Pasó |
| S8 | No quiere más mensajes | Pasó |
| S11 | Errores evidentes que NO se deben preguntar | Pasó en parte (el guion no llega al resumen) |
| S9 | Abreviaturas y jerga | Pasó (a confirmar: «envíos a todo el país») |
| S10 | Respuestas vacías o ambiguas | Pasó |

## Cómo se corrió (para poder repetirlo)
- **Código probado:** `main` en el commit `d1c164c` (fusión del PR #32). Es el mismo commit que corre en Railway (despliegue
  `2b597281`, `SUCCESS`, 2026-11-09 21:22 UTC).
- **Comando:** `python tools/pruebas_con_errores_humanos.py --real` desde `backend/`, con un entorno **limpio** (`env -i`): variables
  falsas para todo lo que no es la IA, `SUPABASE_DB_URL` apuntando a un **Postgres local desechable** (puerto 5433, PostgreSQL 16) y
  `ANTHROPIC_API_KEY` tomada de la clave de pruebas de la sesión (`ANTHROPIC_API_KEY_PRUEBAS`; el valor no se escribió en ningún
  archivo). Ninguna variable ni dato de producción intervino.
- **Qué es real y qué es de mentira:** la IA (Anthropic) es **real**. El producto («Audífonos Bluetooth», SKU `AUD-BT-001`, negro y
  blanco, $24.99, envío incluido, hasta 3 unidades), el pedido de Rocketfy y el aviso de Telegram son **simulados**; no se envió ni se
  guardó nada real (es la misma simulación de «Probar con Victoria»).
- **Antes de la corrida real** se corrió `--seco` (IA falsa) para comprobar que el guion funciona: los 11 casos corrieron sin error.
  Esa salida no se guardó (son solo «respuesta de prueba»).
- **Pruebas automáticas en el mismo entorno:** `python -m pytest -q` → **2010 pasaron, 0 fallaron** (26,77 s), con las migraciones 001 a
  027 aplicadas en la base local.
- **Comprobaciones de solo lectura sobre producción ese día:** la migración `027_confirmacion_de_datos.sql` figura aplicada en
  Supabase (2026-11-09 21:21 UTC, un minuto **antes** del despliegue) y el despliegue de Railway arrancó sano (`/health` 200, bot y
  scheduler con sus seis tareas, sin errores).

## Límites de esta corrida (qué NO se puede concluir)
1. **Una sola vez por caso.** La IA no responde igual cada vez; un caso que pasó hoy podría fallar otro día.
2. **Instrucciones y parámetros por defecto.** El entorno de prueba tenía la base vacía, así que Victoria usó el texto original
   (`victoria_system_prompt.txt`) y los valores por defecto del código. Si en producción se guardaron instrucciones o parámetros
   distintos desde la app (Control → Instrucciones / Parámetros), el comportamiento real podría diferir. **Eso no se comparó.**
3. **Producto inventado**, no un producto del catálogo real; y **no se probó WhatsApp real** ni la espera de ráfagas de 5 s con un
   cliente de verdad.
4. **El modelo de IA exacto y el costo** no los registra el script; no los medí. El script indica «unos centavos».
5. **S11** no llega al resumen y **S5** solo usa «dale» (no «👍» ni «ta bien»).
6. La salida del script **recorta** los resultados largos de las herramientas (se ve «-> SKU: … / Méto»); eso es del script al
   imprimir, no de Victoria.

## Observaciones generales
- Victoria llama `registrar_producto` en casi cada turno repitiendo los mismos datos y el total siempre fue el mismo ($24.99 por
  unidad, calculado por el código). No se vio ningún efecto dañino en la simulación; no se probó qué pasa con un pedido real.
- Usa `clasificar_lead` con frecuencia (tibio → caliente → perdido) y **nunca se lo menciona al cliente**, como pide la herramienta.
- Las reglas del código funcionaron como red de seguridad: el total y el stock los puso el código, el par ciudad–provincia
  incoherente no se guardó (S6) y la venta no se cerró sin confirmar (S1 y S5).

## Pendientes que salen de esta corrida
1. **Decidir** si agregar a las instrucciones de Victoria un párrafo sobre interpretar errores de escritura sin corregirlos.
   Recomendación: **no hace falta ahora**; ya lo hace bien. Revisar de nuevo si en uso real aparecen fallos.
2. **Confirmar** si es cierto «hacemos envíos a todo el país» (S9) y, si no lo es, corregir las instrucciones.
3. **Pulir** la despedida doble al escalar (S2) y la pregunta doble (S3).
4. **Repetir** la lista varias veces y con un producto real del catálogo, y comparar con las instrucciones que realmente están
   guardadas en producción.
5. Valorar si, en S6, Victoria debería guardar el nombre y la dirección ya claros aunque falte aclarar la provincia.

## Resultados por caso

### S1 — Compra completa con faltas de ortografía y ciudad mal escrita

**Veredicto:** PASÓ

**Qué debe pasar** (de `PRUEBAS_CON_ERRORES_HUMANOS.md`): Entiende el producto; corrige «guayakil» → Guayaquil sin preguntar (y deduce Guayas); el resumen dice «Guayaquil, Guayas» y el «sip» lo confirma; solo entonces cierra.

**Qué hizo Victoria:**
- Entendió «blutu» y «kiero» y consultó la ficha del producto (`ver_ficha_producto`).
- Con «el negro xfa, 2» registró 2 × negro; el total **$49.98** lo calculó el código (la herramienta devolvió «no lo cambies»).
- Con «guayakil, provincia guayas» llamó `guardar_datos_cliente` con cantón **Guayaquil** y provincia **Guayas**, sin preguntarle nada al cliente.
- Con «cuando llege pago» registró contraentrega y llamó `mostrar_resumen_para_confirmar`; el resumen mostró «Guayaquil, Guayas» bien escrito.
- Solo después de «sip todo bien» llamó `confirmar_datos_envio` y luego `cerrar_venta`.

**Observaciones:**
- Ninguna relacionada con el criterio. Estado final: pedido SÍ, confirmado SÍ (simulado: el pedido de Rocketfy y el aviso de Telegram son de mentira).

**Estado final guardado:** `nombre='Maria Jose Pacheco' direccion='Cdla Kennedy Mz 5 Villa 3' canton='Guayaquil' provincia='Guayas' producto='AUD-BT-001' cant=2 variante='Negro' pago='contraentrega' pedido=SI confirmado=SI`

**Salida completa de este caso (textual):**

```text
S1 — Compra completa con faltas de ortografía y ciudad mal escrita
Esperado: Corrige «guayakil» a Guayaquil sin preguntar, muestra el resumen con «Guayaquil, Guayas» y cierra tras el «sip».
------------------------------------------------------------------------------
CLIENTE : 'ola kiero unos audifonos blutu'
  [herramienta] ver_ficha_producto {'producto_sku': 'AUD-BT-001'}
                -> SKU: AUD-BT-001 / Nombre: Audífonos Bluetooth / Descripción: Audífonos inalámbricos con 20 horas de batería, micrófono integrado y estuche de carga. No tienen cable. / Precio por unidad: $24.99 / Tiempo de entrega: 2 a 4 días hábiles / Méto
  [herramienta] clasificar_lead {'temperatura': 'tibio', 'motivo': 'Mostró interés directo preguntando por el producto'}
                -> Clasificación registrada. No se lo menciones al cliente y sigue con la conversación.
VICTORIA: ¡Hola! 😊 Claro que sí, tenemos los Audífonos Bluetooth a $24.99.

Vienen con estuche de carga, 20 horas de batería y micrófono integrado. ¿Los quiere en negro o blanco?

¿Me confirma también su nombre completo y la dirección a donde se los enviamos? 📦
CLIENTE : 'cuanto cuestan? y q colores ay'
  [herramienta] ver_ficha_producto {'producto_sku': 'AUD-BT-001'}
                -> SKU: AUD-BT-001 / Nombre: Audífonos Bluetooth / Descripción: Audífonos inalámbricos con 20 horas de batería, micrófono integrado y estuche de carga. No tienen cable. / Precio por unidad: $24.99 / Tiempo de entrega: 2 a 4 días hábiles / Méto
VICTORIA: Cuestan $24.99 cada uno, y el envío ya está incluido 🙌

Vienen en color negro o blanco, ¿cuál prefiere?
CLIENTE : 'el negro xfa, 2'
  [herramienta] registrar_producto {'producto_sku': 'AUD-BT-001', 'producto_nombre': 'Audífonos Bluetooth', 'variante': 'negro', 'cantidad': 2}
                -> Producto registrado: 2 x Audífonos Bluetooth. Total a cobrar: $49.98. Ese es el monto exacto que debes comunicarle al cliente; no lo cambies.
  [herramienta] clasificar_lead {'temperatura': 'caliente', 'motivo': 'Confirmó producto, color y cantidad, listo para comprar'}
                -> Clasificación registrada. No se lo menciones al cliente y sigue con la conversación.
VICTORIA: ¡Listo! 2 audífonos Bluetooth color negro 🎧

El total es **$49.98** (envío incluido).

Ahora, para el envío, ¿me confirma:
- Su nombre completo
- Dirección exacta
- Cantón y provincia?
CLIENTE : 'mi nombre es maria jose pacheco, vivo en guayakil, provincia guayas, en la cdla kennedy mz 5 villa 3'
  [herramienta] registrar_producto {'producto_sku': 'AUD-BT-001', 'producto_nombre': 'Audífonos Bluetooth', 'cantidad': 2, 'variante': 'Negro'}
                -> Producto registrado: 2 x Audífonos Bluetooth. Total a cobrar: $49.98. Ese es el monto exacto que debes comunicarle al cliente; no lo cambies.
  [herramienta] guardar_datos_cliente {'nombre_cliente': 'Maria Jose Pacheco', 'direccion': 'Cdla Kennedy Mz 5 Villa 3', 'canton': 'Guayaquil', 'provincia': 'Guayas'}
                -> Datos guardados correctamente.
  [herramienta] clasificar_lead {'temperatura': 'caliente', 'motivo': 'Confirmó producto, cantidad, variante y dio sus datos de envío'}
                -> Clasificación registrada. No se lo menciones al cliente y sigue con la conversación.
VICTORIA: ¡Perfecto, María José! Ya quedó registrado todo 📝

Confirmado: 2 audífonos Bluetooth negros, total **$49.98** (envío incluido).

Ahora, ¿cómo prefiere pagar: contraentrega o por transferencia?
CLIENTE : 'cuando llege pago'
  [herramienta] registrar_producto {'producto_sku': 'AUD-BT-001', 'producto_nombre': 'Audífonos Bluetooth', 'cantidad': 2, 'variante': 'Negro'}
                -> Producto registrado: 2 x Audífonos Bluetooth. Total a cobrar: $49.98. Ese es el monto exacto que debes comunicarle al cliente; no lo cambies.
  [herramienta] registrar_metodo_pago {'metodo_pago': 'contraentrega'}
                -> Método de pago registrado.
  [herramienta] clasificar_lead {'temperatura': 'caliente', 'motivo': 'Confirmó producto, cantidad, datos de envío y forma de pago'}
                -> Clasificación registrada. No se lo menciones al cliente y sigue con la conversación.
  [herramienta] mostrar_resumen_para_confirmar 
                -> Envíale al cliente este resumen tal cual (puedes agregar un saludo breve) y espera su respuesta. No cierres la venta todavía. Si responde que sí, usa confirmar_datos_envio; si quiere corregir algo, guarda el cambio y vuelve a usar
VICTORIA: Perfecto, María José 😊 Para dejar listo su pedido, ¿me confirma que estos datos están correctos?

• Nombre: Maria Jose Pacheco
• Dirección: Cdla Kennedy Mz 5 Villa 3 — Guayaquil, Guayas
• Producto: 2 × Audífonos Bluetooth (Negro)
• Total a pagar: $49.98
• Forma de pago: Contra entrega (paga al recibir)

Si todo está bien, respóndame «sí» ✅
CLIENTE : 'sip todo bien'
  [herramienta] confirmar_datos_envio 
                -> Datos confirmados por el cliente. Ya puedes cerrar la venta con cerrar_venta.
  [herramienta] clasificar_lead {'temperatura': 'caliente', 'motivo': 'Confirmó todos los datos y el pedido para pago contraentrega'}
                -> Clasificación registrada. No se lo menciones al cliente y sigue con la conversación.
  [herramienta] cerrar_venta 
                -> ¡Pedido confirmado! Llega en 2 a 4 días hábiles. Comunícaselo al cliente y agradécele.
VICTORIA: ¡Listo, María José! 🎉 Su pedido quedó confirmado y le llega en 2 a 4 días hábiles a la Cdla Kennedy.

Muchas gracias por su compra, cualquier cosa me escribe 💛
------------------------------------------------------------------------------
ESTADO FINAL: nombre='Maria Jose Pacheco' direccion='Cdla Kennedy Mz 5 Villa 3' canton='Guayaquil' provincia='Guayas' producto='AUD-BT-001' cant=2 variante='Negro' pago='contraentrega' pedido=SI confirmado=SI
```

### S2 — No sabe el nombre del producto

**Veredicto:** PASÓ

**Qué debe pasar** (de `PRUEBAS_CON_ERRORES_HUMANOS.md`): Identifica el producto por la descripción; no inventa; la garantía la pasa a una persona.

**Qué hizo Victoria:**
- Identificó los «audífonos que no tienen cable» con la ficha de «Audífonos Bluetooth».
- «los negros cuanto salen» y «y viene con estuche?» los contestó bien ($24.99; estuche de carga incluido) sin inventar nada.
- Ante «y la garantia cuanto es?» no dio ninguna cifra: llamó `escalar_a_humano` (el producto de la prueba tiene «Garantía» en temas que no debe responder).

**Observaciones:**
- **Despedida doble:** al escalar mandó dos textos seguidos que dicen casi lo mismo («Le voy a comunicar con alguien…» y «Ya le paso su consulta a un asesor…»). Es cosmético; conviene pulirlo.

**Estado final guardado:** `nombre=None direccion=None canton=None provincia=None producto=None cant=1 variante=None pago=None pedido=no confirmado=no`

**Salida completa de este caso (textual):**

```text
S2 — No sabe el nombre del producto
Esperado: Identifica el producto por la descripción («los que no tienen cable») y no inventa datos.
------------------------------------------------------------------------------
CLIENTE : 'buenas tardes tienen esos audifonos q no tienen cable?'
  [herramienta] ver_ficha_producto {'producto_sku': 'AUD-BT-001'}
                -> SKU: AUD-BT-001 / Nombre: Audífonos Bluetooth / Descripción: Audífonos inalámbricos con 20 horas de batería, micrófono integrado y estuche de carga. No tienen cable. / Precio por unidad: $24.99 / Tiempo de entrega: 2 a 4 días hábiles / Méto
VICTORIA: ¡Buenas tardes! 😊 Sí, claro, tenemos los Audífonos Bluetooth, sin cable, inalámbricos.

Cuentan con:
- 20 horas de batería
- Micrófono integrado
- Estuche de carga incluido

Precio: $24.99 c/u
Entrega: 2 a 4 días hábiles, envío incluido 🚚

¿Le interesa llevarlos? Vienen en negro o blanco, ¿cuál prefiere?
CLIENTE : 'los negros cuanto salen'
VICTORIA: ¡Los negros salen en $24.99! 🖤

¿Le gustaría que proceda con el pedido?
CLIENTE : 'y viene con estuche?'
VICTORIA: ¡Sí! Viene con su estuche de carga incluido 📦✨

¿Le gustaría que proceda con el pedido de los negros?
CLIENTE : 'y la garantia cuanto es?'
  [herramienta] ver_ficha_producto {'producto_sku': 'AUD-BT-001'}
                -> SKU: AUD-BT-001 / Nombre: Audífonos Bluetooth / Descripción: Audífonos inalámbricos con 20 horas de batería, micrófono integrado y estuche de carga. No tienen cable. / Precio por unidad: $24.99 / Tiempo de entrega: 2 a 4 días hábiles / Méto
  [herramienta] escalar_a_humano {'motivo': 'Cliente pregunta por garantía del producto, tema que no debo responder'}
                -> Escalado correctamente. Este es tu último mensaje — despídete cordialmente informando que un asesor la va a contactar en breve.
  [herramienta] clasificar_lead {'temperatura': 'tibio', 'motivo': 'Interesado en el producto pero pregunta por garantía antes de decidir'}
                -> Clasificación registrada. No se lo menciones al cliente y sigue con la conversación.
VICTORIA: Mire, el tema de garantía lo maneja directamente un asesor para darle la información correcta 🙏 Le voy a comunicar con alguien que le ayude con eso.

Ya le paso su consulta a un asesor para que le confirme el tema de la garantía 👍 En un momento se comunica con usted. ¡Que tenga buena tarde! 😊
  (conversación escalada a una persona)
------------------------------------------------------------------------------
ESTADO FINAL: nombre=None direccion=None canton=None provincia=None producto=None cant=1 variante=None pago=None pedido=no confirmado=no
```

### S3 — Palabras pegadas y letras comidas

**Veredicto:** PASÓ

**Qué debe pasar** (de `PRUEBAS_CON_ERRORES_HUMANOS.md`): Entiende nombre, ciudad y cantidad; responde a «tan caro» sin inventar descuentos.

**Qué hizo Victoria:**
- De «mellamo juan perez vivoen cuenca azuay» guardó nombre **Juan Perez**, cantón **Cuenca**, provincia **Azuay**.
- A «xq tan caro mm» respondió resaltando lo que incluye (batería, micrófono, estuche, envío incluido) **sin ofrecer descuentos**.
- Con «kiero 1 nomas blanco» registró 1 × blanco, total $24.99, y pidió la dirección exacta (aún faltaba).

**Observaciones:**
- **Pregunta doble:** al responder lo del precio cerró con dos preguntas casi iguales («¿Le gustaría llevarlos?» y «¿Le parece bien el precio o tiene alguna otra duda?»). Cosmético.

**Estado final guardado:** `nombre='Juan Perez' direccion=None canton='Cuenca' provincia='Azuay' producto='AUD-BT-001' cant=1 variante='blanco' pago=None pedido=no confirmado=no`

**Salida completa de este caso (textual):**

```text
S3 — Palabras pegadas y letras comidas
Esperado: Entiende «quierocomprarlo», «mellamo juan», «vivoen cuenca».
------------------------------------------------------------------------------
CLIENTE : 'holaquiero comprarlos audifonos'
  [herramienta] ver_ficha_producto {'producto_sku': 'AUD-BT-001'}
                -> SKU: AUD-BT-001 / Nombre: Audífonos Bluetooth / Descripción: Audífonos inalámbricos con 20 horas de batería, micrófono integrado y estuche de carga. No tienen cable. / Precio por unidad: $24.99 / Tiempo de entrega: 2 a 4 días hábiles / Méto
VICTORIA: ¡Hola! Qué bien 😊 Los Audífonos Bluetooth están en $24.99, traen estuche de carga y 20 horas de batería.

¿Los quiere en negro o blanco?
CLIENTE : 'mellamo juan perez vivoen cuenca azuay'
  [herramienta] guardar_datos_cliente {'nombre_cliente': 'Juan Perez', 'canton': 'Cuenca', 'provincia': 'Azuay'}
                -> Datos guardados correctamente.
  [herramienta] clasificar_lead {'temperatura': 'caliente', 'motivo': 'Ya dio su nombre y ubicación para el envío'}
                -> Clasificación registrada. No se lo menciones al cliente y sigue con la conversación.
VICTORIA: Gracias, Juan 🙌

Me falta la dirección exacta donde le entregamos (calle, número, referencia).

Y una cosita más: ¿los audífonos los quiere en negro o blanco?
CLIENTE : 'xq tan caro mm'
  [herramienta] ver_ficha_producto {'producto_sku': 'AUD-BT-001'}
                -> SKU: AUD-BT-001 / Nombre: Audífonos Bluetooth / Descripción: Audífonos inalámbricos con 20 horas de batería, micrófono integrado y estuche de carga. No tienen cable. / Precio por unidad: $24.99 / Tiempo de entrega: 2 a 4 días hábiles / Méto
  [herramienta] clasificar_lead {'temperatura': 'tibio', 'motivo': 'Mostró duda por el precio, aún no confirma compra'}
                -> Clasificación registrada. No se lo menciones al cliente y sigue con la conversación.
VICTORIA: Entiendo, Juan. Pero mire, por ese precio lleva unos audífonos inalámbricos con 20 horas de batería, micrófono y su estuche de carga incluido — y el envío ya viene incluido en el precio, no paga nada extra 😊

¿Le gustaría llevarlos?

¿Le parece bien el precio o tiene alguna otra duda?
CLIENTE : 'kiero 1 nomas blanco'
  [herramienta] registrar_producto {'producto_sku': 'AUD-BT-001', 'producto_nombre': 'Audífonos Bluetooth', 'variante': 'blanco', 'cantidad': 1}
                -> Producto registrado: 1 x Audífonos Bluetooth. Total a cobrar: $24.99. Ese es el monto exacto que debes comunicarle al cliente; no lo cambies.
  [herramienta] clasificar_lead {'temperatura': 'caliente', 'motivo': 'Confirmó producto, variante y cantidad, quiere comprar'}
                -> Clasificación registrada. No se lo menciones al cliente y sigue con la conversación.
VICTORIA: ¡Listo! 1 audífono Bluetooth blanco, total $24.99 😊

Ahora me falta su dirección exacta para el envío (calle, número, referencia).
------------------------------------------------------------------------------
ESTADO FINAL: nombre='Juan Perez' direccion=None canton='Cuenca' provincia='Azuay' producto='AUD-BT-001' cant=1 variante='blanco' pago=None pedido=no confirmado=no
```

### S4 — Mensajes en pedacitos (llegan juntos tras la espera)

**Veredicto:** PASÓ

**Qué debe pasar** (de `PRUEBAS_CON_ERRORES_HUMANOS.md`): Responde **una** vez a todo junto, sin repetir el saludo.

**Qué hizo Victoria:**
- Recibió los cinco pedacitos como un solo mensaje y mandó **una sola respuesta** con un solo saludo («¡Hola, buenas tardes!»).
- Registró el producto en blanco y pidió nombre, dirección, cantón y provincia.

**Observaciones:**
- El cliente escribió «los blancos» (plural) y Victoria asumió **1 unidad**. Lo dijo abiertamente («Le anoto 1 unidad…»), así que el cliente puede corregirla; pero la cantidad real no estaba clara.

**Estado final guardado:** `nombre=None direccion=None canton=None provincia=None producto='AUD-BT-001' cant=1 variante='blanco' pago=None pedido=no confirmado=no`

**Salida completa de este caso (textual):**

```text
S4 — Mensajes en pedacitos (llegan juntos tras la espera)
Esperado: Responde UNA vez a todo junto, sin repetir el saludo ni perderse.
------------------------------------------------------------------------------
CLIENTE : 'Hola\nbuenas tardes\nquiero\nunos audifonos\nlos blancos'
  [herramienta] ver_ficha_producto {'producto_sku': 'AUD-BT-001'}
                -> SKU: AUD-BT-001 / Nombre: Audífonos Bluetooth / Descripción: Audífonos inalámbricos con 20 horas de batería, micrófono integrado y estuche de carga. No tienen cable. / Precio por unidad: $24.99 / Tiempo de entrega: 2 a 4 días hábiles / Méto
  [herramienta] registrar_producto {'producto_sku': 'AUD-BT-001', 'producto_nombre': 'Audífonos Bluetooth', 'variante': 'Blanco'}
                -> Producto registrado: 1 x Audífonos Bluetooth. Total a cobrar: $24.99. Ese es el monto exacto que debes comunicarle al cliente; no lo cambies.
  [herramienta] clasificar_lead {'temperatura': 'caliente', 'motivo': 'Confirmó producto y variante, quiere comprar ya'}
                -> Clasificación registrada. No se lo menciones al cliente y sigue con la conversación.
VICTORIA: ¡Hola, buenas tardes! 😊 Sí, tenemos los Audífonos Bluetooth en blanco, a $24.99.

Le anoto 1 unidad de los Audífonos Bluetooth blancos, total **$24.99**, y el envío ya viene incluido 🙌

Para coordinar el envío, ¿me regala su nombre completo, dirección, cantón y provincia?
------------------------------------------------------------------------------
ESTADO FINAL: nombre=None direccion=None canton=None provincia=None producto='AUD-BT-001' cant=1 variante='blanco' pago=None pedido=no confirmado=no
```

### S5 — Respuestas de confirmación informales

**Veredicto:** PASÓ

**Qué debe pasar** (de `PRUEBAS_CON_ERRORES_HUMANOS.md`): Al corregir la dirección **vuelve a mostrar el resumen**; «dale» cuenta como sí y recién ahí cierra.

**Qué hizo Victoria:**
- Guardó a Ana López, «Av. Amazonas N34-12 y Atahualpa», Quito, Pichincha, y con «contraentrega» mostró el primer resumen.
- Ante «no, la direccion es av. 10 de agosto y colon» guardó la dirección nueva y **volvió a mostrar el resumen** con «Av. 10 de Agosto y Colón — Quito, Pichincha».
- Con «dale» llamó `confirmar_datos_envio` y recién ahí `cerrar_venta`.

**Observaciones:**
- El guion de este caso solo usa «dale» como confirmación. Los otros ejemplos de la descripción del script («👍», «ta bien») **no se probaron** con un resumen pendiente (el 👍 solo aparece en S10, sin resumen).

**Estado final guardado:** `nombre='Ana López' direccion='Av. 10 de Agosto y Colón' canton='Quito' provincia='Pichincha' producto='AUD-BT-001' cant=1 variante='Negro' pago='contraentrega' pedido=SI confirmado=SI`

**Salida completa de este caso (textual):**

```text
S5 — Respuestas de confirmación informales
Esperado: Entiende «dale», «👍», «ta bien» como sí; un «no, la direccion es otra» como corrección y vuelve a confirmar.
------------------------------------------------------------------------------
CLIENTE : 'quiero 1 audifono negro'
  [herramienta] ver_ficha_producto {'producto_sku': 'AUD-BT-001'}
                -> SKU: AUD-BT-001 / Nombre: Audífonos Bluetooth / Descripción: Audífonos inalámbricos con 20 horas de batería, micrófono integrado y estuche de carga. No tienen cable. / Precio por unidad: $24.99 / Tiempo de entrega: 2 a 4 días hábiles / Méto
  [herramienta] registrar_producto {'producto_sku': 'AUD-BT-001', 'producto_nombre': 'Audífonos Bluetooth', 'variante': 'Negro', 'cantidad': 1}
                -> Producto registrado: 1 x Audífonos Bluetooth. Total a cobrar: $24.99. Ese es el monto exacto que debes comunicarle al cliente; no lo cambies.
  [herramienta] clasificar_lead {'temperatura': 'caliente', 'motivo': 'Confirmó producto, variante y cantidad directamente'}
                -> Clasificación registrada. No se lo menciones al cliente y sigue con la conversación.
VICTORIA: ¡Perfecto! Le registro 1 audífono Bluetooth negro 🎧

Total: $24.99 (envío incluido)

Para el envío, ¿me regala su nombre completo, dirección, cantón y provincia? 😊
CLIENTE : 'ana lopez, quito pichincha, av amazonas n34-12 y atahualpa'
  [herramienta] registrar_producto {'producto_sku': 'AUD-BT-001', 'producto_nombre': 'Audífonos Bluetooth', 'cantidad': 1, 'variante': 'Negro'}
                -> Producto registrado: 1 x Audífonos Bluetooth. Total a cobrar: $24.99. Ese es el monto exacto que debes comunicarle al cliente; no lo cambies.
  [herramienta] guardar_datos_cliente {'nombre_cliente': 'Ana López', 'direccion': 'Av. Amazonas N34-12 y Atahualpa', 'canton': 'Quito', 'provincia': 'Pichincha'}
                -> Datos guardados correctamente.
  [herramienta] clasificar_lead {'temperatura': 'caliente', 'motivo': 'Confirmó producto y dio todos sus datos de envío'}
                -> Clasificación registrada. No se lo menciones al cliente y sigue con la conversación.
VICTORIA: ¡Listo, Ana! Ya tengo sus datos 📝

Ahora, ¿cómo prefiere pagar: contraentrega o transferencia?
CLIENTE : 'contraentrega'
  [herramienta] registrar_producto {'producto_sku': 'AUD-BT-001', 'producto_nombre': 'Audífonos Bluetooth', 'variante': 'Negro', 'cantidad': 1}
                -> Producto registrado: 1 x Audífonos Bluetooth. Total a cobrar: $24.99. Ese es el monto exacto que debes comunicarle al cliente; no lo cambies.
  [herramienta] registrar_metodo_pago {'metodo_pago': 'contraentrega'}
                -> Método de pago registrado.
  [herramienta] clasificar_lead {'temperatura': 'caliente', 'motivo': 'Confirmó producto, datos de envío y método de pago'}
                -> Clasificación registrada. No se lo menciones al cliente y sigue con la conversación.
  [herramienta] mostrar_resumen_para_confirmar 
                -> Envíale al cliente este resumen tal cual (puedes agregar un saludo breve) y espera su respuesta. No cierres la venta todavía. Si responde que sí, usa confirmar_datos_envio; si quiere corregir algo, guarda el cambio y vuelve a usar
VICTORIA: Para dejar listo su pedido, ¿me confirma por favor que estos datos están correctos?

• Nombre: Ana López
• Dirección: Av. Amazonas N34-12 y Atahualpa — Quito, Pichincha
• Producto: 1 × Audífonos Bluetooth (Negro)
• Total a pagar: $24.99
• Forma de pago: Contra entrega (paga al recibir)

¿Está todo correcto? 😊
CLIENTE : 'no, la direccion es av. 10 de agosto y colon'
  [herramienta] guardar_datos_cliente {'direccion': 'Av. 10 de Agosto y Colón'}
                -> Datos guardados correctamente.
  [herramienta] mostrar_resumen_para_confirmar 
                -> Envíale al cliente este resumen tal cual (puedes agregar un saludo breve) y espera su respuesta. No cierres la venta todavía. Si responde que sí, usa confirmar_datos_envio; si quiere corregir algo, guarda el cambio y vuelve a usar
VICTORIA: Ya corregí la dirección 👍

Entonces le confirmo:

• Nombre: Ana López
• Dirección: Av. 10 de Agosto y Colón — Quito, Pichincha
• Producto: 1 × Audífonos Bluetooth (Negro)
• Total a pagar: $24.99
• Forma de pago: Contra entrega (paga al recibir)

¿Está todo correcto? 😊
CLIENTE : 'dale'
  [herramienta] guardar_datos_cliente {'nombre_cliente': 'Ana López', 'direccion': 'Av. 10 de Agosto y Colón', 'canton': 'Quito', 'provincia': 'Pichincha'}
                -> Datos guardados correctamente.
  [herramienta] confirmar_datos_envio 
                -> Datos confirmados por el cliente. Ya puedes cerrar la venta con cerrar_venta.
  [herramienta] clasificar_lead {'temperatura': 'caliente', 'motivo': 'Confirmó el resumen y método de pago, listo para cerrar'}
                -> Clasificación registrada. No se lo menciones al cliente y sigue con la conversación.
  [herramienta] cerrar_venta 
                -> ¡Pedido confirmado! Llega en 2 a 4 días hábiles. Comunícaselo al cliente y agradécele.
VICTORIA: ¡Listo, Ana! Su pedido quedó confirmado 🎉

Le llega en 2 a 4 días hábiles a su dirección en Quito. Paga contraentrega cuando lo reciba.

¡Muchas gracias por su compra! Cualquier cosa, aquí estoy 😊
------------------------------------------------------------------------------
ESTADO FINAL: nombre='Ana López' direccion='Av. 10 de Agosto y Colón' canton='Quito' provincia='Pichincha' producto='AUD-BT-001' cant=1 variante='Negro' pago='contraentrega' pedido=SI confirmado=SI
```

### S6 — Ciudad y provincia que no cuadran

**Veredicto:** PASÓ

**Qué debe pasar** (de `PRUEBAS_CON_ERRORES_HUMANOS.md`): No guarda «Quito, Guayas» (no cuadra: Quito es de Pichincha); le pregunta con naturalidad cuál es la correcta, sin inventar.

**Qué hizo Victoria:**
- No llamó `guardar_datos_cliente`: **no guardó el par incoherente**.
- Respondió: «usted puso Quito, pero Quito pertenece a la provincia de **Pichincha**, no Guayas. ¿Me confirma cuál es correcto?».

**Observaciones:**
- Al no guardar nada, el nombre («Pedro Ruiz») y la dirección («calle 9 de octubre 123»), que sí estaban claros, **tampoco quedaron guardados** (estado final: todo vacío salvo el producto). El texto sigue en la conversación, así que se recupera en el siguiente turno, pero conviene tenerlo presente.

**Estado final guardado:** `nombre=None direccion=None canton=None provincia=None producto='AUD-BT-001' cant=1 variante='blanco' pago=None pedido=no confirmado=no`

**Salida completa de este caso (textual):**

```text
S6 — Ciudad y provincia que no cuadran
Esperado: No guarda «Quito, Guayas» (no cuadra); pregunta cuál es la correcta sin inventar.
------------------------------------------------------------------------------
CLIENTE : 'quiero 1 audifono blanco'
  [herramienta] ver_ficha_producto {'producto_sku': 'AUD-BT-001'}
                -> SKU: AUD-BT-001 / Nombre: Audífonos Bluetooth / Descripción: Audífonos inalámbricos con 20 horas de batería, micrófono integrado y estuche de carga. No tienen cable. / Precio por unidad: $24.99 / Tiempo de entrega: 2 a 4 días hábiles / Méto
  [herramienta] registrar_producto {'producto_sku': 'AUD-BT-001', 'producto_nombre': 'Audífonos Bluetooth', 'variante': 'Blanco', 'cantidad': 1}
                -> Producto registrado: 1 x Audífonos Bluetooth. Total a cobrar: $24.99. Ese es el monto exacto que debes comunicarle al cliente; no lo cambies.
  [herramienta] clasificar_lead {'temperatura': 'caliente', 'motivo': 'Confirmó producto, variante y cantidad directamente'}
                -> Clasificación registrada. No se lo menciones al cliente y sigue con la conversación.
VICTORIA: ¡Listo! 🎧 Le registro 1 Audífono Bluetooth en blanco, con estuche de carga incluido. El total es **$24.99** y el envío ya está incluido 😊

Para coordinar el envío, ¿me regala su nombre completo, dirección exacta, cantón y provincia?
CLIENTE : 'soy pedro ruiz, vivo en quito provincia guayas, calle 9 de octubre 123'
  [herramienta] registrar_producto {'producto_sku': 'AUD-BT-001', 'producto_nombre': 'Audífonos Bluetooth', 'variante': 'Blanco', 'cantidad': 1}
                -> Producto registrado: 1 x Audífonos Bluetooth. Total a cobrar: $24.99. Ese es el monto exacto que debes comunicarle al cliente; no lo cambies.
  [herramienta] clasificar_lead {'temperatura': 'caliente', 'motivo': 'Confirmó producto y dio sus datos de envío'}
                -> Clasificación registrada. No se lo menciones al cliente y sigue con la conversación.
VICTORIA: Pedro, una consulta: usted puso Quito, pero Quito pertenece a la provincia de **Pichincha**, no Guayas. ¿Me confirma cuál es correcto? 🙂
------------------------------------------------------------------------------
ESTADO FINAL: nombre=None direccion=None canton=None provincia=None producto='AUD-BT-001' cant=1 variante='blanco' pago=None pedido=no confirmado=no
```

### S7 — Pide hablar con una persona, con errores

**Veredicto:** PASÓ

**Qué debe pasar** (de `PRUEBAS_CON_ERRORES_HUMANOS.md`): Usa «escalar a humano».

**Qué hizo Victoria:**
- Llamó `escalar_a_humano` y se despidió con una sola frase breve. La conversación quedó escalada a una persona.

**Observaciones:**
- Ninguna.

**Estado final guardado:** `nombre=None direccion=None canton=None provincia=None producto=None cant=1 variante=None pago=None pedido=no confirmado=no`

**Salida completa de este caso (textual):**

```text
S7 — Pide hablar con una persona, con errores
Esperado: Usa escalar_a_humano.
------------------------------------------------------------------------------
CLIENTE : 'kiero ablar con una persona porfa'
  [herramienta] escalar_a_humano {'motivo': 'Cliente pidió explícitamente hablar con una persona.'}
                -> Escalado correctamente. Este es tu último mensaje — despídete cordialmente informando que un asesor la va a contactar en breve.
VICTORIA: Listo, ya le aviso a un asesor para que la contacte en breve. ¡Que tenga un buen día! 🙌
  (conversación escalada a una persona)
------------------------------------------------------------------------------
ESTADO FINAL: nombre=None direccion=None canton=None provincia=None producto=None cant=1 variante=None pago=None pedido=no confirmado=no
```

### S8 — No quiere más mensajes

**Veredicto:** PASÓ

**Qué debe pasar** (de `PRUEBAS_CON_ERRORES_HUMANOS.md`): Usa «no contactar» y se despide con amabilidad.

**Qué hizo Victoria:**
- Llamó `no_contactar` y además `clasificar_lead` con temperatura **perdido** y motivo `no_le_interesa`.
- Se despidió con «Entendido, no le molesto más. ¡Que tenga un buen día!».

**Observaciones:**
- Ninguna.

**Estado final guardado:** `nombre=None direccion=None canton=None provincia=None producto=None cant=1 variante=None pago=None pedido=no confirmado=no`

**Salida completa de este caso (textual):**

```text
S8 — No quiere más mensajes
Esperado: Usa no_contactar y se despide con amabilidad.
------------------------------------------------------------------------------
CLIENTE : 'no gracias, ya no me escriban mas porfa'
  [herramienta] no_contactar {'motivo': 'Cliente pidió explícitamente que no le vuelvan a escribir'}
                -> Listo: no se le escribirá por iniciativa nuestra. Despídete con amabilidad y brevedad, sin insistir ni ofrecer nada más. Este es tu último mensaje.
  [herramienta] clasificar_lead {'temperatura': 'perdido', 'motivo': 'Cliente pidió que no le contacten más', 'motivo_perdida': 'no_le_interesa'}
                -> Clasificación registrada. No se lo menciones al cliente y sigue con la conversación.
VICTORIA: Entendido, no le molesto más. ¡Que tenga un buen día! 🙌
------------------------------------------------------------------------------
ESTADO FINAL: nombre=None direccion=None canton=None provincia=None producto=None cant=1 variante=None pago=None pedido=no confirmado=no
```

### S11 — Errores evidentes que no se preguntan

**Veredicto:** PASÓ EN PARTE (lo que se pudo comprobar, pasó)

**Qué debe pasar** (de `PRUEBAS_CON_ERRORES_HUMANOS.md`): Entiende «blanko» = Blanco y «quto» = Quito (con Pichincha) **sin preguntarlo**; el resumen dice «Blanco» y «Quito, Pichincha».

**Qué hizo Victoria:**
- «blanko» → registró variante **Blanco**, sin preguntar.
- «quto» → guardó cantón **Quito** y provincia **Pichincha**, sin preguntar; nombre «Ana» y dirección «Calle 10 y 12».

**Observaciones:**
- **No verificado:** el guion de este caso termina tras dos mensajes, antes de que aparezca el resumen. La parte «el resumen dice Blanco y Quito, Pichincha» no se alcanzó a comprobar aquí (sí se comprobó la misma idea con otra ciudad en S1).

**Estado final guardado:** `nombre='Ana' direccion='Calle 10 y 12' canton='Quito' provincia='Pichincha' producto='AUD-BT-001' cant=1 variante='blanco' pago=None pedido=no confirmado=no`

**Salida completa de este caso (textual):**

```text
S11 — Errores evidentes que no se preguntan
Esperado: «blanko» = Blanco y «quto» = Quito sin preguntar; el resumen los muestra bien escritos.
------------------------------------------------------------------------------
CLIENTE : 'quiero 1 audifono blanko'
  [herramienta] ver_ficha_producto {'producto_sku': 'AUD-BT-001'}
                -> SKU: AUD-BT-001 / Nombre: Audífonos Bluetooth / Descripción: Audífonos inalámbricos con 20 horas de batería, micrófono integrado y estuche de carga. No tienen cable. / Precio por unidad: $24.99 / Tiempo de entrega: 2 a 4 días hábiles / Méto
  [herramienta] registrar_producto {'producto_sku': 'AUD-BT-001', 'producto_nombre': 'Audífonos Bluetooth', 'variante': 'Blanco', 'cantidad': 1}
                -> Producto registrado: 1 x Audífonos Bluetooth. Total a cobrar: $24.99. Ese es el monto exacto que debes comunicarle al cliente; no lo cambies.
  [herramienta] clasificar_lead {'temperatura': 'caliente', 'motivo': 'Cliente confirmó producto, variante y cantidad directamente'}
                -> Clasificación registrada. No se lo menciones al cliente y sigue con la conversación.
VICTORIA: ¡Perfecto! 🎧 Le registré 1 Audífono Bluetooth color blanco, total $24.99 (envío incluido).

Ahora para el envío, ¿me da su nombre completo, dirección exacta, cantón y provincia?
CLIENTE : 'soy ana, vivo en quto, calle 10 y 12'
  [herramienta] registrar_producto {'producto_sku': 'AUD-BT-001', 'producto_nombre': 'Audífonos Bluetooth', 'variante': 'Blanco', 'cantidad': 1}
                -> Producto registrado: 1 x Audífonos Bluetooth. Total a cobrar: $24.99. Ese es el monto exacto que debes comunicarle al cliente; no lo cambies.
  [herramienta] guardar_datos_cliente {'nombre_cliente': 'Ana', 'direccion': 'Calle 10 y 12', 'canton': 'Quito', 'provincia': 'Pichincha'}
                -> Datos guardados correctamente.
  [herramienta] clasificar_lead {'temperatura': 'caliente', 'motivo': 'Dio producto, variante y datos de envío sin dudar'}
                -> Clasificación registrada. No se lo menciones al cliente y sigue con la conversación.
VICTORIA: Gracias, Ana 😊 Ya tengo todo eso.

Ahora, ¿cómo prefiere pagar: contraentrega o por transferencia?
------------------------------------------------------------------------------
ESTADO FINAL: nombre='Ana' direccion='Calle 10 y 12' canton='Quito' provincia='Pichincha' producto='AUD-BT-001' cant=1 variante='blanco' pago=None pedido=no confirmado=no
```

### S9 — Abreviaturas y jerga

**Veredicto:** PASÓ

**Qué debe pasar** (de `PRUEBAS_CON_ERRORES_HUMANOS.md`): Entiende «cnto», «tmb», «dnd»; no se pierde.

**Qué hizo Victoria:**
- «wenas cnto sale el aud blutu» → dio el precio $24.99 y preguntó el color.
- «tmb ay en blanco? dnd lo envian? soy de ambato» → confirmó negro y blanco, entrega de 2 a 4 días, envío incluido.
- «ok x favor 1 blanco» → registró 1 × blanco y guardó cantón **Ambato**, provincia **Tungurahua** (la deducida).

**Observaciones:**
- **A confirmar:** dijo «Hacemos envíos a todo el país». Esa frase **no está en la ficha del producto de la prueba**. Busqué «todo el país», «a nivel nacional» y «todo el ecuador» en `backend/src/routes/whatsapp/` y `backend/src/routes/productos_bot/` y no apareció. Las instrucciones que se guardan desde la app (en la base de datos) **no las consulté**. Antes de dejar que Victoria lo prometa a clientes reales, confirmar si es cierto.

**Estado final guardado:** `nombre=None direccion=None canton='Ambato' provincia='Tungurahua' producto='AUD-BT-001' cant=1 variante='blanco' pago=None pedido=no confirmado=no`

**Salida completa de este caso (textual):**

```text
S9 — Abreviaturas y jerga
Esperado: Entiende «cnto sale», «tmb», «x favor», «dnd» y no se pierde.
------------------------------------------------------------------------------
CLIENTE : 'wenas cnto sale el aud blutu'
  [herramienta] ver_ficha_producto {'producto_sku': 'AUD-BT-001'}
                -> SKU: AUD-BT-001 / Nombre: Audífonos Bluetooth / Descripción: Audífonos inalámbricos con 20 horas de batería, micrófono integrado y estuche de carga. No tienen cable. / Precio por unidad: $24.99 / Tiempo de entrega: 2 a 4 días hábiles / Méto
VICTORIA: ¡Hola! 👋 Los Audífonos Bluetooth están a $24.99 la unidad, con estuche de carga incluido y envío gratis 🚚

¿Le interesa llevar uno? Vienen en negro o blanco, ¿cuál prefiere?
CLIENTE : 'tmb ay en blanco? dnd lo envian? soy de ambato'
  [herramienta] ver_ficha_producto {'producto_sku': 'AUD-BT-001'}
                -> SKU: AUD-BT-001 / Nombre: Audífonos Bluetooth / Descripción: Audífonos inalámbricos con 20 horas de batería, micrófono integrado y estuche de carga. No tienen cable. / Precio por unidad: $24.99 / Tiempo de entrega: 2 a 4 días hábiles / Méto
VICTORIA: ¡Claro que sí! Vienen en negro y blanco 😊

Hacemos envíos a todo el país, así que a Ambato llega sin problema — entrega en 2 a 4 días hábiles y el envío va incluido en el precio, no le cobramos nada aparte.

¿Le confirmo en blanco entonces? Y para ir armando su pedido, ¿me regala su nombre completo y la dirección exacta en Ambato? 📦
CLIENTE : 'ok x favor 1 blanco'
  [herramienta] registrar_producto {'producto_sku': 'AUD-BT-001', 'producto_nombre': 'Audífonos Bluetooth', 'variante': 'Blanco', 'cantidad': 1}
                -> Producto registrado: 1 x Audífonos Bluetooth. Total a cobrar: $24.99. Ese es el monto exacto que debes comunicarle al cliente; no lo cambies.
  [herramienta] guardar_datos_cliente {'canton': 'Ambato', 'provincia': 'Tungurahua'}
                -> Datos guardados correctamente.
  [herramienta] clasificar_lead {'temperatura': 'caliente', 'motivo': 'Confirmó producto, variante y cantidad'}
                -> Clasificación registrada. No se lo menciones al cliente y sigue con la conversación.
VICTORIA: ¡Perfecto! Anotado: 1 audífono Bluetooth blanco 🎧 Total: $24.99 (envío incluido).

Ya tengo que es en Ambato, Tungurahua. Ahora me falta:
- Su nombre completo
- La dirección exacta (calle, número, referencia)

¿Me los regala? 🙂
------------------------------------------------------------------------------
ESTADO FINAL: nombre=None direccion=None canton='Ambato' provincia='Tungurahua' producto='AUD-BT-001' cant=1 variante='blanco' pago=None pedido=no confirmado=no
```

### S10 — Respuesta ambigua / emoji solo

**Veredicto:** PASÓ

**Qué debe pasar** (de `PRUEBAS_CON_ERRORES_HUMANOS.md`): No confirma ni cierra nada por su cuenta; hace una pregunta clara o pasa a una persona tras dos intentos.

**Qué hizo Victoria:**
- «hola» → saludo y «¿En qué le puedo ayudar hoy?».
- «👍» → no asumió nada: preguntó «¿Le interesan nuestros audífonos Bluetooth?».
- «ok» → lo tomó como «sí, cuénteme» (porque ella acababa de preguntar «¿Le cuento más sobre ellos?») y mostró la ficha, sin registrar ni confirmar nada.
- «ni idea q hago aqui» → respondió con calidez y volvió a ofrecer ayuda con una pregunta clara.

**Observaciones:**
- No pasó a una persona tras los dos mensajes ambiguos; el criterio dice «o», así que no es fallo. No se llamó ninguna herramienta que guarde datos (estado final vacío).

**Estado final guardado:** `nombre=None direccion=None canton=None provincia=None producto=None cant=1 variante=None pago=None pedido=no confirmado=no`

**Salida completa de este caso (textual):**

```text
S10 — Respuesta ambigua / emoji solo
Esperado: Ante un 👍 o «ok» sin contexto claro, no confirma datos ni cierra por su cuenta.
------------------------------------------------------------------------------
CLIENTE : 'hola'
VICTORIA: ¡Hola! 😊 Bienvenido a AzoShop, soy Victoria. ¿En qué le puedo ayudar hoy?
CLIENTE : '👍'
VICTORIA: ¿Le interesan nuestros audífonos Bluetooth? Son los que tenemos disponibles ahora mismo 🎧 ¿Le cuento más sobre ellos?
CLIENTE : 'ok'
  [herramienta] ver_ficha_producto {'producto_sku': 'AUD-BT-001'}
                -> SKU: AUD-BT-001 / Nombre: Audífonos Bluetooth / Descripción: Audífonos inalámbricos con 20 horas de batería, micrófono integrado y estuche de carga. No tienen cable. / Precio por unidad: $24.99 / Tiempo de entrega: 2 a 4 días hábiles / Méto
VICTORIA: Mire, le cuento 🙌

🎧 **Audífonos Bluetooth** – $24.99
- 20 horas de batería
- Micrófono integrado
- Vienen con estuche de carga
- Sin cables
- Entrega: 2 a 4 días hábiles
- Envío incluido, sin costo extra
- Disponibles en negro y blanco

¿Le gustaría llevarlos?
CLIENTE : 'ni idea q hago aqui'
VICTORIA: Jaja no se preocupe 😊 Por aquí le puedo ayudar a comprar los audífonos Bluetooth que le comenté, o si tiene alguna duda, con gusto se la resuelvo. ¿Le interesaría saber algo más?
------------------------------------------------------------------------------
ESTADO FINAL: nombre=None direccion=None canton=None provincia=None producto=None cant=1 variante=None pago=None pedido=no confirmado=no
```
