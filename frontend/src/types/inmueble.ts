/** Espejo de backend/src/routes/inmuebles/schemas.py (módulo «Inmuebles», migración 037). El dinero y las medidas viajan
 * como string (nunca float). */

export type TipoInmueble = "casa" | "departamento" | "terreno" | "local" | "oficina" | "bodega" | "otro";
export type OperacionInmueble = "venta" | "alquiler";
export type EstadoInmueble = "borrador" | "activo" | "pausado" | "vendido" | "archivado";
export type UsoInmueble = "residencial" | "comercial" | "mixto";

export type InmuebleResumen = {
  id: number;
  codigo: string;
  titulo: string;
  tipo: TipoInmueble;
  operacion: OperacionInmueble;
  estado: EstadoInmueble;
  precio: string | null;
  mostrarPrecio: boolean;
  precioNegociable: boolean | null;
  ciudad: string | null;
  sector: string | null;
  direccion: string | null;
  habitaciones: number | null;
  banos: string | null;
  terrenoM2: string | null;
  construccionM2: string | null;
  actualizadoEn: string;
  portadaUrl: string | null;
  portadaPath: string | null;
  visitasPorConfirmar: number;
  visitasProximas: number;
};

export type MaterialInmueble = { id: number; url: string; storagePath: string; orden: number; tipo: "imagen" | "video" };
export type AnuncioInmueble = { idAnuncio: string; nombre: string | null; creadoEn: string };

export type InmuebleDetalle = Omit<InmuebleResumen, "portadaUrl" | "portadaPath" | "visitasPorConfirmar" | "visitasProximas"> & {
  referenciaLlegada: string | null;
  latitud: string | null;
  longitud: string | null;
  frenteM: string | null;
  fondoM: string | null;
  pisos: number | null;
  parqueaderos: number | null;
  uso: UsoInmueble | null;
  descripcion: string | null;
  caracteristicas: string | null;
  servicios: string | null;
  documentacion: string | null;
  preguntasFrecuentes: string | null;
  temasNoResponder: string | null;
  horariosVisita: string | null;
  encargadoVisitas: string | null;
  notasInternas: string | null;
  creadoEn: string;
  material: MaterialInmueble[];
  anuncios: AnuncioInmueble[];
  /** Lo que conviene completar para que el asistente responda bien (no impide publicar). */
  faltantes: string[];
  /** Carpeta del bucket «productos» donde se suben sus fotos y videos. */
  carpeta: string;
};

export type EstadoVisita = "solicitada" | "confirmada" | "realizada" | "no_asistio" | "cancelada";

export type Visita = {
  id: number;
  inmuebleId: number;
  inmuebleTitulo: string;
  inmuebleCodigo: string;
  conversacionId: number | null;
  nombreCliente: string | null;
  telefono: string | null;
  estado: EstadoVisita;
  /** Lo que pidió el cliente, en sus palabras. */
  preferenciaCliente: string | null;
  personas: number | null;
  /** La fecha y hora que confirmó el dueño (UTC; se muestra en hora de Ecuador). */
  fechaHora: string | null;
  encargado: string | null;
  notas: string | null;
  motivoCancelacion: string | null;
  creadaPor: "asistente" | "dueno";
  creadoEn: string;
  confirmadaEn: string | null;
  avisadoClienteEn: string | null;
  /** Solo dentro de las 24 h desde el último mensaje del cliente se le puede escribir por WhatsApp. */
  ventanaAbierta: boolean;
  ventanaExpiraEn: string | null;
};

export type ResumenVisitas = { porConfirmar: number; proximas: number; hoy: number };

export type NumeroWhatsapp = {
  phoneNumberId: string;
  nombre: string;
  telefonoVisible: string | null;
  asistente: "ventas" | "inmuebles";
  activo: boolean;
  esPrincipal?: boolean;
};

export const NOMBRE_TIPO_INMUEBLE: Record<TipoInmueble, string> = {
  casa: "Casa",
  departamento: "Departamento",
  terreno: "Terreno",
  local: "Local comercial",
  oficina: "Oficina",
  bodega: "Bodega",
  otro: "Otro",
};
