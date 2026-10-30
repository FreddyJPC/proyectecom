import type { LucideIcon } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export type Tono = "primary" | "success" | "warning" | "danger" | "info" | "neutral";

const TONOS: Record<Tono, string> = {
  primary: "bg-accent text-accent-foreground",
  success: "bg-status-success-soft text-status-success-ink",
  warning: "bg-status-warning-soft text-status-warning-ink",
  danger: "bg-status-danger-soft text-status-danger-ink",
  info: "bg-status-info-soft text-status-info-ink",
  neutral: "bg-status-neutral-soft text-status-neutral-ink",
};

/** Tarjeta de una cifra clave. Si recibe `href` toda la tarjeta es un enlace
 * (objetivo táctil grande). `cargando` muestra el esqueleto sin saltos de
 * layout. */
export function StatCard({
  label,
  value,
  hint,
  icon: Icon,
  tono = "primary",
  href,
  cargando,
  destacado,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  icon?: LucideIcon;
  tono?: Tono;
  href?: string;
  cargando?: boolean;
  destacado?: boolean;
}) {
  const cuerpo = (
    <Card
      className={cn(
        "h-full gap-3 p-4 shadow-card ring-1 ring-border transition-colors sm:p-5",
        href && "hover:ring-primary/40 hover:bg-accent/30",
        destacado && "ring-status-danger/40 bg-status-danger-soft/40",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-medium text-muted-foreground">{label}</p>
        {Icon && (
          <span className={cn("flex size-8 shrink-0 items-center justify-center rounded-lg", TONOS[tono])}>
            <Icon className="size-4" aria-hidden />
          </span>
        )}
      </div>
      <div>
        {cargando ? (
          <Skeleton className="h-8 w-24" />
        ) : (
          <p className="tabular text-2xl font-semibold tracking-tight sm:text-3xl">{value}</p>
        )}
        {hint && !cargando && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
      </div>
    </Card>
  );

  if (!href) return cuerpo;
  return (
    <Link href={href} className="block rounded-xl outline-none focus-visible:ring-3 focus-visible:ring-ring/50">
      {cuerpo}
    </Link>
  );
}
