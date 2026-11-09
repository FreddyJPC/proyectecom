/** Espejo de backend/src/routes/anuncios/schemas.py. El dinero siempre viaja como texto con 2 decimales. */

/** Un anuncio visto (o vinculado de antemano), con lo último que dijo Meta de él y lo que ha vendido en el periodo. */
export type Anuncio = {
  idAnuncio: string;
  productoSku: string | null;
  productoNombre: string | null;
  /** El nombre que le pusiste al vincularlo (útil antes de que llegue el primer cliente). */
  nombreVinculo: string | null;
  titulo: string | null;
  texto: string | null;
  urlAnuncio: string | null;
  tipoOrigen: string | null;
  tipoMedia: string | null;
  imagenUrl: string | null;
  miniaturaUrl: string | null;
  primeraLlegada: string | null;
  ultimaLlegada: string | null;
  /** Mensajes que llegaron por este anuncio en el periodo. */
  llegadas: number;
  /** Clientes distintos que llegaron por este anuncio en el periodo. */
  conversaciones: number;
  ventas: number;
  ingresos: string;
  /** Suma de la ganancia de las ventas con costo conocido. */
  ganancia: string;
  ventasSinCosto: number;
};

export type CifrasDeOrigen = {
  conversaciones: number;
  ventas: number;
  ingresos: string;
  ganancia: string;
};

export type ResumenOrigenes = {
  anuncio: CifrasDeOrigen;
  directo: CifrasDeOrigen;
  llegadas: number;
  anunciosActivos: number;
  anunciosSinVincular: number;
};

export type VinculoAnuncio = {
  idAnuncio: string;
  productoSku: string;
  productoNombre: string;
};

export type PeriodoAnuncios = "7" | "30" | "90" | "todo";
