/** Espejo de backend/src/routes/productos_bot/schemas.py. El dinero viaja
 * siempre como string (nunca float). */

export type EstadoProductoBot = "borrador" | "listo" | "activo" | "pausado" | "agotado" | "archivado";

export type ProductoBotResumen = {
  sku: string;
  nombre: string;
  estado: EstadoProductoBot;
  precio: string;
  costoRocketfy: string | null;
  stockUltimo: number | null;
  maxUnidadesPorPedido: number;
  imagenUrl: string | null;
  publicadoEn: string | null;
  actualizadoEn: string | null;
};

export type Verificacion = {
  /** Impiden publicar o reanudar. */
  bloqueos: string[];
  /** Se puede publicar, pero conviene saberlo. */
  avisos: string[];
};

export type EntradaHistorial = {
  accion: string;
  usuario: string | null;
  /** Para ediciones: { campo: [antes, después] }. */
  cambios: Record<string, unknown> | null;
  creadoEn: string | null;
};

export type ProductoBotDetalle = {
  sku: string;
  nombre: string;
  estado: EstadoProductoBot;
  precio: string;
  costoRocketfy: string | null;
  precioSugeridoRocketfy: string | null;
  stockUltimo: number | null;
  stockActualizadoEn: string | null;
  pesoKg: string | null;
  imagenUrl: string | null;
  rocketfyProductId: number | null;
  descripcion: string;
  variantes: string | null;
  tiempoEntrega: string;
  metodosPago: string[];
  preguntasFrecuentes: string | null;
  temasNoResponder: string | null;
  maxUnidadesPorPedido: number;
  notasInternas: string | null;
  /** Precio de la competencia que la persona anota a mano (opcional). */
  precioCompetencia: string | null;
  publicadoEn: string | null;
  publicadoPor: string | null;
  creadoEn: string | null;
  actualizadoEn: string | null;
  verificacion: Verificacion;
  historial: EntradaHistorial[];
};

/** Cuerpo del PATCH: solo viajan los campos que cambiaron. */
export type EditarProductoBotInput = Partial<{
  nombre: string;
  descripcion: string;
  precio: string;
  variantes: string | null;
  tiempoEntrega: string;
  metodosPago: string[];
  preguntasFrecuentes: string | null;
  temasNoResponder: string | null;
  maxUnidadesPorPedido: number;
  notasInternas: string | null;
  precioCompetencia: string | null;
}>;

/** Acciones que cambian el estado (POST /productos-bot/<sku>/<accion>). */
export type AccionProductoBot = "publicar" | "reanudar" | "pausar" | "archivar" | "restaurar";

/** Métodos de pago que Victoria sabe manejar (espejo de
 * `METODOS_PAGO_VALIDOS` en el backend). */
export const METODOS_PAGO: { valor: string; label: string; ayuda: string }[] = [
  { valor: "contraentrega", label: "Contraentrega", ayuda: "El cliente paga al recibir." },
  { valor: "transferencia", label: "Transferencia", ayuda: "Pago anticipado: lo confirmas tú a mano." },
];

// ---------------------------------------------------------------------------
// Calculadora de precio y ajustes del negocio (Fase C). Espejo de
// backend/src/routes/productos_bot/schemas.py y backend/src/routes/ajustes/schemas.py.
// Dinero siempre como string con dos decimales; márgenes como string.
// ---------------------------------------------------------------------------

export type NivelPrecio = {
  clave: "minimo" | "recomendado" | "premium";
  nombre: string;
  precio: string;
  /** Ganancia por unidad ya descontados costo, envío estimado y otros costos. */
  ganancia: string;
  margenPct: string;
};

export type EvaluacionPrecio = {
  precio: string;
  ganancia: string;
  margenPct: string;
  /** Por debajo del mínimo para publicar: el backend no dejará publicarlo así. */
  bajoPiso: boolean;
  bajoMargenMinimo: boolean;
};

export type RecomendacionPrecio = {
  /** Falso mientras la persona no haya guardado sus ajustes: se usan valores de partida. */
  ajustesConfirmados: boolean;
  costo: string | null;
  /** Precio mínimo con el que se puede publicar. */
  piso: string;
  envioEstimado: string;
  otrosCostosFijos: string;
  otrosCostosPct: string;
  margenMinimoPct: string;
  margenObjetivoPct: string;
  precioSugerido: string | null;
  precioCompetencia: string | null;
  niveles: NivelPrecio[];
  evaluacion: EvaluacionPrecio | null;
  avisos: string[];
};

export type CalibracionEnvio = {
  observaciones: number;
  minimo: string;
  mediana: string;
  maximo: string;
};

export type Redondeo = "terminado_99" | "ninguno";

export type AjustesNegocio = {
  margenMinimoPct: string;
  margenObjetivoPct: string;
  envioEstimado: string;
  otrosCostosFijos: string;
  otrosCostosPct: string;
  redondeo: Redondeo;
  /** Borradores de IA que se pueden pedir por día (cada uno tiene costo). */
  topeRedaccionesDia: number;
  confirmado: boolean;
  actualizadoPor: string | null;
  actualizadoEn: string | null;
  calibracionEnvio: CalibracionEnvio | null;
};

/** Cuerpo del PUT /ajustes/negocio: los seis ajustes de precios completos y el tope de IA. */
export type GuardarAjustesInput = Pick<
  AjustesNegocio,
  "margenMinimoPct" | "margenObjetivoPct" | "envioEstimado" | "otrosCostosFijos" | "otrosCostosPct" | "redondeo" | "topeRedaccionesDia"
>;

// ---------------------------------------------------------------------------
// Redactar con IA (Fase D). Espejo de backend/src/routes/productos_bot/schemas.py.
// El borrador NO está guardado en ninguna parte: pasa a la ficha solo cuando la
// persona lo acepta, y se guarda cuando pulsa «Guardar cambios».
// ---------------------------------------------------------------------------

/** Los campos de la ficha que la IA puede redactar (nombres como en la API). */
export type CampoRedactable = "nombre" | "descripcion" | "variantes" | "preguntasFrecuentes" | "temasNoResponder";

export const CAMPOS_REDACTABLES: CampoRedactable[] = ["nombre", "descripcion", "variantes", "preguntasFrecuentes", "temasNoResponder"];

/** De dónde sale un texto: Rocketfy, las notas de la persona, ambos, o lo añadió la IA por su cuenta. */
export type FuenteContenido = "rocketfy" | "notas" | "mixto" | "ia";

export type AlertaContenido = {
  /** `null` = alerta general, de todo el borrador. */
  campo: CampoRedactable | null;
  texto: string;
  /** "ia": la escribió el modelo; "verificacion": la detectó el código al revisar el texto. */
  origen: "ia" | "verificacion";
};

export type UsoIA = {
  tope: number;
  usadas: number;
  restantes: number;
};

export type BorradorContenido = {
  /** Solo vienen los campos que se pidieron. */
  campos: Partial<Record<CampoRedactable, string>>;
  fuentes: Partial<Record<CampoRedactable, FuenteContenido>>;
  alertas: AlertaContenido[];
  uso: UsoIA;
};

export type NotasParaIA = {
  dirigidoA: string;
  destacar: string;
  evitar: string;
  otrosDatos: string;
};

export type GenerarContenidoInput = {
  notas: NotasParaIA;
  productoDeSalud: boolean;
  /** Si no viene, se redactan todos. Un solo campo = «Regenerar». */
  campos?: CampoRedactable[];
};

