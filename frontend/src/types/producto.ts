/** GET /productos proxya la respuesta cruda de Rocketfy (no pasa por un
 * schema propio -- ver backend/src/routes/productos/controllers.py). Solo
 * se tipan los campos que la UI usa. */
export type Producto = {
  sku: string;
  name: string;
  price: string;
  stock: number;
};

export type CatalogoRocketfy = {
  data: Producto[];
  pagination: {
    current_page: number;
    last_page: number;
    per_page: number;
    total: number;
  };
};

/** Espejo de backend/src/routes/productos/schemas.py::SkuMonitoreadoResponseSchema */
export type SkuMonitoreado = {
  sku: string;
  umbralStockMinimo: number;
  activo: boolean;
  ultimoStock: number | null;
  ultimoPrecio: string | null;
  ultimoSnapshotEn: string | null;
};
