import { Badge } from "@/components/ui/badge";
import type { StatusVariant } from "@/lib/estados";
import { cn } from "@/lib/utils";

const VARIANT_CLASSES: Record<StatusVariant, string> = {
  success: "bg-status-success/10 text-status-success",
  warning: "bg-status-warning/15 text-status-warning",
  danger: "bg-status-danger/10 text-status-danger",
  info: "bg-status-info/10 text-status-info",
  neutral: "bg-status-neutral text-status-neutral-foreground",
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
  return (
    <Badge variant="outline" className={cn("border-transparent", VARIANT_CLASSES[variant], className)}>
      {label}
    </Badge>
  );
}
