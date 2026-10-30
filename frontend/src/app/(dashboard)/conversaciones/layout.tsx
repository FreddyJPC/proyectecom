"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

import { InboxList } from "./inbox-list";

/** Bandeja de conversaciones en dos paneles (lista + chat).
 *
 * - Escritorio ancho (lg+): los dos paneles a la vez, como WhatsApp Web; la
 *   lista conserva filtros y página al cambiar de conversación porque este
 *   layout no se vuelve a montar.
 * - Móvil / tablet: una sola pantalla a la vez; la lista en /conversaciones
 *   y el chat en /conversaciones/[id] (con flecha para volver en la cabecera).
 *
 * Ocupa todo el alto disponible (sin scroll de página): la lista y los
 * mensajes se desplazan por dentro y el campo de respuesta queda fijo abajo. */
export default function ConversacionesLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const enDetalle = pathname !== "/conversaciones";

  return (
    <div className="-mx-4 -mt-4 -mb-28 flex h-[calc(100dvh-7.5rem-env(safe-area-inset-bottom))] md:-mx-6 md:-mt-6 md:-mb-8 md:h-[calc(100dvh-3.5rem)]">
      <aside
        className={cn(
          "min-h-0 w-full flex-col bg-card lg:flex lg:w-[24rem] lg:shrink-0 lg:border-r xl:w-[26rem]",
          enDetalle ? "hidden" : "flex",
        )}
      >
        <InboxList />
      </aside>
      <section className={cn("min-h-0 min-w-0 flex-1 flex-col bg-background", enDetalle ? "flex" : "hidden lg:flex")}>
        {children}
      </section>
    </div>
  );
}
