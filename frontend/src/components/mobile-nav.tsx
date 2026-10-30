"use client";

import { Menu } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { useEscaladasSinRevisar } from "@/components/escaladas-context";
import { useSidebar } from "@/components/ui/sidebar";
import { NAV_GRUPOS, esRutaActiva } from "@/config/site";
import { cn } from "@/lib/utils";

// Las 4 secciones que se usan todos los días van a un toque del pulgar; el
// resto (Catálogo, Métricas, Nuevo pedido) vive en "Más", que abre el menú.
const URLS_PRINCIPALES = ["/", "/conversaciones", "/pedidos", "/incidencias"];

/** Barra de navegación inferior, solo en móvil. En un celular el menú lateral
 * queda lejos del pulgar y oculto: esta barra deja lo esencial siempre a la
 * vista y respeta el área segura de los iPhone con "notch". */
export function MobileNav() {
  const pathname = usePathname();
  const escaladas = useEscaladasSinRevisar();
  const { setOpenMobile } = useSidebar();

  const items = NAV_GRUPOS.flatMap((g) => g.items).filter((i) => URLS_PRINCIPALES.includes(i.url));

  return (
    <nav
      aria-label="Navegación principal"
      className="pb-safe fixed inset-x-0 bottom-0 z-40 border-t bg-card/95 backdrop-blur supports-[backdrop-filter]:bg-card/80 md:hidden"
    >
      <ul className="mx-auto grid max-w-lg grid-cols-5">
        {items.map((item) => {
          const activo = esRutaActiva(pathname, item.url);
          const contador = item.url === "/conversaciones" ? escaladas : 0;
          return (
            <li key={item.url}>
              <Link
                href={item.url}
                aria-current={activo ? "page" : undefined}
                className={cn(
                  "relative flex h-16 flex-col items-center justify-center gap-1 text-[0.7rem] font-medium transition-colors outline-none focus-visible:bg-muted",
                  activo ? "text-primary" : "text-muted-foreground active:bg-muted",
                )}
              >
                <span className="relative">
                  <item.icon className={cn("size-[1.4rem]", activo && "stroke-[2.3]")} />
                  {contador > 0 && (
                    <span className="tabular absolute -top-1.5 -right-2.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-status-danger px-1 text-[0.65rem] font-semibold text-status-danger-foreground">
                      {contador}
                    </span>
                  )}
                </span>
                {item.short}
                {activo && <span className="absolute top-0 h-0.5 w-8 rounded-full bg-primary" aria-hidden />}
              </Link>
            </li>
          );
        })}
        <li>
          <button
            type="button"
            onClick={() => setOpenMobile(true)}
            className="flex h-16 w-full flex-col items-center justify-center gap-1 text-[0.7rem] font-medium text-muted-foreground outline-none transition-colors focus-visible:bg-muted active:bg-muted"
          >
            <Menu className="size-[1.4rem]" />
            Más
          </button>
        </li>
      </ul>
    </nav>
  );
}
