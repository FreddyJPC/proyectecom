/** Parámetros del sistema controlados desde la app (backend: src/config/parametros). */

export type TipoParametro = "entero" | "booleano" | "texto" | "opcion";
export type ValorParametro = number | boolean | string;

/** De dónde sale el valor que rige hoy: lo guardado en la app, la variable del
 * servidor (Railway) o el valor original que trae el código. */
export type OrigenParametro = "app" | "servidor" | "original";

export type OpcionParametro = {
  valor: string;
  etiqueta: string;
  nota: string;
};

export type Parametro = {
  clave: string;
  nombre: string;
  paraQueSirve: string;
  tipo: TipoParametro;
  valor: ValorParametro;
  origen: OrigenParametro;
  /** Lo que valdría si no hubiera nada guardado en la app. */
  valorOriginal: ValorParametro;
  valorApp: ValorParametro | null;
  variableServidor: string | null;
  valorServidor: ValorParametro | null;
  minimo: number | null;
  maximo: number | null;
  largoMaximo: number | null;
  unidad: string;
  /** Cuándo se nota un cambio (texto para mostrar). */
  aplica: string;
  /** Pide confirmación al guardar. */
  sensible: boolean;
  aviso: string;
  opciones: OpcionParametro[];
  /** Problemas con un valor guardado o con la variable del servidor (se ignoran). */
  avisos: string[];
  actualizadoPor: string | null;
  actualizadoEn: string | null;
};

export type GrupoParametros = {
  clave: string;
  nombre: string;
  descripcion: string;
  parametros: Parametro[];
};

export type ParametrosRespuesta = {
  grupos: GrupoParametros[];
};

export type CambioParametro = {
  clave: string;
  nombre: string;
  /** Texto tal como se guardó; vacío = antes no había nada guardado. */
  valorAnterior: string | null;
  /** Vacío = se restauró el valor original. */
  valorNuevo: string | null;
  usuario: string | null;
  creadoEn: string;
};
