"use client";

import { PackageSearch, Search } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { apiFetch } from "@/lib/api";
import { formatMoney } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { CatalogoRocketfy, Producto } from "@/types/producto";

export function AgregarProductoDialog({
  onSeleccionar,
  trigger,
}: {
  onSeleccionar: (producto: Producto) => void;
  trigger: ReactNode;
}) {
  const [abierto, setAbierto] = useState(false);
  const [q, setQ] = useState("");
  const [resultados, setResultados] = useState<Producto[]>([]);
  const [cargando, setCargando] = useState(false);

  useEffect(() => {
    if (!abierto) return;
    let cancelado = false;
    const timeout = setTimeout(() => {
      apiFetch<CatalogoRocketfy>(`/productos?${new URLSearchParams({ q })}`)
        .then((data) => {
          if (!cancelado) setResultados(data.data);
        })
        .catch(() => {
          if (!cancelado) setResultados([]);
        })
        .finally(() => {
          if (!cancelado) setCargando(false);
        });
    }, 300);
    return () => {
      cancelado = true;
      clearTimeout(timeout);
    };
  }, [q, abierto]);

  return (
    <Dialog
      open={abierto}
      onOpenChange={(v) => {
        setAbierto(v);
        if (v) {
          setCargando(true);
          setQ("");
        }
      }}
    >
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="max-h-[92dvh] gap-3">
        <DialogHeader>
          <DialogTitle>Agregar producto</DialogTitle>
          <DialogDescription>Busca en el catálogo de Rocketfy por nombre o SKU.</DialogDescription>
        </DialogHeader>
        <div className="relative">
          <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
          <Input
            autoFocus
            type="search"
            placeholder="Buscar por SKU o nombre…"
            aria-label="Buscar producto"
            value={q}
            onChange={(e) => {
              setCargando(true);
              setQ(e.target.value);
            }}
            className="pl-9"
          />
        </div>
        <div className="max-h-[55dvh] overflow-y-auto rounded-lg border">
          {cargando && (
            <div className="space-y-2 p-3" aria-busy="true">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-12" />
              ))}
            </div>
          )}

          {!cargando && resultados.length === 0 && (
            <div className="flex flex-col items-center gap-2 p-8 text-center text-sm text-muted-foreground">
              <PackageSearch className="size-6" aria-hidden />
              Sin resultados para «{q}».
            </div>
          )}

          {!cargando &&
            resultados.map((producto) => {
              const agotado = producto.stock <= 0;
              return (
                <button
                  key={producto.sku}
                  type="button"
                  disabled={agotado}
                  onClick={() => {
                    onSeleccionar(producto);
                    setAbierto(false);
                  }}
                  className={cn(
                    "flex min-h-14 w-full items-center justify-between gap-3 border-b px-3.5 py-2.5 text-left text-sm outline-none transition-colors last:border-0",
                    agotado ? "cursor-not-allowed opacity-55" : "hover:bg-accent focus-visible:bg-accent",
                  )}
                >
                  <span className="min-w-0">
                    <span className="block truncate font-medium">{producto.name}</span>
                    <span className="tabular block text-xs text-muted-foreground">{producto.sku}</span>
                  </span>
                  <span className="flex shrink-0 flex-col items-end gap-1">
                    <span className="tabular font-semibold">{formatMoney(producto.price)}</span>
                    {agotado ? (
                      <Badge variant="outline" className="border-transparent bg-status-danger-soft text-status-danger-ink">
                        Agotado
                      </Badge>
                    ) : (
                      <span className="tabular text-xs text-muted-foreground">{producto.stock} en stock</span>
                    )}
                  </span>
                </button>
              );
            })}
        </div>
      </DialogContent>
    </Dialog>
  );
}
