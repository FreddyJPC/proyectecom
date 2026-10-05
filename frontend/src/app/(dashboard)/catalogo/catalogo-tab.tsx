"use client";

import { ChevronLeft, ChevronRight, Search } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { apiFetch, ApiError } from "@/lib/api";
import type { CatalogoRocketfy } from "@/types/producto";

import { MonitorearDialog } from "./monitorear-dialog";

export function CatalogoTab({ onCambio }: { onCambio: () => void }) {
  const [datos, setDatos] = useState<CatalogoRocketfy | null>(null);
  const [cargando, setCargando] = useState(true);
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);

  useEffect(() => {
    let cancelado = false;
    const params = new URLSearchParams({ page: String(page) });
    if (q) params.set("q", q);

    const timeout = setTimeout(() => {
      apiFetch<CatalogoRocketfy>(`/productos?${params}`)
        .then((data) => {
          if (!cancelado) setDatos(data);
        })
        .catch((err: unknown) => {
          if (cancelado) return;
          toast.error(err instanceof ApiError ? err.message : "No se pudo cargar el catálogo.");
        })
        .finally(() => {
          if (!cancelado) setCargando(false);
        });
    }, 300);

    return () => {
      cancelado = true;
      clearTimeout(timeout);
    };
  }, [q, page]);

  return (
    <div className="flex flex-col gap-4">
      <div className="relative max-w-sm">
        <Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
        <Input
          placeholder="Buscar por SKU o nombre…"
          value={q}
          onChange={(e) => {
            setCargando(true);
            setPage(1);
            setQ(e.target.value);
          }}
          className="pl-8"
        />
      </div>

      <div className="rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>SKU</TableHead>
              <TableHead>Nombre</TableHead>
              <TableHead>Precio</TableHead>
              <TableHead>Stock</TableHead>
              <TableHead className="text-right">Acción</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {cargando &&
              Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i}>
                  {Array.from({ length: 5 }).map((_, j) => (
                    <TableCell key={j}>
                      <Skeleton className="h-4 w-full" />
                    </TableCell>
                  ))}
                </TableRow>
              ))}

            {!cargando && datos?.data.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} className="h-24 text-center text-muted-foreground">
                  Sin resultados.
                </TableCell>
              </TableRow>
            )}

            {!cargando &&
              datos?.data.map((producto) => (
                <TableRow key={producto.sku}>
                  <TableCell className="font-mono text-xs">{producto.sku}</TableCell>
                  <TableCell>{producto.name}</TableCell>
                  <TableCell>${producto.price}</TableCell>
                  <TableCell>{producto.stock}</TableCell>
                  <TableCell className="text-right">
                    <MonitorearDialog
                      sku={producto.sku}
                      onSuccess={onCambio}
                      trigger={
                        <Button variant="outline" size="sm">
                          Monitorear
                        </Button>
                      }
                    />
                  </TableCell>
                </TableRow>
              ))}
          </TableBody>
        </Table>
      </div>

      <div className="flex items-center justify-end gap-2">
        <span className="text-sm text-muted-foreground">
          Página {datos?.pagination.current_page ?? 1} de {datos?.pagination.last_page ?? 1}
          {datos ? ` — ${datos.pagination.total} productos` : ""}
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
          disabled={!datos || page >= datos.pagination.last_page}
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
