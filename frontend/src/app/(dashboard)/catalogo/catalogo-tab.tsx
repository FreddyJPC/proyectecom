"use client";

import { Eye, PackageSearch, Search, TriangleAlert, X } from "lucide-react";
import { useEffect, useState } from "react";

import { EmptyState } from "@/components/app/empty-state";
import { ListSkeleton } from "@/components/app/list-skeleton";
import { PaginationBar } from "@/components/app/pagination-bar";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useApi } from "@/hooks/use-api";
import { formatMoney } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { CatalogoRocketfy, SkuMonitoreado } from "@/types/producto";

import { MonitorearDialog } from "./monitorear-dialog";

// Sin un mínimo definido por el dueño, "poco stock" es una referencia general.
const POCO_STOCK = 5;

export function CatalogoTab({ monitoreados, onCambio }: { monitoreados: SkuMonitoreado[]; onCambio: () => void }) {
  const [entrada, setEntrada] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);

  useEffect(() => {
    const t = setTimeout(() => {
      setQ(entrada.trim());
      setPage(1);
    }, 300);
    return () => clearTimeout(t);
  }, [entrada]);

  const params = new URLSearchParams({ page: String(page) });
  if (q) params.set("q", q);
  const { data, error, cargando, actualizando, recargar } = useApi<CatalogoRocketfy>(`/productos?${params}`);

  const porSku = new Map(monitoreados.filter((m) => m.activo).map((m) => [m.sku, m]));

  return (
    <>
      <div className="relative max-w-md">
        <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
        <Input type="search" placeholder="Buscar por nombre o SKU" aria-label="Buscar en el catálogo" className="pr-9 pl-9" value={entrada} onChange={(e) => setEntrada(e.target.value)} />
        {entrada && (
          <button type="button" onClick={() => setEntrada("")} aria-label="Borrar búsqueda" className="absolute top-1/2 right-1 flex size-8 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground hover:text-foreground">
            <X className="size-4" />
          </button>
        )}
      </div>

      <Card className={cn("gap-0 overflow-hidden py-0 transition-opacity", actualizando && data && "opacity-70")}>
        {cargando ? (
          <ListSkeleton filas={7} />
        ) : error && !data ? (
          <EmptyState
            icon={TriangleAlert}
            tone="danger"
            title="No se pudo cargar el catálogo"
            description={error}
            action={
              <Button variant="outline" onClick={recargar}>
                Reintentar
              </Button>
            }
          />
        ) : data && data.data.length === 0 ? (
          <EmptyState icon={PackageSearch} title="Sin resultados" description={q ? `No hay productos que coincidan con «${q}».` : "El catálogo está vacío."} />
        ) : (
          <ul className="divide-y">
            {data?.data.map((p) => {
              const vigilado = porSku.get(p.sku);
              const umbral = vigilado?.umbralStockMinimo ?? POCO_STOCK;
              const agotado = p.stock <= 0;
              const bajo = !agotado && p.stock <= umbral;
              return (
                <li key={p.sku} className="flex flex-wrap items-center gap-x-4 gap-y-3 px-4 py-4 sm:flex-nowrap sm:px-5">
                  <div className="min-w-0 flex-1 basis-full sm:basis-auto">
                    <p className="font-medium">{p.name}</p>
                    <p className="tabular text-xs text-muted-foreground">{p.sku}</p>
                  </div>

                  <div className="flex items-center gap-4 sm:gap-6">
                    <div className="w-20 sm:text-right">
                      <p className="text-xs text-muted-foreground">Precio</p>
                      <p className="tabular font-semibold">{formatMoney(p.price)}</p>
                    </div>
                    <div className="w-28">
                      <p className="text-xs text-muted-foreground">Stock</p>
                      <div className="flex items-center gap-2">
                        <span className="tabular font-semibold">{p.stock}</span>
                        {agotado ? <StatusBadge label="Agotado" variant="danger" className="h-5 px-2 text-[0.7rem]" /> : bajo ? <StatusBadge label="Bajo" variant="warning" className="h-5 px-2 text-[0.7rem]" /> : null}
                      </div>
                    </div>
                  </div>

                  <div className="ml-auto sm:ml-0 sm:w-36 sm:text-right">
                    <MonitorearDialog
                      sku={p.sku}
                      umbralInicial={vigilado?.umbralStockMinimo}
                      onSuccess={onCambio}
                      trigger={
                        vigilado ? (
                          <Button variant="secondary" size="sm" className="text-status-success-ink">
                            <Eye /> Vigilado
                          </Button>
                        ) : (
                          <Button variant="outline" size="sm">
                            <Eye /> Vigilar
                          </Button>
                        )
                      }
                    />
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </Card>

      {data && <PaginationBar page={data.pagination.current_page} pageSize={data.pagination.per_page} total={data.pagination.total} onPage={setPage} disabled={actualizando} />}
    </>
  );
}
