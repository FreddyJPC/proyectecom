import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/** Encabezado estándar de página: título, descripción y acciones. Las
 * acciones van a la derecha del título; si son varias (p. ej. Modificar +
 * Rechazar) `accionesDebajoEnMovil` las baja a su propia fila en pantallas
 * chicas para no apretar el texto. */
export function PageHeader({
  title,
  description,
  actions,
  badge,
  accionesDebajoEnMovil,
  className,
}: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  badge?: ReactNode;
  accionesDebajoEnMovil?: boolean;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex gap-3 sm:items-end sm:justify-between",
        accionesDebajoEnMovil ? "flex-col sm:flex-row" : "items-start justify-between",
        className,
      )}
    >
      <div className="min-w-0 space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-xl font-semibold tracking-tight text-balance sm:text-2xl">{title}</h1>
          {badge}
        </div>
        {description && <p className="max-w-prose text-sm text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
