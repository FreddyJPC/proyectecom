"use client";

import { FilePenLine, PackageOpen, PackagePlus, Settings2, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { EmptyState } from "@/components/app/empty-state";
import { FilterChips, type Chip } from "@/components/app/filter-chips";
import { ListSkeleton } from "@/components/app/list-skeleton";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { estadoProductoBotInfo } from "@/lib/estados";
import { formatMoney, tiempoRelativo } from "@/lib/format";
import { esPropio, type EstadoProductoBot, type ProductoBotResumen } from "@/types/producto-bot";

import { ACCIONES_POR_ESTADO, AccionEstadoBoton } from "./accion-estado";
import { AjustesPreciosDialog } from "./ajustes-precios-dialog";
import { fichaHref } from "./preparar-boton";

// Igual que en el catálogo: sin un mínimo definido, "poco stock" es una referencia general.
const POCO_STOCK = 5;

type Filtro = "todos" | "venta" | "borradores" | "pausados" | "archivados";
// ADR-012: de dónde viene el producto. Se filtra aparte del estado.
type FiltroOrigen = "todos" | "rocketfy" | "propio";

const ESTADOS_DEL_FILTRO: Record<Exclude<Filtro, "todos">, EstadoProductoBot[]> = {
  venta: ["activo"],
  borradores: ["borrador", "listo"],
  pausados: ["pausado", "agotado"],
  archivados: ["archivado"],
};

function coincide(p: ProductoBotResumen, filtro: Filtro): boolean {
  if (filtro === "todos") return p.estado !== "archivado";
  return ESTADOS_DEL_FILTRO[filtro].includes(p.estado);
}

/** Pestaña "Mis productos": los productos que tienen ficha de ventas, con su
 * estado. Solo los que están "A la venta" los ve Victoria. */
export function MisProductosTab({
  items,
  cargando,
  error,
  recargar,
  onIrAlCatalogo,
}: {
  items: ProductoBotResumen[] | null;
  cargando: boolean;
  error: string | null;
  recargar: () => void;
  onIrAlCatalogo: () => void;
}) {
  const [filtro, setFiltro] = useState<Filtro>("todos");
  const [origen, setOrigen] = useState<FiltroOrigen>("todos");

  const delOrigen = items?.filter((p) => origen === "todos" || p.proveedor === origen);
  const chips: Chip[] = [
    { value: "todos", label: "Todos" },
    { value: "venta", label: "A la venta", count: delOrigen?.filter((p) => coincide(p, "venta")).length },
    { value: "borradores", label: "Borradores", count: delOrigen?.filter((p) => coincide(p, "borradores")).length },
    { value: "pausados", label: "Pausados", count: delOrigen?.filter((p) => coincide(p, "pausados")).length },
    { value: "archivados", label: "Archivados", count: delOrigen?.filter((p) => coincide(p, "archivados")).length },
  ];
  const chipsOrigen: Chip[] = [
    { value: "todos", label: "Todos los orígenes" },
    { value: "rocketfy", label: "Rocketfy", count: items?.filter((p) => p.proveedor === "rocketfy" && p.estado !== "archivado").length },
    { value: "propio", label: "Propios", count: items?.filter((p) => p.proveedor === "propio" && p.estado !== "archivado").length },
  ];

  const visibles = delOrigen?.filter((p) => coincide(p, filtro)) ?? [];

  return (
    <>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <p className="max-w-prose text-sm text-muted-foreground">
          Aquí están los productos que preparaste para que Victoria los venda, de Rocketfy y propios. <strong className="font-medium text-foreground">Solo los que están «A la venta» los ve Victoria</strong>; el resto son borradores, pausados o archivados. Cada hora se actualizan costo y stock de los de Rocketfy, y un producto que se queda sin stock se pausa solo.
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <Button asChild size="sm">
            <Link href="/catalogo/propio/nuevo">
              <PackagePlus /> Publicar producto propio
            </Link>
          </Button>
          <AjustesPreciosDialog
            // Los ajustes cambian qué productos tienen el margen en riesgo: se vuelve a pedir la lista.
            onGuardado={recargar}
            trigger={
              <Button variant="outline" size="sm">
                <Settings2 /> Ajustes de precios
              </Button>
            }
          />
        </div>
      </div>

      <FilterChips chips={chipsOrigen} value={origen} onChange={(v) => setOrigen(v as FiltroOrigen)} label="Filtrar por origen" />
      <FilterChips chips={chips} value={filtro} onChange={(v) => setFiltro(v as Filtro)} label="Filtrar por estado" />

      <Card className="gap-0 overflow-hidden py-0">
        {cargando ? (
          <ListSkeleton filas={4} />
        ) : error && !items ? (
          <EmptyState
            icon={TriangleAlert}
            tone="danger"
            title="No se pudieron cargar tus productos"
            description={error}
            action={
              <Button variant="outline" onClick={recargar}>
                Reintentar
              </Button>
            }
          />
        ) : visibles.length === 0 ? (
          items && items.length === 0 ? (
            <EmptyState
              icon={PackageOpen}
              title="Aún no preparaste ningún producto"
              description="Pulsa «Preparar para vender» en un producto de Rocketfy del Catálogo, o publica uno tuyo. Se crea como borrador y Victoria no lo ve hasta que lo publiques."
              action={
                <div className="flex flex-wrap justify-center gap-2">
                  <Button onClick={onIrAlCatalogo}>Ir al Catálogo</Button>
                  <Button asChild variant="outline">
                    <Link href="/catalogo/propio/nuevo">Publicar producto propio</Link>
                  </Button>
                </div>
              }
            />
          ) : (
            <EmptyState icon={PackageOpen} title="Nada en este filtro" description="Prueba con otro filtro para ver tus demás productos." />
          )
        ) : (
          <ul className="divide-y">
            {visibles.map((p) => {
              const estado = estadoProductoBotInfo(p.estado);
              const propio = esPropio(p);
              const sinControl = propio && !p.controlaStock;
              const agotado = !sinControl && p.stockUltimo != null && p.stockUltimo <= 0;
              const bajo = !sinControl && p.stockUltimo != null && !agotado && p.stockUltimo <= POCO_STOCK;
              const principal = ACCIONES_POR_ESTADO[p.estado][0];
              return (
                <li key={p.sku} className="flex flex-wrap items-center gap-x-4 gap-y-3 px-4 py-4 sm:flex-nowrap sm:px-5">
                  <div className="min-w-0 flex-1 basis-full space-y-1 sm:basis-auto">
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                      <Link href={fichaHref(p.sku)} className="rounded-sm font-medium outline-none hover:underline focus-visible:ring-2 focus-visible:ring-ring">
                        {p.nombre}
                      </Link>
                      <StatusBadge label={estado.label} variant={estado.variant} className="h-5 px-2 text-[0.7rem]" />
                      {propio && <StatusBadge label="Propio" variant="info" className="h-5 px-2 text-[0.7rem]" />}
                      {p.margenEnRiesgo && <StatusBadge label="Margen en riesgo" variant="warning" className="h-5 px-2 text-[0.7rem]" />}
                    </div>
                    <p className="text-xs text-muted-foreground">
                      <span className="tabular">{p.sku}</span>
                      {p.categoria && <> · {p.categoria}</>}
                      {!p.envioIncluido && <> · envío aparte</>}
                      {p.actualizadoEn && <> · actualizado {tiempoRelativo(p.actualizadoEn)}</>}
                    </p>
                  </div>

                  <div className="flex items-center gap-4 sm:gap-6">
                    <div className="w-20 sm:text-right">
                      <p className="text-xs text-muted-foreground">Precio</p>
                      <p className="tabular font-semibold">{formatMoney(p.precio)}</p>
                    </div>
                    <div className="w-20">
                      <p className="text-xs text-muted-foreground">Pedidos (30 d)</p>
                      <p className="tabular font-semibold">{p.pedidos30d ?? 0}</p>
                    </div>
                    <div className="w-28">
                      <p className="text-xs text-muted-foreground">Stock</p>
                      <div className="flex items-center gap-2">
                        {sinControl ? <span className="text-sm text-muted-foreground">Sin control</span> : <span className="tabular font-semibold">{p.stockUltimo ?? "—"}</span>}
                        {agotado ? <StatusBadge label="Agotado" variant="danger" className="h-5 px-2 text-[0.7rem]" /> : bajo ? <StatusBadge label="Bajo" variant="warning" className="h-5 px-2 text-[0.7rem]" /> : null}
                      </div>
                    </div>
                  </div>

                  <div className="ml-auto flex items-center gap-2">
                    <AccionEstadoBoton accion={principal} producto={p} onHecho={recargar} />
                    <Button asChild variant="outline" size="sm">
                      <Link href={fichaHref(p.sku)} aria-label={`Abrir la ficha de ${p.nombre}`}>
                        <FilePenLine /> Ficha
                      </Link>
                    </Button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </Card>
    </>
  );
}
