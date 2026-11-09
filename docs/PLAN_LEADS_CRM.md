# Plan: módulo de Leads (CRM), temperatura, «no contactar» y seguimiento

> Pedido de Freddy (2026-11-09): un panel de leads con tabla y filtros, una **temperatura** por lead
> (caliente / tibio / frío / perdido / ganado) que **Victoria define** al leer la conversación, la protección de
> «no contactar», y el seguimiento de clientes que se enfrían (pendiente #67). Estado: **plan, sin implementar**.

## 1. Cómo está hoy (verificado en el código y en producción, 2026-11-09)
- `leads` es la **hoja de venta** de un cliente: nombre, dirección, producto, método de pago y la etapa técnica
  (`recopilando_datos`, `esperando_pago`, `listo_para_despacho`, `despachado`, `por_gestionar`, `cancelado`).
- **Hay un solo lead por conversación (= por teléfono) en el código, no en la base**: la tabla no tiene restricción
  única. Solo 3 lugares lo suponen (`obtener_por_conversacion`, `obtener_o_crear` y la regla de «cliente con pedido
  previo»), por eso cambiarlo es abordable.
- Consecuencia: un cliente que ya compró y vuelve **no lo atiende Victoria**, pasa siempre al dueño (regla 2 del
  webhook); y un cliente que no compró y vuelve por otro producto **pisa** el lead anterior.
- **No existe**: temperatura, panel de leads, historial de cambios, «no contactar», ni seguimiento a clientes fríos.
- Producción: 6 conversaciones y 5 leads (datos de prueba; nada real todavía).

## 2. Decisiones de diseño (recomendadas)
**2.1 Contacto y lead son cosas distintas.** La **conversación** (teléfono) es el *contacto*, que dura para siempre. Un
**lead** es una *oportunidad de compra*: puede haber varios con el tiempo, **uno abierto a la vez**. Así «José, audífonos
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

**2.4 «No contactar» es del contacto, no del lead.** Marca en la conversación (`no_contactar`, motivo, fecha, quién).
Victoria la pone con una herramienta `no_contactar` cuando el cliente dice que no le interesa o que no le escriban; el
dueño la puede quitar. **Bloquea todo mensaje que enviemos por iniciativa propia** (empujón y plantilla). No impide
responder si el cliente vuelve a escribir él.

**2.5 Cliente que ya compró y vuelve (cambia el comportamiento del bot).** Recomendación: Victoria lo atiende como
**cliente recurrente** (se le indica en su contexto que ya compró) y usa `escalar_a_humano` para lo que sea del pedido
anterior (envío, reclamos); si quiere comprar de nuevo, se abre un lead nuevo. Hoy todo eso va al dueño. *Es la parte
de más riesgo del plan: se prueba con un escenario nuevo en «Probar con Victoria» antes de desplegar.*

## 3. Cambios de datos
- **Migración 024:** `leads.temperatura` (+ `temperatura_motivo`, `temperatura_origen` = ia/regla/dueño,
  `temperatura_en`, `temperatura_fijada_hasta`); `conversaciones.no_contactar` (+ motivo, fecha, quién); tabla
  `lead_historial`. **Relleno** de los leads existentes por reglas (ganado/perdido; el resto tibio).
- **Migración 025 (con el seguimiento):** tabla `seguimientos` (qué se envió a quién y cuándo; impide repetir).
- Solo se agregan objetos; no se edita nada ya aplicado.

## 4. Victoria
- Herramientas nuevas: `clasificar_lead`, `no_contactar`.
- Una sección nueva en sus **instrucciones editables** («Cómo clasificar leads»), con las definiciones de la tabla 2.2,
  para que las ajustes desde la app sin tocar código (ADR-011). Ahí también se fija el **trato de usted** (hoy el texto
  dice «cercana y profesional» pero no fija tú/usted).
- «Probar con Victoria» muestra la temperatura que habría puesto.
- Costo: unas pocas llamadas de herramienta por conversación; no hay un job de IA aparte.

## 5. Panel de Leads (frontend)
Pantalla nueva **Leads** en «Operación» (en móvil, tarjetas; desde `md`, tabla):
- **Resumen arriba:** leads por temperatura, valor en juego (suma de totales de los abiertos) y tasa de cierre.
- **Filtros:** temperatura (chips), etapa, origen (anuncio/directo y cuál anuncio), producto, antigüedad, «sin respuesta
  hace…», «no contactar» y búsqueda por nombre o teléfono; orden por actividad, valor o temperatura.
- **Columnas:** cliente, producto, temperatura, etapa, origen, valor, último mensaje, seguimiento.
- **Detalle** (panel lateral): datos, motivo de la IA, **línea de tiempo** (cambios de temperatura y seguimientos),
  enlace a la conversación, y acciones: cambiar temperatura, marcar perdido con motivo, «no contactar».
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

## 7. Fases (en este orden)
| Fase | Qué se entrega | Tamaño relativo |
|---|---|---|
| **F1** | Migración 024, **varios leads por contacto**, «no contactar» en la conversación, historial, reglas de temperatura y relleno, API de lectura. Tests | Grande (como Anuncios E1) |
| **F2** | Victoria: herramientas `clasificar_lead` y `no_contactar`, instrucciones nuevas, trato de usted, **cliente recurrente**, simulación. Tests | Mediano, el de más riesgo |
| **F3** | Panel de Leads: pantalla, filtros, detalle, acciones, menú, servidor falso, auditoría de accesibilidad | Grande (como Anuncios, frontend) |
| **F4** | Seguimiento: migración 025, job, parámetros, Telegram, plantilla enviada a Meta para revisión | Mediano |
| **F5** (opcional) | Tablero Kanban, exportar a CSV, recordatorios al dueño, conversión por temperatura y por anuncio | A pedido |

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
- No verificado: tiempo de revisión de Meta para la plantilla; límites de envío del negocio sin verificación de empresa.

## 9. Fuera de este plan
Varios usuarios o asignar leads a vendedores, tareas y calendario, importar contactos, integraciones con otros CRM.
