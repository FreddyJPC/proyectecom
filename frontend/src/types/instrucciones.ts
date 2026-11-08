/** Instrucciones de Victoria editables desde la app (backend: src/routes/instrucciones). */

export type SeccionInstrucciones = {
  id: string;
  nombre: string;
  ayuda: string;
  /** Falso = atada al código: solo se lee. */
  editable: boolean;
  /** Largo máximo (solo las editables). */
  maximo: number;
  /** El texto del programa (lo que rige si no hay versión publicada). */
  original: string;
  /** El texto que rige HOY con los clientes. */
  vigente: string;
  /** El texto del borrador, o null si no hay borrador o la sección no se edita. */
  borrador: string | null;
};

export type EstadoVersion = "borrador" | "publicada" | "archivada";

export type VersionInstrucciones = {
  id: number;
  estado: EstadoVersion;
  nota: string | null;
  creadoPor: string | null;
  creadoEn: string;
  publicadaEn: string | null;
};

export type Instrucciones = {
  secciones: SeccionInstrucciones[];
  /** «original» = el texto del programa; «publicada» = una versión hecha desde la app. */
  usando: "original" | "publicada";
  publicada: VersionInstrucciones | null;
  borrador: VersionInstrucciones | null;
  /** Versiones publicadas alguna vez (la actual y las archivadas), de la más nueva a la más vieja. */
  versiones: VersionInstrucciones[];
  maximoTotal: number;
  /** Largo de lo que no se edita: sumado a lo escrito en las secciones da el largo del prompt. */
  caracteresFijos: number;
};
