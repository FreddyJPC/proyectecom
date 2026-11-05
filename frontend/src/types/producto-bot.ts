/** Espejo de backend/src/routes/productos_bot/schemas.py. El dinero viaja
 * siempre como string (nunca float). */

export type EstadoProductoBot = "borrador" | "listo" | "activo" | "pausado" | "agotado" | "archivado";

export type ProductoBotResumen = {
  sku: string;
  nombre: string;
  estado: EstadoProductoBot;
  precio: string;
  costoRocketfy: string | null;
  stockUltimo: number | null;
  maxUnidadesPorPedido: number;
  imagenUrl: string | null;
  publicadoEn: string | null;
  actualizadoEn: string | null;
};

export type Verificacion = {
  /** Impiden publicar o reanudar. */
  bloqueos: string[];
  /** Se puede publicar, pero conviene saberlo. */
  avisos: string[];
};

export type EntradaHistorial = {
  accion: string;
  usuario: string | null;
  /** Para ediciones: { campo: [antes, después] }. */
  cambios: Record<string, unknown> | null;
  creadoEn: string | null;
};

export type ProductoBotDetalle = {
  sku: string;
  nombre: string;
  estado: EstadoProductoBot;
  precio: string;
  costoRocketfy: string | null;
  precioSugeridoRocketfy: string | null;
  stockUltimo: number | null;
  stockActualizadoEn: string | null;
  pesoKg: string | null;
  imagenUrl: string | null;
  rocketfyProductId: number | null;
  descripcion: string;
  variantes: string | null;
  tiempoEntrega: string;
  metodosPago: string[];
  preguntasFrecuentes: string | null;
  temasNoResponder: string | null;
  maxUnidadesPorPedido: number;
  notasInternas: string | null;
  publicadoEn: string | null;
  publicadoPor: string | null;
  creadoEn: string | null;
  actualizadoEn: string | null;
  verificacion: Verificacion;
  historial: EntradaHistorial[];
};

/** Cuerpo del PATCH: solo viajan los campos que cambiaron. */
export type EditarProductoBotInput = Partial<{
  nombre: string;
  descripcion: string;
  precio: string;
  variantes: string | null;
  tiempoEntrega: string;
  metodosPago: string[];
  preguntasFrecuentes: string | null;
  temasNoResponder: string | null;
  maxUnidadesPorPedido: number;
  notasInternas: string | null;
}>;

/** Acciones que cambian el estado (POST /productos-bot/<sku>/<accion>). */
export type AccionProductoBot = "publicar" | "reanudar" | "pausar" | "archivar" | "restaurar";

/** Métodos de pago que Victoria sabe manejar (espejo de
 * `METODOS_PAGO_VALIDOS` en el backend). */
export const METODOS_PAGO: { valor: string; label: string; ayuda: string }[] = [
  { valor: "contraentrega", label: "Contraentrega", ayuda: "El cliente paga al recibir." },
  { valor: "transferencia", label: "Transferencia", ayuda: "Pago anticipado: lo confirmas tú a mano." },
];
