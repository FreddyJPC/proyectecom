# 06 — Estado Actual del Proyecto

> Contexto de negocio: el proyecto se llama internamente **PROYECTECOM**
> y es la infraestructura de backend/dashboard para **AzoShop**
> (dropshipping, Ecuador). El plan siempre incluyó, como fase final, un
> bot de WhatsApp con IA (nombre tentativo **"Sofía"**) — ver
> `docs/BotPlanifiacion.md`, que ya existe con una planificación bastante
> detallada de una sesión previa con Claude web. Este documento describe
> qué tan avanzado está todo LO DEMÁS (lo que no es el bot todavía).

## 1. Qué funciona al 100% hoy

### Backend (Flask) — "Fase 1", completa y validada contra producción real
Cubre los 7 requerimientos originales del negocio:
- Crear + confirmar pedidos en Rocketfy, con idempotencia real probada
  (network timeouts, rechazos de negocio, reintentos seguros).
- Recepción de webhooks de Rocketfy + job de reconciliación de respaldo.
- Vigilancia de stock/precio de productos pautados, con alertas
  persistidas.
- Modificar/cancelar pedidos ya creados.
- Métricas agregadas de negocio.
- Catálogo de productos y de ubicaciones (832 cantones de Ecuador).

**105 tests automáticos (pytest), todos pasando.** Validado además con
pedidos reales de bajo valor contra la API real de Rocketfy (creados y
luego rechazados) — no hay sandbox del proveedor, así se prueba todo.

### Frontend (Next.js) — "Fase 2", 6 de 7 etapas construidas
Dashboard interno para el dueño del negocio: login, listado/detalle de
pedidos con acciones manuales, incidencias y alertas, explorador de
catálogo + gestión de SKUs monitoreados, métricas, y un formulario de
creación manual de pedido (respaldo mientras no exista el bot). Falta
solo la etapa de pulido/despliegue final.

## 2. Qué está a medias o incompleto

- **Canal real de envío de WhatsApp a clientes finales — nunca se
  construyó, quedó explícitamente diferido por el dueño del negocio
  hasta ahora.** Esto es exactamente el punto de partida del proyecto
  del bot. Hoy existe solo un `LoggingNotificationChannel` (placeholder
  que loguea, no envía nada de verdad) como resultado de haber adaptado
  un patrón de un proyecto de ejemplo no relacionado.
- **Alertas internas al dueño:** el dashboard ya muestra incidencias y
  alertas (Fase 2), pero es "hay que entrar a mirar" — no hay ningún
  aviso push/proactivo todavía (ni email, ni Telegram, nada). Esto se
  cruza directamente con la necesidad del bot de "notificar al dueño
  cuando escala a atención personal" (`docs/BotPlanifiacion.md`, sección
  5) — es el mismo problema sin resolver, no dos problemas distintos.
- **Despliegue real:** todo corre hoy en procesos de desarrollo local
  (`flask run`, `next dev`) en la máquina del dueño. El webhook de
  Rocketfy se probó una vez con un túnel temporal (`cloudflared`), que ya
  se cerró — no hay una URL pública real hoy. No se ha elegido hosting
  (Render, Railway, VPS, etc.) para ninguna de las dos apps.
- **Estrategia de jobs en producción:** los jobs en background
  (reconciliación, vigilancia de stock) solo arrancan hoy en el proceso
  de desarrollo (`if __name__ == "__main__"`), no está definido cómo
  arrancarían con gunicorn multi-worker en producción.
- **KYC de la cuenta Rocketfy:** se infiere aprobado porque la API ya
  responde bien, pero nunca se confirmó formalmente en su panel.

## 3. Dependencias externas

- **Rocketfy** — API REST propia, sin sandbox, es el proveedor logístico.
- **Supabase** — Postgres + Auth (un solo proyecto, usado para ambas
  cosas).
- **Meta / WhatsApp Cloud API** — decidido como canal para el bot
  (`docs/BotPlanifiacion.md`), pero la configuración de la cuenta de
  Meta Business todavía está en progreso (ver esa misma sección 13 del
  documento — falta verificación de empresa, WABA, tokens, plantillas).
- Ningún LLM está integrado todavía en ningún lado del proyecto.

## 4. Decisiones técnicas importantes y por qué

- **Sin ORM, SQL crudo con psycopg2** — proyecto chico, el equipo prefirió
  control directo sobre el SQL antes que la capa extra de un ORM.
- **Persistencia mínima (ADR-002)** — Rocketfy es la fuente de verdad del
  pedido, la base propia solo existe para idempotencia/auditoría/locks,
  no para duplicar todo su modelo de datos.
- **Dinero siempre como string/Decimal, nunca float** — advertencia
  explícita del proveedor sobre errores de redondeo; se respeta en todo
  el proyecto, incluido el frontend (formateo de display con
  `toFixed(2)` está documentado como "solo para mostrar, nunca para
  calcular").
- **Verificación de sesión contra la API de Supabase en cada request**
  (no JWT local) — decisión consciente de simplicidad para un panel de
  un solo usuario administrador; documentado como cambiable a
  verificación local (JWKS) si el volumen lo justifica en el futuro.
- **Next.js 16 + React 19** — el proyecto usa versiones nuevas con
  cambios de breaking changes reales respecto a versiones anteriores
  (ej. `middleware.ts` se renombró a `proxy.ts`) — si Claude web genera
  código de Next.js basado en conocimiento más viejo, puede sugerir
  patrones ya obsoletos en este proyecto específico.

## 5. Problemas conocidos / limitaciones actuales

- No existe endpoint de cotización de flete en la API de Rocketfy — ni
  nosotros ni el bot pueden saber el costo de envío antes de intentar
  confirmar un pedido (ver hallazgo del "mínimo real dinámico" en
  `02_flujo_distribuidor.md`).
- No existe endpoint de saldo de wallet/liquidaciones para vendedores —
  el dashboard solo muestra agregados operativos, no el saldo real.
- La forma exacta de la respuesta de `POST /orders/bulk/getInfo` de
  Rocketfy no está documentada con ejemplo — el job de reconciliación la
  parsea de forma defensiva pero no se ha confirmado con volumen real.
- El proyecto completo (`PROYECTECOM/`) no tiene control de versiones
  (no es un repo git) — solo `frontend/` tiene un git local propio, sin
  commits desde el inicial.
