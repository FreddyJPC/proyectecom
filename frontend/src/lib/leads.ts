import type { EstadoInfo } from "@/lib/estados";
import type { MotivoPerdida, OrigenTemperatura, Temperatura, TipoDeContacto } from "@/types/leads";

/**
 * Temperatura de un lead (docs/PLAN_LEADS_CRM.md §2.2): qué tan probable es que compre. Espejo de
 * `backend/src/routes/leads/temperaturas.py`. El sistema de diseño solo tiene cinco colores de estado:
 * caliente = naranja (hay que atenderlo ya), tibio = azul, frío = gris, perdido = rojo, ganado = verde.
 */
export const TEMPERATURAS: Record<Temperatura, EstadoInfo & { explicacion: string }> = {
  caliente: { label: "Caliente", variant: "warning", explicacion: "Va en serio: pide precio, datos de envío o cómo pagar." },
  tibio: { label: "Tibio", variant: "info", explicacion: "Hay interés, pero todavía no se decide." },
  frio: { label: "Frío", variant: "neutral", explicacion: "Dejó de responder o su interés bajó. Aún se puede recuperar." },
  perdido: { label: "Perdido", variant: "danger", explicacion: "Ya no va a comprar. Queda guardado el motivo." },
  ganado: { label: "Ganado", variant: "success", explicacion: "Compró: la venta se cerró." },
};

export const TEMPERATURAS_ABIERTAS: Temperatura[] = ["caliente", "tibio", "frio"];

export function temperaturaInfo(t: string): EstadoInfo & { explicacion: string } {
  return TEMPERATURAS[t as Temperatura] ?? { label: t, variant: "neutral", explicacion: "" };
}

export const MOTIVOS_PERDIDA: Record<MotivoPerdida, string> = {
  precio: "El precio",
  sin_respuesta: "No respondió",
  compro_en_otro_lado: "Compró en otro lado",
  sin_cobertura: "No llegamos a su ciudad",
  sin_stock: "Sin stock",
  no_le_interesa: "No le interesa",
  otro: "Otro motivo",
};

/** Etapa del lead (`leads.estado`): DÓNDE VA, no qué tan probable es que compre. */
export const ETAPAS_LEAD: Record<string, string> = {
  recopilando_datos: "Recopilando datos",
  esperando_pago: "Esperando pago",
  listo_para_despacho: "Listo para despachar",
  despachado: "Despachado",
  por_gestionar: "Por gestionar",
  cancelado: "Cancelado",
};

export function etapaLead(etapa: string): string {
  return ETAPAS_LEAD[etapa] ?? etapa.replace(/_/g, " ");
}

/** La temperatura que imponen los hechos (espejo de `temperatura_por_hechos` del backend): una venta cerrada es «ganado»
 * y una cancelada «perdido»; mientras exista, el dueño no puede contradecirla. null = los hechos no dicen nada. */
export function temperaturaImpuesta(etapa: string): Temperatura | null {
  if (etapa === "despachado" || etapa === "por_gestionar") return "ganado";
  if (etapa === "cancelado") return "perdido";
  return null;
}

/** Quién puso la temperatura. */
export const ORIGEN_TEMPERATURA: Record<OrigenTemperatura, string> = {
  ia: "Victoria",
  regla: "El sistema",
  dueno: "Tú",
};

export const TIPOS_CONTACTO: Record<TipoDeContacto, EstadoInfo> = {
  prospecto: { label: "Prospecto", variant: "neutral" },
  cliente: { label: "Cliente", variant: "success" },
  recurrente: { label: "Cliente recurrente", variant: "success" },
};

/** Cómo llegó el cliente (`origen`): anuncio o directo. */
export function nombreOrigen(origen: string): string {
  return origen === "anuncio" ? "Anuncio" : origen === "directo" ? "Directo" : origen === "web_formulario" ? "Formulario web" : origen;
}

/** ¿Esta fecha todavía no llega? (p. ej. hasta cuándo está fijada la temperatura). Solo presentación. */
export function esFutura(iso: string | null | undefined): boolean {
  return !!iso && new Date(iso).getTime() > Date.now();
}
