/** Espejo de backend/src/routes/gestion/schemas.py: lo que necesita al dueño («Por gestionar»). */

export type EstadoSolicitud = "pendiente" | "atendida";

export type Solicitud = {
  id: number;
  conversacionId: number;
  /** quiere_comprar | quiere_pagar | pide_envio | quiere_ver_producto | quiere_negociar | sin_cobertura | pedido_cerrado | otro */
  tipo: string;
  tipoEtiqueta: string;
  detalle: string | null;
  estado: EstadoSolicitud;
  notaAtencion: string | null;
  atendidaPor: string | null;
  creadaEn: string | null;
  atendidaEn: string | null;
  canal: string | null;
  idExterno: string | null;
  telefono: string | null;
  nombreCliente: string | null;
  direccion: string | null;
  canton: string | null;
  provincia: string | null;
  producto: string | null;
  variante: string | null;
  cantidad: number | null;
  metodoPago: string | null;
  entrega: string | null;
  /** Dinero como string; solo si ya hay un pedido cerrado. */
  total: string | null;
  proveedor: string | null;
  tienePedido: boolean;
  /** La venta ligada (solo si ya hay un pedido cerrado) y lo que se puede hacer con ella; lo decide el servidor. */
  ventaId: number | null;
  /** por_gestionar | gestionada | cancelada | despachada */
  ventaEstado: string | null;
  ventaCobradaEn: string | null;
  ventaCobradaPor: string | null;
  ventaNotaCobro: string | null;
  ventaCanceladaEn: string | null;
  ventaCanceladaPor: string | null;
  ventaMotivoCancelacion: string | null;
  puedeCobrar: boolean;
  puedeDeshacerCobro: boolean;
  puedeCancelar: boolean;
};

/** Respuesta de POST /ventas/<id>/cobrar, /deshacer-cobro y /cancelar. */
export type VentaAccionada = {
  id: number;
  estado: string;
  total: string | null;
  cobrada: boolean;
  /** Unidades que volvieron al stock al cancelar (0 si el producto no lleva control de stock). */
  stockDevuelto: number;
  /** Al cancelar, el producto recuperó unidades pero sigue en «Agotado»: reanudarlo es manual. */
  productoSigueAgotado: boolean;
};
