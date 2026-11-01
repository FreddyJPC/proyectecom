"use client";

import { PanelLeftClose, PanelLeftOpen, Plus } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { useEscaladasSinRevisar } from "@/components/escaladas-context";
import { BrandMark } from "@/components/brand-mark";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
  useSidebar,
} from "@/components/ui/sidebar";
import { NAV_GRUPOS, NAV_NUEVO_PEDIDO, SITE, esRutaActiva } from "@/config/site";

export function AppSidebar() {
  const pathname = usePathname();
  const escaladasSinRevisar = useEscaladasSinRevisar();
  const { setOpenMobile, state, toggleSidebar } = useSidebar();
  const contraido = state === "collapsed";

  // En móvil el menú es un panel que se abre encima: hay que cerrarlo al
  // navegar, si no tapa la pantalla a la que se acaba de ir.
  const alNavegar = () => setOpenMobile(false);

  return (
    <Sidebar collapsible="icon" role="navigation" aria-label="Menú principal">
      {/* Contraído, la barra mide 3 rem (48 px): con p-2 quedan 32 px de ancho
          útil, justo lo que mide un botón de ícono. Con p-3 (24 px) la marca y
          el botón se desbordaban y quedaban pegados al borde. */}
      <SidebarHeader className="gap-3 p-3 group-data-[collapsible=icon]:p-2">
        <Link
          href="/"
          onClick={alNavegar}
          aria-label={`${SITE.name}: ir al resumen`}
          className="flex items-center gap-2.5 rounded-lg p-1 outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:p-0"
        >
          <BrandMark className="size-8" />
          <div className="leading-tight group-data-[collapsible=icon]:hidden">
            <p className="text-sm font-semibold tracking-tight">{SITE.name}</p>
            <p className="text-xs text-muted-foreground">Panel operativo</p>
          </div>
        </Link>

        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              asChild
              size="lg"
              tooltip={NAV_NUEVO_PEDIDO.title}
              className="justify-center bg-primary font-medium text-primary-foreground shadow-card hover:bg-primary/90 hover:text-primary-foreground active:bg-primary/90 active:text-primary-foreground group-data-[collapsible=icon]:justify-center"
            >
              <Link href={NAV_NUEVO_PEDIDO.url} onClick={alNavegar}>
                <Plus className="size-4" />
                <span className="group-data-[collapsible=icon]:hidden">{NAV_NUEVO_PEDIDO.title}</span>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent>
        {NAV_GRUPOS.map((grupo) => (
          <SidebarGroup key={grupo.label}>
            <SidebarGroupLabel>{grupo.label}</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {grupo.items.map((item) => {
                  const mostrarContador = item.url === "/conversaciones" && escaladasSinRevisar > 0;
                  return (
                    <SidebarMenuItem key={item.url}>
                      <SidebarMenuButton asChild isActive={esRutaActiva(pathname, item.url)} tooltip={item.title}>
                        <Link href={item.url} onClick={alNavegar} aria-current={esRutaActiva(pathname, item.url) ? "page" : undefined}>
                          <item.icon />
                          <span>{item.title}</span>
                          {mostrarContador && (
                            <span
                              className="tabular ml-auto inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-status-danger px-1.5 text-xs font-semibold text-status-danger-foreground group-data-[collapsible=icon]:hidden"
                              aria-label={`${escaladasSinRevisar} escaladas sin revisar`}
                            >
                              {escaladasSinRevisar}
                            </span>
                          )}
                        </Link>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  );
                })}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        ))}
      </SidebarContent>

      {/* Contraer / expandir el menú: vive en la propia barra, abajo, donde se
          espera un control de la navegación (antes estaba en la cabecera). */}
      <SidebarFooter className="border-t border-sidebar-border group-data-[collapsible=icon]:p-2">
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              tooltip={contraido ? "Expandir menú" : "Contraer menú"}
              onClick={toggleSidebar}
              aria-expanded={!contraido}
              aria-label={contraido ? "Expandir menú" : "Contraer menú"}
              className="text-muted-foreground"
            >
              {contraido ? <PanelLeftOpen /> : <PanelLeftClose />}
              <span className="group-data-[collapsible=icon]:hidden">Contraer menú</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}
