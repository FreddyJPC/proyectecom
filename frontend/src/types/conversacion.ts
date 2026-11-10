/** Espejo intencional de backend/src/routes/conversaciones/schemas.py. Si
 * un campo cambia allá, cambia acá. */

export type UltimoMensaje = {
  rol: string;
  contenido: string;
  creadoEn: string | null;
};

export type ConversacionResumen = {
  id: number;
  /** Por dónde habla el cliente: whatsapp | instagram | messenger (ADR-014). */
  canal: string;
  /** Identificador del cliente en ese canal (en WhatsApp, su teléfono). */
  idExterno: string | null;
  /** Puede faltar: un cliente de Instagram o Messenger no tiene teléfono hasta que lo da. */
  telefono: string | null;
  /** Nombre del contacto (perfil del canal o el que dio al comprar). */
  nombre: string | null;
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
  /** Conversaciones que el dueño atiende (intención de compra de un producto propio). */
  enGestion: number;
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
  /** El mensaje trae una foto, un audio o un PDF (se baja de Meta al pedirlo). */
  tieneArchivo?: boolean;
  /** Lo que se entendió del archivo: la descripción de la foto o la transcripción del audio. */
  analisis?: string | null;
};

/** La ventana gratuita de Meta para clientes que llegan por anuncio. Es informativa: solo la de 24 h permite texto libre. */
export type VentanaGratuita = {
  estado: "sin_anuncio" | "pendiente" | "abierta" | "cerrada";
  expiraEn: string | null;
  responderAntesDe: string | null;
};

/** El anuncio más reciente por el que llegó el cliente, con lo que Meta mandó de él. */
export type AnuncioDeConversacion = {
  idAnuncio: string | null;
  titulo: string | null;
  texto: string | null;
  urlAnuncio: string | null;
  tipoOrigen: string | null;
  tipoMedia: string | null;
  imagenUrl: string | null;
  miniaturaUrl: string | null;
  producto: { sku: string; nombre: string } | null;
  /** Cuántas veces ha llegado este cliente por un anuncio. */
  llegadas: number;
};

export type LlegadaPorAnuncio = {
  idAnuncio: string | null;
  titulo: string | null;
  creadoEn: string | null;
};

export type ConversacionDetalle = {
  id: number;
  contactoId: number;
  canal: string;
  idExterno: string;
  telefono: string | null;
  nombre: string | null;
  /** Cómo llegó el cliente: «anuncio» o «directo» (no confundir con el canal). */
  origen: string;
  estado: string;
  idAnuncio: string | null;
  notasInternas: string | null;
  /** Ventana de servicio: 24 h desde el último mensaje del cliente. Solo mientras está abierta se puede escribir texto libre. */
  ventanaAbierta: boolean;
  ventanaExpiraEn: string | null;
  creadaEn: string | null;
  actualizadaEn: string | null;
  ventanaGratuita: VentanaGratuita | null;
  anuncio: AnuncioDeConversacion | null;
  llegadasPorAnuncio: LlegadaPorAnuncio[] | null;
};

export type ConversacionDetalleCompleto = {
  conversacion: ConversacionDetalle;
  lead: LeadConversacion | null;
  mensajes: MensajeConversacion[];
};
