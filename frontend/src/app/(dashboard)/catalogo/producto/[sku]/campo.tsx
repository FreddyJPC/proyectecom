import type { ReactNode } from "react";

import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

/** Campo de formulario con su etiqueta, el error (si lo hay) y un contador de caracteres opcional.
 *
 * Dos niveles de explicación, a propósito:
 *   - `ayuda`: una pista CORTA que se ve siempre bajo el campo (formato, unidad). Máximo una línea.
 *   - `info`: el botón ⓘ (`InfoButton`) junto a la etiqueta, con la explicación larga («para qué sirve», ejemplos). */
export function Campo({
  id,
  label,
  ayuda,
  info,
  error,
  contador,
  opcional,
  children,
}: {
  id: string;
  label: string;
  ayuda?: ReactNode;
  info?: ReactNode;
  error?: string;
  contador?: { actual: number; maximo: number };
  opcional?: boolean;
  children: ReactNode;
}) {
  return (
    <div className="grid gap-1.5">
      <div className="flex items-center gap-1">
        <Label htmlFor={id}>
          {label}
          {opcional && <span className="font-normal text-muted-foreground"> (opcional)</span>}
        </Label>
        {info}
      </div>
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
