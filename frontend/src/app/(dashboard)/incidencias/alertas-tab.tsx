"use client";

import { ArrowRight, CheckCircle2, PackageMinus, PackageX, Search, Tag, TrendingDown, TriangleAlert, X, type LucideIcon } from "lucide-react";
import { useEffect, useState } from "react";

import { EmptyState } from "@/components/app/empty-state";
import { ListSkeleton } from "@/components/app/list-skeleton";
import { PaginationBar } from "@/components/app/pagination-bar";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useApi } from "@/hooks/use-api";
import { tipoAlertaStockInfo } from "@/lib/estados";
import { formatFechaHora, formatMoney, tiempoRelativo } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { AlertaStock, Paginado } from "@/types/incidencia";

const PAGE_SIZE = 20;

/** Icono y color de cada tipo de alerta (el color siempre va acompañado de su etiqueta). */
const ESTILO_POR_TIPO: Record<string, { icono: LucideIcon; tono: string }> = {
  stock_bajo: { icono: PackageMinus, tono: "bg-status-warning-soft text-status-warning-ink" },
  cambio_precio: { icono: Tag, tono: "bg-status-info-soft text-status-info-ink" },
  producto_agotado: { icono: PackageX, tono: "bg-status-danger-soft text-status-danger-ink" },
  margen_en_riesgo: { icono: TrendingDown, tono: "bg-status-warning-soft text-status-warning-ink" },
};

function Detalle({ alerta }: { alerta: AlertaStock }) {
  if (alerta.tipo === "stock_bajo") {
    const stock = Number(alerta.detalle.stock);
    const umbral = Number(alerta.detalle.umbral);
    // Barra de nivel: cuánto stock queda respecto del mínimo que definiste.
    const pct = umbral > 0 ? Math.min(100, Math.round((stock / umbral) * 100)) : 0;
    return (
      <div className="space-y-1.5">
        <p className="text-sm">
          Quedan <strong className="tabular font-semibold">{stock}</strong> unidades · tu mínimo es <span className="tabular">{umbral}</span>
        </p>
        <div className="h-1.5 w-full max-w-48 overflow-hidden rounded-full bg-muted" role="img" aria-label={`Stock al ${pct}% del mínimo`}>
          <div className={cn("h-full rounded-full", pct <= 40 ? "bg-status-danger" : "bg-status-warning")} style={{ width: `${pct}%` }} />
        </div>
      </div>
    );
  }
  if (alerta.tipo === "cambio_precio") {
    return (
      <p className="tabular flex items-center gap-2 text-sm">
        <span className="text-muted-foreground line-through">{formatMoney(String(alerta.detalle.precioAnterior))}</span>
        <ArrowRight className="size-3.5 text-muted-foreground" aria-hidden />
        <strong className="font-semibold">{formatMoney(String(alerta.detalle.precioActual))}</strong>
      </p>
    );
  }
  if (alerta.tipo === "producto_agotado") {
    return (
      <p className="text-sm">
        Rocketfy reporta <strong className="tabular font-semibold">0</strong> unidades: el producto se pausó solo y Victoria ya no lo ofrece. Reanúdalo desde Mis productos cuando vuelva el stock.
      </p>
    );
  }
  if (alerta.tipo === "margen_en_riesgo") {
    return (
      <div className="space-y-1">
        <p className="tabular flex flex-wrap items-center gap-x-2 text-sm">
          <span>Costo</span>
          <span className="text-muted-foreground line-through">{formatMoney(String(alerta.detalle.costoAnterior ?? ""))}</span>
          <ArrowRight className="size-3.5 text-muted-foreground" aria-hidden />
          <strong className="font-semibold">{formatMoney(String(alerta.detalle.costoActual))}</strong>
        </p>
        <p className="text-sm">
          Con tu precio de <span className="tabular">{formatMoney(String(alerta.detalle.precio))}</span> el margen es <strong className="tabular font-semibold">{alerta.detalle.margenPct} %</strong> (tu mínimo es{" "}
          <span className="tabular">{alerta.detalle.margenMinimoPct} %</span>). El precio no se cambió: revísalo tú.
        </p>
      </div>
    );
  }
  return <p className="text-sm text-muted-foreground">{JSON.stringify(alerta.detalle)}</p>;
}

export function AlertasTab() {
  const [entrada, setEntrada] = useState("");
  const [sku, setSku] = useState("");
  const [page, setPage] = useState(1);

  useEffect(() => {
    const t = setTimeout(() => {
      setSku(entrada.trim());
      setPage(1);
    }, 300);
    return () => clearTimeout(t);
  }, [entrada]);

  const params = new URLSearchParams({ page: String(page), pageSize: String(PAGE_SIZE) });
  if (sku) params.set("sku", sku);
  const { data, error, cargando, actualizando, recargar } = useApi<Paginado<AlertaStock>>(`/incidencias/stock?${params}`);

  return (
    <>
      <div className="relative max-w-sm">
        <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
        <Input type="search" placeholder="Filtrar por SKU" aria-label="Filtrar alertas por SKU" className="pr-9 pl-9" value={entrada} onChange={(e) => setEntrada(e.target.value)} />
        {entrada && (
          <button type="button" onClick={() => setEntrada("")} aria-label="Borrar filtro" className="absolute top-1/2 right-1 flex size-8 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground hover:text-foreground">
            <X className="size-4" />
          </button>
        )}
      </div>

      <Card className={cn("gap-0 overflow-hidden py-0 transition-opacity", actualizando && data && "opacity-70")}>
        {cargando ? (
          <ListSkeleton />
        ) : error && !data ? (
          <EmptyState
            icon={TriangleAlert}
            tone="danger"
            title="No se pudieron cargar las alertas"
            description={error}
            action={
              <Button variant="outline" onClick={recargar}>
                Reintentar
              </Button>
            }
          />
        ) : data && data.items.length === 0 ? (
          <EmptyState
            icon={CheckCircle2}
            title={sku ? "Sin alertas para ese SKU" : "Sin alertas de stock o precio"}
            description={sku ? "Prueba con otro SKU." : "Cuando un producto vigilado baje de su mínimo, cambie de precio, se quede sin stock o su margen quede en riesgo, te avisamos aquí."}
          />
        ) : (
          <ul className="divide-y">
            {data?.items.map((a) => {
              const info = tipoAlertaStockInfo(a.tipo);
              const { icono: Icono, tono } = ESTILO_POR_TIPO[a.tipo] ?? ESTILO_POR_TIPO.cambio_precio;
              return (
                <li key={a.id} className="flex items-start gap-3 px-4 py-4 sm:px-5">
                  <span
                    className={cn("mt-0.5 flex size-10 shrink-0 items-center justify-center rounded-full", tono)}
                  >
                    <Icono className="size-[1.1rem]" aria-hidden />
                  </span>
                  <div className="min-w-0 flex-1 space-y-1.5">
                    <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
                      <span className="tabular font-semibold">{a.sku}</span>
                      <StatusBadge label={info.label} variant={info.variant} />
                    </div>
                    <Detalle alerta={a} />
                  </div>
                  <div className="shrink-0 text-right text-xs text-muted-foreground">
                    <p className="font-medium text-foreground/80">{tiempoRelativo(a.creadoEn)}</p>
                    <p className="hidden sm:block">{formatFechaHora(a.creadoEn)}</p>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </Card>

      {data && <PaginationBar page={page} pageSize={PAGE_SIZE} total={data.total} onPage={setPage} disabled={actualizando} />}
    </>
  );
}
