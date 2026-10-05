import type { LucideIcon } from "lucide-react";
import { AlertTriangle, BarChart3, Boxes, LayoutDashboard, MessageCircle, Package, PlusCircle } from "lucide-react";

/** Metadata y navegación del sitio. Única fuente de verdad: cualquier
 * texto/ruta que aparezca en más de un lugar (layout, sidebar, header,
 * breadcrumbs) se define acá, no se repite. */
export const SITE = {
  name: "PROYECTECOM",
  title: "PROYECTECOM · Panel",
  description: "Panel operativo del negocio: pedidos, incidencias, stock y métricas.",
} as const;

export type NavItem = {
  title: string;
  url: string;
  icon: LucideIcon;
};

export const NAV_PRINCIPAL: NavItem[] = [
  { title: "Resumen", url: "/", icon: LayoutDashboard },
  { title: "Conversaciones", url: "/conversaciones", icon: MessageCircle },
  { title: "Pedidos", url: "/pedidos", icon: Package },
  { title: "Incidencias y Alertas", url: "/incidencias", icon: AlertTriangle },
  { title: "Catálogo y Stock", url: "/catalogo", icon: Boxes },
  { title: "Métricas", url: "/metricas", icon: BarChart3 },
];

export const NAV_NUEVO_PEDIDO: NavItem = {
  title: "Nuevo pedido",
  url: "/pedidos/nuevo",
  icon: PlusCircle,
};

/** Título de página por ruta, usado por <SiteHeader />. Se deriva de
 * NAV_PRINCIPAL/NAV_NUEVO_PEDIDO para no declarar los mismos textos dos
 * veces. */
export const TITULOS_POR_RUTA: Record<string, string> = Object.fromEntries(
  [...NAV_PRINCIPAL, NAV_NUEVO_PEDIDO].map((item) => [item.url, item.title]),
);
