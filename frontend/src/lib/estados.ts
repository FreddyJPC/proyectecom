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
  // Fase F: los genera la sincronización de productos publicados (backend/.../productos_bot/sincronizacion.py).
  producto_agotado: { label: "Se pausó: sin stock", variant: "danger" },
  margen_en_riesgo: { label: "Margen en riesgo", variant: "warning" },
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
  // ADR-012: el dueño la atiende (producto propio): Victoria ya no responde.
  en_gestion: { label: "En gestión", variant: "info" },
  // El dueño sacó a Victoria de la conversación (botón «Tomar la conversación» o al escribirle al cliente desde el panel).
  manual: { label: "Atiendes tú", variant: "info" },
  cerrada: { label: "Cerrada", variant: "neutral" },
  fria: { label: "Fría", variant: "neutral" },
};

/**
 * Tipos de solicitud de gestión («Por gestionar», ADR-012). Espejo de
 * `backend/src/routes/gestion/tipos.py`. Un pedido cerrado es lo más urgente de gestionar.
 */
export const TIPOS_SOLICITUD: Record<string, EstadoInfo> = {
  pedido_cerrado: { label: "Pedido cerrado", variant: "success" },
  quiere_comprar: { label: "Quiere comprar", variant: "info" },
  quiere_pagar: { label: "Quiere pagar", variant: "info" },
  pide_envio: { label: "Pide envío o retiro", variant: "info" },
  quiere_ver_producto: { label: "Quiere ver el producto", variant: "warning" },
  quiere_negociar: { label: "Quiere negociar", variant: "warning" },
  sin_cobertura: { label: "Destino sin cobertura", variant: "danger" },
  otro: { label: "Otra gestión", variant: "neutral" },
};

export function tipoSolicitudInfo(tipo: string): EstadoInfo {
  return TIPOS_SOLICITUD[tipo] ?? { label: tipo, variant: "neutral" };
}

/**
 * En qué quedó el dinero de una venta de un producto propio (ADR-012): «atendida» solo quiere decir que
 * el dueño gestionó el pedido; el cobro es otra cosa. Devuelve null si la solicitud no tiene venta.
 */
export function estadoDeCobro(s: { tienePedido: boolean; ventaEstado: string | null; ventaCobradaEn: string | null }): EstadoInfo | null {
  if (!s.tienePedido) return null;
  if (s.ventaEstado === "cancelada") return { label: "Venta cancelada", variant: "danger" };
  if (s.ventaCobradaEn) return { label: "Cobrada", variant: "success" };
  return { label: "Por cobrar", variant: "warning" };
}

/**
 * Estados de `productos_bot.estado` (Fase B de la gestión de productos).
 * Espejo de `backend/src/routes/productos_bot/services.py`. Solo "activo"
 * (aquí "A la venta") es lo que Victoria ofrece; el resto son productos que
 * no se venden: aún sin publicar, en pausa, sin stock o archivados.
 */
export const ESTADOS_PRODUCTO_BOT: Record<string, EstadoInfo & { explicacion: string }> = {
  borrador: { label: "Borrador", variant: "neutral", explicacion: "Todavía no se vende. Completa los datos y publícalo." },
  listo: { label: "Listo", variant: "info", explicacion: "Completo, a la espera de publicarse." },
  activo: { label: "A la venta", variant: "success", explicacion: "Victoria lo ofrece a los clientes." },
  pausado: { label: "Pausado", variant: "warning", explicacion: "Victoria no lo ofrece. Puedes reanudarlo cuando quieras." },
  agotado: { label: "Agotado", variant: "danger", explicacion: "Sin stock: Victoria no lo ofrece hasta que lo reanudes." },
  archivado: { label: "Archivado", variant: "neutral", explicacion: "Fuera de la lista. Puedes restaurarlo como borrador." },
};

export function estadoProductoBotInfo(estado: string): EstadoInfo & { explicacion: string } {
  return ESTADOS_PRODUCTO_BOT[estado] ?? { label: estado, variant: "neutral", explicacion: "" };
}

/** Etiqueta legible de cada acción del historial de un producto. */
export const ACCIONES_HISTORIAL: Record<string, string> = {
  creado: "Creado como borrador",
  editado: "Editado",
  publicado: "Publicado",
  pausado: "Pausado",
  reanudado: "Reanudado",
  archivado: "Archivado",
  restaurado: "Restaurado como borrador",
  actualizado_rocketfy: "Datos de Rocketfy actualizados",
  redactado_ia: "Borrador redactado con IA",
  simulacion_completa: "Compra de prueba completada con Victoria",
  agotado: "Se pausó solo: sin stock en Rocketfy",
};

/** De dónde sale un texto redactado con IA. «Sugerido por IA» es la señal de
 * alerta: lo añadió la IA por su cuenta y hay que verificarlo. */
export const FUENTES_CONTENIDO: Record<string, EstadoInfo & { ayuda: string }> = {
  rocketfy: { label: "De Rocketfy", variant: "info", ayuda: "Sale de lo que dice Rocketfy." },
  notas: { label: "De tus notas", variant: "success", ayuda: "Sale de lo que escribiste tú." },
  mixto: { label: "Rocketfy y tus notas", variant: "info", ayuda: "Combina lo que dice Rocketfy con lo que escribiste tú." },
  ia: { label: "Sugerido por IA: verifica", variant: "warning", ayuda: "Lo añadió la IA por su cuenta o no se pudo comprobar con tus datos. Verifícalo antes de aceptarlo." },
};

export function fuenteContenidoInfo(fuente: string | undefined): EstadoInfo & { ayuda: string } {
  return FUENTES_CONTENIDO[fuente ?? "ia"] ?? FUENTES_CONTENIDO.ia;
}

/** Nombre legible de cada campo de la ficha tal como los llama la API (camelCase). */
export const ETIQUETAS_CAMPOS_REDACTABLES: Record<string, string> = {
  nombre: "Nombre del producto",
  descripcion: "Descripción",
  variantes: "Variantes",
  preguntasFrecuentes: "Preguntas frecuentes",
  temasNoResponder: "Temas que Victoria NO debe responder",
};

/** Nombre legible de cada campo que aparece en `cambios` del historial (son
 * nombres de columna de `productos_bot`). */
export const CAMPOS_HISTORIAL: Record<string, string> = {
  nombre: "Nombre",
  descripcion: "Descripción",
  precio: "Precio",
  variantes: "Variantes",
  tiempo_entrega: "Tiempo de entrega",
  metodos_pago_aceptados: "Métodos de pago",
  preguntas_frecuentes: "Preguntas frecuentes",
  temas_no_responder: "Temas que no debe responder",
  max_unidades_por_pedido: "Unidades máximas por pedido",
  notas_internas: "Notas internas",
  precio_competencia: "Precio de la competencia",
  costo_rocketfy: "Costo en Rocketfy",
  precio_sugerido_rocketfy: "Precio sugerido por Rocketfy",
  estado: "Estado",
  categoria_id: "Categoría",
  envio_incluido: "Envío incluido en el precio",
  costo_flete_estimado: "Flete estimado del producto",
  costo_propio: "Lo que te cuesta",
  controla_stock: "Control de stock",
  stock_ultimo: "Stock",
  entregas: "Opciones de entrega",
  fotos: "Fotos",
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
