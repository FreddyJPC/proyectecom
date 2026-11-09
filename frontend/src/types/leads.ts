/** Forma de la API de leads (backend/src/routes/leads/schemas.py). Dinero siempre como texto. */

export type Temperatura = "caliente" | "tibio" | "frio" | "perdido" | "ganado";

/** Quién puso la temperatura: el dueño a mano, una regla sobre hechos/tiempo o Victoria (IA). */
export type OrigenTemperatura = "dueno" | "regla" | "ia";

export type MotivoPerdida = "precio" | "sin_respuesta" | "compro_en_otro_lado" | "sin_cobertura" | "sin_stock" | "no_le_interesa" | "otro";

export type Lead = {
  id: number;
  contactoId: number;
  conversacionId: number;
  canal: string;
  idExterno: string;
  telefono: string | null;
  nombre: string | null;
  productoSku: string | null;
  productoNombre: string | null;
  productoVariante: string | null;
  cantidad: number | null;
  total: string | null;
  /** Dónde va el lead (recopilando datos, esperando pago, despachado…): no es la temperatura. */
  etapa: string;
  temperatura: Temperatura;
  temperaturaEtiqueta: string;
  temperaturaMotivo: string | null;
  temperaturaOrigen: OrigenTemperatura;
  temperaturaEn: string | null;
  /** Si el dueño la fijó a mano, hasta cuándo no la toca el enfriamiento automático ni Victoria. */
  temperaturaFijadaHasta: string | null;
  motivoPerdida: MotivoPerdida | null;
  motivoPerdidaEtiqueta: string | null;
  origen: string;
  idAnuncio: string | null;
  tituloAnuncio: string | null;
  creadoEn: string;
  actualizadoEn: string;
  cerradoEn: string | null;
  noContactar: boolean;
  noContactarMotivo: string | null;
  estadoConversacion: string | null;
  ultimoMensaje: { rol: string; contenido: string; creadoEn: string } | null;
  ultimoClienteEn: string | null;
  /** El último mensaje de seguimiento automático que se le envió (empujón o plantilla), si hubo. */
  ultimoSeguimiento: { tipo: TipoSeguimiento; enviadoEn: string | null } | null;
};

export type LeadsListado = {
  items: Lead[];
  total: number;
  page: number;
  pageSize: number;
};

export type PeriodoLeads = "7" | "30" | "90" | "todo";

export type ResumenLeads = {
  calientes: number;
  tibios: number;
  frios: number;
  valorEnJuego: string;
  nuevos: number;
  ganados: number;
  perdidos: number;
  ingresosGanados: string;
  /** Porcentaje con un decimal ("37.5"), o null si todavía no se cerró ningún lead en el periodo. */
  tasaDeCierre: string | null;
  noContactar: number;
  motivosDePerdida: { motivo: string; etiqueta: string; leads: number }[];
};

/** Empujón: texto libre dentro de las 24 h. Plantilla: mensaje aprobado por Meta, pasadas las 24 h. */
export type TipoSeguimiento = "empujon" | "plantilla";

/** Un mensaje que el sistema le escribió por su cuenta al cliente que dejó de contestar. */
export type Seguimiento = {
  id: number;
  tipo: TipoSeguimiento;
  /** Los `reservado` (envío a medias) llegan igual: se muestran como pendientes. */
  estado: "reservado" | "enviado" | "fallido";
  contenido: string | null;
  plantilla: string | null;
  error: string | null;
  creadoEn: string;
  enviadoEn: string | null;
};

export type CambioDeTemperatura = {
  id: number;
  de: Temperatura | null;
  a: Temperatura;
  origen: OrigenTemperatura;
  motivo: string | null;
  usuario: string | null;
  creadoEn: string;
};

export type TipoDeContacto = "prospecto" | "cliente" | "recurrente";

export type ContactoFicha = {
  id: number;
  nombre: string | null;
  telefono: string | null;
  tipo: TipoDeContacto | null;
  noContactar: boolean;
  noContactarMotivo: string | null;
  noContactarEn: string | null;
  noContactarPor: OrigenTemperatura | null;
  creadoEn: string;
  conversaciones: { id: number; canal: string; idExterno: string; estado: string; creadaEn: string }[];
  leads: {
    id: number;
    conversacionId: number;
    productoNombre: string | null;
    temperatura: Temperatura;
    etapa: string;
    total: string | null;
    origen: string;
    creadoEn: string;
    cerradoEn: string | null;
  }[];
  compras: {
    cantidad: number;
    totalGastado: string;
    ganancia: string;
    comprasSinCosto: number;
    ultimaCompra: string | null;
  };
  anuncios: {
    llegadas: number;
    primera: string | null;
    ultima: string | null;
    primerAnuncio: { idAnuncio: string; titulo: string | null } | null;
  };
};

export type LeadDetalle = {
  lead: Lead;
  historial: CambioDeTemperatura[];
  contacto: ContactoFicha | null;
  seguimientos: Seguimiento[];
};
