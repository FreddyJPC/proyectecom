"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { apiFetch, ApiError } from "@/lib/api";
import { tipoAlertaStockInfo } from "@/lib/estados";
import type { AlertaStock, Paginado } from "@/types/incidencia";

const PAGE_SIZE = 20;

function detalleTexto(alerta: AlertaStock): string {
  if (alerta.tipo === "stock_bajo") {
    return `Stock: ${alerta.detalle.stock} (umbral: ${alerta.detalle.umbral})`;
  }
  if (alerta.tipo === "cambio_precio") {
    return `$${alerta.detalle.precioAnterior} → $${alerta.detalle.precioActual}`;
  }
  return JSON.stringify(alerta.detalle);
}

export function AlertasTab() {
  const [datos, setDatos] = useState<Paginado<AlertaStock> | null>(null);
  const [cargando, setCargando] = useState(true);
  const [sku, setSku] = useState("");
  const [page, setPage] = useState(1);

  useEffect(() => {
    let cancelado = false;
    const params = new URLSearchParams({ page: String(page), pageSize: String(PAGE_SIZE) });
    if (sku) params.set("sku", sku);

    const timeout = setTimeout(() => {
      apiFetch<Paginado<AlertaStock>>(`/incidencias/stock?${params}`)
        .then((data) => {
          if (!cancelado) setDatos(data);
        })
        .catch((err: unknown) => {
          if (cancelado) return;
          toast.error(err instanceof ApiError ? err.message : "No se pudo cargar las alertas de stock.");
        })
        .finally(() => {
          if (!cancelado) setCargando(false);
        });
    }, 300);

    return () => {
      cancelado = true;
      clearTimeout(timeout);
    };
  }, [sku, page]);

  const totalPaginas = datos ? Math.max(1, Math.ceil(datos.total / PAGE_SIZE)) : 1;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-4">
        <Input
          placeholder="Filtrar por SKU…"
          value={sku}
          onChange={(e) => {
            setCargando(true);
            setPage(1);
            setSku(e.target.value);
          }}
          className="max-w-xs"
        />
        <span className="text-sm text-muted-foreground">
          {datos ? `${datos.total} alerta${datos.total === 1 ? "" : "s"}` : ""}
        </span>
      </div>

      <div className="rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Fecha</TableHead>
              <TableHead>SKU</TableHead>
              <TableHead>Tipo</TableHead>
              <TableHead>Detalle</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {cargando &&
              Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i}>
                  {Array.from({ length: 4 }).map((_, j) => (
                    <TableCell key={j}>
                      <Skeleton className="h-4 w-full" />
                    </TableCell>
                  ))}
                </TableRow>
              ))}

            {!cargando && datos?.items.length === 0 && (
              <TableRow>
                <TableCell colSpan={4} className="h-24 text-center text-muted-foreground">
                  Sin alertas de stock o precio todavía.
                </TableCell>
              </TableRow>
            )}

            {!cargando &&
              datos?.items.map((alerta) => {
                const info = tipoAlertaStockInfo(alerta.tipo);
                return (
                  <TableRow key={alerta.id}>
                    <TableCell className="text-xs text-muted-foreground">
                      {alerta.creadoEn && new Date(alerta.creadoEn).toLocaleString("es-EC")}
                    </TableCell>
                    <TableCell className="font-mono text-xs">{alerta.sku}</TableCell>
                    <TableCell>
                      <StatusBadge label={info.label} variant={info.variant} />
                    </TableCell>
                    <TableCell className="text-sm">{detalleTexto(alerta)}</TableCell>
                  </TableRow>
                );
              })}
          </TableBody>
        </Table>
      </div>

      <div className="flex items-center justify-end gap-2">
        <span className="text-sm text-muted-foreground">
          Página {page} de {totalPaginas}
        </span>
        <Button
          variant="outline"
          size="icon"
          disabled={page <= 1}
          onClick={() => {
            setCargando(true);
            setPage((p) => p - 1);
          }}
        >
          <ChevronLeft />
        </Button>
        <Button
          variant="outline"
          size="icon"
          disabled={page >= totalPaginas}
          onClick={() => {
            setCargando(true);
            setPage((p) => p + 1);
          }}
        >
          <ChevronRight />
        </Button>
      </div>
    </div>
  );
}
