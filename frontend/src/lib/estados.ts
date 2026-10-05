export type StatusVariant = "success" | "warning" | "danger" | "info" | "neutral";

export type EstadoInfo = { label: string; variant: StatusVariant };

/**
 * Estados locales de un pedido (columna `pedidos.estado_local`).
 * Espejo intencional de la lógica en
 * `backend/src/routes/pedidos/services.py` (ver PROGRESS.md, Etapa 3 y 6).
 * Si un estado nuevo se agrega allá, agregarlo también acá.
 */
export const ESTADOS_LOCALES: Record<string, EstadoInfo> = {
  pendiente_creacion: { label: "Pendiente de creación", variant: "warning" },
  error: { label: "Error", variant: "danger" },
  incompleto: { label: "Incompleto", variant: "warning" },
  creado: { label: "Creado, sin confirmar", variant: "info" },
  confirmado: { label: "Confirmado", variant: "success" },
  rechazado: { label: "Rechazado", variant: "danger" },
};

/**
 * `status_id` de Rocketfy (Anexo A del proveedor). Espejo intencional de
 * `backend/src/integrations/rocketfy/constants.py::RocketfyStatus` — si
 * cambia allá, cambia acá.
 */
export const ROCKETFY_STATUS: Record<number, EstadoInfo> = {
  1: { label: "Nuevo", variant: "info" },
  2: { label: "Confirmado - Pendiente de preparación", variant: "info" },
  3: { label: "Rechazado", variant: "danger" },
  4: { label: "Preparado", variant: "info" },
  5: { label: "Enviado", variant: "info" },
  6: { label: "En ruta", variant: "info" },
  7: { label: "Novedad", variant: "warning" },
  8: { label: "Entregado", variant: "success" },
  9: { label: "Devuelto en tránsito", variant: "warning" },
  10: { label: "Devuelto recepcionado", variant: "neutral" },
  11: { label: "Pendiente de confirmación", variant: "warning" },
  12: { label: "Aplazado", variant: "warning" },
  13: { label: "Carrito abandonado", variant: "neutral" },
  14: { label: "No confirmable", variant: "danger" },
  15: { label: "Duplicado", variant: "danger" },
  23: { label: "Recogida en agencia", variant: "info" },
};

/**
 * Tipo de alerta de `alertas_stock` (Fase 2 - Etapa 3). Espejo de los
 * valores que `StockWatcherService` persiste en
 * `backend/src/jobs/stock_watcher/service.py`.
 */
export const TIPO_ALERTA_STOCK: Record<string, EstadoInfo> = {
  stock_bajo: { label: "Stock bajo", variant: "warning" },
  cambio_precio: { label: "Cambio de precio", variant: "info" },
};

export function tipoAlertaStockInfo(tipo: string): EstadoInfo {
  return TIPO_ALERTA_STOCK[tipo] ?? { label: tipo, variant: "neutral" };
}

/**
 * Estados de `conversaciones.estado` (Fase 3.2, módulo de Conversaciones).
 * Espejo intencional de las migraciones de `conversaciones` en el
 * backend. "cerrada" y "fria" comparten variante "neutral" -- el sistema
 * de diseño solo define 5 variantes de color, no hay un gris más claro
 * aparte para distinguirlas visualmente.
 */
export const ESTADOS_CONVERSACION: Record<string, EstadoInfo> = {
  activa: { label: "Activa", variant: "success" },
  esperando_pago: { label: "Esperando pago", variant: "warning" },
  escalada: { label: "Escalada", variant: "danger" },
  cerrada: { label: "Cerrada", variant: "neutral" },
  fria: { label: "Fría", variant: "neutral" },
};

export function estadoConversacionInfo(estado: string): EstadoInfo {
  return ESTADOS_CONVERSACION[estado] ?? { label: estado, variant: "neutral" };
}

export function estadoLocalInfo(estado: string): EstadoInfo {
  return ESTADOS_LOCALES[estado] ?? { label: estado, variant: "neutral" };
}

export function rocketfyStatusInfo(statusId: number | null | undefined): EstadoInfo | null {
  if (statusId == null) return null;
  return ROCKETFY_STATUS[statusId] ?? { label: `Estado ${statusId}`, variant: "neutral" };
}
