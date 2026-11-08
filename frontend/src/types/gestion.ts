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
};
