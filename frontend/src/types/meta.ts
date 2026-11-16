/** Estado de la conexión con Meta (`GET /meta/estado`, ADR-016). El token nunca viaja: solo si está configurado. */
export type EstadoEventoMeta = "pendiente" | "enviando" | "enviado" | "fallido" | "dudoso" | "descartado";

export type EventoMeta = {
  id: number;
  ventaId: number;
  estado: EstadoEventoMeta;
  motivo: string | null;
  /** Dinero siempre como texto. */
  valor: string;
  moneda: string;
  intentos: number;
  creadoEn: string | null;
  enviadoEn: string | null;
};

export type EstadoMeta = {
  tokenConfigurado: boolean;
  cuentaWhatsappConfigurada: boolean;
  datasetId: string | null;
  /** Token, cuenta de WhatsApp y dataset: lo necesario para poder avisar ventas. */
  listo: boolean;
  /** El interruptor «Avisar a Meta cuando vendo por un anuncio» (Parámetros). */
  avisosActivos: boolean;
  eventos: Record<EstadoEventoMeta, number>;
  ultimosEventos: EventoMeta[];
};

/** Tablero de anuncios (GET /meta/anuncios, ADR-017). */
export type AnuncioMeta = {
  idAnuncio: string;
  nombre: string | null;
  estado: string | null;
  estadoEfectivo: string | null;
  campana: string | null;
  conjunto: string | null;
  presupuestoDiario: string | null;
  titulo: string | null;
  miniaturaUrl: string | null;
  productoSku: string | null;
  productoNombre: string | null;
  ofertaId: number | null;
  ofertaNombre: string | null;
  gasto: string;
  /** Conversaciones iniciadas según Meta. */
  conversacionesMeta: number;
  /** Clientes que llegaron por este anuncio según nuestra base. */
  conversaciones: number;
  impresiones: number;
  clics: number;
  ventas: number;
  entregadas: number;
  devueltas: number;
  ingreso: string;
  descuentos: string;
  costoPorConversacion: string | null;
  costoPorVenta: string | null;
  /** Ganancia de las ventas menos el gasto (null si alguna venta no tiene costo). */
  gananciaNeta: string | null;
  roas: string | null;
};

export type AlertaAnuncio = { id: number; regla: string; idAnuncio: string | null; mensaje: string; creadaEn: string };
export type AccionAnuncio = {
  id: number;
  idAnuncio: string;
  regla: string | null;
  motivo: string;
  resultado: "hecho" | "fallido" | "dudoso";
  detalle: string | null;
  creadaPor: string | null;
  creadaEn: string;
};

export type TableroAnuncios = {
  dias: number;
  lecturaActiva: boolean;
  ultimaLectura: string | null;
  totales: { gasto: string; ingreso: string; ventas: number; conversacionesMeta: number; costoPorVenta: string | null; gananciaNeta: string | null };
  anuncios: AnuncioMeta[];
  alertas: AlertaAnuncio[];
  acciones: AccionAnuncio[];
};

export type CuentaPublicitaria = { cuentaPublicitaria: string | null; lecturaActiva?: boolean };
