import type { LucideIcon } from "lucide-react";

export function Proximamente({
  icon: Icon,
  titulo,
  etapa,
  descripcion,
}: {
  icon: LucideIcon;
  titulo: string;
  etapa: string;
  descripcion: string;
}) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3 rounded-lg border border-dashed py-24 text-center">
      <Icon className="size-8 text-muted-foreground" />
      <div className="space-y-1">
        <p className="text-sm font-medium">{titulo}</p>
        <p className="text-sm text-muted-foreground max-w-sm">{descripcion}</p>
      </div>
      <span className="text-xs text-muted-foreground">{etapa} — PROGRESS.md</span>
    </div>
  );
}
