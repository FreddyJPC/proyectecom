/** Espejo de backend/src/routes/precios/controllers.py (ADR-017). El dinero siempre viaja como texto con 2 decimales. */

export type TipoTransferencia = "precio" | "porcentaje" | "monto";
export type TipoRegateo = "porcentaje" | "monto";

export type Escala = { cantidad: number; precioTotal: string };

/** «Precios y descuentos» de un producto. */
export type ReglasPrecio = {
  sku: string;
  nombre: string;
  /** Precio normal (contra entrega). */
  precio: string;
  costo: string | null;
  /** Menor precio por unidad que todavía deja tu margen mínimo (null si no se puede calcular). */
  precioMinimo: string | null;
  margenConfirmado: boolean;
  envioIncluido: boolean;
  maxUnidades: number;
  transferenciaTipo: TipoTransferencia | null;
  transferenciaValor: string | null;
  regateoTipo: TipoRegateo | null;
  regateoValor: string | null;
  envioGratisDesdeUnidades: number | null;
  envioGratisDesdeMonto: string | null;
  escalas: Escala[];
};

export type TransferenciaNegocio = { transferenciaTipo: Exclude<TipoTransferencia, "precio"> | null; transferenciaValor: string | null };

export type SituacionOferta = "vigente" | "programada" | "vencida" | "sin_cupo" | "pausada" | "archivada";

export type ItemOferta = {
  productoSku: string;
  productoNombre: string | null;
  cantidad: number;
  variante: string | null;
  precio: string;
  productoActivo: boolean;
};

export type Oferta = {
  id: number;
  nombre: string;
  descripcion: string | null;
  textoAnuncio: string | null;
  precio: string;
  /** Lo que costarían los productos por separado. */
  precioLista: string;
  ahorro: string;
  envioIncluido: boolean;
  desde: string | null;
  hasta: string | null;
  cupo: number | null;
  maximoPorCliente: number;
  visibilidad: "anuncio" | "publica";
  regateoTipo: TipoRegateo | null;
  regateoValor: string | null;
  transferenciaTipo: TipoTransferencia | null;
  transferenciaValor: string | null;
  bajoMargenAutorizado: boolean;
  estado: "activa" | "pausada" | "archivada";
  situacion: SituacionOferta;
  vigente: boolean;
  items: ItemOferta[];
  anuncios: string[];
  ventas: number;
  ingreso: string;
  creadaEn: string | null;
};

export type ListaOfertas = { ofertas: Oferta[] };
