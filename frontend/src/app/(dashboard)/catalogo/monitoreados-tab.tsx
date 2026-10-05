"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { apiFetch, ApiError } from "@/lib/api";
import type { SkuMonitoreado } from "@/types/producto";

import { MonitorearDialog } from "./monitorear-dialog";

export function MonitoreadosTab({ refrescarKey }: { refrescarKey: number }) {
  const [items, setItems] = useState<SkuMonitoreado[] | null>(null);
  const [cargando, setCargando] = useState(true);
  const [quitando, setQuitando] = useState<string | null>(null);

  function cargar() {
    apiFetch<SkuMonitoreado[]>("/productos/monitoreados?soloActivos=false")
      .then(setItems)
      .catch((err: unknown) => {
        toast.error(err instanceof ApiError ? err.message : "No se pudo cargar los SKUs monitoreados.");
      })
      .finally(() => setCargando(false));
  }

  useEffect(() => {
    cargar();
  }, [refrescarKey]);

  async function handleQuitar(sku: string) {
    setQuitando(sku);
    try {
      await apiFetch(`/productos/monitoreados/${encodeURIComponent(sku)}`, { method: "DELETE" });
      toast.success(`SKU '${sku}' desactivado del monitoreo.`);
      cargar();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo desactivar el SKU.");
    } finally {
      setQuitando(null);
    }
  }

  return (
    <div className="rounded-lg border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>SKU</TableHead>
            <TableHead>Umbral</TableHead>
            <TableHead>Último stock</TableHead>
            <TableHead>Último precio</TableHead>
            <TableHead>Estado</TableHead>
            <TableHead className="text-right">Acciones</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {cargando &&
            Array.from({ length: 3 }).map((_, i) => (
              <TableRow key={i}>
                {Array.from({ length: 6 }).map((_, j) => (
                  <TableCell key={j}>
                    <Skeleton className="h-4 w-full" />
                  </TableCell>
                ))}
              </TableRow>
            ))}

          {!cargando && items?.length === 0 && (
            <TableRow>
              <TableCell colSpan={6} className="h-24 text-center text-muted-foreground">
                Ningún SKU monitoreado todavía — agrega uno desde la pestaña &ldquo;Catálogo&rdquo;.
              </TableCell>
            </TableRow>
          )}

          {!cargando &&
            items?.map((item) => (
              <TableRow key={item.sku}>
                <TableCell className="font-mono text-xs">{item.sku}</TableCell>
                <TableCell>{item.umbralStockMinimo}</TableCell>
                <TableCell>{item.ultimoStock ?? "—"}</TableCell>
                <TableCell>{item.ultimoPrecio ? `$${item.ultimoPrecio}` : "—"}</TableCell>
                <TableCell>
                  <Badge variant={item.activo ? "secondary" : "outline"}>
                    {item.activo ? "Activo" : "Inactivo"}
                  </Badge>
                </TableCell>
                <TableCell className="flex justify-end gap-2">
                  <MonitorearDialog
                    sku={item.sku}
                    umbralInicial={item.umbralStockMinimo}
                    onSuccess={cargar}
                    trigger={
                      <Button variant="outline" size="sm">
                        Editar umbral
                      </Button>
                    }
                  />
                  {item.activo && (
                    <Button
                      variant="destructive"
                      size="sm"
                      disabled={quitando === item.sku}
                      onClick={() => handleQuitar(item.sku)}
                    >
                      Quitar
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
        </TableBody>
      </Table>
    </div>
  );
}
