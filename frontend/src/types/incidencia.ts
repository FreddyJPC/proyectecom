/** Espejo intencional de backend/src/routes/incidencias/schemas.py */

export type EventoWebhook = {
  id: number;
  idRocketfy: number;
  idLocal: number | null;
  statusId: number;
  statusName: string | null;
  details: string | null;
  trackingCode: string | null;
  trackingUrl: string | null;
  shippingCompany: string | null;
  eventDate: string | null;
  recibidoEn: string | null;
};

export type AlertaStock = {
  id: number;
  sku: string;
  tipo: string;
  detalle: Record<string, string | number>;
  creadoEn: string | null;
};

export type Paginado<T> = {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
};
