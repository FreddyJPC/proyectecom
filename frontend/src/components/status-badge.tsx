import { Badge } from "@/components/ui/badge";
import type { StatusVariant } from "@/lib/estados";
import { cn } from "@/lib/utils";

// Fondo suave + texto "ink" (contraste AA) + punto sólido: el estado no
// depende solo del color, siempre va acompañado de su texto.
const VARIANT_CLASSES: Record<StatusVariant, { badge: string; dot: string }> = {
  success: { badge: "bg-status-success-soft text-status-success-ink", dot: "bg-status-success" },
  warning: { badge: "bg-status-warning-soft text-status-warning-ink", dot: "bg-status-warning" },
  danger: { badge: "bg-status-danger-soft text-status-danger-ink", dot: "bg-status-danger" },
  info: { badge: "bg-status-info-soft text-status-info-ink", dot: "bg-status-info" },
  neutral: { badge: "bg-status-neutral-soft text-status-neutral-ink", dot: "bg-status-neutral" },
};

/** Badge de estado reutilizable en toda la app (pedidos, incidencias,
 * resumen). Colores centralizados en src/lib/estados.ts + globals.css --
 * nunca elegir un color de estado "a mano" en una página. */
export function StatusBadge({
  label,
  variant,
  className,
}: {
  label: string;
  variant: StatusVariant;
  className?: string;
}) {
  const v = VARIANT_CLASSES[variant];
  return (
    <Badge variant="outline" className={cn("h-6 gap-1.5 border-transparent px-2.5 text-xs font-medium", v.badge, className)}>
      <span className={cn("size-1.5 shrink-0 rounded-full", v.dot)} aria-hidden />
      {label}
    </Badge>
  );
}
