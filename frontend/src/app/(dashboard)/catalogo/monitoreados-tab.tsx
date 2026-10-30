"use client";

import { EyeOff, Pencil, ShieldCheck, TriangleAlert } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { EmptyState } from "@/components/app/empty-state";
import { ListSkeleton } from "@/components/app/list-skeleton";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { apiFetch, ApiError } from "@/lib/api";
import { formatMoney, tiempoRelativo } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { SkuMonitoreado } from "@/types/producto";

import { MonitorearDialog } from "./monitorear-dialog";

export function MonitoreadosTab({
  items,
  cargando,
  error,
  recargar,
}: {
  items: SkuMonitoreado[] | null;
  cargando: boolean;
  error: string | null;
  recargar: () => void;
}) {
  const [quitando, setQuitando] = useState<string | null>(null);

  async function handleQuitar(sku: string) {
    setQuitando(sku);
    try {
      await apiFetch(`/productos/monitoreados/${encodeURIComponent(sku)}`, { method: "DELETE" });
      toast.success(`Dejaste de vigilar ${sku}.`);
      recargar();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo dejar de vigilar el producto.");
    } finally {
      setQuitando(null);
    }
  }

  return (
    <Card className="gap-0 overflow-hidden py-0">
      {cargando ? (
        <ListSkeleton filas={3} />
      ) : error && !items ? (
        <EmptyState
          icon={TriangleAlert}
          tone="danger"
          title="No se pudo cargar la lista"
          description={error}
          action={
            <Button variant="outline" onClick={recargar}>
              Reintentar
            </Button>
          }
        />
      ) : items && items.length === 0 ? (
        <EmptyState
          icon={ShieldCheck}
          title="Aún no vigilas ningún producto"
          description="Ve a la pestaña Catálogo y pulsa «Vigilar» en los productos que anuncias. Te avisaremos cuando su stock baje del mínimo o cambie su precio."
        />
      ) : (
        <ul className="divide-y">
          {items?.map((m) => {
            const stock = m.ultimoStock;
            const pct = stock != null && m.umbralStockMinimo > 0 ? Math.min(100, Math.round((stock / (m.umbralStockMinimo * 2)) * 100)) : null;
            const bajo = stock != null && stock <= m.umbralStockMinimo;
            return (
              <li key={m.sku} className={cn("flex flex-col gap-3 px-4 py-4 sm:flex-row sm:items-center sm:gap-6 sm:px-5", !m.activo && "bg-muted/30")}>
                <div className="min-w-0 flex-1 space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={cn("tabular font-semibold", !m.activo && "text-muted-foreground")}>{m.sku}</span>
                    {m.activo ? <StatusBadge label={bajo ? "Stock bajo" : "Vigilando"} variant={bajo ? "warning" : "success"} /> : <StatusBadge label="Pausado" variant="neutral" />}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Aviso cuando queden {m.umbralStockMinimo} o menos
                    {m.ultimoSnapshotEn && <> · revisado {tiempoRelativo(m.ultimoSnapshotEn)}</>}
                  </p>
                </div>

                <div className="flex items-center gap-6">
                  <div className="min-w-24">
                    <p className="text-xs text-muted-foreground">Stock actual</p>
                    <p className="tabular font-semibold">{stock ?? "—"}</p>
                    {pct !== null && (
                      <div className="mt-1 h-1.5 w-24 overflow-hidden rounded-full bg-muted" role="img" aria-label={`Nivel de stock ${pct}%`}>
                        <div className={cn("h-full rounded-full", bajo ? "bg-status-danger" : "bg-status-success")} style={{ width: `${Math.max(pct, 4)}%` }} />
                      </div>
                    )}
                  </div>
                  <div className="min-w-16">
                    <p className="text-xs text-muted-foreground">Precio</p>
                    <p className="tabular font-semibold">{formatMoney(m.ultimoPrecio)}</p>
                  </div>
                </div>

                <div className="flex gap-2">
                  <MonitorearDialog
                    sku={m.sku}
                    umbralInicial={m.umbralStockMinimo}
                    onSuccess={recargar}
                    trigger={
                      <Button variant="outline" size="sm">
                        <Pencil /> {m.activo ? "Editar mínimo" : "Reactivar"}
                      </Button>
                    }
                  />
                  {m.activo && (
                    <Button variant="ghost" size="sm" disabled={quitando === m.sku} onClick={() => handleQuitar(m.sku)} className="text-muted-foreground hover:text-destructive">
                      <EyeOff /> Dejar de vigilar
                    </Button>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
