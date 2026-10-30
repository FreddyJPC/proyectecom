# Conceptos Técnicos — explicado para Freddy

> Este archivo acumula explicaciones de cosas técnicas que van apareciendo
> durante el desarrollo (connection strings, MCP, configuraciones, etc.),
> para no llenar el chat de explicaciones repetidas y poder volver a
> consultarlas cuando haga falta. Se agrega contenido nuevo al final de cada
> sección o como sección nueva — no se borra lo anterior.
>
> Si algo de aquí no te queda claro o quieres que profundice, dímelo y lo
> ampliamos, no hay problema en volver sobre un tema.

---

## Índice

1. [Connection string de Postgres — qué es y sus partes](#1-connection-string-de-postgres)
2. [Direct connection vs Connection Pooler — por qué usamos el pooler](#2-direct-connection-vs-connection-pooler)
3. [Archivos `.env` / `.env.example` — por qué existen y por qué nunca se suben a git](#3-archivos-env--envexample)
4. [Qué es MCP (Model Context Protocol)](#4-qué-es-mcp-model-context-protocol)
5. [MCP local vs MCP remoto (HTTP/OAuth) — lo que configuraste](#5-mcp-local-vs-mcp-remoto)
6. [Personal Access Token / OAuth y por qué importa el alcance (scopes)](#6-personal-access-token--oauth-y-el-alcance-scopes)
7. [Por qué hace falta reiniciar la sesión para ver nuevas herramientas MCP](#7-por-qué-reiniciar-la-sesión)
8. [Qué significa "publicar/desplegar" el backend, y por qué hace falta para el webhook](#8-qué-significa-publicardesplegar-el-backend)
9. [Por qué Victoria "usa herramientas" en vez de solo escribir texto, y qué significa que el LLM esté "desacoplado"](#9-por-qué-victoria-usa-herramientas-y-qué-significa-que-el-llm-esté-desacoplado)
10. [Proceso e hilo (thread) — la base para entender worker y gunicorn](#10-proceso-e-hilo-thread)
11. [Worker — las dos cosas distintas que se llaman así en este proyecto](#11-worker)
12. [Gunicorn — el servidor que corre tu backend en producción](#12-gunicorn)
13. [Scheduler — el "despertador" de las tareas automáticas](#13-scheduler)
14. [Job — cada tarea automática concreta](#14-job)
15. [Firma del webhook (HMAC) y App Secret](#15-firma-del-webhook-hmac-y-app-secret)
16. [Monorepo y Root Directory](#16-monorepo-y-root-directory)
17. [Diseño responsivo y "mobile-first"](#17-diseño-responsivo-y-mobile-first)
18. [Tokens de diseño y modo oscuro](#18-tokens-de-diseño-y-modo-oscuro)
19. [Accesibilidad (WCAG) y cómo se mide](#19-accesibilidad-wcag-y-cómo-se-mide)

---

## 1. Connection string de Postgres

Una connection string es, literalmente, todos los datos que hacen falta para
conectarse a una base de datos, empaquetados en una sola línea de texto con
un formato estándar. La que usamos tiene esta forma:

```
postgresql://postgres.xugulrtvulrqkpcaldwf:[PASSWORD]@aws-0-us-west-2.pooler.supabase.com:5432/postgres
```

Desglosada:

| Parte | Valor en tu caso | Qué es |
|---|---|---|
| `postgresql://` | — | El "protocolo": le dice a cualquier librería que esto es una conexión Postgres |
| `postgres.xugulrtvulrqkpcaldwf` | usuario | El usuario de base de datos. En Supabase, cuando usas el pooler, el usuario lleva pegado tu project ref (`xugulrtvulrqkpcaldwf`) para que el pooler sepa a qué proyecto rutear la conexión, ya que un solo pooler atiende a muchos proyectos de muchos clientes |
| `[PASSWORD]` | tu contraseña de DB | La contraseña del usuario `postgres` de tu proyecto (la definiste al crear el proyecto, o la reseteas desde el dashboard) |
| `aws-0-us-west-2.pooler.supabase.com` | host | El servidor al que te conectas. No es "tu" base de datos directamente — es un intermediario (más detalle en la sección 2) |
| `5432` | puerto | El puerto estándar de Postgres. (Fíjate que también existe el `6543` — ver sección 2) |
| `postgres` (al final) | nombre de la base | La base de datos dentro del servidor. Supabase, por defecto, usa una sola base llamada `postgres` para todo tu proyecto (los "schemas" dentro de ella son los que separan cosas, como `public`, `auth`, etc.) |

Cualquier programa (psycopg2 en Python, `psql`, un ORM, etc.) puede tomar esa
única línea y saber exactamente cómo conectarse, sin que tengas que pasarle
5 parámetros sueltos.

---

## 2. Direct connection vs Connection Pooler

Supabase te ofrece más de una forma de conectarte a la misma base de datos,
y no es capricho — resuelven problemas distintos.

**Direct connection** (`db.<project-ref>.supabase.co:5432`): te conecta
directo al servidor Postgres real, sin intermediarios. Es la más simple
conceptualmente, pero tiene dos límites:
- Postgres solo aguanta un número limitado de conexiones simultáneas (en
  planes chicos, unas decenas). Si tu backend abre muchas conexiones a la
  vez (por ejemplo, varias peticiones HTTP llegando al mismo tiempo, cada
  una abriendo su propia conexión), te puedes quedar sin cupo.
- Desde hace un tiempo, Supabase solo le da a este host una dirección
  **IPv6** por defecto (a menos que pagues un add-on de IPv4 dedicada). Es
  justo lo que nos pasó: el entorno donde yo ejecuto comandos no tiene salida
  IPv6, así que no pude resolver ese host.

**Connection Pooler** (`aws-0-<región>.pooler.supabase.com`, el que usamos):
en vez de conectarte directo a Postgres, te conectas a un programa
intermediario llamado **Supavisor** (antes se usaba PgBouncer). Ese programa
mantiene un grupo ("pool") de conexiones ya abiertas hacia Postgres, y te
"presta" una cada vez que la necesitas, devolviéndola al pool cuando terminas.
Así, cientos de peticiones de tu app pueden compartir un puñado de conexiones
reales a la base, en vez de que cada una abra la suya. Además, este host sí
tiene dirección IPv4, por eso nos funcionó.

Dos modos del pooler, por si los ves en el dashboard:
- **Transaction mode** (puerto `6543`): la conexión se presta solo durante
  una transacción y se devuelve enseguida. Ideal para backends web con
  muchas peticiones cortas (nuestro caso, cuando el backend esté corriendo).
- **Session mode** (puerto `5432`, el que usamos ahora): la conexión se
  mantiene mientras dure tu sesión/script. Más parecido a una conexión
  directa. Lo usamos aquí porque `apply_migrations.py` es un script que
  corre una vez y termina, no un servidor con tráfico constante.

Cuando construyamos el backend de verdad (Etapa 0 en adelante), probablemente
usemos el pooler en modo transacción para las conexiones normales de la app.

---

## 3. Archivos `.env` / `.env.example`

Un programa necesita "secretos" para funcionar: contraseñas de base de
datos, tokens de APIs externas, etc. Hay dos formas malas de manejarlos y
una buena:

- **Mala:** escribirlos directo en el código fuente (lo que encontramos en
  `BACKEND/src/netsuite_core/config.py` del proyecto de ejemplo). El
  problema es que el código se comparte, se sube a git, lo ve cualquiera que
  tenga acceso al repo — y si el repo se hace público por error, el secreto
  queda expuesto para siempre en el historial.
- **Buena:** el código lee los secretos desde **variables de entorno**
  (`os.getenv("SUPABASE_DB_URL")` en Python), y esas variables se definen en
  un archivo `.env` que **nunca se sube a git** (por eso existe
  `PROYECTECOM/.gitignore` con la línea `*.env`).

`.env.example` es el archivo hermano que **sí se sube a git**: tiene la
misma lista de variables, pero vacías o con valores de ejemplo. Sirve como
"plantilla" — cuando alguien más clona el proyecto (o tú mismo en otra
máquina), sabe exactamente qué variables tiene que rellenar sin que nadie
tenga que pasarle los secretos reales por chat o email.

---

## 4. Qué es MCP (Model Context Protocol)

Por defecto, yo (Claude) solo puedo hacer lo que mis herramientas
incorporadas me dejan: leer/escribir archivos, correr comandos de terminal,
etc. No tengo forma nativa de, por ejemplo, "hablar" con tu cuenta de
Supabase, o con Slack, o con Jira.

**MCP (Model Context Protocol)** es un estándar abierto (creado por
Anthropic, pero cualquiera lo puede implementar) que define cómo un programa
externo — un "servidor MCP" — le puede ofrecer herramientas nuevas a un
asistente de IA. Cuando registras un servidor MCP, básicamente le estás
diciendo a Claude Code: "aquí hay un programa que sabe hablar con Supabase;
apréndete las funciones que ofrece (crear tablas, correr SQL, listar
proyectos, etc.) y trátalas como si fueran herramientas tuyas".

Cada empresa/producto que quiere que las IAs trabajen con sus datos puede
publicar su propio servidor MCP. Supabase publicó uno oficial — es el que
registraste.

---

## 5. MCP local vs MCP remoto

Cuando te di el comando original, era para un MCP **local** (`stdio`): un
programita (`npx @supabase/mcp-server-supabase`) que se instala y corre **en
tu propia máquina**, y habla con la API de Supabase usando un token que tú
le pasas.

Tú en cambio configuraste el MCP **remoto** (`--transport http`), que apunta
a un servidor que corre en la infraestructura de Supabase
(`https://mcp.supabase.com/mcp`), no en tu máquina. En vez de darle un token
manualmente, hiciste login por **OAuth** (el mismo flujo de "iniciar sesión
con Google/GitHub" que usas en cualquier web) directo contra tu cuenta de
Supabase. Es una alternativa perfectamente válida y en algunos sentidos más
cómoda — no tienes que generar ni guardar un token tú mismo. La diferencia
práctica es que la sesión se autentica contra tu cuenta completa de
Supabase en vez de contra un token acotado a un solo proyecto, por eso te
comenté lo del parámetro `--features` (qué categorías de acciones puede
hacer ese MCP: solo base de datos, o también manejar otros proyectos,
branches, funciones, etc.).

---

## 6. Personal Access Token / OAuth y el alcance (scopes)

Un **token** es una credencial que representa "quién sos" ante un sistema,
sin tener que mandar tu contraseña real cada vez. Un **Personal Access
Token (PAT)** es un token que generas manualmente desde el dashboard de un
servicio (Supabase, GitHub, etc.) para que una herramienta externa actúe en
tu nombre.

El **alcance (scope)** es qué le permites hacer a ese token. Es la misma
lógica que cuando una app te pide permiso en el celular: "quiere acceder a
tus contactos" — puedes decir que sí a contactos pero no a la cámara. Con
Supabase, el equivalente es el parámetro `--features`: le dice al MCP qué
categorías de acciones puede ejecutar (solo leer/escribir en la base de
datos, o también crear proyectos nuevos, borrar otros proyectos de tu
cuenta, manejar Edge Functions, etc.). La regla general en seguridad es dar
siempre el mínimo permiso necesario para el trabajo — así, si algo sale mal
(un bug, una instrucción mal interpretada, una fuga del token), el daño
posible queda acotado.

---

## 7. Por qué reiniciar la sesión

Cuando Claude Code arranca, carga la lista de servidores MCP disponibles
una sola vez, al inicio. Si registras un servidor MCP nuevo **mientras la
sesión ya está corriendo** (como hiciste), el proceso activo no se entera
solo — sigue con la lista que cargó al principio. Cerrar la terminal mata
ese proceso; al volver a abrirlo, arranca de cero y ahí sí lee la lista
actualizada de servidores MCP, incluyendo el que acabas de agregar.

---

## 8. Qué significa "publicar/desplegar" el backend

### El problema concreto

Ahora mismo el backend (la app Flask) solo corre **dentro de tu propia
computadora**, en una dirección que literalmente significa "esta misma
máquina" (`127.0.0.1` / `localhost`). Eso ya nos alcanzó para probar
crear/confirmar/rechazar un pedido real (sección 5 del `RESUMEN_FASE1.md`),
porque en esos casos **nosotros llamamos a Rocketfy** — igual que llamar a
alguien por teléfono: puedes hacerlo desde cualquier parte, tú marcas.

El webhook es lo contrario: ahí es **Rocketfy quien nos tiene que llamar a
nosotros** cada vez que un pedido cambia de estado. Y para que alguien te
llame, necesitas un número al que se pueda marcar. `127.0.0.1` no es ese
número — apunta "hacia adentro" de cada computadora, así que el servidor de
Rocketfy, si intenta usarlo, terminaría intentando llamarse a sí mismo, no
a ti. Por eso el webhook nunca se ha podido probar con eventos reales: no
tenemos todavía una dirección a la que Rocketfy le pueda avisar algo.

### Qué es "publicar" entonces

Publicar / desplegar significa: hacer correr esa misma app, sin cambiarle
el código, en un servidor que:
1. Esté prendido y conectado a internet todo el tiempo (no depende de que
   tu laptop esté encendida).
2. Tenga una dirección pública fija (un dominio tipo `tuapi.com` o al menos
   una URL estable) a la que cualquiera en internet — incluido Rocketfy —
   le pueda mandar una petición.
3. Use HTTPS (la versión encriptada de HTTP), que es lo mínimo que cualquier
   proveedor serio va a exigir para mandarte datos de clientes.

Lo que se publica es **solo el backend** (la carpeta `PROYECTECOM/backend/`
tal cual está hoy) — no hay que "publicar" la base de datos, porque
Supabase ya es un servicio en internet, siempre encendido, desde el primer
día. El frontend se publicará por separado más adelante, cuando exista.

### Dos caminos, y no hay que decidir el definitivo todavía

- **Túnel temporal** (herramientas como `ngrok` o `cloudflared`): le da a tu
  computadora una URL pública **por un rato**, mientras el túnel esté
  abierto y tu laptop prendida. Sirve perfecto para la prueba que nos
  falta: darle esa URL a Rocketfy, generar un pedido de prueba, ver si el
  webhook recibe el aviso — y listo. No sirve para producción real: si
  cierras la terminal o apagas la laptop, la URL deja de funcionar (y
  normalmente cambia cada vez que abres el túnel de nuevo, a menos que
  pagues por una fija).
- **Hosting real** (un servidor en la nube — Render, Railway, Fly.io, un
  VPS, etc.): la app corre ahí 24/7, con una URL estable, independiente de
  tu computadora. Esta es la respuesta definitiva, la que necesitas antes
  de operar con clientes reales — pero es una decisión más grande (elegir
  proveedor, costo, cómo se despliegan actualizaciones) que no hace falta
  tomar hoy solo para probar el webhook una vez.

Para la prueba pendiente del webhook, lo más simple es empezar con el túnel
temporal; el hosting real queda para cuando decidamos ir a producción de
verdad (Etapa 8/9 o antes de vender con clientes reales).

---

## 9. Por qué Victoria "usa herramientas" y qué significa que el LLM esté "desacoplado"

### El problema de solo pedirle texto a la IA

Una forma simple (y frágil) de hacer un bot con IA sería: pedirle a Claude
que, al final de cada respuesta, escriba también un bloque de texto con
el estado del pedido — por ejemplo, algo como
`{"producto": "X", "direccion": "..."}` mezclado en su propia respuesta.
El problema es que estás pidiéndole a un modelo de lenguaje que escriba
texto **con el formato exacto correcto todo el tiempo**, y que tu código
después intente "leer" ese texto para sacar los datos. Un espacio de más,
una comilla que falta, una palabra rara — y tu código ya no puede leerlo,
justo en el peor momento (cerrando una venta real).

### La alternativa: "tool use" (herramientas)

Los proveedores de IA modernos (Claude, GPT, Gemini) resuelven esto con
un mecanismo mejor: en vez de que la IA escriba el dato en su propio
texto, tú le dices de antemano "acá tienes estas funciones disponibles,
con estos parámetros exactos" — y cuando la IA quiere guardar un dato,
en vez de escribirlo como texto libre, literalmente **pide ejecutar una
de esas funciones**, con los parámetros ya organizados y validados por el
propio proveedor (nunca llega mal formado). Tu código ejecuta esa función
de verdad (guardar en la base de datos, por ejemplo) y le devuelve el
resultado a la IA para que siga la conversación sabiendo qué pasó.

Victoria tiene 5 de estas "herramientas": guardar los datos del cliente,
registrar qué producto quiere, registrar cómo va a pagar, cerrar la venta,
y escalar a un humano. Es mucho más confiable que pedirle que escriba un
JSON de memoria: la estructura de los datos la garantiza el mecanismo de
la IA, no la buena redacción del modelo en ese momento puntual.

### Qué significa que el LLM esté "desacoplado"

Hoy Victoria usa Claude (Anthropic). Pero le pediste explícitamente al
equipo que construyó esto que, si en el futuro quieres cambiar a otro
proveedor (Gemini, GPT, el que sea), **eso no debería obligar a reescribir
cómo Victoria vende** — solo cambiar qué proveedor está conectado atrás.

La forma de lograr eso es una capa intermedia: todo el código que decide
CÓMO vende Victoria (el prompt, las 5 herramientas, cuándo escalar a un
humano) habla con una interfaz genérica y neutral, no con Claude
directamente. Es como un enchufe universal: el resto de la casa (los
electrodomésticos) no le importa si la electricidad viene de un panel
solar o de la red pública — mientras el enchufe encaje, funciona igual.
Acá el "enchufe" es un archivo (`contratos.py`) que define cómo se ve un
mensaje, una respuesta, una herramienta — en términos genéricos, sin nada
específico de Claude.

Solo existe UN archivo en todo el proyecto
(`anthropic_provider.py`) que sabe que el proveedor real es Claude — es
el "adaptador" que traduce entre el lenguaje genérico y el lenguaje
específico de la API de Anthropic. El día que quieras agregar Gemini,
alguien escribe un archivo nuevo equivalente para Gemini, y cambia una
sola variable de configuración (`LLM_PROVIDER=gemini` en vez de
`LLM_PROVIDER=anthropic`) — nada del resto del sistema se toca. Incluso
hay una prueba automática que corre cada vez que se hacen cambios y que
falla sola si alguien, sin darse cuenta, mezcla código específico de
Claude fuera de ese único archivo permitido — para que esta propiedad no
se rompa con el tiempo sin que nadie lo note.


---

## 10. Proceso e hilo (thread)

Dos palabras que aparecen todo el tiempo y que conviene tener claras.

- **Proceso:** un programa en ejecución. Cuando arrancas tu backend, el
  sistema operativo crea *un proceso*: su propio espacio de memoria, aislado
  de los demás. Si dos procesos quieren compartir algo, tienen que
  comunicarse por fuera (una base de datos, la red).
- **Hilo (thread):** una "línea de trabajo" *dentro* de un proceso. Un
  proceso puede tener varios hilos haciendo cosas a la vez, y **todos
  comparten la misma memoria**.

**Analogía:** el proceso es un restaurante; los hilos son los meseros que
trabajan dentro. Todos comparten la misma cocina (memoria). Otro restaurante
(otro proceso) tiene su propia cocina y no ve la tuya.

**En tu proyecto:** el backend es un proceso. Dentro de él hay varios hilos:
unos atienden las peticiones web, uno es el del bot (ver §11) y otro es el
del scheduler (ver §13). Por eso importa cuántos procesos corre gunicorn: si
hubiera dos, habría *dos cocinas*, cada una con su propio bot y sus propios
jobs.

---

## 11. Worker

"Worker" significa "trabajador" y en este proyecto se usa para **dos cosas
distintas**. Es normal confundirlas.

### a) El `BotWorker` (el trabajador de Victoria)
Archivo: `backend/src/routes/whatsapp/worker.py`.

Cuando un cliente escribe, Meta exige que tu webhook responda en menos de
unos 5 segundos. Pero pensar la respuesta de Victoria (llamar a Claude,
usar herramientas, enviar por WhatsApp) puede tardar 10 o 15 segundos.

La solución: el webhook **solo anota la tarea** ("responderle a este
cliente") y contesta "recibido" a Meta enseguida. Un **hilo aparte, el
BotWorker**, saca las tareas de una cola y hace el trabajo lento sin
presión de tiempo. Es como un mesero que toma tu pedido y se lo pasa a la
cocina, en vez de quedarse parado a esperar que el plato esté listo.

Para que no se pierdan tareas si el servidor se reinicia, cada tarea se
guarda también en la tabla `cola_mensajes` de la base de datos.

### b) Un *worker de gunicorn*
Es otra cosa: es **un proceso entero** que gunicorn arranca para atender
peticiones web (ver §12). "Tener 4 workers" significa tener 4 copias del
backend corriendo a la vez.

**La conexión entre ambas:** como el BotWorker (a) vive *dentro* del
proceso, si gunicorn arrancara 4 workers (b) habría 4 BotWorkers
compitiendo por la misma cola. Por eso en producción usamos **1 worker de
gunicorn con varios hilos**.

---

## 12. Gunicorn

**Qué es:** un servidor de aplicaciones web para Python. Su trabajo es
recibir las peticiones de internet y entregárselas a tu aplicación Flask.

**Por qué no usamos solo Flask:** cuando corres `python app.py` (o
`flask run`), Flask levanta un servidor de **desarrollo**: cómodo para
probar, pero no está pensado para aguantar tráfico real, errores ni
reinicios. Gunicorn es el servidor de **producción**: más robusto, maneja
varias peticiones a la vez y se recupera de fallos.

**Analogía:** Flask es la cocina y el menú; gunicorn es el equipo de sala
que recibe a los clientes y les lleva los pedidos a la cocina.

**Cómo lo arrancamos:** `gunicorn -c gunicorn.conf.py src.app:app`.
Significa: "usa la configuración de `gunicorn.conf.py` y carga el objeto
`app` que está en el archivo `src/app.py`".

**Detalle que nos mordió:** gunicorn *importa* `src/app.py`, pero no lo
*ejecuta como programa principal*. El bloque `if __name__ == "__main__":`
del final del archivo solo corre con `python app.py`. Allí arrancaba el
scheduler, así que en producción los jobs **no se habrían encendido**. Ahora
se encienden dentro de `create_app()` con la variable `ENABLE_SCHEDULER=true`.

**Nuestra configuración** (`backend/gunicorn.conf.py`): 1 worker, 4 hilos,
puerto tomado de la variable `PORT` que inyecta Railway.

---

## 13. Scheduler

**Qué es:** un "despertador" para código. Le dices "ejecuta esta función
cada 45 minutos" y él se encarga de dispararla a su hora, sin que nadie
tenga que hacer una petición.

**Cuál usamos:** `APScheduler`, un paquete de Python. Corre en un hilo
dentro del mismo proceso del backend (ver §10).

**Qué agenda en tu proyecto** (`backend/src/app.py`, `start_scheduler()`):
| Job | Frecuencia |
|---|---|
| Reconciliación de pedidos | cada 45 min |
| Stock watcher | cada 60 min |

**Cómo sabes si está encendido en producción:** abre `/health` del backend;
debe responder `{"scheduler": true, "status": "ok"}`.

**Candado anti-duplicados:** si por error hubiera dos schedulers, ambos
intentarían ejecutar el mismo job. Para eso existe la tabla `job_locks`: el
primero toma el candado y el segundo se retira. Aun así evitamos tener dos.

---

## 14. Job

**Qué es:** una tarea concreta que el sistema ejecuta por su cuenta, sin que
nadie se la pida. Es "lo que hay que hacer" (el scheduler es "cuándo").

**Los dos jobs de tu proyecto:**

1. **Reconciliación** (`backend/src/jobs/reconciliacion/`). Rocketfy te
   avisa de cambios de estado de los pedidos por webhook, pero un aviso
   puede perderse en el camino. Este job le pregunta periódicamente a
   Rocketfy "¿cómo van estos pedidos?" y corrige lo que se haya quedado
   desactualizado. Es la red de seguridad del webhook.
2. **Stock watcher** (`backend/src/jobs/stock_watcher/`). Revisa los
   productos que estás pautando en publicidad. Si el stock baja del límite
   que definiste, o cambia el precio, crea una **alerta** que ves en
   `/incidencias`. Protege tu inversión: no quieres pagar anuncios de un
   producto agotado.

**Si un job falla:** los dos están envueltos para que una excepción se
registre en el log y **nunca tumbe el backend**. El siguiente ciclo lo
vuelve a intentar.

---

## 15. Firma del webhook (HMAC) y App Secret

**El problema:** un webhook es una dirección pública. Cualquiera que la
conozca puede enviarle datos haciéndose pasar por Meta. Eso permitiría
gastar tu dinero en llamadas a Claude o crear pedidos falsos.

**La solución:** Meta y tú comparten una clave secreta, el **App Secret** de
tu app en Facebook Developers (Configuración de la app → Básica). Con ella,
Meta calcula un código a partir del contenido de cada mensaje y lo manda en
el encabezado `X-Hub-Signature-256`. Ese código se llama **HMAC-SHA256**.

Tu backend calcula el mismo código con su copia de la clave y lo compara. Si
coinciden, el mensaje viene de Meta y nadie lo modificó. Si no, responde
**401** y descarta el mensaje. Quien no tenga la clave no puede fabricar una
firma válida; y si alguien cambia aunque sea una letra del mensaje, la firma
deja de coincidir.

**No confundir con otras llaves:**
| Variable | Para qué |
|---|---|
| `WHATSAPP_API_TOKEN` | Tu backend **envía** mensajes a Meta |
| `WHATSAPP_WEBHOOK_VERIFY_TOKEN` | Meta confirma **una vez** que eres el dueño de la URL (handshake GET) |
| `WHATSAPP_APP_SECRET` | Verifica la firma de **cada** mensaje que Meta te manda |

**Falla cerrado:** si `WHATSAPP_APP_SECRET` no está configurada, el webhook
rechaza todo POST. Mejor un bot callado que un bot abierto a cualquiera.

---

## 16. Monorepo y Root Directory

**Monorepo:** un solo repositorio de git que contiene varios proyectos. El
tuyo tiene `backend/` y `frontend/`. (Decisión en `PROGRESS.md`, ADR-008:
mantenerlo así porque ambos cambian juntos y el proyecto lo mantiene una
persona.)

**Root Directory:** una opción de Railway y Vercel que dice "de este repo,
ocúpate solo de esta carpeta". Railway usa `backend`, Vercel usa `frontend`.
Así, ambas plataformas leen el mismo repo pero cada una construye únicamente
su parte.

**Watch Paths:** un filtro adicional: "redespliega solo si cambiaron
archivos de esta ruta". Evita que un cambio en el dashboard reinicie el
backend (y con él, el bot de Victoria).


---

## 17. Diseño responsivo y "mobile-first"

**Responsivo:** una misma página que se reacomoda según el ancho de la pantalla
(celular, tablet, computador), en vez de tener tres versiones.

**Mobile-first** ("primero el celular"): se diseña pensando en el celular y
después se agregan mejoras para pantallas grandes. Para ti es lo más
importante, porque probablemente revisarás pedidos y chats desde el teléfono.

Ejemplos de cómo se aplicó en tu panel:
- **Tabla en computador, tarjetas en celular.** Una tabla de 5 columnas no cabe
  en 390 px: se cortaba y el estado y el total quedaban fuera de la pantalla.
  Ahora, en celular cada pedido es una tarjeta con lo esencial a la vista.
- **Barra inferior** con las 4 secciones de uso diario, al alcance del pulgar.
- **Botones de al menos 40 px**: un dedo no es un cursor; los botones diminutos
  se pulsan mal.
- **Bandeja de chats:** en computador ves la lista y el chat a la vez (como
  WhatsApp Web); en celular, una pantalla a la vez.

En el código se ve en clases como `md:hidden` (se oculta desde pantallas
medianas) o `lg:grid-cols-4` (4 columnas solo en pantallas grandes). Los puntos
de corte usados son: `sm` 640 px, `md` 768 px, `lg` 1024 px, `xl` 1280 px.

---

## 18. Tokens de diseño y modo oscuro

**Token de diseño:** un nombre para un valor de diseño, definido una sola vez.
En vez de escribir "este azul exacto" en cien lugares, se define `--primary` y
todo lo demás lo usa. Viven en `frontend/src/app/globals.css`.

**Por qué importa:**
- **Cambiar la marca es tocar un lugar.** Si mañana quieres otro color
  principal, se cambia `--primary` y toda la app cambia coherentemente.
- **Modo oscuro gratis y consistente.** Cada token tiene su valor claro y su
  valor oscuro; la app elige según el tema (botón sol/luna de la cabecera:
  claro, oscuro o el de tu sistema).
- **Estados con significado fijo.** Verde = éxito, ámbar = atención, rojo =
  problema, celeste = información. El color de marca (índigo) es otro a
  propósito, para que nunca confundas "botón principal" con "todo bien".

Cada estado tiene 4 tonos: el **sólido** (puntos, barras), el **texto sobre
sólido**, el **fondo suave** (etiquetas) y el **texto oscuro sobre fondo
suave** (para que se lea bien).

---

## 19. Accesibilidad (WCAG) y cómo se mide

**Accesibilidad:** que la app pueda usarla cualquiera, incluso con baja visión,
con lector de pantalla (que lee la página en voz alta) o solo con teclado, y
también cuando hay mucho sol y la pantalla se ve mal.

**WCAG 2.1 nivel AA:** el estándar internacional de referencia. Lo más
cotidiano que exige:
- **Contraste:** el texto debe distinguirse del fondo (mínimo 4.5 a 1). Antes,
  varias etiquetas de estado verdes y amarillas no lo cumplían.
- **Nombres para todo:** un botón solo con un ícono necesita una etiqueta
  invisible que el lector de pantalla pueda leer (`aria-label`).
- **Teclado:** todo se puede alcanzar y usar con Tab y Enter; hay un enlace
  "Saltar al contenido".
- **Estructura:** un solo `<main>`, encabezados en orden (h1, h2…).

**Cómo se midió:** con **axe-core**, una herramienta automática que revisa cada
pantalla y lista los incumplimientos. Se corrió en las 9 pantallas, en claro y
oscuro, en escritorio y móvil. Encontró problemas reales (por ejemplo, los
selectores de provincia y cantón no tenían nombre para lectores de pantalla) y
quedó en **cero violaciones**. Está en `frontend/tools/ui-preview/` para
repetirla cuando se cambie la interfaz. Una herramienta automática no
detecta todo, pero cubre mucho de lo más común.
