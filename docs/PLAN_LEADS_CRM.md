# Plan: módulo de Leads (CRM), temperatura, «no contactar» y seguimiento

> Pedido de Freddy (2026-11-09): un panel de leads con tabla y filtros, una **temperatura** por lead
> (caliente / tibio / frío / perdido / ganado) que **Victoria define** al leer la conversación, la protección de
> «no contactar», y el seguimiento de clientes que se enfrían (pendiente #67). Estado: **plan; la Fase 0 (cimientos
> multicanal, ADR-014, migración 024) ya está hecha y probada localmente, sin desplegar; falta lo demás**.
>
> **Aclaración del 2026-11-09 (cambia el plan):** el negocio venderá también por **Instagram y Messenger**, y los datos
> actuales son de prueba. Por eso el contacto ya **no** vive dentro de `conversaciones`: hay una tabla `contactos` y una
> conversación por canal. Donde este documento dice «la conversación es el contacto», léase «el contacto (`contactos`)».
> Las migraciones se renumeran: **024 = Fase 0 (hecha)**, **025 = leads CRM (F1)**, **026 = seguimientos (F4)**.

## 1. Cómo está hoy (verificado en el código y en producción, 2026-11-09)
- `leads` es la **hoja de venta** de un cliente: nombre, dirección, producto, método de pago y la etapa técnica
  (`recopilando_datos`, `esperando_pago`, `listo_para_despacho`, `despachado`, `por_gestionar`, `cancelado`).
- **Hay un solo lead por conversación en el código, no en la base**: la tabla no tiene restricción
  única. Solo 3 lugares lo suponen (`obtener_por_conversacion`, `obtener_o_crear` y la regla de «cliente con pedido
  previo»), por eso cambiarlo es abordable.
- Consecuencia: un cliente que ya compró y vuelve **no lo atiende Victoria**, pasa siempre al dueño (regla 2 del
  webhook); y un cliente que no compró y vuelve por otro producto **pisa** el lead anterior.
- **No existe**: temperatura, panel de leads, historial de cambios, «no contactar», ni seguimiento a clientes fríos.
- Producción: 6 conversaciones y 5 leads (datos de prueba; nada real todavía).

## 2. Decisiones de diseño (recomendadas)
**2.1 Contacto y lead son cosas distintas.** El **contacto** (`contactos`, Fase 0) es la persona y dura para siempre; sus
**conversaciones** son un hilo por canal (WhatsApp, Instagram, Messenger). Un **lead** es una *oportunidad de compra*: puede haber varios con el tiempo, **uno abierto a la vez**. Así «José, audífonos
en octubre» y «José, zapatos en noviembre» son dos leads del mismo contacto, y la recompra deja de ser un problema.

**2.2 Dos ejes, para no mezclar «dónde va» con «qué tan probable es».**
- **Etapa** (ya existe, la fija el sistema): dónde va en el proceso.
- **Temperatura** (nueva): qué tan probable es que compre. Valores: **caliente, tibio, frío, perdido, ganado**.
  *Perdido* y *ganado* son finales; los otros tres están abiertos.

| Temperatura | Significa | Ejemplo |
|---|---|---|
| **Caliente** | Quiere comprar ya | Dio sus datos, preguntó cómo pagar, escribió hoy |
| **Tibio** | Interesado, no decidido | Pregunta precios y características, o era caliente y lleva 2 días callado |
| **Frío** | Poco interés o mucho silencio | Un «hola, ¿cuánto cuesta?» y nada más; lleva 5 días sin responder |
| **Perdido** | Ya no se va a vender | Dijo que no, canceló, o no respondió a los seguimientos |
| **Ganado** | Se vendió | Venta cerrada (despachada o en «Por gestionar») |

**2.3 Quién decide la temperatura (de más a menos fuerte).**
1. **El dueño**, a mano desde el panel (queda fijada y la IA no la pisa por unos días).
2. **Reglas del sistema** sobre hechos: ganado = venta cerrada; perdido = cancelada, «no contactar» o sin respuesta tras
   los seguimientos.
3. **Victoria**, con una herramienta nueva `clasificar_lead(temperatura, motivo)`: aporta el **juicio** (¿qué tan en
   serio compra?) y deja su **motivo** por escrito, visible en el panel.
4. **El paso del tiempo**: un job enfría (caliente→tibio→frío→perdido) según el silencio; los plazos son parámetros.
Cada cambio queda en un **historial** (de → a, quién, motivo, cuándo): así se ve por qué un lead cambió y se puede
medir si la IA acierta.

**2.4 «No contactar» es del contacto, no del lead ni del canal.** Marca en `contactos` (`no_contactar`, motivo, fecha, quién):
si pidió que no le escriban por WhatsApp, tampoco se le escribe por Instagram.
Victoria la pone con una herramienta `no_contactar` cuando el cliente dice que no le interesa o que no le escriban; el
dueño la puede quitar. **Bloquea todo mensaje que enviemos por iniciativa propia** (empujón y plantilla). No impide
responder si el cliente vuelve a escribir él.

**2.5 Cliente que ya compró y vuelve (cambia el comportamiento del bot).** Recomendación: Victoria lo atiende como
**cliente recurrente** (se le indica en su contexto que ya compró) y usa `escalar_a_humano` para lo que sea del pedido
anterior (envío, reclamos); si quiere comprar de nuevo, se abre un lead nuevo. Hoy todo eso va al dueño. *Es la parte
de más riesgo del plan: se prueba con un escenario nuevo en «Probar con Victoria» antes de desplegar.*

**2.6 Contraste con los CRM grandes (Salesforce, HubSpot, Zoho, Dynamics), pedido de Freddy 2026-11-09.** Su modelo
estándar separa **Contacto** (registro maestro y único de la persona), **Oportunidad / Deal** (cada intención de compra,
con su propio embudo, valor y estado; relación 1 a N) y **Lead** (prospecto aún sin calificar, un estado temporal).
Lo que justifica separar contacto y oportunidad: **visión 360** del cliente, **valor de vida (LTV)** y **atribución de
marketing** por compra. Cómo encaja aquí (comprobado en el esquema el 2026-11-09):

| En un CRM grande | Aquí | Observación |
|---|---|---|
| **Contacto** (único, deduplicado por teléfono) | `contactos` (Fase 0, ADR-014) | Teléfono único cuando existe; un cliente de Instagram puede no tenerlo. Cada canal es una `conversaciones` que cuelga del contacto. **El contacto no se borra nunca** (ver §10) |
| **Oportunidad / Deal** | `leads` | Una fila por intención de compra. Se conserva el nombre `leads` en código y base (renombrar tocaría todo sin ganar nada) |
| **Lead** (sin calificar) | la *temperatura* (frío/tibio) | No es una tabla aparte: calificar = subir la temperatura |
| **Actividades / línea de tiempo** | `mensajes` + `conversacion_anuncios` + `lead_historial` | Se muestran juntas en la ficha |

Lo que esta referencia **agrega al plan** (no estaba):
1. **Atribución por oportunidad (corrige un defecto de lo desplegado el 2026-11-09; sigue pendiente, es de F1).** Hoy
   `conversaciones.origen` pasa a «anuncio» (antes «fep») con el primer anuncio y **no vuelve nunca a «directo»**, y
   `ventas.origen`/`ventas.id_anuncio` (antes `ventas.canal`) copian ese valor al cerrar la venta. Con el ejemplo de José (anuncio en enero, laptop en mayo sin anuncio) la venta de mayo se contaría
   como venta del anuncio de enero. Corrección: **cada lead guarda su propio origen y anuncio** (`leads.origen`,
   `leads.id_anuncio`, `leads.ctwa_clid`), fijados al abrirse y actualizados si llega otro anuncio mientras sigue
   abierto. Un lead nuevo hereda el anuncio **solo si la llegada por anuncio es reciente** (parámetro
   `leads.dias_atribucion`, propuesta: 30 días); si no, es «directo (cliente que ya había venido por anuncio)». La venta
   copia el origen **del lead**, no el de la conversación. El primer anuncio del contacto (*first touch*) se calcula del
   historial `conversacion_anuncios`, sin columna nueva.
2. **Ficha del contacto (visión 360):** todos sus leads, llegadas por anuncio, ventas y conversación en un solo lugar.
3. **Valor del cliente (LTV):** compras, total gastado y ganancia por contacto, sumando sus ventas no canceladas
   (`ventas.conversacion_id`).
4. **Tipo de contacto derivado**, sin columna: *prospecto* (nunca compró), *cliente* (1 compra), *recurrente* (2 o más).
5. **Victoria recibe el historial del contacto** («en octubre preguntó por audífonos», «ya compró zapatos»): es el
   equivalente a lo que ve el vendedor en pantalla.
6. **Motivo de pérdida estructurado** (catálogo: precio, no respondió, compró en otro lado, sin cobertura, sin stock, no le
   interesó, otro) además del texto libre, para poder reportar **por qué se pierde**.
7. **Nombre del contacto:** *(hecho en la Fase 0)* `contactos.nombre` (el del perfil del canal o el último que dio al
   comprar) y `conversaciones.nombre_perfil`; el webhook de WhatsApp ya lo toma de `contacts[].profile.name` (por confirmar
   con un mensaje real).

**Diferencias a propósito con los CRM grandes:** (a) **un solo lead abierto a la vez** por contacto (ellos permiten
varias oportunidades abiertas): así Victoria atiende un producto cada vez y el panel no se llena de duplicados; si el
cliente quiere dos productos, van como líneas de la misma venta; (b) **sin «Cuenta/Empresa»** (vendemos a personas);
(c) **sin etapas configurables ni probabilidad por etapa** (la temperatura cubre eso; puede venir en F5).

## 3. Cambios de datos
- **Migración 025 (F1; la 024 ya es la Fase 0):** `leads.temperatura` (+ `temperatura_motivo`, `temperatura_origen` = ia/regla/dueño,
  `temperatura_en`, `temperatura_fijada_hasta`); `leads.origen`, `leads.id_anuncio`, `leads.ctwa_clid` (atribución por
  oportunidad) y `leads.motivo_perdida`; `contactos.no_contactar` (+ motivo, fecha, quién); tabla `lead_historial`. **Relleno** de los leads existentes por reglas (ganado/perdido; el resto tibio; el
  origen del lead se toma de la conversación).
- **Migración 026 (con el seguimiento):** tabla `seguimientos` (qué se envió a quién y cuándo; impide repetir).
- Solo se agregan objetos; no se edita nada ya aplicado.

## 4. Victoria
- Herramientas nuevas: `clasificar_lead`, `no_contactar`.
- Una sección nueva en sus **instrucciones editables** («Cómo clasificar leads»), con las definiciones de la tabla 2.2,
  para que las ajustes desde la app sin tocar código (ADR-011). Ahí también se fija el **trato de usted** (hoy el texto
  dice «cercana y profesional» pero no fija tú/usted).
- Recibe en su contexto un **resumen del historial del contacto** (leads anteriores con producto y resultado, compras, si
  vino por anuncio), para no tratar al cliente como un desconocido.
- «Probar con Victoria» muestra la temperatura que habría puesto.
- Costo: unas pocas llamadas de herramienta por conversación; no hay un job de IA aparte.

## 5. Panel de Leads (frontend)
Pantalla nueva **Leads** en «Operación» (en móvil, tarjetas; desde `md`, tabla):
- **Resumen arriba:** leads por temperatura, valor en juego (suma de totales de los abiertos) y tasa de cierre.
- **Filtros:** temperatura (chips), etapa, origen (anuncio/directo y cuál anuncio), producto, antigüedad, «sin respuesta
  hace…», «no contactar» y búsqueda por nombre o teléfono; orden por actividad, valor o temperatura.
- **Columnas:** cliente, producto, temperatura, etapa, origen, valor, último mensaje, seguimiento.
- **Detalle** (panel lateral): datos, motivo de la IA, **línea de tiempo** (cambios de temperatura y seguimientos),
  enlace a la conversación, y acciones: cambiar temperatura, marcar perdido con motivo (de un catálogo), «no contactar».
- **Ficha del contacto** (visión 360): tipo (prospecto/cliente/recurrente), cuánto ha comprado y ganado (LTV), todos sus
  leads, sus llegadas por anuncio (primera y última) y la conversación.
- **Reporte «por qué perdemos»** (motivos de pérdida) y conversión por anuncio con la atribución por oportunidad.
- Colores con los tokens de estado: caliente = `warning`, tibio = `info`, frío = `neutral`, perdido = `danger`,
  ganado = `success`. API: `GET /leads`, `GET /leads/resumen`, `PATCH /leads/<id>`, `GET /leads/<id>/historial`.

## 6. Seguimiento (pendiente #67), ya integrado
- **Empujón gratis** (texto libre dentro de las 24 h): a quien lleva unas horas callado; texto definido por Freddy:
  «Hola 👋 ¿Sigue interesado(a)? Cuénteme y lo terminamos en un momento 😊» (editable en Parámetros).
- **Plantilla** (después de 24 h, **solo clientes de anuncio con la ventana gratuita abierta**, categoría marketing,
  sin variables): «Hola 👋 Soy Victoria, de AzoShop. Hace poco estuvimos conversando y quedó pendiente su pedido.
  ¿Sigue interesado(a)?» (nombre `retomar_conversacion`; se crea en la cuenta del número 096 316 2902).
- **Reglas:** nunca a «no contactar», ni a perdidos o ganados, ni a conversaciones que tomó una persona; **máximo un
  empujón y una plantilla por contacto en toda su vida**; tope diario; horario 9:00–20:00 (Ecuador); dos interruptores
  **apagados por defecto**; el mensaje se guarda en la conversación para que Victoria sepa que ya se le escribió.
- La temperatura decide a quién conviene escribir (no a los fríos sin señal de interés ni a los perdidos).
- **Por canal:** las plantillas de Meta son de WhatsApp; el seguimiento solo escribe por los canales que lo permiten y
  tienen adaptador (hoy, WhatsApp). La ventana de cada canal (hoy solo se conoce la de WhatsApp) se define al conectarlo.

## 7. Fases (en este orden)
| Fase | Qué se entrega | Tamaño relativo |
|---|---|---|
| **F0** (hecha) | **Cimientos multicanal (ADR-014, migración 024):** `contactos`, una conversación por canal, canal separado de origen, registro de canales de envío, claves protegidas contra el borrado. 1608 pruebas; **sin desplegar** | Hecho |
| **F1** | Migración 025, **varios leads por contacto** (ojo: `ConversacionRepository.listar` une `leads` por conversación y con varios leads repetiría filas: usar el lead más reciente), **atribución por oportunidad** (la venta copia el origen del lead), «no contactar» en el contacto, historial, reglas de temperatura y relleno, API de lectura. Tests | Grande (como Anuncios E1) |
| **F2** | Victoria: herramientas `clasificar_lead` y `no_contactar`, instrucciones nuevas, trato de usted, **cliente recurrente con el historial del contacto en su contexto**, simulación. Tests | Mediano, el de más riesgo |
| **F3** | Panel de Leads: pantalla, filtros, detalle, **ficha del contacto (360 y valor del cliente)**, acciones, menú, servidor falso, auditoría de accesibilidad | Grande (como Anuncios, frontend) |
| **F4** | Seguimiento: migración 026, job, parámetros, Telegram, plantilla enviada a Meta para revisión | Mediano |
| **F5** (opcional) | Tablero Kanban, exportar a CSV, recordatorios al dueño, conversión por temperatura y por anuncio | A pedido |
| **R** (retención, cuando haga falta) | Depurar solo lo pesado y sin valor comercial (mensajes viejos de conversaciones cerradas, cola ya procesada, webhooks crudos), con interruptor apagado; ver §10 | Mediano; no urgente |

**Paralelo:** la plantilla se puede enviar a revisión de Meta **apenas Freddy apruebe el texto final** (la revisión tarda
y no depende del código). Cada fase se despliega por separado: primero la migración, después el código, con
confirmación de Freddy.

## 8. Riesgos y lo que no se sabe
- **La IA se puede equivocar al clasificar.** Mitigación: motivo visible, historial, override del dueño y reglas duras
  por encima. Cuánto acierta solo se sabrá con conversaciones reales (hoy no hay).
- **Cambiar la atención al cliente que ya compró** toca el bot con clientes reales: pruebas extra y una instrucción de
  seguridad (lo del pedido anterior siempre va a una persona).
- **Calidad del número en Meta:** si muchos clientes bloquean los mensajes proactivos, Meta puede bajarla; por eso el
  tope, el horario, «no contactar» y los interruptores apagados.
- **Datos personales:** el panel solo lo ve quien tiene sesión (modelo de un solo administrador, pendiente #65).
- **Regla de atribución (30 días propuestos) es una decisión de negocio**, no un hecho de Meta: se ajusta como parámetro.
  Las ventas ya cerradas conservan el origen que tenían (hoy no hay ventas reales, así que no hay nada que corregir).
- No verificado: tiempo de revisión de Meta para la plantilla; límites de envío del negocio sin verificación de empresa;
  que el webhook de WhatsApp traiga el nombre del perfil (`contacts[].profile.name`, por confirmar con un mensaje real);
  el resumen de los CRM grandes viene de una consulta de Freddy y de conocimiento general, **no se contrastó con la
  documentación actual de cada producto**.

## 9. Fuera de este plan
Varios usuarios o asignar leads a vendedores, tareas y calendario, importar contactos, integraciones con otros CRM.

## 10. Qué se conserva para siempre y qué se puede depurar (pedido de Freddy, 2026-11-09)
**Pedido:** poder liberar espacio de la base en el futuro sin perder nada que sirva para vender o analizar (contactos,
nombres, teléfonos, intereses, ventas, anuncios). **Comprobado en producción (solo lectura) y en las migraciones:**

**10.1 Lo que hay hoy**
- *(Antes de la Fase 0)* `conversaciones` era a la vez el *contacto* y el *estado de la charla*, pero su fila es diminuta:
  **no ocupa espacio**. Lo que crece es `mensajes` (unos 108 caracteres de media por
  mensaje; ~350 bytes por mensaje con sus índices, estimado con los 38 mensajes de prueba).
- **No hay ningún borrado automático** en el sistema: ni mensajes, ni la cola (`cola_mensajes`, hoy 8 filas, todas ya
  procesadas), ni `webhook_events` (el JSON crudo de Rocketfy, que trae datos del cliente que ya están en `ventas` y
  `pedidos`). `stock_snapshots` crecería con el monitor de stock (hoy 0 filas porque no hay SKUs monitoreados; la
  velocidad real no se midió).
- **El riesgo real era la cascada (resuelto en la Fase 0, migración 024):** borrar una fila de `conversaciones` arrastraba `mensajes` y `cola_mensajes` (bien)
  **pero también `leads`, `conversacion_anuncios` y `solicitudes_gestion`** (el historial de intereses y de anuncios,
  justo lo que se quiere conservar). `ventas` está a salvo: copia nombre, teléfono, dirección, productos, costos y
  origen, y su clave a la conversación es «dejar en blanco», no «borrar».

**10.2 Clasificación**
| Se conserva siempre | Se puede depurar con el tiempo |
|---|---|
| `contactos`, `conversaciones` (sin sus mensajes), `leads`, `lead_historial`, `seguimientos`, `conversacion_anuncios`, `ventas`, `ventas_lineas`, `solicitudes_gestion`, `pedidos` (auditoría contra duplicados), `anuncios_productos`, productos y parámetros con sus historiales | `mensajes` de conversaciones viejas y cerradas; `cola_mensajes` ya procesada; `webhook_events` ya procesados; `stock_snapshots` antiguos |

**10.3 Decisiones de arquitectura (solo lo necesario)**
- **Sí hay una tabla `contactos` aparte** *(decisión cambiada el 2026-11-09)*: el análisis de espacio decía que no hacía
  falta (la fila pesa unos cientos de bytes), pero Freddy aclaró que el negocio venderá por Instagram y Messenger, y ahí un
  contacto tiene más de un canal: se hizo en la Fase 0 (ADR-014).
- **El contacto está protegido de borrados accidentales** (migración 024, hecha): las claves de `leads`,
  `conversacion_anuncios` y `solicitudes_gestion` pasan a «impedir el borrado»; `mensajes` y `cola_mensajes` siguen en
  cascada porque es lo depurable. Costo (ya pagado): las pruebas y la herramienta `chat_con_victoria.py` limpiaban
  borrando la conversación; ahora usan un ayudante que borra antes sus hijos. Si algún día un cliente pide que se
  borren sus datos, habrá que hacerlo con un procedimiento explícito (hoy no existe).
- **El interés sobrevive a los mensajes:** producto del lead, temperatura, motivo escrito por Victoria, origen, valor y
  anuncio quedan en el lead; el contenido de la charla es lo único que se depura.

**10.4 Fase R (retención), cuando haga falta; no ahora**
- Todo como parámetros (ADR-011) y **apagado por defecto**: interruptor general; días para mensajes (propuesta: 180 desde
  la última actividad), cola (30), webhooks (90) y snapshots (90).
- Un mensaje solo se depura si su conversación **no tiene** lead abierto, venta por gestionar o cobrar, ni solicitud
  pendiente, y pasó el plazo.
- Tarea nocturna por lotes que registra cuántas filas borró; vista del tamaño de la base en Control.
- Cuándo activarla: con la estimación del supuesto «100 conversaciones nuevas al día, 30 mensajes cada una» (mío, no
  medido) serían unos 380 MB al año solo en mensajes. Falta confirmar el tamaño que permite el plan de Supabase de Freddy.
