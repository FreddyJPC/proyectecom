# AzoShop — Planificación del Bot Conversacional de WhatsApp
> Documento de referencia del proyecto. Última actualización: septiembre 2026.

---

## 1. Contexto del Proyecto

**Marca:** AzoShop  
**Web:** https://www.azoshopec.com  
**Instagram:** https://www.instagram.com/azoshop.ec  
**Modelo de negocio:** Dropshipping variado — mercado Ecuador  
**Canal principal de captación:** Meta Ads con botón Click-to-WhatsApp  
**Integración de mensajería:** WhatsApp Cloud API de Meta (directo, sin BSP)  
**Lenguaje de programación:** Python  

---

## 2. Arquitectura General del Sistema

```
┌─────────────────────────────────────────┐
│           WhatsApp (cliente)            │
└──────────────────┬──────────────────────┘
                   │ webhook
┌──────────────────▼──────────────────────┐
│         Servidor Python                 │
│  - Recibe mensajes entrantes            │
│  - Detecta origen (FEP / web / directo) │
│  - Maneja estado de cada conversación   │
│  - Decide si bot responde o escala      │
└──────────────────┬──────────────────────┘
                   │
        ┌──────────┴──────────┐
        │                     │
┌───────▼───────┐    ┌────────▼────────┐
│   IA (LLM)    │    │  Base de datos  │
│  El cerebro   │    │  - Conversaciones│
│  del bot      │    │  - Pedidos      │
│               │    │  - Clientes     │
└───────────────┘    └─────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │ Plataforma de     │
                    │ dropshipping      │
                    │ (flujo ya existe) │
                    └───────────────────┘
```

---

## 3. Personalidad del Bot

- **Nombre:** Sofía de AzoShop (u otro nombre a definir)
- **Tono:** Cálido, profesional, cercano
- **Identidad:** Asesora de ventas humana — NO se presenta como bot
- **Excepción:** Si el cliente pregunta directamente si es bot, respuesta a definir
- **Idioma:** Español ecuatoriano natural, sin ser demasiado formal

---

## 4. Flujos Definidos

---

### Flujo 1 — Cliente escribe por WhatsApp (FEP o directo)

**Origen:** Cliente llega desde anuncio Meta Ads (FEP 72h) o escribe directamente al número.

**Ventaja FEP:** Todos los mensajes dentro de las 72h son gratuitos. El payload del webhook incluye el objeto `referral` que identifica el origen y el anuncio específico (`source_id`, `ctwa_clid`).

```
1. Cliente escribe al WhatsApp
         ↓
2. Servidor detecta si es FEP (campo "referral" en webhook)
         ↓
3. Bot saluda y presenta el producto del anuncio
         ↓
4. Bot resuelve dudas del producto
         ↓
5. Bot intenta cerrar: "¿Te lo enviamos?"
         ↓
6. Bot recopila datos de envío (nombre, dirección, teléfono)
         ↓
7. Bot pregunta método de pago
    ├── Contraentrega → confirma pedido y guarda datos
    └── Pago previo → espera captura → verifica → confirma → guarda datos
         ↓
8. Bot confirma pedido y comunica tiempo de entrega
         ↓
9. Datos pasan al flujo existente de dropshipping
```

**Datos que recopila el bot durante la conversación:**
- Nombre completo
- Teléfono de contacto
- Dirección de envío completa
- Producto y variante (color, talla, etc.)
- Método de pago
- Confirmación de pago (captura si aplica)
- Origen (ID del anuncio si es FEP)

---

### Flujo 2 — Cliente compra en landing page → Bot confirma

**Origen:** Cliente entra a la landing page de un producto, llena formulario y da clic en "Comprar".

**Diferencia clave:** El bot INICIA la conversación, por lo que el primer mensaje debe ser una plantilla aprobada por Meta (mensaje de utilidad). Se cobra ~$0.0048.

**Ventaja:** Cliente ya tiene alta intención de compra. La conversación es más corta porque los datos ya existen en la base de datos.

```
1. Cliente llena formulario en la web
         ↓
2. Datos entran a la base de datos
         ↓
3. Sistema detecta nuevo registro y dispara el bot
         ↓
4. Bot envía plantilla aprobada de apertura:
   "Hola {{nombre}}, soy Sofía de AzoShop 👋
    Vi que mostraste interés en *{{producto}}*.
    ¿Confirmamos tu pedido para comenzar con el envío?"
         ↓
5. Cliente responde → se abre ventana de 24h → bot conversa libremente
         ↓
6. Bot confirma datos del formulario con el cliente
         ↓
7. Bot pregunta método de pago
    ├── Contraentrega → confirma pedido
    └── Pago previo → manda datos bancarios → espera captura → confirma
         ↓
8. Bot confirma pedido y tiempo de entrega
         ↓
9. Datos actualizados van al flujo de dropshipping
```

**Manejo de no respuesta:**
```
Hora 0:   Bot envía plantilla de apertura
Hora 2:   Sin respuesta → Bot envía plantilla de recordatorio
          "Hola {{nombre}}, solo quería confirmar si 
           recibiste mi mensaje sobre tu pedido 😊"
Hora 24:  Sin respuesta → Lead marcado como frío
          Queda en base de datos para seguimiento manual
```
> ⚠️ No enviar más de 2 mensajes sin respuesta para proteger el Quality Rating del número.

---

### Flujo 3 — Cliente existente con problema postventa ⚠️ PENDIENTE DE DESARROLLAR

**Origen:** Cliente que ya compró escribe al número días después.

**Lógica:** Al recibir un mensaje, el bot consulta la base de datos por el número de teléfono. Si encuentra un pedido activo asociado, cambia a modo postventa.

**Casos que cubre:**
- Pedido no ha llegado
- Producto incorrecto
- Producto dañado
- Solicitud de devolución

**Comportamiento definido:**
- El bot NO intenta vender
- Consulta el estado del pedido en la base de datos
- Escala SIEMPRE a atención personal (postventa requiere criterio humano)
- Notifica al dueño para intervenir

> 🔴 **Pendiente:** Definir respuestas específicas del bot para cada caso de postventa y el mensaje de transición a atención humana.

---

### Flujo 4 — Cliente sin contexto de producto ⚠️ PENDIENTE DE DESARROLLAR

**Origen:** Cliente escribe directamente al número sin venir de anuncio y sin haber llenado formulario. Pregunta genérica: "¿Qué venden?", "¿Tienen audífonos?", etc.

**Comportamiento propuesto:**
- Bot responde de forma genérica sobre AzoShop
- Muestra categorías o productos disponibles actualmente
- Intenta identificar interés específico
- Lleva al cliente hacia un producto concreto para retomar flujo de venta

> 🔴 **Pendiente:** Definir catálogo mínimo de respuestas, cómo se actualiza cuando cambian los productos disponibles, y el flujo de transición hacia el cierre de venta.

---

## 5. Sistema de Escalado a Atención Personal

El bot escala a atención humana cuando:

- El cliente pregunta algo que no está en la base de conocimiento del producto
- El cliente se queja de un pedido anterior (activa Flujo 3)
- El cliente solicita explícitamente hablar con una persona
- El bot falla 2 veces seguidas en interpretar la intención del cliente
- El cliente menciona devoluciones o garantías con casos específicos
- Cualquier situación ambigua que el bot no pueda manejar con confianza

**Mensaje de transición del bot:**
> "Déjame conectarte con uno de nuestros asesores para ayudarte mejor con esto, en un momento te atienden."

**Acción del sistema:**
- Conversación se marca como `estado: atencion_personal`
- El bot deja de responder automáticamente en esa conversación
- Se notifica al dueño (pendiente definir canal: email, Telegram, etc.)
- El dueño interviene manualmente desde su teléfono

> 🔴 **Pendiente:** Definir canal de notificación al dueño cuando se activa el escalado.

---

## 6. Base de Conocimiento del Bot

Por cada producto en campaña, el bot necesita tener cargado:

| Campo | Descripción |
|-------|-------------|
| Nombre del producto | Nombre exacto como aparece en el anuncio |
| Descripción | Características principales, beneficios |
| Precio | Precio de venta al público |
| Variantes | Colores, tallas, modelos disponibles |
| Tiempo de entrega | Estimado en días hábiles |
| Métodos de pago | Qué se acepta (transferencia, contraentrega, etc.) |
| Datos bancarios | Para pagos previos (a cargar de forma segura) |
| Preguntas frecuentes | Las dudas más comunes sobre ese producto |
| Qué NO puede responder | Lista de temas que deben escalar a humano |

> ⚠️ Cada vez que se lanza un anuncio nuevo, hay que actualizar la base de conocimiento del bot con el producto correspondiente.

---

## 7. Estructura de Datos — Pedidos en Base de Datos

```python
pedido = {
    "id": "uuid",
    "telefono_whatsapp": "593987654321",
    "nombre_cliente": "Juan Pérez",
    "producto": "Nombre del producto",
    "variante": "Color rojo, talla M",
    "direccion_envio": "Calle X, Cuenca, Ecuador",
    "metodo_pago": "contraentrega | transferencia",
    "estado_pago": "pendiente | confirmado",
    "captura_pago_url": "url_de_la_imagen_si_aplica",
    "origen": "fep | web_formulario | directo",
    "id_anuncio": "23847382910",  # Solo si es FEP
    "estado_pedido": "nuevo | confirmado | enviado | entregado | problema",
    "estado_conversacion": "vendiendo | datos_recopilados | pago_pendiente | cerrado | atencion_personal | frio",
    "fecha_creacion": "2026-09-08T14:00:00",
    "fecha_actualizacion": "2026-09-08T15:30:00"
}
```

---

## 8. Señales de Estado que Devuelve la IA

En cada respuesta, la IA devuelve además del mensaje al cliente una señal de estado que el servidor usa para actualizar la base de datos:

| Señal | Significado |
|-------|-------------|
| `vendiendo` | Conversación en curso, aún no hay compromiso |
| `datos_recopilados` | Cliente confirmó datos de envío |
| `pago_pendiente` | Esperando captura de transferencia |
| `venta_cerrada` | Pedido confirmado, listo para dropshipping |
| `escalar_a_humano` | Bot no puede continuar, necesita intervención |
| `cliente_existente` | Se detectó número con pedido previo (postventa) |

---

## 9. Detección de Origen FEP en el Webhook

```python
def procesar_mensaje(payload):
    mensaje = payload["messages"][0]
    es_fep = "referral" in mensaje
    
    if es_fep:
        anuncio_id = mensaje["referral"]["source_id"]
        ctwa_clid = mensaje["referral"]["ctwa_clid"]
        # Cargar contexto del producto asociado a ese anuncio
        # Registrar origen para tracking de conversiones
    else:
        # Flujo directo o web
        pass
```

**Datos disponibles en el objeto `referral`:**
- `source_url` — URL del anuncio
- `source_type` — Siempre "ad" para Click-to-WhatsApp
- `source_id` — ID del anuncio en Meta Ads
- `headline` — Título del anuncio
- `body` — Texto del anuncio
- `ctwa_clid` — ID de clic para tracking de conversiones

---

## 10. Decisiones de Arquitectura Tomadas

| Decisión | Elección | Razón |
|----------|----------|-------|
| Acceso a WhatsApp | Cloud API de Meta directo | Sin depender de BSP, control total, sin margen intermediario |
| Lenguaje | Python | Preferencia del desarrollador |
| Tipo de bot | IA conversacional (LLM) | No solo respuestas predefinidas |
| BSP | Ninguno | Conexión directa a Meta |
| Inicio de conversaciones | Solo para Flujo 2 y seguimientos | Minimizar costos de plantillas |

---

## 11. Pendientes por Definir

### Técnicos
- [ ] Elegir el LLM a usar (Claude, GPT-4, Gemini, etc.)
- [ ] Definir base de datos (PostgreSQL, MongoDB, Supabase, etc.)
- [ ] Definir servidor de hosting (Railway, Render, VPS, etc.)
- [ ] Canal de notificación al dueño cuando se activa escalado a humano
- [ ] Estrategia de actualización de base de conocimiento cuando cambian productos

### De negocio
- [ ] Nombre definitivo del bot / asesora virtual
- [ ] Política de devoluciones y garantías (para que el bot sepa qué escalar)
- [ ] Horario de atención humana (para que el bot sepa cuándo puede prometer respuesta)
- [ ] Datos bancarios para pagos previos
- [ ] Tiempo de entrega estándar por zona en Ecuador

### Plantillas de Meta a crear y aprobar
- [ ] Plantilla de apertura Flujo 2 (confirmación de pedido web)
- [ ] Plantilla de recordatorio Flujo 2 (seguimiento sin respuesta)
- [ ] Plantilla de seguimiento postventa si aplica

---

## 12. Orden de Desarrollo Recomendado

```
1. Flujo 1 completo (WhatsApp directo / FEP) ← EMPEZAR AQUÍ
2. Flujo 3 (postventa) — llegará antes de lo esperado
3. Flujo 4 (consulta sin contexto de producto)
4. Flujo 2 (landing page + formulario web)
5. Canales futuros: Instagram DMs, chatbot web (NO ahora)
```

---

## 13. Estado de Configuración de Meta (Progreso Actual)

- [x] Cuenta de Facebook personal (Freddy Javier Paguay)
- [x] Portfolio comercial creado (AzoShop)
- [x] Página de Facebook creada (pendiente renombrar a AzoShop)
- [ ] Información del negocio completa (nombre legal, RUC, dirección, web)
- [ ] Verificación de empresa Meta
- [ ] Registro en Meta for Developers
- [ ] App tipo "Business" creada con producto WhatsApp
- [ ] Número de teléfono registrado en WABA
- [ ] Token de acceso permanente generado
- [ ] Webhook configurado
- [ ] Plantillas de mensaje creadas y aprobadas

---

*Documento generado en base a sesión de planificación — septiembre 2026*
*Continuar con: configuración de Meta Business Suite → Información del negocio*