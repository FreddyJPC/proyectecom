# Pruebas de Victoria con errores humanos

**Para qué sirve:** la gente real escribe con faltas, abrevia, junta palabras, no sabe el nombre del producto y contesta «dale» o
«👍». Esta lista sirve para comprobar, con la IA real, que Victoria lo entiende y que el sistema no se deja engañar por un dato
mal escrito. Se corre en la app: **Catálogo → un producto → «Probar con Victoria»** (no envía nada a ningún cliente ni crea pedidos
reales). Escribe cada mensaje tal cual, en orden, y compara con «Qué debe pasar».

También se puede correr desde la terminal con `backend/tools/pruebas_con_errores_humanos.py --real` (necesita `ANTHROPIC_API_KEY`;
cuesta unos centavos). El producto del guion es «Audífonos Bluetooth», colores negro y blanco, envío incluido, hasta 3 unidades.

| # | Situación | Mensajes del cliente (en orden) | Qué debe pasar |
|---|---|---|---|
| S1 | Compra completa con faltas y ciudad mal escrita | `ola kiero unos audifonos blutu` → `cuanto cuestan? y q colores ay` → `el negro xfa, 2` → `mi nombre es maria jose pacheco, vivo en guayakil, provincia guayas, en la cdla kennedy mz 5 villa 3` → `cuando llege pago` → `sip todo bien` | Entiende el producto; corrige **«guayakil» → Guayaquil sin preguntar** (y deduce Guayas); en el resumen aparece «Guayaquil, Guayas» bien escrito y el «sip» lo confirma; solo entonces cierra. Si no hay `si guayaquil`, igual debe seguir. |
| S2 | No sabe el nombre del producto | `buenas tardes tienen esos audifonos q no tienen cable?` → `los negros cuanto salen` → `y viene con estuche?` → `y la garantia cuanto es?` | Identifica el producto por la descripción; no inventa; la garantía la pasa a una persona. |
| S3 | Palabras pegadas, letras comidas | `holaquiero comprarlos audifonos` → `mellamo juan perez vivoen cuenca azuay` → `xq tan caro mm` → `kiero 1 nomas blanco` | Entiende nombre, ciudad y cantidad; responde a «tan caro» sin inventar descuentos. |
| S4 | Mensajes en pedacitos (llegan juntos) | `Hola` ⏎ `buenas tardes` ⏎ `quiero` ⏎ `unos audifonos` ⏎ `los blancos` (en un solo mensaje, con saltos de línea) | Responde **una** vez a todo junto, sin repetir el saludo. |
| S5 | Confirmaciones informales y correcciones | `quiero 1 audifono negro` → `ana lopez, quito pichincha, av amazonas n34-12 y atahualpa` → `contraentrega` → (cuando muestre el resumen) `no, la direccion es av. 10 de agosto y colon` → (nuevo resumen) `dale` | Al corregir la dirección **vuelve a mostrar el resumen**; «dale» cuenta como sí y recién ahí cierra. |
| S6 | Ciudad y provincia que no cuadran | `quiero 1 audifono blanco` → `soy pedro ruiz, vivo en quito provincia guayas, calle 9 de octubre 123` | No guarda «Quito, Guayas» (no cuadra: Quito es de Pichincha); le pregunta con naturalidad cuál es la correcta, sin inventar. |
| S7 | Pide una persona, con errores | `kiero ablar con una persona porfa` | Usa «escalar a humano». |
| S8 | No quiere más mensajes | `no gracias, ya no me escriban mas porfa` | Usa «no contactar» y se despide con amabilidad. |
| S9 | Abreviaturas y jerga | `wenas cnto sale el aud blutu` → `tmb ay en blanco? dnd lo envian? soy de ambato` → `ok x favor 1 blanco` | Entiende «cnto», «tmb», «dnd»; no se pierde. |
| S11 | Errores evidentes que NO se deben preguntar | `quiero 1 audifono blanko` → `soy ana, vivo en quto, calle 10 y 12` | Entiende «blanko» = Blanco y «quto» = Quito (con Pichincha) **sin preguntarlo**; el resumen dice «Blanco» y «Quito, Pichincha». |
| S10 | Respuestas vacías o ambiguas | `hola` → `👍` → `ok` → `ni idea q hago aqui` | No confirma ni cierra nada por su cuenta; hace una pregunta clara o pasa a una persona tras dos intentos. |

## Qué mirar en cada prueba
1. **Las herramientas que usó** (el panel las muestra): ¿guardó lo correcto, en el momento correcto?
2. **La venta en curso** (cliente, dirección, cantón, provincia, producto, total): ¿quedó con lo que el cliente quiso decir?
3. **Que nunca cierre sin el «sí» del cliente** al resumen, y que cualquier corrección obligue a confirmar de nuevo.

Si algo falla, anota el número de caso y lo que escribió Victoria; eso se arregla en las instrucciones de Victoria (Control →
Instrucciones) o en el código, según el caso.
