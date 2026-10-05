"use client";

import { Search } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";

import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { apiFetch } from "@/lib/api";
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
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Agregar producto</DialogTitle>
        </DialogHeader>
        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
          <Input
            autoFocus
            placeholder="Buscar por SKU o nombre…"
            value={q}
            onChange={(e) => {
              setCargando(true);
              setQ(e.target.value);
            }}
            className="pl-8"
          />
        </div>
        <div className="max-h-80 overflow-y-auto rounded-md border">
          {cargando &&
            Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="m-2 h-10" />)}

          {!cargando && resultados.length === 0 && (
            <p className="p-4 text-center text-sm text-muted-foreground">Sin resultados.</p>
          )}

          {!cargando &&
            resultados.map((producto) => (
              <button
                key={producto.sku}
                type="button"
                onClick={() => {
                  onSeleccionar(producto);
                  setAbierto(false);
                }}
                className="flex w-full items-center justify-between gap-2 border-b px-3 py-2 text-left text-sm last:border-0 hover:bg-accent"
              >
                <span className="flex flex-col">
                  <span className="font-medium">{producto.name}</span>
                  <span className="font-mono text-xs text-muted-foreground">{producto.sku}</span>
                </span>
                <span className="shrink-0 text-xs text-muted-foreground">
                  ${producto.price} · stock {producto.stock}
                </span>
              </button>
            ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}
