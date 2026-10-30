"use client";

import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export type Chip = { value: string; label: string; count?: number; tone?: "danger" | "default" };

/** Filtros como "chips" deslizables en horizontal. En móvil reemplazan a los
 * selects (un toque en vez de abrir un menú); el carrusel llega al borde de
 * la pantalla para que se note que se puede deslizar. */
export function FilterChips({
  chips,
  value,
  onChange,
  label,
  className,
  trailing,
}: {
  chips: Chip[];
  value: string;
  onChange: (value: string) => void;
  label: string;
  className?: string;
  trailing?: ReactNode;
}) {
  return (
    <div className={cn("-mx-4 flex items-center gap-2 px-4 md:mx-0 md:px-0", className)}>
      <div role="group" aria-label={label} className="no-scrollbar flex min-w-0 flex-1 gap-2 overflow-x-auto py-0.5">
        {chips.map((chip) => {
          const activo = chip.value === value;
          return (
            <button
              key={chip.value}
              type="button"
              aria-pressed={activo}
              onClick={() => onChange(chip.value)}
              className={cn(
                "inline-flex h-10 shrink-0 items-center gap-2 rounded-full border px-4 text-sm font-medium transition-colors outline-none focus-visible:ring-3 focus-visible:ring-ring/50 md:h-9",
                activo
                  ? "border-primary bg-primary text-primary-foreground shadow-card"
                  : "border-border bg-card text-foreground/80 hover:bg-muted",
              )}
            >
              {chip.label}
              {chip.count !== undefined && chip.count > 0 && (
                <span
                  className={cn(
                    "tabular inline-flex h-5 min-w-5 items-center justify-center rounded-full px-1.5 text-xs font-semibold",
                    chip.tone === "danger"
                      ? "bg-status-danger text-status-danger-foreground"
                      : activo
                        ? "bg-primary-foreground/20 text-primary-foreground"
                        : "bg-muted text-muted-foreground",
                  )}
                >
                  {chip.count}
                </span>
              )}
            </button>
          );
        })}
      </div>
      {trailing}
    </div>
  );
}
