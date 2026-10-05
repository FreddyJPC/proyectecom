import type { LucideIcon } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function MetricCard({
  icon: Icon,
  label,
  value,
  money,
}: {
  icon: LucideIcon;
  label: string;
  value: string | number | null;
  money?: boolean;
}) {
  // Solo para mostrar: Rocketfy a veces manda 0 (número) en vez de "0.00"
  // cuando no hay movimiento -- Number(...).toFixed(2) nunca se usa para
  // calcular ni para guardar, solo para que se vea consistente.
  const mostrar = value == null ? "—" : money ? `$${Number(value).toFixed(2)}` : value;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-normal text-muted-foreground">{label}</CardTitle>
        <Icon className="size-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-semibold tabular-nums">{mostrar}</div>
      </CardContent>
    </Card>
  );
}
