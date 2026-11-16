/** «Aprendizaje de Victoria» (entrada 0.0.140): cada vez que se trabó, no entendió o pasó la conversación a un asesor. */
export type MensajeDeCaso = { rol: string; texto: string; en: string | null };

export type CasoAprendizaje = {
  id: number;
  creadoEn: string;
  conversacionId: number | null;
  leadId: number | null;
  cliente: string | null;
  canal: string | null;
  tipo: string;
  tipoNombre: string;
  /** victoria | sistema | dueno */
  origen: string;
  motivo: string;
  /** Lo último que escribió el cliente antes de que pasara (copia exacta). */
  mensajeCliente: string | null;
  etapa: string | null;
  productoSku: string | null;
  mensajes: MensajeDeCaso[];
  estado: "pendiente" | "revisado" | "resuelto" | "descartado";
  categoria: string | null;
  accion: string | null;
  nota: string | null;
  revisadoPor: string | null;
  revisadoEn: string | null;
};

export type ListaAprendizaje = { casos: CasoAprendizaje[]; total: number; pagina: number; porPagina: number };

export type ResumenAprendizaje = {
  pendientes: number;
  total: number;
  porTipo: { tipo: string; tipoNombre: string; cantidad: number }[];
  porEtapa: { etapa: string | null; cantidad: number }[];
  tipos: { tipo: string; nombre: string }[];
  acciones: { accion: string; nombre: string }[];
};
