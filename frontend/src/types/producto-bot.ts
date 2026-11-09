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
  /** Pedidos creados en Rocketfy con este producto en los últimos 30 días. */
  pedidos30d: number;
  /** Con el precio y el costo de hoy, el margen está bajo tu mínimo (solo con ajustes confirmados). */
  margenEnRiesgo: boolean;
  /** De dónde viene: "rocketfy" (el pedido se crea solo) o "propio" (lo gestionas tú). */
  proveedor: string;
  proveedorNombre: string;
  categoria: string | null;
  /** Solo productos propios: false = siempre disponible, sin llevar la cuenta de unidades. */
  controlaStock: boolean;
  /** true = el precio ya trae el envío; false = se cobra aparte según las opciones de entrega. */
  envioIncluido: boolean;
};

/** Una opción de entrega de un producto (envío o retiro). Dinero como string. */
export type OpcionEntrega = {
  id: number;
  nombre: string;
  tipo: "envio" | "retiro";
  /** Lo que paga el cliente por esta opción. */
  costoCliente: string;
  /** Lo que le cuesta al negocio (opcional). */
  costoNegocio: string | null;
  cantones: string[];
  provincias: string[];
  /** Aplica a todo destino que no cubra otro envío con cantones o provincias. */
  restoDelPais: boolean;
  direccionRetiro: string | null;
  tiempoEntrega: string | null;
  activo: boolean;
};

/** Lo que se envía al guardar las opciones (el servidor asigna los `id`). */
export type OpcionEntregaInput = Omit<OpcionEntrega, "id">;

/** Una foto de la galería del producto (guardada en el bucket «productos»). */
export type ImagenProducto = {
  id: number;
  url: string;
  /** Ruta dentro del bucket: `<sku>/<archivo>.jpg`. */
  storagePath: string;
  orden: number;
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
  proveedor: string;
  proveedorNombre: string;
  categoriaId: number | null;
  categoria: string | null;
  /** Lo que te cuesta una unidad (solo productos propios). */
  costoPropio: string | null;
  controlaStock: boolean;
  envioIncluido: boolean;
  /** Lo que cuesta el flete de ESTE producto; vacío = se usa el envío estimado general. */
  costoFleteEstimado: string | null;
  entregas: OpcionEntrega[];
  imagenes: ImagenProducto[];
  /** Carpeta de las fotos de este producto dentro del bucket (`p<id>`): la app sube ahí. */
  carpetaFotos: string;
};

export const esPropio = (p: { proveedor: string }) => p.proveedor === "propio";

/** Cuerpo del POST /productos-bot/propios: todo lo necesario para publicar un producto propio. */
export type CrearProductoPropioInput = {
  nombre: string;
  descripcion: string;
  precio: string;
  costoPropio: string | null;
  controlaStock: boolean;
  stock: number | null;
  categoriaId: number | null;
  variantes: string | null;
  tiempoEntrega: string;
  metodosPago: string[];
  preguntasFrecuentes: string | null;
  temasNoResponder: string | null;
  maxUnidadesPorPedido: number;
  envioIncluido: boolean;
  costoFleteEstimado: string | null;
  entregas: OpcionEntregaInput[];
};

export type Categoria = { id: number; nombre: string; activo: boolean; productos: number };

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
  categoriaId: number | null;
  envioIncluido: boolean;
  costoFleteEstimado: string | null;
  costoPropio: string | null;
  controlaStock: boolean;
  stock: number;
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
  /** Mensajes de prueba con Victoria que se pueden enviar por día (cada uno llama a la IA). */
  topePruebasDia: number;
  confirmado: boolean;
  actualizadoPor: string | null;
  actualizadoEn: string | null;
  calibracionEnvio: CalibracionEnvio | null;
};

/** Cuerpo del PUT /ajustes/negocio: los seis ajustes de precios completos y los topes de IA. */
export type GuardarAjustesInput = Pick<
  AjustesNegocio,
  | "margenMinimoPct"
  | "margenObjetivoPct"
  | "envioEstimado"
  | "otrosCostosFijos"
  | "otrosCostosPct"
  | "redondeo"
  | "topeRedaccionesDia"
  | "topePruebasDia"
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

/** El uso de «Probar con Victoria»: además del tope diario, cuántos mensajes admite
 * cada prueba (parámetro «Mensajes por prueba»). */
export type UsoPruebas = UsoIA & {
  maxMensajes: number;
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

// ---------------------------------------------------------------------------
// Probar con Victoria (Fase E). Espejo de backend/src/routes/productos_bot/schemas.py.
// La prueba NO se guarda en el servidor: la app lleva la conversación y la venta
// en curso y las reenvía en cada mensaje. Nada sale a Rocketfy, WhatsApp ni Telegram.
// ---------------------------------------------------------------------------

export type MensajePrueba = {
  rol: "cliente" | "bot";
  contenido: string;
};

/** La venta en curso (lo que Victoria va anotando). */
export type EstadoPrueba = {
  nombreCliente: string | null;
  direccion: string | null;
  canton: string | null;
  provincia: string | null;
  productoSku: string | null;
  productoNombre: string | null;
  productoVariante: string | null;
  cantidad: number;
  /** Lo calcula el sistema (precio × cantidad + envío); dinero como string. */
  total: string | null;
  /** Solo los productos (sin el envío). */
  subtotal: string | null;
  costoEnvio: string;
  entregaOpcionId: number | null;
  entregaNombre: string | null;
  entregaTipo: string | null;
  metodoPago: "contraentrega" | "transferencia" | null;
  estado: "recopilando_datos" | "esperando_pago" | "despachado" | "por_gestionar";
  idPedidoLocal: number | null;
  idPedidoRocketfy: number | null;
};

export type LlamadaHerramienta = {
  nombre: string;
  entrada: Record<string, unknown>;
  /** Lo que el sistema le respondió a Victoria. */
  resultado: string;
};

/** Lo que SE HABRÍA enviado a Rocketfy (con los nombres de campo de su API). No se envió nada. */
export type PedidoSimulado = {
  payload: Record<string, unknown>;
  confirmado: boolean;
};

export type AvisoSimulado = {
  canal: string;
  texto: string;
};

/** La foto que Victoria habría enviado por WhatsApp (no se envió nada). */
export type FotoSimulada = {
  /** Cómo queda en la conversación («📷 Foto de … (SKU)»): se reenvía en el historial para no repetirla. */
  mensaje: string;
  url: string;
  descripcion: string;
};

/** La venta de un producto PROPIO que se habría guardado al cerrarla (no se guardó nada). */
export type VentaManualSimulada = {
  producto: string;
  variante: string | null;
  cantidad: number;
  subtotal: string;
  costoEnvioCliente: string;
  total: string;
  costoProductos: string | null;
  costoEnvioNegocio: string | null;
  ganancia: string | null;
  entrega: string | null;
  metodoPago: string | null;
  /** Cómo llegó el cliente: «anuncio» o «directo». */
  origen: string;
};

export type SolicitudSimulada = { tipo: string; etiqueta: string; detalle: string };

export type TurnoSimulado = {
  respuesta: string;
  herramientas: LlamadaHerramienta[];
  estado: EstadoPrueba;
  escalada: boolean;
  pedido: PedidoSimulado | null;
  avisos: AvisoSimulado[];
  uso: UsoPruebas;
  fotos: FotoSimulada[];
  ventaManual: VentaManualSimulada | null;
  solicitudes: SolicitudSimulada[];
};

export type ProbarInput = {
  mensaje: string;
  historial: MensajePrueba[];
  estado: EstadoPrueba | null;
  desdeAnuncio: boolean;
  escalada: boolean;
  /** Probar con el borrador de las instrucciones de Victoria en vez de con las que rigen hoy. */
  usarBorrador?: boolean;
};
