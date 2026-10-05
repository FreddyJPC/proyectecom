"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { apiFetch, ApiError } from "@/lib/api";
import { rocketfyStatusInfo } from "@/lib/estados";
import type { EventoWebhook, Paginado } from "@/types/incidencia";

const PAGE_SIZE = 20;

export function EventosTab() {
  const [datos, setDatos] = useState<Paginado<EventoWebhook> | null>(null);
  const [cargando, setCargando] = useState(true);
  const [todos, setTodos] = useState(false);
  const [page, setPage] = useState(1);

  useEffect(() => {
    let cancelado = false;
    const params = new URLSearchParams({ page: String(page), pageSize: String(PAGE_SIZE) });
    if (todos) params.set("todos", "true");

    apiFetch<Paginado<EventoWebhook>>(`/incidencias/eventos?${params}`)
      .then((data) => {
        if (!cancelado) setDatos(data);
      })
      .catch((err: unknown) => {
        if (cancelado) return;
        toast.error(err instanceof ApiError ? err.message : "No se pudo cargar las incidencias.");
      })
      .finally(() => {
        if (!cancelado) setCargando(false);
      });

    return () => {
      cancelado = true;
    };
  }, [todos, page]);

  const totalPaginas = datos ? Math.max(1, Math.ceil(datos.total / PAGE_SIZE)) : 1;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Checkbox
            id="todos"
            checked={todos}
            onCheckedChange={(v) => {
              setCargando(true);
              setPage(1);
              setTodos(v === true);
            }}
          />
          <Label htmlFor="todos" className="text-sm font-normal">
            Mostrar todo el historial (no solo lo que requiere atención)
          </Label>
        </div>
        <span className="text-sm text-muted-foreground">
          {datos ? `${datos.total} evento${datos.total === 1 ? "" : "s"}` : ""}
        </span>
      </div>

      <div className="rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Fecha</TableHead>
              <TableHead>Pedido</TableHead>
              <TableHead>Estado</TableHead>
              <TableHead>Detalle</TableHead>
              <TableHead>Transportadora</TableHead>
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

            {!cargando && datos?.items.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} className="h-24 text-center text-muted-foreground">
                  {todos ? "Todavía no llega ningún evento del webhook." : "Sin incidencias pendientes de atención. 🎉"}
                </TableCell>
              </TableRow>
            )}

            {!cargando &&
              datos?.items.map((evento) => {
                const info = rocketfyStatusInfo(evento.statusId);
                return (
                  <TableRow key={evento.id}>
                    <TableCell className="text-xs text-muted-foreground">
                      {(evento.eventDate ?? evento.recibidoEn) &&
                        new Date((evento.eventDate ?? evento.recibidoEn)!).toLocaleString("es-EC")}
                    </TableCell>
                    <TableCell>
                      {evento.idLocal ? (
                        <Link href={`/pedidos/${evento.idLocal}`} className="font-mono text-xs underline">
                          {evento.idLocal}
                        </Link>
                      ) : (
                        "—"
                      )}
                    </TableCell>
                    <TableCell>
                      {info && <StatusBadge label={info.label} variant={info.variant} />}
                    </TableCell>
                    <TableCell className="max-w-xs truncate text-sm">{evento.details || "—"}</TableCell>
                    <TableCell className="text-sm">{evento.shippingCompany || "—"}</TableCell>
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
