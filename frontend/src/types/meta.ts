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
