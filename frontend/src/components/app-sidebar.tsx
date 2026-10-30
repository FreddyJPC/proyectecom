"use client";

import { Plus } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { useEscaladasSinRevisar } from "@/components/escaladas-context";
import { BrandMark } from "@/components/brand-mark";
import {
  Sidebar,
  SidebarContent,
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
  const { setOpenMobile } = useSidebar();

  // En móvil el menú es un panel que se abre encima: hay que cerrarlo al
  // navegar, si no tapa la pantalla a la que se acaba de ir.
  const alNavegar = () => setOpenMobile(false);

  return (
    <Sidebar collapsible="icon" role="navigation" aria-label="Menú principal">
      <SidebarHeader className="gap-3 p-3">
        <Link href="/" onClick={alNavegar} className="flex items-center gap-2.5 rounded-lg p-1 outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring">
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
                <span>{NAV_NUEVO_PEDIDO.title}</span>
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
      <SidebarRail />
    </Sidebar>
  );
}
