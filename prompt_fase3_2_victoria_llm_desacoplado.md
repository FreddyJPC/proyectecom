<contexto>

# Fase 3.2 — Victoria con un LLM Desacoplado como Cerebro Conversacional + Persistencia de Cola

## Quién eres y cuál es tu rol

Eres Claude CLI, el agente desarrollador con capacidades de ejecución en este proyecto. Trabajas en equipo con Claude Web (instancia de chat), quien diseña la arquitectura y genera los prompts de desarrollo. El usuario es el intermediario entre ambos.

## Resumen de dónde quedó la Fase 3.1

La Fase 3.1 construyó la infraestructura base: webhook de WhatsApp, worker en background, y tres tablas (`conversaciones`, `mensajes`, `leads`). Se probó contra un evento real de Meta (vía el botón "Probar" del panel, ya que la app no está publicada) y quedó validado que el canal completo funciona: recepción, idempotencia, detección de FEP, persistencia, cola en background, tolerancia a fallos. **129 tests pasando, 0 fallando.**

El worker en esa fase solo respondía un mensaje fijo de prueba. Esta fase reemplaza eso con la lógica real: Victoria pensando y vendiendo con un LLM.

También se resuelve en esta misma fase un pendiente de la 3.1: la cola del `BotWorker` vive solo en memoria — si el proceso se reinicia con mensajes sin procesar, se pierden en silencio. Se agrega persistencia mínima.

## Objetivo de esta fase (3.2)

1. Persistir la cola de tareas del worker en Supabase (sobrevive a reinicios).
2. Construir la base de conocimiento de productos que usa Victoria (separada del catálogo de Rocketfy).
3. Integrar un LLM como cerebro conversacional de Victoria, **detrás de una interfaz de proveedor desacoplada** — ver la sección siguiente, es la decisión de arquitectura más importante de esta fase.
4. Conectar el cierre de venta real con `PedidoService.crear_y_confirmar()` (llamada directa en Python, mismo proceso, sin HTTP).
5. Notificaciones por Telegram cuando el bot escala a atención personal.
6. Un script de simulación en terminal para conversar con Victoria sin depender de WhatsApp — necesario porque la app de Meta sigue sin publicar.

## Decisión de arquitectura central de esta fase: el LLM está desacoplado del resto del sistema

**El usuario fue explícito sobre esto y es un requisito duro, no una preferencia:** si en el futuro decide cambiar el proveedor de LLM (por ejemplo de Claude a Gemini o GPT), el cambio debe limitarse a escribir un adaptador nuevo y cambiar una variable de entorno — **nunca** debe requerir tocar la lógica de conversación, las herramientas de Victoria, el manejo de estado del lead, o el prompt.

### Cómo se logra esto

Se define una interfaz neutral (`LLMProvider`, una clase abstracta) con tipos de datos propios del proyecto — nunca tipos del SDK de un proveedor específico. El adaptador de Anthropic implementa esa interfaz y es el **único lugar del proyecto** donde se importa el SDK `anthropic` o se manipulan sus tipos de respuesta. Todo lo demás (el servicio de conversación, las herramientas, los tests del loop de conversación) trabaja exclusivamente con los tipos neutrales.

```
backend/src/integrations/llm/
├── contratos.py              # dataclasses neutrales + la interfaz LLMProvider (ABC)
├── exceptions.py             # excepciones neutrales, no ligadas a un proveedor
├── factory.py                # get_llm_client() -> lee LLM_PROVIDER y devuelve el adapter correcto
└── providers/
    └── anthropic_provider.py # ÚNICO archivo del proyecto que importa el SDK `anthropic`
```

Agregar Gemini o GPT en el futuro es: escribir `providers/gemini_provider.py` implementando la misma interfaz `LLMProvider`, agregar una rama en `factory.py`, y cambiar `LLM_PROVIDER=gemini` en el `.env`. Nada más se toca.

**Beneficio adicional de este diseño, no solo para cambiar de proveedor:** los tests de la lógica de conversación (Tarea 6) pueden usar un `LLMProvider` falso en memoria que devuelve respuestas guionadas, sin necesidad de mockear HTTP ni depender del formato de wire de ningún proveedor real. Los tests quedan más simples y más rápidos.

## Otras decisiones de arquitectura ya tomadas — léelas antes de programar

### Por qué el pago por transferencia siempre requiere un humano en esta fase

Victoria no tiene visión de imágenes integrada todavía (eso implicaría descargar el media de WhatsApp y mandarlo al LLM como imagen — se deja explícitamente fuera de alcance de esta fase). Como no puede verificar una captura de pago, la regla es **determinista en código, no una decisión del LLM**: en cuanto llega una imagen y el lead está en estado `esperando_pago`, el sistema escala automáticamente a atención humana sin pasar por Victoria. El dueño ya tiene un formulario de creación manual de pedido en el dashboard (Fase 2) para cerrar la venta una vez verificado el comprobante a mano. Los pedidos contraentrega sí los cierra Victoria sola.

### Por qué la detección de cliente con pedido previo es determinista, no una decisión de Victoria

Si un número de teléfono que ya tiene un lead en estado `despachado` vuelve a escribir, el sistema lo reconoce **antes de invocar al LLM siquiera** y escala directo a atención humana. Es una versión mínima y segura del "Flujo 3 (postventa)" del documento de planificación original — no se construye el árbol completo de casos de postventa en esta fase.

### Por qué existe un simulador de terminal

Con la app de Meta sin publicar, un mensaje real de un cliente no llega al webhook. El simulador llama directamente a la lógica de conversación (sin pasar por el webhook ni por el cliente de WhatsApp) e imprime la respuesta en la terminal.

### Separación de responsabilidades: lógica pura vs. efectos de envío

`VictoriaConversationService.procesar_turno()` recibe un mensaje del cliente y devuelve el texto de respuesta — sin llamar a `WhatsAppClient` dentro de sí misma. Quien la llama (el `BotWorker` en producción, o el script simulador en pruebas) decide qué hacer con el texto devuelto.

## Convenciones obligatorias del proyecto (recordatorio de la Fase 3.1)

- Mismo patrón de capas en todos los módulos nuevos.
- SQL crudo con psycopg2, sin ORM.
- Dinero siempre `numeric(12,2)` en BD y `Decimal` en Python, nunca `float`.
- Logging estructurado JSON.
- **Tests para todo el código nuevo.**
- Documentar en `PROGRESS.md` con el razonamiento de cada decisión.
- Si algo de aquí contradice el código real, detente y avisa antes de improvisar.

</contexto>

---

<instrucciones>

# Instrucciones generales de ejecución

- Ejecuta las tareas en el orden indicado — cada una depende de la anterior.
- Corre `pytest` completo después de cada tarea.
- **Regla dura de todo el desarrollo:** ningún archivo fuera de `backend/src/integrations/llm/providers/anthropic_provider.py` puede importar el paquete `anthropic` ni referenciar alguno de sus tipos (`anthropic.types.*`). Si en algún momento sientes la tentación de hacerlo en `services.py`, `tools.py`, o los tests del servicio de conversación, es una señal de que algo se filtró y hay que corregirlo antes de seguir.
- El proveedor concreto a usar ahora es Anthropic, modelo `claude-sonnet-5` — configurado por variables de entorno, nunca hardcodeado dentro de la lógica de negocio.
- Usa el SDK oficial `anthropic` de Python dentro del adapter (agrégalo a `requirements.txt`, fija la versión que quede instalada).
- La `ANTHROPIC_API_KEY` real debe ingresarla el usuario desde console.anthropic.com — tú solo dejas la variable lista en `.env`/`.env.example` y el código que la consume.
- Al terminar todas las tareas, entrega el resumen descrito en `<nota_final>`.

</instrucciones>

---

<requerimientos>

# Tarea 1 — Persistencia de la cola del worker

## Por qué

La cola actual (`queue.Queue` en memoria) pierde todo si el proceso se reinicia con tareas pendientes. Se agrega una tabla que registra cada tarea antes de encolarla en memoria, así el worker puede recuperar el trabajo pendiente al arrancar.

## Migración — Tabla `cola_mensajes`

```sql
-- Registro persistente de cada tarea que el BotWorker debe procesar.
-- El campo "modo" separa dos caminos: uno determinista (mensaje fijo,
-- sin pasar por el LLM) y uno que sí invoca a Victoria.
CREATE TABLE cola_mensajes (
    id                  bigserial PRIMARY KEY,
    conversacion_id     bigint NOT NULL REFERENCES conversaciones(id) ON DELETE CASCADE,
    mensaje_id          bigint REFERENCES mensajes(id) ON DELETE SET NULL,
    modo                text NOT NULL,
        -- 'ia'    → invocar a VictoriaConversationService.procesar_turno()
        -- 'fijo'  → enviar texto_fijo tal cual, sin pasar por el LLM
    texto_fijo          text,
        -- Solo si modo = 'fijo'. NULL si modo = 'ia'.
    estado              text NOT NULL DEFAULT 'pendiente',
        -- 'pendiente' | 'procesando' | 'completado' | 'error'
    intentos            integer NOT NULL DEFAULT 0,
    error_detalle       text,
    creado_en           timestamptz NOT NULL DEFAULT now(),
    procesado_en        timestamptz
);

CREATE INDEX cola_mensajes_estado_idx ON cola_mensajes(estado, creado_en);
```

## Cambios en `worker.py`

```python
"""
Flujo actualizado:

encolar(tarea):
    1. INSERT en cola_mensajes con estado='pendiente' → obtiene el id de la fila
    2. put() en la queue.Queue en memoria, incluyendo ese id (cola_mensajes_id)

_loop():
    1. get() de la queue.Queue
    2. UPDATE cola_mensajes SET estado='procesando' WHERE id = cola_mensajes_id
    3. Ejecutar la tarea (modo 'fijo' o 'ia')
    4. Si sale bien: UPDATE estado='completado', procesado_en=now()
    5. Si falla: UPDATE estado='error', error_detalle=str(excepcion), intentos += 1
       (nunca relanzar la excepción — el worker sigue vivo)

recuperar_pendientes() — se llama UNA VEZ al iniciar el worker (en iniciar()):
    1. SELECT * FROM cola_mensajes
       WHERE estado = 'pendiente'
          OR (estado = 'procesando' AND creado_en < now() - interval '5 minutes')
       ORDER BY creado_en ASC
    2. Por cada fila: put() en la queue.Queue en memoria
       (una tarea en 'procesando' hace más de 5 minutos se asume huérfana
       de un proceso anterior que murió a medio trabajar)
"""
```

## Verificación de la Tarea 1

- Test: encolar una tarea, matar el worker (sin marcarla completada), crear un `BotWorker` nuevo, llamar `iniciar()`, confirmar que la tarea se recupera y se procesa.
- Test: una tarea que falla queda con `estado='error'` y el worker sigue procesando la siguiente.
- Corre `pytest`.

</requerimientos>

---

<requerimientos>

# Tarea 2 — Base de conocimiento de productos del bot

## Por qué

Victoria necesita información de venta por producto. **Esto es completamente distinto del catálogo de Rocketfy que ya existe** (ese es para verificar stock/SKU real con fines logísticos). La base de conocimiento del bot es de contenido de ventas, y vive en tablas propias.

## Migración — Tabla `productos_bot`

```sql
-- Base de conocimiento de ventas de Victoria. Se carga manualmente por
-- ahora (sin panel de administración todavía). No confundir con el
-- catálogo de Rocketfy (ese es para SKU/stock real, no para ventas).
CREATE TABLE productos_bot (
    id                      bigserial PRIMARY KEY,
    sku                     text NOT NULL UNIQUE,
    nombre                  text NOT NULL,
    descripcion             text NOT NULL,
    precio                  numeric(12,2) NOT NULL,
    variantes               text,
    tiempo_entrega          text NOT NULL,
    metodos_pago_aceptados  text NOT NULL DEFAULT 'contraentrega, transferencia',
    preguntas_frecuentes    text,
    temas_no_responder      text,
    activo                  boolean NOT NULL DEFAULT true,
    creado_en               timestamptz NOT NULL DEFAULT now(),
    actualizado_en          timestamptz NOT NULL DEFAULT now()
);
```

## Migración — Tabla `anuncios_productos`

```sql
-- Vincula el id_anuncio (objeto referral de Meta cuando el cliente
-- viene de un anuncio FEP) con el producto correspondiente.
CREATE TABLE anuncios_productos (
    id_anuncio      text PRIMARY KEY,
    producto_sku    text NOT NULL REFERENCES productos_bot(sku),
    creado_en       timestamptz NOT NULL DEFAULT now()
);
```

## Script de carga — `backend/tools/cargar_producto_bot.py`

```python
"""
Uso:
    python tools/cargar_producto_bot.py

Pide interactivamente por consola: sku, nombre, descripcion, precio,
variantes (opcional), tiempo_entrega, metodos_pago_aceptados (default:
"contraentrega, transferencia"), preguntas_frecuentes (opcional),
temas_no_responder (opcional), id_anuncio a vincular (opcional).

Si el sku ya existe, pregunta si se desea actualizar en vez de fallar
por la restricción UNIQUE.
"""
```

## Verificación de la Tarea 2

- Aplica las migraciones, confirma en Supabase que las tablas existen.
- Corre el script y carga un producto de prueba.
- Test: repositorio de productos obtiene correctamente un producto por SKU y por id_anuncio.
- Corre `pytest`.

</requerimientos>

---

<requerimientos>

# Tarea 3 — Capa de abstracción del LLM (contratos neutrales + adaptador de Anthropic)

## Por qué

Esta es la tarea que garantiza que cambiar de proveedor de LLM en el futuro sea barato. Se define primero la interfaz y los tipos neutrales, y **después** se escribe el único adaptador concreto que existe hoy (Anthropic). Ningún otro archivo del proyecto debe conocer el SDK de Anthropic.

## Estructura de archivos

```
backend/src/integrations/llm/
├── __init__.py
├── contratos.py
├── exceptions.py
├── factory.py
└── providers/
    ├── __init__.py
    └── anthropic_provider.py
```

## `contratos.py` — los tipos neutrales y la interfaz

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class HerramientaLLM:
    """Definición de una herramienta que el LLM puede invocar.
    `parametros` es JSON Schema estándar — este formato ya es compartido
    entre proveedores, así que se define una sola vez acá. Cada adapter
    lo traduce a su propio formato de wire (Anthropic lo llama
    "input_schema", OpenAI lo envuelve distinto, etc.) — pero quien
    define la herramienta (tools.py) nunca necesita saberlo."""
    nombre: str
    descripcion: str
    parametros: dict


@dataclass
class LlamadaHerramienta:
    """El LLM pidió ejecutar una herramienta con estos argumentos."""
    id: str
    nombre: str
    entrada: dict


@dataclass
class ResultadoHerramienta:
    """El resultado de haber ejecutado una LlamadaHerramienta, para
    devolverle al LLM en el siguiente turno."""
    id_llamada: str
    contenido: str


@dataclass
class MensajeLLM:
    """Un turno de la conversación, en formato neutral."""
    rol: Literal["user", "assistant"]
    texto: str | None = None
    llamadas_herramientas: list[LlamadaHerramienta] = field(default_factory=list)
    resultados_herramientas: list[ResultadoHerramienta] = field(default_factory=list)


@dataclass
class RespuestaLLM:
    """Lo que devuelve el proveedor tras un turno."""
    texto: str
    llamadas_herramientas: list[LlamadaHerramienta]
    razon_de_parada: Literal["fin", "necesita_herramientas", "limite_alcanzado"]


class LLMProvider(ABC):
    """Contrato que cualquier proveedor de LLM debe cumplir. El servicio
    de conversación (Tarea 6) SOLO conoce esta interfaz — nunca un SDK
    concreto."""

    @abstractmethod
    def generar_respuesta(
        self,
        system: str,
        mensajes: list[MensajeLLM],
        herramientas: list[HerramientaLLM],
        max_tokens: int = 1024,
    ) -> RespuestaLLM:
        ...
```

## `exceptions.py` — neutrales, no ligadas a un proveedor

```python
class LLMAuthError(Exception):
    """Credenciales inválidas o faltantes, sin importar el proveedor."""

class LLMRequestError(Exception):
    """Error de red, timeout, o error de servidor del proveedor."""

class LLMRateLimitError(Exception):
    """Se alcanzó el límite de rate limit — reintentable con backoff."""
```

## `providers/anthropic_provider.py` — el único archivo que importa `anthropic`

```python
"""
AnthropicProvider implementa LLMProvider. Aquí, y solo aquí, se traduce
entre los tipos neutrales de contratos.py y el SDK/wire format de
Anthropic.

Traducción de entrada (neutral → Anthropic):
    - HerramientaLLM → {"name": nombre, "description": descripcion, "input_schema": parametros}
    - MensajeLLM con texto → {"role": rol, "content": texto}
    - MensajeLLM con llamadas_herramientas (viene de un turno anterior
      del propio asistente) → {"role": "assistant", "content": [bloques
      de tipo "tool_use" reconstruidos]}
    - MensajeLLM con resultados_herramientas → {"role": "user", "content":
      [{"type": "tool_result", "tool_use_id": id_llamada, "content": contenido}, ...]}
    - system se pasa tal cual al parámetro `system` de la API de Anthropic

Llamada real:
    self._client.messages.create(
        model=self._modelo,   # viene de LLM_MODEL, default "claude-sonnet-5"
        max_tokens=max_tokens,
        system=system,
        messages=mensajes_traducidos,
        tools=herramientas_traducidas,
    )

Traducción de salida (Anthropic → neutral):
    - Concatenar todos los bloques content de tipo "text" → RespuestaLLM.texto
    - Cada bloque de tipo "tool_use" → LlamadaHerramienta(id=block.id, nombre=block.name, entrada=block.input)
    - stop_reason "tool_use" → razon_de_parada = "necesita_herramientas"
    - stop_reason "end_turn" → razon_de_parada = "fin"
    - stop_reason "max_tokens" → razon_de_parada = "limite_alcanzado"

Manejo de errores:
    - anthropic.AuthenticationError → LLMAuthError
    - anthropic.RateLimitError → LLMRateLimitError
    - anthropic.APIConnectionError, timeout → LLMRequestError
    - Cualquier otro anthropic.APIStatusError → LLMRequestError

El constructor recibe el modelo y la api_key ya resueltos desde
settings — no lee variables de entorno directamente, para que sea
fácil de instanciar en tests con valores de prueba.
"""
```

## `factory.py`

```python
"""
def get_llm_client() -> LLMProvider:
    proveedor = settings.LLM_PROVIDER  # "anthropic" por ahora

    if proveedor == "anthropic":
        return AnthropicProvider(
            api_key=settings.ANTHROPIC_API_KEY,
            modelo=settings.LLM_MODEL,
        )

    # Cuando se agregue un proveedor nuevo en el futuro, se suma acá:
    # elif proveedor == "openai":
    #     return OpenAIProvider(api_key=settings.OPENAI_API_KEY, modelo=settings.LLM_MODEL)
    # elif proveedor == "gemini":
    #     return GeminiProvider(api_key=settings.GEMINI_API_KEY, modelo=settings.LLM_MODEL)

    raise ValueError(f"Proveedor de LLM no soportado: {proveedor}")

Cacheado con functools.lru_cache, mismo patrón que los otros factories
del proyecto.
"""
```

## Variables de entorno nuevas

```env
# Selecciona el proveedor de LLM activo. Hoy solo existe el adapter de
# "anthropic" — agregar otro proveedor en el futuro es escribir su
# adapter y sumarlo acá, sin tocar el resto del sistema.
LLM_PROVIDER=anthropic

# Modelo a usar, interpretado por el adapter del proveedor activo.
LLM_MODEL=claude-sonnet-5

# Ya existía vacía desde la Fase 3.1 — ahora se vuelve requerida
# (fail-fast) SOLO SI LLM_PROVIDER=anthropic.
ANTHROPIC_API_KEY=

# Límites de seguridad del loop de conversación (ver Tarea 6)
BOT_MAX_TURNOS_HERRAMIENTAS=5
BOT_MAX_MENSAJES_HISTORIAL=40
```

En `settings.py`: la validación fail-fast de `ANTHROPIC_API_KEY` debe ser condicional a que `LLM_PROVIDER == "anthropic"` (no una validación ciega) — así el día que se cambie de proveedor, la variable que se exige por fail-fast es la que corresponda a ese proveedor, no siempre la de Anthropic.

> **Nota para ti, CLI:** la `ANTHROPIC_API_KEY` real la pega el usuario en su `.env` local. Avísale explícitamente en tu resumen final si llegaste a un punto donde la necesitas y no está disponible.

## Verificación de la Tarea 3

- Tests de `AnthropicProvider` mockeando el SDK: confirma que la traducción neutral → Anthropic y Anthropic → neutral es correcta en ambas direcciones (incluyendo un caso con `tool_use` y otro con `resultados_herramientas`).
- Test: 401 → `LLMAuthError`, 429 → `LLMRateLimitError`, timeout → `LLMRequestError`.
- Test de `factory.py`: `LLM_PROVIDER=anthropic` devuelve una instancia de `AnthropicProvider`; un valor no soportado lanza `ValueError`.
- **Test de contención:** un test que recorra los archivos de `backend/src/routes/whatsapp/` y `backend/src/integrations/llm/contratos.py`, `factory.py`, `exceptions.py` y confirme que ninguno contiene la cadena `import anthropic` ni `from anthropic` — esto detecta automáticamente si en algún momento el SDK se filtró fuera de `anthropic_provider.py`.
- Corre `pytest`.

</requerimientos>

---

<requerimientos>

# Tarea 4 — Las herramientas (tools) que Victoria puede usar

## Por qué

En vez de que Victoria devuelva un JSON de estado en texto libre, usa el mecanismo de tool use del LLM: puede llamar funciones estructuradas durante la conversación. Los esquemas se definen en el formato neutral (`HerramientaLLM`) de la Tarea 3 — nunca en el formato de wire de un proveedor específico.

## Dónde viven

`backend/src/routes/whatsapp/tools.py`

## Los 5 esquemas de herramientas, en formato neutral

```python
from src.integrations.llm.contratos import HerramientaLLM

HERRAMIENTAS_VICTORIA = [
    HerramientaLLM(
        nombre="guardar_datos_cliente",
        descripcion=(
            "Guarda o actualiza los datos de contacto y envío del cliente "
            "a medida que los va confirmando en la conversación. Llama esta "
            "herramienta cada vez que el cliente confirme un dato nuevo — "
            "no esperes a tener todos los datos para llamarla."
        ),
        parametros={
            "type": "object",
            "properties": {
                "nombre_cliente": {"type": "string"},
                "direccion": {"type": "string"},
                "canton": {"type": "string"},
                "provincia": {"type": "string"},
            },
        },
    ),
    HerramientaLLM(
        nombre="registrar_producto",
        descripcion=(
            "Registra qué producto quiere comprar el cliente y el total a "
            "cobrar. Llámala en cuanto el cliente confirme un producto "
            "específico."
        ),
        parametros={
            "type": "object",
            "properties": {
                "producto_sku": {"type": "string"},
                "producto_nombre": {"type": "string"},
                "total": {
                    "type": "number",
                    "description": "Precio total en dólares, hasta 2 decimales",
                },
            },
            "required": ["producto_sku", "producto_nombre", "total"],
        },
    ),
    HerramientaLLM(
        nombre="registrar_metodo_pago",
        descripcion="Registra cómo va a pagar el cliente.",
        parametros={
            "type": "object",
            "properties": {
                "metodo_pago": {
                    "type": "string",
                    "enum": ["contraentrega", "transferencia"],
                },
            },
            "required": ["metodo_pago"],
        },
    ),
    HerramientaLLM(
        nombre="cerrar_venta",
        descripcion=(
            "Cierra la venta y dispara el envío del pedido. Solo llama esta "
            "herramienta cuando tengas confirmados TODOS estos datos: "
            "nombre del cliente, dirección completa, cantón, provincia, "
            "producto y método de pago. Si el método de pago es "
            "transferencia, esta herramienta te va a decir que falta "
            "verificar el comprobante. No la llames si falta cualquier dato."
        ),
        parametros={"type": "object", "properties": {}},
    ),
    HerramientaLLM(
        nombre="escalar_a_humano",
        descripcion=(
            "Transfiere la conversación a un asesor humano y deja de "
            "responder automáticamente. Úsala cuando: el cliente pregunta "
            "algo que no está en tu información del producto, pide "
            "explícitamente hablar con una persona, no puedes interpretar "
            "con confianza lo que quiere, o cualquier situación ambigua. "
            "Nunca inventes información — si dudas, escala."
        ),
        parametros={
            "type": "object",
            "properties": {
                "motivo": {
                    "type": "string",
                    "description": "Breve explicación de por qué se escala.",
                },
            },
            "required": ["motivo"],
        },
    ),
]
```

## Los handlers — qué hace cada herramienta cuando se ejecuta

Cada handler recibe `(lead_id: int, conversacion_id: int, entrada: dict) -> ResultadoHerramienta` (el tipo neutral de la Tarea 3, no un dict suelto).

**`handle_guardar_datos_cliente`:**
```python
"""
UPDATE leads SET
    nombre_cliente = COALESCE(:nombre_cliente, nombre_cliente),
    direccion      = COALESCE(:direccion, direccion),
    canton         = COALESCE(:canton, canton),
    provincia      = COALESCE(:provincia, provincia),
    actualizado_en = now()
WHERE id = :lead_id

Devuelve ResultadoHerramienta(contenido="Datos guardados correctamente.")
"""
```

**`handle_registrar_producto`:**
```python
"""
UPDATE leads SET producto_sku=:sku, producto_nombre=:nombre, total=:total,
    actualizado_en=now() WHERE id=:lead_id

Devuelve ResultadoHerramienta(contenido="Producto registrado.")
"""
```

**`handle_registrar_metodo_pago`:**
```python
"""
UPDATE leads SET
    metodo_pago = :metodo_pago,
    estado = CASE WHEN :metodo_pago = 'transferencia' THEN 'esperando_pago' ELSE estado END,
    actualizado_en = now()
WHERE id = :lead_id

Devuelve ResultadoHerramienta(contenido="Método de pago registrado.")
"""
```

**`handle_cerrar_venta`** — el más importante, con lógica de negocio real:

```python
"""
1. Leer el lead completo desde BD.

2. Validar que estén todos los campos requeridos (nombre_cliente,
   direccion, canton, provincia, producto_sku, producto_nombre, total,
   metodo_pago). Si falta alguno:
   → ResultadoHerramienta(contenido="Faltan datos: <lista>. Pide esos datos al cliente antes de intentar cerrar de nuevo.")
   (No se toca BD ni se llama a Rocketfy.)

3. Si metodo_pago == 'transferencia':
   → ResultadoHerramienta(contenido="Este pedido es por transferencia. Pide al cliente la foto del comprobante antes de continuar. No se puede cerrar todavía.")
   (No se llama a Rocketfy — el cierre pasa por verificación humana de la imagen.)

4. Si metodo_pago == 'contraentrega':
   a. Armar CrearPedidoInputDTO (idLocal=int(time.time()), datos del lead,
      noContraEntrega=False, lineas=[{sku, nombre, cantidad=1}]).
   b. Llamar directamente: PedidoService(client=get_rocketfy_client()).crear_y_confirmar(dto)
   c. Según resultado:
      - 'confirmado' → UPDATE leads SET estado='despachado', id_pedido_local=..., id_pedido_rocketfy=...
        → ResultadoHerramienta(contenido=f"¡Pedido confirmado! Llega en {producto.tiempo_entrega}. Comunícaselo al cliente y agradécele.")
      - Error ambiguo (409, pendiente_creacion) → llamar automáticamente a
        handle_escalar_a_humano(motivo="Error ambiguo al confirmar en Rocketfy, requiere revisión manual.")
        → ResultadoHerramienta(contenido="Hubo un problema técnico. Ya se avisó a un asesor humano — dile al cliente que en breve le confirman.")
      - Error de regla de negocio (422) → llamar automáticamente a
        handle_escalar_a_humano(motivo=f"Rocketfy rechazó la confirmación: {mensaje_error}")
        → ResultadoHerramienta(contenido="No se pudo confirmar por una regla del proveedor de envíos. Ya se avisó a un asesor.")

Nota de diseño: los fallos de Rocketfy SIEMPRE escalan a un humano
automáticamente — nunca se deja que Victoria decida cómo manejar el
fallo. Cerrar una venta real es el punto de máximo riesgo; el manejo
de errores es código determinista, no criterio del modelo.
"""
```

**`handle_escalar_a_humano`:**
```python
"""
1. UPDATE conversaciones SET estado='escalada' WHERE id=:conversacion_id
2. TelegramNotifier.notificar_escalado(conversacion_id, telefono, motivo)
   (si Telegram no está configurado, esto solo loguea una advertencia)
3. Devuelve ResultadoHerramienta(contenido="Escalado correctamente. Este es tu último mensaje — despídete cordialmente informando que un asesor la va a contactar en breve.")
"""
```

## Verificación de la Tarea 4

- Test de cada handler por separado, con `PedidoService` mockeado (`responses`, igual que Rocketfy en los tests existentes).
- Test: `cerrar_venta` con datos incompletos → no llama a Rocketfy, devuelve qué falta.
- Test: `cerrar_venta` con transferencia → no llama a Rocketfy, pide comprobante.
- Test: `cerrar_venta` con contraentrega y Rocketfy devolviendo 422 → escala automáticamente.
- Todos los tests de esta tarea trabajan con `ResultadoHerramienta` (el tipo neutral) — ninguno debe importar nada de `anthropic`.
- Corre `pytest`.

</requerimientos>

---

<requerimientos>

# Tarea 5 — El system prompt de Victoria

## Por qué

El system prompt es la pieza más importante del bot — define su personalidad, sus límites, y cuándo debe rendirse en vez de inventar. Vive en un archivo de texto separado del código. Este archivo es independiente de qué proveedor de LLM esté activo — es solo texto que se le pasa al parámetro `system` de `generar_respuesta()`.

## Archivo: `backend/src/routes/whatsapp/victoria_system_prompt.txt`

```text
Eres Victoria, asesora de ventas de AzoShop, una tienda online ecuatoriana.

## Tu personalidad
Hablas como una persona real, cercana y profesional — nunca te presentas
como un bot ni mencionas que eres inteligencia artificial, a menos que el
cliente te lo pregunte directamente. En ese caso, sé honesta pero breve,
y sigue ayudando con la venta.

Escribes en español ecuatoriano natural, con mensajes cortos como los que
manda una persona real por WhatsApp — no párrafos largos. Puedes usar
emojis con moderación, sin exagerar.

## Tu objetivo
Cerrar la venta del producto sobre el que te están preguntando. Tu
proceso natural es: saludar, presentar o resolver dudas del producto,
intentar cerrar la venta, recopilar los datos de envío, definir el
método de pago, y confirmar el pedido.

## Información del producto de esta conversación
{contexto_producto}

## Reglas que nunca rompes
- Nunca inventas información que no esté en la sección de arriba. Si no
  sabes algo, dilo con naturalidad y usa la herramienta escalar_a_humano.
- Nunca ofreces descuentos, promociones, o condiciones que no estén
  explícitamente en la información del producto.
- Nunca prometes un tiempo de entrega distinto al que aparece arriba.
- Si el cliente pregunta por devoluciones, garantías, o problemas con un
  pedido anterior, usa escalar_a_humano — no intentes resolverlo tú.
- Si el cliente pide explícitamente hablar con una persona, usa
  escalar_a_humano de inmediato.
- Si después de dos intentos claros no logras entender qué quiere el
  cliente, usa escalar_a_humano en vez de seguir adivinando.

## Cómo usar tus herramientas
- Guarda cada dato del cliente (nombre, dirección, cantón, provincia) en
  cuanto te lo confirme, con guardar_datos_cliente — no esperes a tener
  todo para guardar.
- En cuanto el cliente confirme qué producto quiere, usa registrar_producto.
- En cuanto te diga cómo va a pagar, usa registrar_metodo_pago.
- Cuando ya tengas todos los datos confirmados, intenta cerrar con
  cerrar_venta. Si te dice que falta algo, sigue pidiendo justo eso.

## Estado actual de este lead (lo que ya se sabe de este cliente)
{contexto_lead_actual}

## Fecha de hoy
{fecha_actual}
```

## Cómo se arman los placeholders (los rellena el servicio, Tarea 6)

- `{contexto_producto}`: si hay un producto vinculado a la conversación (por FEP o ya registrado), se arma con los campos de `productos_bot`. Si no hay ninguno, se arma con una lista breve de productos activos disponibles y la instrucción de identificar cuál le interesa al cliente.
- `{contexto_lead_actual}`: resumen en texto plano de qué campos del lead ya están llenos y cuáles faltan.
- `{fecha_actual}`: fecha de hoy en formato legible.

## Verificación de la Tarea 5

- No requiere tests automatizados, pero debe probarse manualmente con el simulador de la Tarea 8 antes de cerrar la fase.

</requerimientos>

---

<requerimientos>

# Tarea 6 — El servicio conversacional (`VictoriaConversationService`)

## Por qué

Arma todo el contexto, ejecuta el loop de tool use, y devuelve el texto final para el cliente. **Trabaja exclusivamente con los tipos neutrales de `contratos.py`** — no conoce ni le importa qué proveedor de LLM está detrás de `LLMProvider`. Recibe el cliente LLM por inyección (vía `get_llm_client()`), nunca instancia un proveedor concreto directamente.

## Ubicación

`backend/src/routes/whatsapp/conversation_service.py`

## El método principal

```python
def procesar_turno(self, conversacion_id: int, mensaje_cliente: str) -> str:
    """
    1. Obtener el lead asociado a esta conversación (crear uno vacío si
       no existe todavía).

    2. Determinar el producto de contexto:
       - Si el lead ya tiene producto_sku → usar ese.
       - Si no, pero la conversación tiene id_anuncio (FEP) → buscar en
         anuncios_productos el sku vinculado.
       - Si tampoco hay eso → modo catálogo genérico.

    3. Armar el system prompt final rellenando los placeholders de
       victoria_system_prompt.txt.

    4. Obtener el historial de MensajeLLM de la conversación (máximo
       BOT_MAX_MENSAJES_HISTORIAL), convirtiendo rol 'cliente'→'user',
       'bot'/'humano'→'assistant'.

    5. Agregar el mensaje_cliente actual como el último MensajeLLM 'user'.

    6. EL LOOP DE HERRAMIENTAS (máximo BOT_MAX_TURNOS_HERRAMIENTAS
       iteraciones):

       mensajes: list[MensajeLLM] = historial + [mensaje_actual]
       texto_final = ""

       repetir hasta BOT_MAX_TURNOS_HERRAMIENTAS veces:
           respuesta: RespuestaLLM = self._llm.generar_respuesta(
               system=system_prompt_armado,
               mensajes=mensajes,
               herramientas=HERRAMIENTAS_VICTORIA,
           )

           texto_final += respuesta.texto

           si respuesta.razon_de_parada == "fin":
               romper el loop — texto_final es la respuesta definitiva

           si respuesta.razon_de_parada == "necesita_herramientas":
               agregar un MensajeLLM(rol="assistant", texto=respuesta.texto,
                   llamadas_herramientas=respuesta.llamadas_herramientas) a `mensajes`

               resultados = []
               por cada llamada en respuesta.llamadas_herramientas:
                   ejecutar el handler correspondiente (Tarea 4),
                   obtener un ResultadoHerramienta
                   resultados.append(ese resultado)

               agregar un MensajeLLM(rol="user", resultados_herramientas=resultados) a `mensajes`

               (si escalar_a_humano fue una de las llamadas: permitir
               una iteración más para que el LLM genere la despedida
               con el resultado que le llegó, pero no más que esa)

       si se alcanzó el máximo de iteraciones sin llegar a "fin":
           ejecutar handle_escalar_a_humano directamente (motivo="Se
           alcanzó el límite de turnos de herramientas sin resolver")
           devolver un mensaje fijo de disculpa + espera de un asesor

    7. Guardar texto_final en la tabla mensajes con rol='bot'.

    8. Devolver texto_final.
    """
```

## Reglas deterministas ANTES de llegar a este método (van en `WebhookService`)

```python
"""
Al recibir un mensaje nuevo (después de guardarlo y marcar leído):

1. Si conversaciones.estado == 'escalada' → no hacer nada más.

2. Si existe algún lead de este teléfono con estado == 'despachado'
   (posible caso de postventa):
   → UPDATE conversaciones SET estado='escalada'
   → Notificar Telegram (motivo="Cliente con pedido previo escribió de nuevo")
   → Encolar tarea modo='fijo': "¡Hola de nuevo! Ya te conecto con
     nuestro equipo de atención, en un momento te responden 🙋"
   → NO se invoca al LLM para este mensaje.

3. Si el mensaje es tipo 'imagen' Y el lead tiene estado == 'esperando_pago':
   → UPDATE conversaciones SET estado='escalada'
   → Notificar Telegram (motivo="Cliente envió posible comprobante de pago")
   → Encolar tarea modo='fijo': "¡Gracias! Ya recibimos tu comprobante,
     en un momento uno de nuestros asesores lo confirma ✅"
   → NO se invoca al LLM para este mensaje.

4. Cualquier otro caso → encolar tarea modo='ia'.
"""
```

## Verificación de la Tarea 6

- Test del loop de herramientas usando un **`LLMProvider` falso propio** (una clase de prueba que implementa la interfaz `LLMProvider` y devuelve una secuencia guionada de `RespuestaLLM` — sin mockear HTTP ni nada de Anthropic): una respuesta con `razon_de_parada="necesita_herramientas"` seguida de una con `"fin"` → el loop termina correctamente.
- Test: se alcanza el máximo de iteraciones → escala automáticamente.
- Test de las 4 reglas deterministas del `WebhookService`, con repositorios en memoria.
- Ninguno de estos tests debe importar `anthropic`.
- Corre `pytest`.

</requerimientos>

---

<requerimientos>

# Tarea 7 — Notificaciones por Telegram

## Por qué

Cuando el bot escala, el dueño necesita enterarse en tiempo real.

## Estructura

```
backend/src/integrations/telegram/
├── __init__.py
├── client.py
└── factory.py
```

## `client.py`

```python
"""
TelegramNotifier.notificar_escalado(conversacion_id, telefono, motivo) -> None

POST a https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage
Body: {"chat_id": TELEGRAM_CHAT_ID, "text": f"🔴 Victoria escaló una conversación\\n\\nTeléfono: {telefono}\\nMotivo: {motivo}\\nConversación ID: {conversacion_id}"}

MUY IMPORTANTE: si TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID están vacíos,
este método NO falla — solo loguea una advertencia una vez y retorna.
Cualquier error de red tampoco se propaga — notificar es best-effort,
nunca debe tumbar el flujo principal de escalado.
"""
```

## Verificación de la Tarea 7

- Test: con credenciales configuradas, se hace el POST correcto.
- Test: con credenciales vacías, no se hace ninguna llamada HTTP y no se lanza excepción.
- Test: si la llamada HTTP falla, no se propaga la excepción.
- Corre `pytest`.

</requerimientos>

---

<requerimientos>

# Tarea 8 — Simulador de conversación en terminal

## Por qué

Con la app de Meta sin publicar, no hay forma de conversar de ida y vuelta con Victoria a través de WhatsApp todavía. Este script prueba toda la lógica sin depender de WhatsApp.

## Archivo: `backend/tools/chat_con_victoria.py`

```python
"""
Uso: python tools/chat_con_victoria.py [--telefono 593999999999]

1. Busca o crea una conversación para ese teléfono (origen='directo').
2. Loop: "Tú: " → procesar_turno() → "Victoria: <respuesta>"
   Si la conversación queda 'escalada', avisa y termina el loop.
3. "/reset" — borra conversación y lead de este teléfono, empieza de cero.
4. "/estado" — imprime el estado completo del lead actual.
5. Ctrl+C o "/salir" para terminar.

NO llama a WhatsAppClient en ningún momento.
"""
```

## Verificación de la Tarea 8

- Simula al menos dos conversaciones completas:
  1. Una que termine en venta cerrada por contraentrega (con un producto de prueba cargado con el script de la Tarea 2).
  2. Una donde el cliente pregunte algo fuera de la información del producto y confirmes que Victoria escala correctamente.
- Pega la transcripción completa de ambas en tu resumen final (Tarea 10).

</requerimientos>

---

<requerimientos>

# Tarea 9 — Conectar el worker real

## Cambios en `worker.py`

```python
# modo == 'ia':
texto_respuesta = victoria_conversation_service.procesar_turno(
    conversacion_id=tarea.conversacion_id,
    mensaje_cliente=tarea.texto_mensaje_cliente,
)
whatsapp_client.enviar_texto(telefono=tarea.telefono, mensaje=texto_respuesta)

# modo == 'fijo':
whatsapp_client.enviar_texto(telefono=tarea.telefono, mensaje=tarea.texto_fijo)
```

## Verificación de la Tarea 9

- Corre el `pytest` completo del proyecto — todos los tests (129 anteriores + todos los nuevos) deben pasar.
- Reporta el conteo final exacto de tests y el resultado.

</requerimientos>

---

<requerimientos>

# Tarea 10 — Documentación en PROGRESS.md

## Qué documentar

Sección **"Fase 3.2 — Victoria con un LLM Desacoplado como Cerebro"** en `PROGRESS.md`:

- La decisión de desacoplar el proveedor de LLM detrás de `LLMProvider` — el razonamiento completo (pedido explícito del dueño del negocio: poder cambiar de Anthropic a otro proveedor sin tocar lógica), y cómo el test de contención (Tarea 3) protege esta propiedad hacia adelante.
- Otras decisiones: tool use en vez de JSON parseado, transferencia siempre requiere humano, detección determinista de cliente con pedido previo.
- Tablas nuevas (`cola_mensajes`, `productos_bot`, `anuncios_productos`).
- Las 5 herramientas de Victoria.
- El loop de tool use y sus límites de seguridad.
- Transcripciones completas del simulador (Tarea 8).
- Tests agregados y resultado de `pytest` completo.
- Pendientes abiertos: verificación real de imágenes de pago con visión, panel de administración para `productos_bot`, reactivar conversaciones escaladas desde el dashboard, Flujo 2 (formulario web), Flujo 4 completo, publicar la app de Meta, número real de producción, y agregar un segundo proveedor de LLM cuando se necesite (documentar que la arquitectura ya está lista para eso).

</requerimientos>

---

<nota_final>

# Resumen final al terminar

Cuando termines, dale al usuario un resumen con:

1. **Tests:** conteo total y resultado de `pytest` completo, incluyendo confirmación explícita de que el test de contención (ningún archivo fuera de `anthropic_provider.py` importa `anthropic`) pasa.
2. **Transcripciones del simulador:** las dos conversaciones completas de la Tarea 8.
3. **Confirmación de la `ANTHROPIC_API_KEY`:** si el usuario ya la había puesto, pudiste probar contra la API real; si no, dilo explícitamente.
4. **Desvíos:** cualquier decisión distinta a la especificada, y por qué.
5. **Estado de Telegram:** si todavía no está configurado, confirma que el sistema funciona igual sin fallar.

Con ese resumen, Claude Web va a:
- Guiar al usuario para crear el bot de Telegram real (vía @BotFather).
- Decidir junto con él el siguiente paso: publicar la app de Meta, migrar el número real, o seguir afinando el system prompt con más pruebas del simulador.

</nota_final>
