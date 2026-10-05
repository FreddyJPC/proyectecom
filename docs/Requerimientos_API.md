# Requerimientos de Integración API – Automatización de Flujo

**Asunto:** Requerimientos de Integración API – Automatización de Flujo

Estimado equipo de Rocket,

El objetivo de este documento es alinear mis requerimientos técnicos para la integración entre mi sistema y su plataforma logística.

La meta principal de esta integración es automatizar el flujo de pedidos, minimizando la intervención manual, reduciendo el margen de error en despachos y aumentando la tasa de entregas exitosas mediante notificaciones proactivas al cliente final.

A continuación, detallo los requerimientos divididos por prioridad de implementación, junto con la lógica de negocio que justifica cada necesidad:

---

## FASE 1: Prioridad Alta (Esenciales)

Estas integraciones son las mas esenciales, ya que automatizan el ingreso y seguimiento del paquete.

### 1. Creación de Orden de Despacho (Inyección de Pedido)

- **Tipo esperado:** POST
- **Lógica de negocio:** Una vez que el cliente llena el formulario en mi Landing Page y confirma el pedido vía WhatsApp, mi sistema inyectará los datos estructurados suena como tengan las reglas definidas (Ejemplo: nombre, teléfono, dirección, cantón, provincia, SKU) directamente a su plataforma.
- **Objetivo:** Eliminar la carga manual de datos y acelerar el tiempo de preparación en bodega.

### 2. Consulta de Cobertura y Flete por Destino

- **Tipo esperado:** GET o POST (Cotizador)
- **Lógica de negocio:** Antes de confirmar una orden, mi sistema necesita validar si el cantón o parroquia ingresada por el cliente tiene cobertura para "Pago Contra Entrega" y cuál es el costo logístico de ese trayecto.
- **Objetivo:** Evitar despachar paquetes a zonas sin cobertura de recaudo, lo cual generaría devoluciones automáticas y pérdida de dinero en fletes.

### 3. Sincronización de Estados de Guía Logística

- **Tipo esperado:** Webhooks (Ideal) o Endpoint de consulta GET (Polling).
- **Lógica de negocio:** Necesito recibir actualizaciones en tiempo real cuando la guía cambie de estado (ej. "Generada", "En Ruta", "Novedad", "Entregada", "Devolución").
- **Objetivo:** Con esta data, mi sistema enviará alertas automáticas por WhatsApp al cliente (ej. "Tu paquete llega hoy, ten el efectivo listo"), lo que se espera aumente la tasa de entrega efectiva y resuelve novedades logísticas a tiempo.

---

## FASE 2: Prioridad Secundaria (Escalabilidad y Control Financiero)

Estas integraciones se implementarán para proteger la inversión publicitaria y automatizar la contabilidad.

### 4. Consulta de Stock por SKU

- **Tipo esperado:** GET
- **Lógica de negocio:** Mi sistema consultará periódicamente el inventario disponible de los productos que estoy pautando.
- **Objetivo:** Si el inventario de un producto baja a un nivel crítico, mi sistema pausará automáticamente las campañas publicitarias en Meta/TikTok para evitar vender productos sin stock.

### 5. Cancelación / Edición de Órdenes

- **Tipo esperado:** PUT / DELETE (o POST de anulación)
- **Lógica de negocio:** Habrá casos donde el cliente cancele la compra o corrija su dirección por X razón después de haberla confirmado.
- **Objetivo:** Poder detener o modificar el despacho desde mi sistema antes de que la bodega imprima la guía, ahorrando costos logísticos innecesarios.

### 6. Consultar Liquidaciones y Saldos

- **Tipo esperado:** GET
- **Lógica de negocio:** Necesito consultar el estado financiero de los pedidos entregados (cuánto dinero ya fue recaudado y liquidado a mi favor).
- **Objetivo:** Automatizar mi flujo de caja para saber exactamente qué capital tengo disponible para reinvertir en publicidad o solicitar retiros, sin depender de reportes manuales.

### 7. Consulta de Catálogo Completo y Precios

- **Tipo esperado:** GET
- **Lógica de negocio:** Sincronización de los SKUs disponibles, datos/información del producto y costos base y toda información disponible.
- **Objetivo:** Si el precio base o información de un producto cambia, mi sistema por ejemplo en el caso de cambios en precio me alertará para ajustar mi precio de venta final y proteger mi margen de ganancia.

---

Quedo a su disposición para responder cualquier duda referente al documento o planeación.

Atentamente,

**Freddy Paguay**  
Desarrollador de Software
