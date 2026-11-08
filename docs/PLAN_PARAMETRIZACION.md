# Plan: parámetros del sistema controlados desde la app

> **Estado: PROPUESTA (2026-11-08), a la espera de las decisiones de la sección 9.**
> Pedido por Freddy el 2026-11-08: poder cambiar con un par de clics lo que hoy está
> fijo en variables del servidor o dentro del código, con la explicación de para qué
> sirve cada cosa, un valor de respaldo si algo falta, y —con un análisis previo mío—
> también las instrucciones de Victoria. Escrito por Claude a partir del inventario del
> código (`backend/src/**`, `backend/migrations/*`, `frontend/src/config/site.ts`),
> leído el 2026-11-08. Nada de esto está construido todavía.

## 1. Hacemos esto para…

Que **tú** puedas ajustar el comportamiento del negocio (cuánta memoria tiene Victoria,
si manda fotos, qué dice cuando escala, cada cuánto se revisa el stock…) **desde la
app y sin pedirme un cambio de código ni tocar Railway**. En esta etapa inicial hay
muchas cosas que probar y cambiar; cada cambio de código implica revisión, despliegue
y espera. Un parámetro es solo un clic, se explica solo y se puede deshacer.

## 2. Punto de partida: dónde vive hoy cada valor

| Dónde | Ejemplos | Para cambiarlo |
|---|---|---|
| **Variables del servidor (Railway)** | `BOT_MAX_MENSAJES_HISTORIAL` (40), `BOT_MAX_TURNOS_HERRAMIENTAS` (5), `BOT_ENVIAR_FOTOS` (apagado), `LLM_MODEL` | Entrar a Railway, editar y reiniciar |
| **Tablas de la base** | `ajustes_negocio` (márgenes, envío, redondeo, topes diarios), `productos_bot.max_unidades_por_pedido` | Ya se cambian desde la app (Catálogo) |
| **Constantes dentro del código** | caché de stock 300 s, umbral de stock bajo 5, intervalos de los jobs (45/60/60 min), tres mensajes fijos al cliente, 20 mensajes por prueba… | Cambio de código + despliegue |
| **Archivo de texto** | `victoria_system_prompt.txt` (instrucciones de Victoria) | Cambio de código + despliegue |

No hay hoy ninguna tabla de parámetros del bot. (No se verificó si en Railway alguien
fijó un valor distinto del por defecto en `BOT_MAX_*`; el nuevo sistema respeta esos
valores, ver sección 3.)

## 3. Diseño

### 3.1 Tres niveles de valor, de más fuerte a más débil

1. **Valor guardado desde la app** (tabla `parametros_sistema`). Gana siempre.
2. **Variable del servidor**, si existe (compatibilidad: lo que hoy está en Railway sigue
   valiendo mientras no lo cambies en la app).
3. **Valor por defecto escrito en el código** (el respaldo). Solo entra si no hay
   ninguno de los dos anteriores.

Consecuencia: al desplegar el módulo **nada cambia de comportamiento** hasta que tú
guardes un valor. Y «Restaurar original» borra el valor de la app y vuelve al nivel 2 o 3.

### 3.2 El catálogo de parámetros vive en el código

Cada parámetro se declara una vez en un registro (`backend/src/config/parametros.py`)
con: clave, categoría, nombre, **«¿para qué sirve?»**, tipo (entero, sí/no, texto, opción),
mínimo/máximo, valor por defecto, unidad, **cuándo se aplica** (al siguiente mensaje /
en la próxima corrida / al reiniciar) y si es **sensible** (pide confirmación). La app
lee esa lista por API, así la explicación vive en un solo lugar y nunca queda
desactualizada respecto al código. Una clave que no esté en el registro **no se puede
guardar** (lista blanca, igual que `COLUMNAS_GUARDABLES` en ajustes).

### 3.3 «¿Se consultaría la base en cada acción?» — No

- Todos los valores guardados caben en **una sola consulta** (la tabla es pequeña).
- Se guardan **en memoria del proceso con una vida de 30 segundos**, y se invalidan al
  instante cuando guardas un cambio. Resultado: como máximo **una consulta cada
  30 s**, sin importar cuántos mensajes lleguen.
- Producción corre con **un solo worker de gunicorn** (`workers = 1`, 4 threads): una
  memoria compartida basta. Si algún día hubiera varios workers, el límite de 30 s
  acota cuánto tarda un cambio en verse en todos.
- Comparado con lo que ya cuesta un mensaje (la IA tarda 5–15 s), una lectura en
  memoria es inmediata.
- Si la base falla: se usa el **último valor leído**; si no hay ninguno, el nivel 2 o 3.
  Un parámetro nunca debe tumbar a Victoria ni al webhook.
- Si alguien tocara la base a mano y dejara un valor inválido (texto donde va un
  número), se **ignora**, se avisa en el log y se usa el nivel siguiente.

### 3.4 Datos nuevos (migración 018; nunca se edita una aplicada)

- `parametros_sistema(clave pk, valor text, actualizado_por, actualizado_en)`: **solo
  guarda lo que cambiaste**; lo que no está aquí usa el nivel 2 o 3.
- `parametros_historial(id, clave, valor_anterior, valor_nuevo, usuario, creado_en)`:
  quién cambió qué y cuándo (y qué había antes: es tu «deshacer»).
- Ambas con RLS activado y sin policies (mismo criterio que `ajustes_negocio`).

### 3.5 API (todas exigen login, como el resto) y pantalla

- `GET /parametros` (lista agrupada con definición, valor efectivo y **origen**:
  app / servidor / original) · `PUT /parametros/<clave>` · `DELETE /parametros/<clave>`
  (restaurar original) · `GET /parametros/historial`.
- Pantalla **Control → Parámetros** (`/parametros`), mobile-first: una tarjeta por
  parámetro con nombre, «¿para qué sirve?», control (interruptor, número, lista o
  texto), valor original, insignia de origen, cuándo se aplica, Guardar y Restaurar
  original. Los parámetros sensibles piden confirmación. Estados de carga, vacío y
  error con «Reintentar». Pasa lint, build y la auditoría axe.

## 4. Inventario y decisión parámetro por parámetro

### 4.1 SÍ se parametrizan (fases P1 y P2)

**Victoria (el bot)**

| Clave | Hoy | Rango | Para qué sirve | Se aplica |
|---|---|---|---|---|
| `bot.max_mensajes_historial` | 40 (variable) | 10–100 | Cuántos mensajes anteriores se le entregan a la IA en cada respuesta. Más = recuerda más y cuesta más; menos = más barato y olvida antes. | Siguiente mensaje |
| `bot.max_turnos_herramientas` | 5 (variable) | 2–10 | Cuántas «vueltas» puede dar Victoria usando herramientas para un solo mensaje antes de pasar a una persona. | Siguiente mensaje |
| `bot.enviar_fotos` | apagado (variable) | sí/no | Que Victoria pueda mandar la foto del producto. **Sensible**: primero verificar #58. | Siguiente mensaje |
| `bot.modelo_llm` | `claude-sonnet-5` (variable) | lista cerrada | Qué modelo de IA responde (calidad contra costo). **Sensible**; ver decisión D1. | Siguiente mensaje |
| `bot.texto_postventa` | fijo en `services.py` | 1–300 car. | Lo que se responde al cliente con pedido ya despachado antes de pasarlo a una persona. | Siguiente mensaje |
| `bot.texto_comprobante_recibido` | fijo en `services.py` | 1–300 car. | Lo que se responde cuando el cliente manda una imagen mientras se espera el pago. | Siguiente mensaje |
| `bot.texto_limite_alcanzado` | fijo en `conversation_service.py` | 1–300 car. | Lo que se responde si Victoria se pasa del límite de vueltas y se escala. | Siguiente mensaje |

**Stock y productos**

| Clave | Hoy | Rango | Para qué sirve | Se aplica |
|---|---|---|---|---|
| `stock.cache_segundos` | 300 (código) | 30–1800 | Cuánto tiempo Victoria recuerda el stock consultado antes de volver a preguntarle a Rocketfy (al cerrar la venta siempre se consulta fresco). | Siguiente consulta |
| `stock.umbral_bajo` | 5 en dos sitios (código) | 0–100 | Cuántas unidades se consideran «stock bajo»: avisa al publicar y es el umbral de vigilancia que se crea para el producto. Se unifican las dos constantes (`STOCK_BAJO` y `UMBRAL_STOCK_AL_PUBLICAR`), que valían lo mismo. | Siguiente uso |
| `sync.autopausa_agotado` | siempre activa (código) | sí/no | Que un producto activo con 0 unidades pase solo a «agotado». | Próxima corrida |
| `sync.alerta_margen` | siempre activa (código) | sí/no | Que se avise cuando un cambio de costo en Rocketfy deja el margen bajo tu mínimo. | Próxima corrida |
| `pruebas.max_mensajes` | 20 (código) | 5–50 | Cuántos mensajes admite una prueba en «Probar con Victoria» antes de pedir reiniciarla. | Siguiente mensaje |

**Tareas automáticas (P2: requieren reprogramar el reloj en vivo)**

| Clave | Hoy | Rango | Para qué sirve | Se aplica |
|---|---|---|---|---|
| `jobs.minutos_sync_productos` | 60 (código) | 15–1440 | Cada cuántos minutos se actualizan costo, stock e imagen de los productos publicados. | Al guardar (reprograma) |
| `jobs.minutos_stock_watcher` | 60 (código) | 15–1440 | Cada cuántos minutos se revisa el stock de los SKUs vigilados. | Al guardar |
| `jobs.minutos_reconciliacion` | 45 (código) | 15–1440 | Cada cuántos minutos se reconcilian los pedidos con Rocketfy. | Al guardar |

El mínimo de 15 minutos evita saturar a Rocketfy por un error de tipeo.

### 4.2 Ya están en la app: se quedan donde están

| Qué | Dónde | Por qué no se migra |
|---|---|---|
| Margen mínimo y objetivo, envío estimado, otros costos, redondeo, **topes diarios** de redacción y de pruebas | `ajustes_negocio` + diálogo en Catálogo | Tienen reglas en la base (p. ej. «objetivo ≥ mínimo») y la calculadora ya los usa. Pasarlos a una tabla genérica **perdería esas reglas** y no aporta nada. La pantalla de Parámetros mostrará una tarjeta con enlace para que todo se encuentre en un solo lugar. |
| Unidades máximas por pedido, precio, estado de cada producto | `productos_bot` (por producto) | Son datos de cada producto, no del sistema. |

### 4.3 NO se parametrizan (y por qué)

| Qué | Motivo |
|---|---|
| **Secretos:** `ROCKETFY_API_TOKEN`, `ROCKETFY_WEBHOOK_TOKEN`, `WHATSAPP_API_TOKEN`, `WHATSAPP_APP_SECRET`, `WHATSAPP_WEBHOOK_VERIFY_TOKEN`, `ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`, claves de Supabase | Regla de `CLAUDE.md`: los secretos viven solo en Railway/Vercel. En la base serían legibles desde la app y los respaldos. Un test vigilará que ninguna clave del registro parezca secreto. |
| `SUPABASE_DB_URL` | Sin la base no hay de dónde leer los parámetros (huevo y gallina). |
| `WHATSAPP_SKIP_SIGNATURE` | Apaga la seguridad del webhook; solo para desarrollo. **Nunca** desde una pantalla. |
| `FRONTEND_ORIGIN` | Un valor equivocado deja al dashboard sin poder hablar con el backend, y no se podría corregir desde el mismo dashboard. |
| `LLM_PROVIDER` | Cambia el cableado completo y exige otra clave; no es un ajuste de negocio. |
| `ENABLE_SCHEDULER`, `PORT`, `LOG_LEVEL` | Infraestructura que se lee antes de que exista la base. |
| `ROCKETFY_BASE_URL`, `ROCKETFY_ACCOUNT_EMAIL`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_WABA_ID`, `TELEGRAM_CHAT_ID` | Identidad de las integraciones: casi nunca cambian y un error corta el canal. Mejor en la plataforma, con verificación posterior. |
| Ventanas de Meta (24 h de servicio, 72 h de anuncios) | Son políticas de Meta, no decisiones del negocio. |
| Mínimo de recaudo contraentrega ($10) | Regla de Rocketfy, ya aprendida de sus rechazos (Fase A). |
| Tiempos de espera y reintentos de Rocketfy/WhatsApp/Telegram | Técnicos: mal ajustados pueden **duplicar mensajes o pedidos** (ADR-007). |
| Latido de la base (cada 6 h) y tiempos de los candados de los jobs | Evitan que Supabase pause el proyecto y que dos jobs se pisen. |
| Largos máximos de campos del producto, tope absoluto de 20 unidades por pedido, tokens máximos de la IA | Protegen datos y costos; ajustarlos no aporta valor al negocio. |
| Zona horaria (Ecuador) | Es la del negocio; no cambia. |
| Nombres y esquemas de las herramientas de Victoria y las 4 reglas fijas del webhook | Son lógica: cambiarlas es cambiar el programa. (Sus **textos** sí se parametrizan arriba.) |
| Qué estados de Rocketfy avisan al cliente o al equipo (`EVENTOS_PARA_CLIENTE/EQUIPO`) | Candidato a una fase futura (P4): requiere plantillas aprobadas por Meta para escribir fuera de las 24 h. Hoy el aviso al cliente solo se registra en el log. |

## 5. Las instrucciones de Victoria (prompt): análisis previo

**Veredicto: SÍ, con condiciones, como fase P3 (después de P1 y P2).** Pediste que lo
aprobara un análisis mío antes; este es.

**Ventajas.** Afinar el tono o añadir una regla («no menciones X») sin despliegue; en
esta etapa se afina Victoria casi a diario.

**Riesgos reales (leyendo cómo se arma el prompt hoy):**

| # | Riesgo | Por qué importa |
|---|---|---|
| R1 | El prompt se rellena con `str.format`: **una `{` o `}` suelta en el texto hace fallar CADA respuesta** | Victoria quedaría muda para todos los clientes por un error de tipeo |
| R2 | Borrar los huecos `{contexto_producto}`, `{contexto_lead_actual}` o `{fecha_actual}` | Victoria perdería la ficha del producto o lo que ya se sabe del cliente |
| R3 | Un cambio malo con efecto inmediato sobre clientes reales | Sin ensayo previo ni vuelta atrás |
| R4 | Instrucciones que contradicen el código (nombrar una herramienta que no existe, pedir calcular el total) | El código manda: el total y el stock los decide el sistema (ADR-010); Victoria quedaría confundida |
| R5 | Un prompt muy largo | Se envía completo en **cada** mensaje: más texto = más costo y más lentitud |

**Condiciones para aprobarlo (cada una cubre uno de los riesgos):**

1. **Validación antes de guardar:** exige los tres huecos, rechaza llaves sueltas y
   limita el largo (propuesta: 8 000 caracteres, mostrando el aproximado en tokens). *(R1, R2, R5)*
2. **Borrador y publicado separados:** editas un borrador, **lo pruebas con «Probar con
   Victoria»** (la simulación de la Fase E, que no toca clientes reales), y recién
   entonces publicas con confirmación. *(R3)*
3. **Versiones con quién, cuándo y por qué**, y botones «Volver a la versión anterior» y
   «Restaurar la original del código». *(R3)*
4. **Respaldo:** si la lectura o la validación fallan en producción, Victoria usa el
   archivo del código; **nunca queda sin instrucciones**. *(R1, R2)*
5. **La sección «Cómo usar tus herramientas» queda solo de lectura en la primera versión**
   (se ve, pero no se edita): está atada al código (nombres de herramientas, flujo de
   cierre). Editables: personalidad, objetivo, reglas que nunca rompe y variantes. Ver D2. *(R4)*

**Rendimiento:** una lectura de la base como máximo cada 30 s (misma caché de la sección
3.3). Hoy el archivo se lee una vez al arrancar; el costo añadido es imperceptible frente
a los 5–15 s de la IA.

**Qué NO cambia:** las reglas de dinero, stock, cantidad y pausa siguen en el código. El
prompt puede empeorar el trato a un cliente, pero **no puede saltarse esas reglas**.

## 6. Fases de desarrollo

| Fase | Contenido | Migración |
|---|---|---|
| **P1** | Tabla y registro de parámetros, servicio con caché y respaldos, API, historial, pantalla `/parametros`, y conexión de los parámetros de la sección 4.1 salvo los intervalos de jobs. Tests. | 018 |
| **P2** | Intervalos de las tareas automáticas con reprogramación en vivo (`reschedule_job`). | — |
| **P3** | Instrucciones de Victoria: borrador, validación, prueba, versiones, restaurar. Pantalla `/parametros/instrucciones`. | 019 |

Cada fase: tests, documentación (`PROGRESS.md`, `docs/CONCEPTOS_TECNICOS.md`,
`.env.example` indicando que las variables ahora son «respaldo»), revisión móvil y
oscuro, y **confirmación tuya antes de aplicar cada migración y de desplegar** (regla de
`CLAUDE.md`). Recordatorio: el despliegue automático de Railway sigue sin dispararse
(pendiente #48): tras fusionar hay que reconectar la fuente.

### Qué código se toca (P1)

- `conversation_service.py`: hoy lee `max_turnos`, `max_historial` y la lista de
  herramientas **una vez al construirse**; pasa a leerlos **en cada turno**.
- `tools.py`: lee `bot_enviar_fotos` una vez en `__init__`; pasa a consultarse al ofrecer
  herramientas y al ejecutar la foto.
- `integrations/llm/factory.py`: `get_llm_client()` está en `lru_cache` fijo al modelo de
  arranque; pasa a un proveedor por modelo (cacheado por nombre).
- `whatsapp/stock.py`, `productos_bot/verificacion.py`, `productos_bot/services.py`,
  `productos_bot/sincronizacion.py`, `productos_bot/pruebas.py`, `whatsapp/services.py`:
  sustituyen sus constantes por lecturas del servicio de parámetros.
- `config/settings.py`: las variables `BOT_*`/`LLM_MODEL` se siguen leyendo, pero como
  **nivel 2** (respaldo), a través del servicio.

## 7. Cómo se verifica

- Tests del registro (todo parámetro con descripción, defecto dentro del rango, ninguna
  clave con aspecto de secreto), de la precedencia app > servidor > código, de la caché
  (reloj falso: vence a los 30 s, se invalida al guardar), del respaldo con la base
  caída, de la API (clave desconocida, fuera de rango, tipo equivocado) y de que cada
  consumidor lee el valor **actual** y no el de arranque.
- Prueba en el backend local con Postgres desechable (suite completa; hoy 909 tests).
- Pantalla: lint, `next build`, auditoría axe sin violaciones, capturas a 390 px y
  escritorio, claro y oscuro.
- Producción tras desplegar: `/health`, que la pantalla liste los parámetros con su
  valor original, y que **ningún comportamiento haya cambiado** mientras no se guarde nada.

## 8. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Guardar un valor que degrade a Victoria (p. ej. 1 vuelta de herramientas) | Rangos con mínimo seguro, confirmación en los sensibles, historial y «Restaurar original» |
| Modelo de IA equivocado o inexistente | Lista cerrada y verificada, no texto libre (D1) |
| Intervalo de jobs demasiado corto | Mínimo de 15 min |
| Cambio hecho a mano en la base con valor inválido | Se ignora y se usa el nivel siguiente, con aviso en el log |
| Dos sitios para lo mismo (variable y parámetro) | La pantalla muestra el **origen** de cada valor y avisa si hay variable del servidor |
| Crecimiento del módulo (todo «parametrizable») | Solo entra lo que tiene dueño y utilidad de negocio; la sección 4.3 documenta lo que se queda fuera |

## 9. Decisiones

**Las tomé yo (dime si quieres cambiar alguna):**
- Orden de prioridad app > servidor > código (compatible con lo que hoy hay en Railway).
- `ajustes_negocio` **no** se migra; se enlaza desde la nueva pantalla.
- Se unifican `STOCK_BAJO` y `UMBRAL_STOCK_AL_PUBLICAR` en `stock.umbral_bajo`.
- Los parámetros sensibles (fotos, modelo, intervalos) piden confirmación al guardar.
- Cualquier usuario con login del dashboard puede cambiar parámetros (hoy solo tú).

**Necesito decidirlas contigo (no estoy segura de la respuesta correcta):**
- **D1 — Modelo de IA desde la app.** Recomiendo incluirlo con lista cerrada porque es la
  palanca más fuerte de costo y calidad, pero no sé qué modelos quieres permitir ni si
  uno más barato empeoraría las ventas; eso solo se sabe probando. ¿Lo incluimos y con
  cuáles modelos?
- **D2 — Sección «Cómo usar tus herramientas» del prompt.** Recomiendo solo lectura en la
  primera versión. Alternativa: editable con un aviso. ¿Cuál prefieres?
- **D3 — Alcance de esta entrega.** Recomiendo construir P1 + P2 ahora y dejar P3 para
  después de verlos en producción, porque P3 es lo más delicado. ¿De acuerdo?
