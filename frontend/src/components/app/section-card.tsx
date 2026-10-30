import { ArrowRight } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

/** Tarjeta con título y enlace "Ver todo": el bloque básico de paneles. El
 * contenido va a sangre completa (sin padding) para que las listas lleguen
 * hasta el borde; quien lo use decide el espaciado interno. */
export function SectionCard({
  titulo,
  descripcion,
  enlace,
  children,
  className,
}: {
  titulo: string;
  descripcion?: string;
  enlace?: { href: string; label?: string };
  children: ReactNode;
  className?: string;
}) {
  return (
    <Card className={cn("gap-0 py-0", className)}>
      <div className="flex items-center justify-between gap-3 border-b px-4 py-3.5 sm:px-5">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold">{titulo}</h2>
          {descripcion && <p className="text-xs text-muted-foreground">{descripcion}</p>}
        </div>
        {enlace && (
          <Link
            href={enlace.href}
            className="group inline-flex min-h-9 shrink-0 items-center gap-1 rounded-md px-1 text-sm font-medium text-primary outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {enlace.label ?? "Ver todo"}
            <ArrowRight className="size-3.5 transition-transform group-hover:translate-x-0.5" aria-hidden />
          </Link>
        )}
      </div>
      {children}
    </Card>
  );
}
