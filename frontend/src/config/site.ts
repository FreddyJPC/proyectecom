import type { LucideIcon } from "lucide-react";
import { AlertTriangle, BarChart3, Boxes, LayoutDashboard, MessageCircle, Package, PlusCircle } from "lucide-react";

/** Metadata y navegación del sitio. Única fuente de verdad: cualquier
 * texto/ruta que aparezca en más de un lugar (layout, sidebar, header,
 * barra inferior, migas de pan) se define acá, no se repite. */
export const SITE = {
  name: "PROYECTECOM",
  /** Nombre corto para espacios chicos (logo, barra móvil). */
  short: "P",
  title: "PROYECTECOM · Panel",
  description: "Panel operativo del negocio: pedidos, incidencias, stock y métricas.",
} as const;

export type NavItem = {
  title: string;
  /** Etiqueta corta para la barra inferior del móvil (cabe bajo un ícono). */
  short: string;
  url: string;
  icon: LucideIcon;
};

export const NAV_GRUPOS: { label: string; items: NavItem[] }[] = [
  {
    label: "Operación",
    items: [
      { title: "Resumen", short: "Resumen", url: "/", icon: LayoutDashboard },
      { title: "Conversaciones", short: "Chats", url: "/conversaciones", icon: MessageCircle },
      { title: "Pedidos", short: "Pedidos", url: "/pedidos", icon: Package },
    ],
  },
  {
    label: "Control",
    items: [
      { title: "Incidencias y Alertas", short: "Alertas", url: "/incidencias", icon: AlertTriangle },
      { title: "Catálogo y Stock", short: "Catálogo", url: "/catalogo", icon: Boxes },
      { title: "Métricas", short: "Métricas", url: "/metricas", icon: BarChart3 },
    ],
  },
];

export const NAV_PRINCIPAL: NavItem[] = NAV_GRUPOS.flatMap((g) => g.items);

export const NAV_NUEVO_PEDIDO: NavItem = {
  title: "Nuevo pedido",
  short: "Nuevo",
  url: "/pedidos/nuevo",
  icon: PlusCircle,
};

/** ¿Esta ruta del menú es la activa? "/" solo coincide exacto; el resto
 * también cuando se está en una subpágina (p. ej. /pedidos/1040 -> Pedidos). */
export function esRutaActiva(pathname: string, url: string): boolean {
  if (url === "/") return pathname === "/";
  if (url === "/pedidos") return pathname === "/pedidos" || (pathname.startsWith("/pedidos/") && pathname !== "/pedidos/nuevo");
  return pathname === url || pathname.startsWith(url + "/");
}

export type Miga = { label: string; href?: string };

/** Migas de pan para la cabecera, derivadas de la ruta. */
export function migasDe(pathname: string): Miga[] {
  if (pathname === "/") return [{ label: "Resumen" }];

  const seccion = NAV_PRINCIPAL.find((i) => i.url !== "/" && (pathname === i.url || pathname.startsWith(i.url + "/")));
  if (!seccion) return [{ label: SITE.name }];

  const resto = pathname.slice(seccion.url.length).replace(/^\//, "");
  if (!resto) return [{ label: seccion.title }];

  if (pathname === NAV_NUEVO_PEDIDO.url) {
    return [{ label: seccion.title, href: seccion.url }, { label: "Nuevo pedido" }];
  }
  if (seccion.url === "/pedidos") return [{ label: seccion.title, href: seccion.url }, { label: `Pedido #${resto}` }];
  if (seccion.url === "/conversaciones") return [{ label: seccion.title, href: seccion.url }, { label: "Conversación" }];
  return [{ label: seccion.title, href: seccion.url }, { label: resto }];
}
