"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { apiFetch, ApiError } from "@/lib/api";
import { ESTADOS_LOCALES, estadoLocalInfo } from "@/lib/estados";
import type { PedidosListado } from "@/types/pedido";

const PAGE_SIZE = 20;

export default function PedidosPage() {
  const [datos, setDatos] = useState<PedidosListado | null>(null);
  const [cargando, setCargando] = useState(true);
  const [estado, setEstado] = useState<string>("todos");
  const [page, setPage] = useState(1);

  useEffect(() => {
    let cancelado = false;

    const params = new URLSearchParams({ page: String(page), pageSize: String(PAGE_SIZE) });
    if (estado !== "todos") params.set("estado", estado);

    apiFetch<PedidosListado>(`/pedidos?${params}`)
      .then((data) => {
        if (!cancelado) setDatos(data);
      })
      .catch((err: unknown) => {
        if (cancelado) return;
        const mensaje = err instanceof ApiError ? err.message : "No se pudo cargar la lista de pedidos.";
        toast.error(mensaje);
      })
      .finally(() => {
        if (!cancelado) setCargando(false);
      });

    return () => {
      cancelado = true;
    };
  }, [estado, page]);

  const totalPaginas = datos ? Math.max(1, Math.ceil(datos.total / PAGE_SIZE)) : 1;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold">Pedidos</h2>
          <p className="text-sm text-muted-foreground">
            {datos ? `${datos.total} pedido${datos.total === 1 ? "" : "s"}` : "Cargando…"}
          </p>
        </div>
        <Select
          value={estado}
          onValueChange={(v) => {
            setCargando(true);
            setEstado(v);
            setPage(1);
          }}
        >
          <SelectTrigger className="w-56">
            <SelectValue placeholder="Filtrar por estado" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="todos">Todos los estados</SelectItem>
            {Object.entries(ESTADOS_LOCALES).map(([key, info]) => (
              <SelectItem key={key} value={key}>
                {info.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>ID</TableHead>
              <TableHead>Cliente</TableHead>
              <TableHead>Teléfono</TableHead>
              <TableHead>Ubicación</TableHead>
              <TableHead>Total</TableHead>
              <TableHead>Estado</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {cargando &&
              Array.from({ length: 5 }).map((_, i) => (
                <TableRow key={i}>
                  {Array.from({ length: 6 }).map((_, j) => (
                    <TableCell key={j}>
                      <Skeleton className="h-4 w-full" />
                    </TableCell>
                  ))}
                </TableRow>
              ))}

            {!cargando && datos?.items.length === 0 && (
              <TableRow>
                <TableCell colSpan={6} className="h-24 text-center text-muted-foreground">
                  No hay pedidos {estado !== "todos" ? "en este estado" : "todavía"}.
                </TableCell>
              </TableRow>
            )}

            {!cargando &&
              datos?.items.map((pedido) => {
                const info = estadoLocalInfo(pedido.estadoLocal);
                return (
                  <TableRow key={pedido.idLocal} className="cursor-pointer">
                    <TableCell className="p-0">
                      <Link href={`/pedidos/${pedido.idLocal}`} className="block px-4 py-2 font-mono text-xs">
                        {pedido.idLocal}
                      </Link>
                    </TableCell>
                    <TableCell className="p-0">
                      <Link href={`/pedidos/${pedido.idLocal}`} className="block px-4 py-2">
                        {pedido.nombreCliente}
                      </Link>
                    </TableCell>
                    <TableCell className="p-0">
                      <Link href={`/pedidos/${pedido.idLocal}`} className="block px-4 py-2">
                        {pedido.telefono}
                      </Link>
                    </TableCell>
                    <TableCell className="p-0">
                      <Link href={`/pedidos/${pedido.idLocal}`} className="block px-4 py-2">
                        {pedido.canton}, {pedido.provincia}
                      </Link>
                    </TableCell>
                    <TableCell className="p-0">
                      <Link href={`/pedidos/${pedido.idLocal}`} className="block px-4 py-2">
                        ${pedido.total}
                      </Link>
                    </TableCell>
                    <TableCell className="p-0">
                      <Link href={`/pedidos/${pedido.idLocal}`} className="flex px-4 py-2">
                        <StatusBadge label={info.label} variant={info.variant} />
                      </Link>
                    </TableCell>
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
