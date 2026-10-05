/** Espejo intencional de backend/src/routes/metricas/schemas.py
 * (MetricasGeneralesResponseSchema) + avisoImportante agregado en el
 * controller. Todos los montos son string (nunca float, ver directriz 5). */
export type MetricasGenerales = {
  pedidosHoy: number | null;
  montoTotalPedidosHoy: string | null;
  confirmadosHoy: number | null;
  ingresoConfirmado: string | null;
  ingresoHoy: string | null;
  ingresoTotal: string | null;
  ingresoEnTransito: string | null;
  ingresoRetenidoPorNovedad: string | null;
  costoProductosEnTransito: string | null;
  avisoImportante: string;
};
