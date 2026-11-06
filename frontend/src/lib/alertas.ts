import { formatMoney } from "@/lib/format";
import type { AlertaStock } from "@/types/incidencia";

/** Una línea que resume una alerta de producto (para las listas compactas). Los
 * tipos vienen de backend/src/jobs/stock_watcher y de la sincronización de
 * productos publicados (backend/src/routes/productos_bot/sincronizacion.py). */
export function resumenAlertaStock(a: AlertaStock): string {
  const d = a.detalle;
  switch (a.tipo) {
    case "stock_bajo":
      return `Quedan ${d.stock} (mínimo ${d.umbral})`;
    case "cambio_precio":
      return `De ${formatMoney(String(d.precioAnterior))} a ${formatMoney(String(d.precioActual))}`;
    case "producto_agotado":
      return "Sin stock en Rocketfy: se pausó solo";
    case "margen_en_riesgo":
      return `Costo ${formatMoney(String(d.costoAnterior ?? ""))} → ${formatMoney(String(d.costoActual))}: margen ${d.margenPct} % (mínimo ${d.margenMinimoPct} %)`;
    default:
      return JSON.stringify(d);
  }
}
