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
