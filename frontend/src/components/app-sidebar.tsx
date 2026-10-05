"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
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
} from "@/components/ui/sidebar";
import { NAV_NUEVO_PEDIDO, NAV_PRINCIPAL, SITE } from "@/config/site";
import { apiFetch } from "@/lib/api";
import type { ConversacionesListado } from "@/types/conversacion";

// Poll simple (no tiempo real, a propósito -- ver decisiones de alcance
// del módulo de Conversaciones): suficiente para que el contador del
// sidebar no quede desactualizado por mucho tiempo sin agregar websockets.
const INTERVALO_POLL_MS = 30_000;

export function AppSidebar() {
  const pathname = usePathname();
  const [escaladasSinRevisar, setEscaladasSinRevisar] = useState(0);

  useEffect(() => {
    let cancelado = false;

    function consultar() {
      apiFetch<ConversacionesListado>("/conversaciones?estado=escalada&pageSize=1")
        .then((data) => {
          if (!cancelado) setEscaladasSinRevisar(data.totalesPorFiltroRapido.escaladasSinRevisar);
        })
        .catch(() => {
          // Best-effort: si falla, el sidebar simplemente no muestra el
          // contador -- no es motivo para un toast de error en cada carga
          // de página.
        });
    }

    consultar();
    const intervalo = setInterval(consultar, INTERVALO_POLL_MS);
    return () => {
      cancelado = true;
      clearInterval(intervalo);
    };
  }, []);

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <div className="flex items-center gap-2 px-2 py-1.5">
          <div className="flex size-7 items-center justify-center rounded-md bg-primary text-primary-foreground text-sm font-semibold">
            {SITE.name.charAt(0)}
          </div>
          <span className="text-sm font-semibold tracking-tight group-data-[collapsible=icon]:hidden">
            {SITE.name}
          </span>
        </div>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Operación</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {NAV_PRINCIPAL.map((item) => (
                <SidebarMenuItem key={item.url}>
                  <SidebarMenuButton asChild isActive={pathname === item.url} tooltip={item.title}>
                    <Link href={item.url}>
                      <item.icon />
                      <span>{item.title}</span>
                      {item.url === "/conversaciones" && escaladasSinRevisar > 0 && (
                        <Badge
                          variant="outline"
                          className="ml-auto h-5 min-w-5 justify-center border-transparent bg-status-danger px-1 text-status-danger-foreground group-data-[collapsible=icon]:hidden"
                        >
                          {escaladasSinRevisar}
                        </Badge>
                      )}
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              asChild
              isActive={pathname === NAV_NUEVO_PEDIDO.url}
              tooltip={NAV_NUEVO_PEDIDO.title}
            >
              <Link href={NAV_NUEVO_PEDIDO.url}>
                <NAV_NUEVO_PEDIDO.icon />
                <span>{NAV_NUEVO_PEDIDO.title}</span>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  );
}
