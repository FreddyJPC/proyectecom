import { formatPhone } from "@/lib/format";

/**
 * Canales de mensajería (ADR-014): POR DÓNDE habla un cliente con el negocio. No confundir con el ORIGEN (cómo llegó:
 * anuncio o directo). Espejo de backend/src/integrations/canales.py.
 */
export const CANALES = {
  whatsapp: "WhatsApp",
  instagram: "Instagram",
  messenger: "Messenger",
} as const;

export type Canal = keyof typeof CANALES;

export function nombreCanal(canal: string | null | undefined): string {
  return CANALES[(canal ?? "whatsapp") as Canal] ?? String(canal);
}

/** Cómo mostrar a un cliente: lo que dio al comprar, el nombre de su perfil, su teléfono o, si no hay nada más, su
 * identificador en el canal (un cliente de Instagram no tiene teléfono hasta que lo da). */
export function nombreDeCliente(c: {
  nombreCliente?: string | null;
  nombre?: string | null;
  telefono?: string | null;
  idExterno?: string | null;
}): string {
  return c.nombreCliente || c.nombre || (c.telefono ? formatPhone(c.telefono) : null) || c.idExterno || "Cliente";
}

/** Línea corta que identifica al cliente en su canal: «WhatsApp · +593 98 765 4321» o «Instagram · 17841…». */
export function lineaDeCanal(c: { canal: string; telefono?: string | null; idExterno?: string | null }): string {
  const dato = c.telefono ? formatPhone(c.telefono) : c.idExterno;
  return dato ? `${nombreCanal(c.canal)} · ${dato}` : nombreCanal(c.canal);
}
