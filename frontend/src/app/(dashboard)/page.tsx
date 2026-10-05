import { AlertTriangle, BarChart3, Boxes, Package } from "lucide-react";
import Link from "next/link";

import { BackendStatus } from "@/components/backend-status";
import { StatusBadge } from "@/components/status-badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ESTADOS_LOCALES } from "@/lib/estados";

const secciones = [
  {
    href: "/pedidos",
    icon: Package,
    titulo: "Pedidos",
    descripcion: "Estado local y de Rocketfy de cada pedido, con acciones manuales.",
    etapa: null,
  },
  {
    href: "/incidencias",
    icon: AlertTriangle,
    titulo: "Incidencias y Alertas",
    descripcion: "Novedades de pedidos y alertas de stock/precio en un solo lugar.",
    etapa: null,
  },
  {
    href: "/catalogo",
    icon: Boxes,
    titulo: "Catálogo y Stock",
    descripcion: "Catálogo de Rocketfy y gestión de SKUs monitoreados.",
    etapa: null,
  },
  {
    href: "/metricas",
    icon: BarChart3,
    titulo: "Métricas",
    descripcion: "Agregados operativos del negocio (no es saldo de wallet).",
    etapa: null,
  },
];

export default function Home() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Resumen</h2>
          <p className="text-sm text-muted-foreground">
            Panel operativo del negocio. Cada sección se va habilitando por etapas.
          </p>
        </div>
        <BackendStatus />
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {secciones.map((s) => (
          <Link key={s.href} href={s.href}>
            <Card className="h-full transition-colors hover:bg-accent/50">
              <CardHeader>
                <s.icon className="size-5 text-muted-foreground" />
                <CardTitle className="text-sm">{s.titulo}</CardTitle>
                <CardDescription>{s.descripcion}</CardDescription>
              </CardHeader>
              <CardContent>
                <span className="text-xs text-muted-foreground">{s.etapa ?? "Disponible"}</span>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Vista previa: colores de estado</CardTitle>
          <CardDescription>
            Paleta que se usará en Pedidos e Incidencias (Etapas 2-3) — definida una sola vez en{" "}
            <code className="text-xs">src/lib/estados.ts</code>.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          {Object.entries(ESTADOS_LOCALES).map(([key, info]) => (
            <StatusBadge key={key} label={info.label} variant={info.variant} />
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
