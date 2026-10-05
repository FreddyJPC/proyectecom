/** Espejo intencional de backend/src/routes/pedidos/schemas.py
 * (PedidoResumenSchema / PedidoDetalleSchema). Si un campo cambia allá,
 * cambia acá. */

export type LineaPedido = {
  sku: string;
  nombre: string;
  cantidad: number;
};

export type PedidoResumen = {
  idLocal: number;
  idRocketfy: number | null;
  estadoLocal: string;
  statusIdRocketfy: number | null;
  nombreCliente: string;
  telefono: string;
  canton: string;
  provincia: string;
  total: string;
  creadoEn: string | null;
  actualizadoEn: string | null;
};

export type PedidoDetalle = {
  idLocal: number;
  idRocketfy: number | null;
  estadoLocal: string;
  statusIdRocketfy: number | null;
  mensajeError: string | null;
  nombreCliente: string;
  telefono: string;
  direccion: string;
  direccion2: string;
  canton: string;
  provincia: string;
  codigoPostal: string | null;
  total: string;
  noContraEntrega: boolean;
  observacionesTransportista: string;
  lineas: LineaPedido[];
  creadoEn: string | null;
  confirmadoEn: string | null;
  actualizadoEn: string | null;
};

export type PedidosListado = {
  items: PedidoResumen[];
  total: number;
  page: number;
  pageSize: number;
};

export type ModificarPedidoInput = Partial<{
  nombreCliente: string;
  email: string;
  telefono: string;
  direccion: string;
  direccion2: string;
  canton: string;
  provincia: string;
  codigoPostal: string;
}>;
