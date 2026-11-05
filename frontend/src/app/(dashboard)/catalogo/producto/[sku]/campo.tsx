import type { ReactNode } from "react";

import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

/** Campo de formulario con su etiqueta, la explicación de para qué sirve, el
 * error (si lo hay) y un contador de caracteres opcional. */
export function Campo({
  id,
  label,
  ayuda,
  error,
  contador,
  opcional,
  children,
}: {
  id: string;
  label: string;
  ayuda?: ReactNode;
  error?: string;
  contador?: { actual: number; maximo: number };
  opcional?: boolean;
  children: ReactNode;
}) {
  return (
    <div className="grid gap-1.5">
      <Label htmlFor={id}>
        {label}
        {opcional && <span className="font-normal text-muted-foreground"> (opcional)</span>}
      </Label>
      {children}
      <div className="flex items-start justify-between gap-3 text-xs">
        <div className="min-w-0 space-y-0.5">
          {ayuda && (
            <p id={`${id}-ayuda`} className="text-muted-foreground">
              {ayuda}
            </p>
          )}
          {error && (
            <p id={`${id}-error`} role="alert" className="font-medium text-status-danger-ink">
              {error}
            </p>
          )}
        </div>
        {contador && (
          <span className={cn("tabular shrink-0 text-muted-foreground", contador.actual >= contador.maximo && "font-medium text-status-warning-ink")}>
            {contador.actual}/{contador.maximo}
          </span>
        )}
      </div>
    </div>
  );
}

/** Valor de `aria-describedby` según haya ayuda y/o error visibles. */
export function descripcionDe(id: string, ayuda: boolean, error?: string) {
  return [ayuda ? `${id}-ayuda` : null, error ? `${id}-error` : null].filter(Boolean).join(" ") || undefined;
}
