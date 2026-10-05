"use client";

import { usePathname } from "next/navigation";

import { Separator } from "@/components/ui/separator";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { SITE, TITULOS_POR_RUTA } from "@/config/site";
import { UserMenu } from "@/components/user-menu";

export function SiteHeader() {
  const pathname = usePathname();
  const titulo =
    TITULOS_POR_RUTA[pathname] ?? (pathname.startsWith("/pedidos/") ? "Pedidos" : SITE.name);

  return (
    <header className="flex h-14 shrink-0 items-center gap-2 border-b px-4">
      <SidebarTrigger className="-ml-1" />
      <Separator orientation="vertical" className="mr-2 h-4" />
      <h1 className="flex-1 text-sm font-medium">{titulo}</h1>
      <UserMenu />
    </header>
  );
}
