/** Espejo intencional de backend/src/routes/conversaciones/schemas.py. Si
 * un campo cambia allá, cambia acá. */

export type UltimoMensaje = {
  rol: string;
  contenido: string;
  creadoEn: string | null;
};

export type ConversacionResumen = {
  id: number;
  telefono: string;
  nombreCliente: string | null;
  origen: string;
  estado: string;
  productoInteres: string | null;
  sinRevisar: boolean;
  ultimoMensaje: UltimoMensaje | null;
  creadaEn: string | null;
  actualizadaEn: string | null;
};

export type TotalesPorFiltroRapido = {
  escaladas: number;
  escaladasSinRevisar: number;
  esperandoPago: number;
};

export type ConversacionesListado = {
  items: ConversacionResumen[];
  total: number;
  page: number;
  pageSize: number;
  totalesPorFiltroRapido: TotalesPorFiltroRapido;
};

export type LeadConversacion = {
  nombreCliente: string | null;
  direccion: string | null;
  canton: string | null;
  provincia: string | null;
  productoSku: string | null;
  productoNombre: string | null;
  productoVariante: string | null;
  total: string | null;
  metodoPago: string | null;
  estadoPago: string | null;
  estado: string | null;
  idPedidoLocal: number | null;
  idPedidoRocketfy: number | null;
};

export type MensajeConversacion = {
  id: number;
  rol: string;
  contenido: string;
  tipo: string;
  creadoEn: string | null;
};

export type ConversacionDetalle = {
  id: number;
  telefono: string;
  origen: string;
  estado: string;
  idAnuncio: string | null;
  notasInternas: string | null;
  ventanaAbierta: boolean;
  ventanaExpiraEn: string | null;
  creadaEn: string | null;
  actualizadaEn: string | null;
};

export type ConversacionDetalleCompleto = {
  conversacion: ConversacionDetalle;
  lead: LeadConversacion | null;
  mensajes: MensajeConversacion[];
};
