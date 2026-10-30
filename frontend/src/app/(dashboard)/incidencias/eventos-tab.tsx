"use client";

import { CheckCircle2, ExternalLink, Info, TriangleAlert, Truck } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { EmptyState } from "@/components/app/empty-state";
import { FilterChips } from "@/components/app/filter-chips";
import { ListSkeleton } from "@/components/app/list-skeleton";
import { PaginationBar } from "@/components/app/pagination-bar";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useApi } from "@/hooks/use-api";
import { rocketfyStatusInfo, type StatusVariant } from "@/lib/estados";
import { formatFechaHora, tiempoRelativo } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { EventoWebhook, Paginado } from "@/types/incidencia";

const PAGE_SIZE = 20;

const ICONO_TONO: Record<StatusVariant, string> = {
  success: "bg-status-success-soft text-status-success-ink",
  warning: "bg-status-warning-soft text-status-warning-ink",
  danger: "bg-status-danger-soft text-status-danger-ink",
  info: "bg-status-info-soft text-status-info-ink",
  neutral: "bg-status-neutral-soft text-status-neutral-ink",
};

export function EventosTab() {
  const [historial, setHistorial] = useState(false);
  const [page, setPage] = useState(1);

  const params = new URLSearchParams({ page: String(page), pageSize: String(PAGE_SIZE) });
  if (historial) params.set("todos", "true");
  const { data, error, cargando, actualizando, recargar } = useApi<Paginado<EventoWebhook>>(`/incidencias/eventos?${params}`);

  return (
    <>
      <FilterChips
        label="Qué eventos mostrar"
        value={historial ? "todo" : "atencion"}
        onChange={(v) => {
          setHistorial(v === "todo");
          setPage(1);
        }}
        chips={[
          { value: "atencion", label: "Requieren atención" },
          { value: "todo", label: "Todo el historial" },
        ]}
      />

      {historial && (
        <p className="flex items-start gap-2 rounded-lg bg-muted px-3.5 py-2.5 text-sm text-muted-foreground">
          <Info className="mt-0.5 size-4 shrink-0" aria-hidden />
          Es una bitácora: un mismo pedido puede aparecer varias veces, una por cada cambio de estado.
        </p>
      )}

      <Card className={cn("gap-0 overflow-hidden py-0 transition-opacity", actualizando && data && "opacity-70")}>
        {cargando ? (
          <ListSkeleton />
        ) : error && !data ? (
          <EmptyState
            icon={TriangleAlert}
            tone="danger"
            title="No se pudieron cargar los eventos"
            description={error}
            action={
              <Button variant="outline" onClick={recargar}>
                Reintentar
              </Button>
            }
          />
        ) : data && data.items.length === 0 ? (
          <EmptyState
            icon={historial ? Truck : CheckCircle2}
            title={historial ? "Aún no llega ningún evento" : "Nada pendiente de atención"}
            description={historial ? "Cuando Rocketfy avise un cambio de estado, aparecerá aquí." : "Ningún envío reporta problemas ahora mismo."}
            action={
              !historial ? (
                <Button variant="outline" onClick={() => setHistorial(true)}>
                  Ver todo el historial
                </Button>
              ) : undefined
            }
          />
        ) : (
          <ul className="divide-y">
            {data?.items.map((e) => {
              const info = rocketfyStatusInfo(e.statusId);
              const fecha = e.eventDate ?? e.recibidoEn;
              return (
                <li key={e.id} className="flex items-start gap-3 px-4 py-4 sm:px-5">
                  <span className={cn("mt-0.5 flex size-10 shrink-0 items-center justify-center rounded-full", ICONO_TONO[info?.variant ?? "neutral"])}>
                    <Truck className="size-[1.1rem]" aria-hidden />
                  </span>
                  <div className="min-w-0 flex-1 space-y-1">
                    <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
                      {e.idLocal ? (
                        <Link href={`/pedidos/${e.idLocal}`} className="tabular inline-flex items-center gap-1 font-semibold text-primary hover:underline">
                          Pedido #{e.idLocal}
                          <ExternalLink className="size-3" aria-hidden />
                        </Link>
                      ) : (
                        <span className="tabular font-semibold">Rocketfy #{e.idRocketfy}</span>
                      )}
                      {info && <StatusBadge label={info.label} variant={info.variant} />}
                    </div>
                    <p className="text-sm">{e.details || <span className="text-muted-foreground">Sin detalle del transportista.</span>}</p>
                    <p className="text-xs text-muted-foreground">
                      {[e.shippingCompany, e.trackingCode && `Guía ${e.trackingCode}`].filter(Boolean).join(" · ")}
                    </p>
                  </div>
                  <div className="shrink-0 text-right text-xs text-muted-foreground">
                    <p className="font-medium text-foreground/80">{tiempoRelativo(fecha)}</p>
                    <p className="hidden sm:block">{formatFechaHora(fecha)}</p>
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
