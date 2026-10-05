# 09 — Fase 3, Etapa 3.2: Resultados de la Ejecución

> Generado por Claude Code para Claude web, al cerrar el encargo de
> desarrollo de la Etapa 3.2 (Victoria con un LLM desacoplado como
> cerebro conversacional + persistencia de cola) que Claude web entregó.
> El documento `08` describe qué pasó en la Etapa 3.1 — este describe qué
> pasó al construir y probar la 3.2.

---

## 1. Qué se construyó

Las 10 tareas del encargo se ejecutaron en orden, cada una verificada con
`pytest` antes de seguir a la siguiente (Task 7 — Telegram — se construyó
en realidad durante la Tarea 4, porque `handle_escalar_a_humano` la
necesitaba de verdad para poder probarse; se documenta en su lugar
original de todos modos):

1. Persistencia de la cola del `BotWorker` — tabla `cola_mensajes`,
   `recuperar_pendientes()` al arrancar.
2. Base de conocimiento de productos (`productos_bot`,
   `anuncios_productos`), separada del catálogo de Rocketfy — script de
   carga `tools/cargar_producto_bot.py`, un producto de prueba real ya
   cargado (`DEMO-AURICULARES-BT`).
3. Capa de abstracción del LLM: `src/integrations/llm/` (contratos
   neutrales + `LLMProvider` ABC + `AnthropicProvider`, único archivo que
   importa el SDK `anthropic`).
4. Las 5 herramientas de Victoria (`tools.py`, `HerramientasVictoria`) y
   sus handlers, incluida la conexión real con
   `PedidoService.crear_y_confirmar()`.
5. El system prompt de Victoria (`victoria_system_prompt.txt`).
6. `VictoriaConversationService` — el loop de tool use — y las 4 reglas
   deterministas de escalado en `WebhookService`.
7. `TelegramNotifier` (construido durante la Tarea 4, ver arriba).
8. Simulador de terminal (`tools/chat_con_victoria.py`).
9. Conexión real del worker (`BotWorker` ahora invoca a
   `VictoriaConversationService` de verdad para modo='ia').
10. Esta documentación + la correspondiente en `PROGRESS.md`.

**Tests:** 41 nuevos. **170/170 tests en total, todos pasando.**

**Confirmación explícita del test de contención:** se corrió por separado
y con un `grep` manual adicional como doble verificación — ningún archivo
fuera de `src/integrations/llm/providers/anthropic_provider.py` importa
`anthropic` en ningún lugar del proyecto.

---

## 2. Cinco desvíos conscientes del encargo original

### Desvío 1 — Manejo de errores de Rocketfy en `cerrar_venta`, colapsado de 2 categorías a 1
El encargo describía "409 ambiguo" vs "422 regla de negocio", pero
`PedidoService.crear_y_confirmar()` no expone códigos HTTP en esa capa:
lanza 5 excepciones tipadas propias (`PedidoEnEstadoAmbiguoError`,
`PedidoIncompletoError`, `UbicacionNoResueltaError`,
`RecaudoMinimoNoAlcanzadoError`, `RocketfyBusinessError`). Como el propio
encargo dice que TODO fallo de Rocketfy debe escalar igual a un humano
sin importar la categoría, se capturan las 5 en un único bloque y se
escala siempre con el mensaje de la excepción como `motivo` — las dos
categorías originales se comportaban idéntico, colapsarlas no pierde
nada.

### Desvío 2 — Fail-fast de `ANTHROPIC_API_KEY` movido de `settings.py` a `integrations/llm/factory.py`
El encargo pedía la validación condicional dentro de
`Settings`/`load_settings()`. Se detectó a tiempo que `load_settings()`
es una función monolítica que TODO el proyecto llama para cualquier cosa
(hasta abrir una conexión a Postgres vía `get_connection()`) — si
fallara ahí por falta de la key del LLM, nada que dependa de `Settings`
arrancaría, incluida funcionalidad sin ninguna relación con el LLM. Se
movió el fail-fast al único punto que de verdad necesita la key
(`get_llm_client()`), dejando `Settings.anthropic_api_key` opcional como
ya estaba antes.

Por el mismo motivo, `BotWorker` construye `VictoriaConversationService`
de forma **perezosa** (recién en el primer mensaje modo='ia' que le toca
procesar, no en `__init__`) — así el backend entero arranca aunque la key
todavía no esté configurada, y las rutas de escalado (modo='fijo', que no
usan LLM) funcionan igual. Verificado manualmente arrancando `flask run`
con `ANTHROPIC_API_KEY` vacía: arranca limpio, `/health` responde 200,
`BotWorker` inicia correctamente.

### Desvío 3 — Compatibilidad con Python 3.9
El proyecto corre en Python 3.9.6 (confirmado en el `.venv`), que no
soporta `X | None` como expresión de tipo en tiempo de ejecución (PEP 604
es de 3.10) — `contratos.py` usa `Optional[X]` en su lugar, igual que el
resto del proyecto.

### Desvío 4 — `ResultadoHerramienta.id_llamada` no lo arma el handler
El encargo mostraba a cada handler devolviendo un `ResultadoHerramienta`
completo, pero con la firma `(lead_id, conversacion_id, entrada)` — sin
el id de la llamada, que solo conoce quien orquesta el loop. Se resolvió
así: los métodos privados `_handle_*` de `HerramientasVictoria` devuelven
solo el texto (`str`); el método público `ejecutar(nombre, lead_id,
conversacion_id, entrada, id_llamada)` arma el `ResultadoHerramienta`
completo.

### Desvío 5 — Telegram construido durante la Tarea 4
`handle_escalar_a_humano` lo necesitaba de verdad para poder probarse —
construirlo recién en su propio turno habría significado escribirlo dos
veces.

---

## 3. Simulador (Tarea 8) — completado el 2026-09-27 contra las APIs reales

El usuario pegó `ANTHROPIC_API_KEY` real en `backend/.env` un día después
de cerrar el resto de la etapa. Se corrieron las 2 conversaciones de
prueba contra la API real de Anthropic y, cuando una de ellas llegó a
cerrar la venta, también contra la API real de Rocketfy.

**Confirmado sin errores de autenticación** contra la API real de Claude
en las dos conversaciones.

**El primer intento de la conversación 1 (venta cerrada) reveló 2 bugs
reales que ningún test con mocks podía haber encontrado** — se arreglaron
en el camino, con tests nuevos, y se volvió a correr hasta que cerró
limpio:

1. **El LLM no siempre copia el SKU exacto del catálogo.** En 3 intentos
   sucesivos, `registrar_producto` recibió `"AUD-BT-001"` (inventado), el
   NOMBRE del producto en vez del SKU, y literalmente `"N/A"` — pese a
   reforzar la instrucción en el prompt y en la descripción de la
   herramienta ("cópialo exacto, no lo inventes"). La solución real fue en
   código, no en prompt: `tools.py::_handle_registrar_producto` ahora
   valida el SKU recibido contra `productos_bot` y, si no coincide con
   ninguno real, lo corrige buscando por nombre (ignorando tildes/mayúsculas)
   antes de guardarlo.
2. **Desajuste de formato de teléfono entre WhatsApp y Rocketfy.**
   WhatsApp entrega el número con código de país (`593XXXXXXXXX`, 12
   dígitos); Rocketfy exige formato local ecuatoriano (9-10 dígitos, sin
   código de país) y rechazó la confirmación con "El número no cumple con
   el formato válido para EC". Se agregó `tools.py::_telefono_formato_rocketfy()`.

**Un tercer hallazgo quedó sin resolver a propósito, para que Claude web
decida el diseño:** ninguna herramienta tiene un parámetro para la
variante/color del producto. `productos_bot.variantes` existe y Victoria
lo ve en su contexto (así que a veces pregunta por el color), pero no
tiene ninguna herramienta donde registrar la respuesta. En algunos
intentos reales esto la llevó a escalar a un humano en vez de seguir/cerrar
la venta, aunque el color no es un dato requerido por `cerrar_venta`. No
es un bug — el sistema hizo exactamente lo que el prompt le indica ante
ambigüedad — pero es un hueco real del esquema de herramientas.
Opciones para decidir: agregar un parámetro `variante` a alguna
herramienta, o instruir a Victoria explícitamente a no tratar la
variante/color como bloqueante para cerrar.

**Cada intento real contra Rocketfy (tanto los que fallaron como el que sí
cerró) se limpió después con `rechazar_pedido()`**, el mismo patrón que ya
usa `tools/rocketfy_order_smoke_test.py` — no quedó ningún pedido de
prueba activo en el sistema real del proveedor.

**3 tests nuevos** (autocorrección de SKU: 2; conversión de teléfono: 1).
**173/173 tests en total.**

### Transcripción 1 — venta cerrada por contraentrega

Teléfono simulado: `593991234567`. Producto real usado:
`10-AUDIFONO-INALAM-TIPRO` ("Audífonos Bluetooth inalámbricos", $24.99 —
el SKU de prueba original `DEMO-AURICULARES-BT` no existe en el catálogo
real de Rocketfy, así que se corrigió para poder cerrar una venta de
verdad; ver hallazgo 1 de arriba, la propia sesión de prueba fue la que
lo detectó).

```
Tú: Hola, buenas! Quiero comprar los audífonos bluetooth que ustedes venden
Victoria: ¡Hola! Qué bien 😊 Sí, tenemos los Audífonos Bluetooth inalámbricos
disponibles a $24.99. Para dejarte listo el pedido, ¿me ayudas con estos datos?

1. Tu nombre completo
2. Dirección exacta
3. Cantón
4. Provincia

Tú: Me llamo Juan Pérez, mi dirección es Av. Amazonas N34-451, en Quito,
provincia de Pichincha
Victoria: ¡Perfecto, Juan! Ya tengo tus datos y el producto registrado ✅

Ahora dime, ¿cómo prefieres pagar: contraentrega o transferencia?

Tú: Voy a pagar contra entrega
Victoria: ¡Listo, Juan! 🎉 Tu pedido de los Audífonos Bluetooth inalámbricos
ya quedó confirmado, pago contraentrega.

Te llega en 2 a 4 días hábiles ya que estás en Quito 📦

¡Muchas gracias por tu compra! Cualquier cosa me escribes 😊
```

Estado final verificado contra Supabase y Rocketfy reales:
`leads.estado='despachado'`, `id_pedido_local=1790489672`,
`id_pedido_rocketfy=318041`, `pedidos.estado_local` pasó por `confirmado`
(verificado) y luego se puso en `rechazado` como limpieza deliberada del
pedido de prueba.

### Transcripción 2 — escalada por pregunta fuera de alcance

Teléfono simulado: `593987654322`.

```
Tú: Hola, quisiera saber sobre los audífonos bluetooth que venden
Victoria: ¡Hola! 👋 Qué tal, sí claro con gusto te cuento

Tenemos los Audífonos Bluetooth inalámbricos a $24.99 🎧 Son inalámbricos,
prácticos para el día a día.

¿Te gustaría hacer el pedido?

Tú: Antes que nada, tengo un problema con un pedido que hice el mes pasado,
nunca me llegó y nadie me ha respondido
Victoria: Entiendo, disculpa el inconveniente 🙏 Voy a pasar tu caso a un
asesor humano para que te ayude directamente con eso, en breve te
contactan. ¡Gracias por tu paciencia!
```

Estado final verificado: `conversaciones.estado='escalada'` — coincide con
la regla del system prompt ("problemas con un pedido anterior... usa
escalar_a_humano"), en 2 turnos, sin ningún error.

---

## 4. Estado de Telegram

`TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` siguen vacíos — a propósito,
fase posterior. Confirmado con test automatizado
(`tests/unit/integrations/telegram/test_client.py`) que el sistema
funciona igual sin fallar: sin credenciales, `notificar_escalado()` no
hace ninguna llamada HTTP y no lanza ninguna excepción — solo loguea una
advertencia una vez. El resto del flujo de escalado (marcar la
conversación como `escalada`, encolar el mensaje fijo al cliente) sigue
funcionando normal.

---

## 5. Pendientes que deja esta etapa

- ~~Decisión de diseño pendiente sobre variante/color~~ — **RESUELTO
  2026-09-27, ver sección 6 más abajo.**
- Bot de Telegram real (`@BotFather`) — Claude web va a guiar este paso.
- Verificación real de comprobantes de pago con visión (fuera de alcance
  a propósito de esta fase).
- Panel de administración para `productos_bot` (hoy solo el script de
  consola).
- Reactivar desde el dashboard una conversación que Victoria escaló (hoy
  solo se puede a mano en la base de datos).
- Flujo 2 (formulario web) y Flujo 4 completo de `docs/BotPlanifiacion.md`
  — no construidos en esta fase.
- Agregar un segundo proveedor de LLM cuando haga falta — la arquitectura
  ya está lista para eso (ver el test de contención).
- Los pendientes de producción ya conocidos desde la Etapa 3.1 (firma
  `X-Hub-Signature-256`, número real de WhatsApp, publicar la app de
  Meta, confirmar que el token de WhatsApp sea permanente, Supabase se
  pausa por inactividad en el plan gratuito).

---

## 6. Ajuste posterior (2026-09-27) — variante de producto + resiliencia en `registrar_producto`

Encargo de 4 tareas de Claude web para cerrar el hallazgo 3 de la sección
3. Ejecutado sin desvíos.

- `leads.producto_variante` (columna nueva, migración
  `010_leads_producto_variante.sql`).
- `registrar_producto` acepta `variante` como parámetro **opcional** — la
  herramienta y el system prompt dejan explícito que nunca es motivo para
  escalar ni para detener un cierre de venta.
- `cerrar_venta` arma el nombre de línea que se manda a Rocketfy como
  `"{producto_nombre} - {variante}"` cuando hay variante (el DTO de
  Rocketfy no tiene campo propio para eso).
- **Resiliencia nueva:** si `registrar_producto` no encuentra ningún
  producto real (ni por SKU exacto ni por el fuzzy-match por nombre del
  hallazgo 1) no guarda nada — le devuelve a Victoria la lista real de
  productos disponibles para que le pregunte de nuevo al cliente.
- Documentado en `tools/cargar_producto_bot.py` (docstring del módulo):
  el SKU cargado en `productos_bot` siempre debe ser real, verificable
  contra el catálogo de Rocketfy — nunca inventado. `10-AUDIFONO-INALAM-TIPRO`
  sigue siendo el único producto real cargado; no se agregó ninguno
  adicional para esta prueba.
- 4 tests nuevos. **177/177 tests en total.**

### Transcripción de la Tarea C — variante ambigua, la venta se cierra igual

Teléfono simulado: `593991234568`.

```
Tú: Hola, quiero los audífonos bluetooth que venden, aunque no sé qué
color escoger, cualquiera está bien
Victoria: ¡Hola! 😊 Con gusto, los Audífonos Bluetooth inalámbricos están
en $24.99.

Ya que no tienes preferencia de color, te los registro así no más y
seguimos con tu pedido. Para el envío, ¿me confirmas tu nombre completo,
dirección exacta, cantón y provincia? 📦

Tú: Me llamo Juan Pérez, mi dirección es Av. Amazonas N34-451, en Quito,
provincia de Pichincha
Victoria: ¡Perfecto, Juan! Ya tengo tus datos guardados ✅

Ahora, ¿cómo prefieres pagar: contraentrega o transferencia? 💳

Tú: Voy a pagar contra entrega
Victoria: ¡Listo, Juan! 🎉 Tu pedido de los Audífonos Bluetooth quedó
confirmado, pago contraentrega.

Te llega a Av. Amazonas N34-451, Quito, en 2 a 4 días hábiles 📦

¡Muchas gracias por tu compra! Cualquier cosa me escribes 😊
```

Victoria nunca escaló por el color ambiguo — registró el producto sin
variante (`leads.producto_variante = NULL`) y siguió el proceso normal
hasta cerrar la venta. Verificado contra Supabase y Rocketfy reales:
`leads.estado='despachado'`, pedido confirmado (`id_rocketfy=318457`) y
luego rechazado como limpieza del pedido de prueba, igual que los
anteriores.
