"use client";

import { ChevronLeft, ChevronRight, Search } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { StatusBadge } from "@/components/status-badge";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { apiFetch, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import { estadoConversacionInfo } from "@/lib/estados";
import type { ConversacionesListado } from "@/types/conversacion";

const PAGE_SIZE = 20;

type Vista = "escalada" | "esperando_pago" | "todas";

function tiempoRelativo(iso: string | null): string {
  if (!iso) return "—";
  const diffMs = Date.now() - new Date(iso).getTime();
  const minutos = Math.round(diffMs / 60000);
  if (minutos < 1) return "recién";
  if (minutos < 60) return `hace ${minutos} min`;
  const horas = Math.round(minutos / 60);
  if (horas < 24) return `hace ${horas} h`;
  const dias = Math.round(horas / 24);
  return `hace ${dias} d`;
}

export default function ConversacionesPage() {
  const [datos, setDatos] = useState<ConversacionesListado | null>(null);
  const [cargando, setCargando] = useState(true);
  const [vista, setVista] = useState<Vista>("todas");
  const [origen, setOrigen] = useState<string>("todos");
  const [busqueda, setBusqueda] = useState("");
  const [page, setPage] = useState(1);

  useEffect(() => {
    let cancelado = false;
    const params = new URLSearchParams({ page: String(page), pageSize: String(PAGE_SIZE) });
    if (vista !== "todas") params.set("estado", vista);
    if (origen !== "todos") params.set("origen", origen);
    if (busqueda) params.set("q", busqueda);

    const timeout = setTimeout(() => {
      apiFetch<ConversacionesListado>(`/conversaciones?${params}`)
        .then((data) => {
          if (!cancelado) setDatos(data);
        })
        .catch((err: unknown) => {
          if (cancelado) return;
          toast.error(err instanceof ApiError ? err.message : "No se pudo cargar la lista de conversaciones.");
        })
        .finally(() => {
          if (!cancelado) setCargando(false);
        });
    }, 300);

    return () => {
      cancelado = true;
      clearTimeout(timeout);
    };
  }, [vista, origen, busqueda, page]);

  const totalPaginas = datos ? Math.max(1, Math.ceil(datos.total / PAGE_SIZE)) : 1;
  const totales = datos?.totalesPorFiltroRapido;

  function cambiarVista(v: string) {
    setCargando(true);
    setVista(v as Vista);
    setPage(1);
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h2 className="text-lg font-semibold">Conversaciones</h2>
        <p className="text-sm text-muted-foreground">
          Lo que Victoria conversa con tus clientes por WhatsApp, y las que necesitan tu atención.
        </p>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <Tabs value={vista} onValueChange={cambiarVista}>
          <TabsList>
            <TabsTrigger value="escalada" className="gap-1.5">
              Escaladas
              {totales !== undefined && totales.escaladas > 0 && (
                <Badge
                  variant="outline"
                  className={cn(
                    "h-5 min-w-5 justify-center px-1",
                    totales.escaladasSinRevisar > 0 && "border-transparent bg-status-danger text-status-danger-foreground",
                  )}
                >
                  {totales.escaladasSinRevisar > 0 ? totales.escaladasSinRevisar : totales.escaladas}
                </Badge>
              )}
            </TabsTrigger>
            <TabsTrigger value="esperando_pago" className="gap-1.5">
              Esperando pago
              {totales !== undefined && totales.esperandoPago > 0 && (
                <Badge variant="outline" className="h-5 min-w-5 justify-center px-1">
                  {totales.esperandoPago}
                </Badge>
              )}
            </TabsTrigger>
            <TabsTrigger value="todas">Todas</TabsTrigger>
          </TabsList>
        </Tabs>

        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="absolute top-2.5 left-2.5 size-4 text-muted-foreground" />
            <Input
              placeholder="Buscar por teléfono o nombre…"
              className="w-64 pl-8"
              value={busqueda}
              onChange={(e) => {
                setCargando(true);
                setPage(1);
                setBusqueda(e.target.value);
              }}
            />
          </div>
          <Select
            value={origen}
            onValueChange={(v) => {
              setCargando(true);
              setOrigen(v);
              setPage(1);
            }}
          >
            <SelectTrigger className="w-40">
              <SelectValue placeholder="Origen" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="todos">Todos los orígenes</SelectItem>
              <SelectItem value="directo">Directo</SelectItem>
              <SelectItem value="fep">Anuncio (FEP)</SelectItem>
              <SelectItem value="web_formulario">Formulario web</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Teléfono</TableHead>
              <TableHead>Cliente</TableHead>
              <TableHead>Producto de interés</TableHead>
              <TableHead>Estado</TableHead>
              <TableHead>Último mensaje</TableHead>
              <TableHead>Actualizado</TableHead>
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
                  No hay conversaciones {vista !== "todas" ? "en este filtro" : "todavía"}.
                </TableCell>
              </TableRow>
            )}

            {!cargando &&
              datos?.items.map((conv) => {
                const info = estadoConversacionInfo(conv.estado);
                return (
                  <TableRow key={conv.id} className={cn("cursor-pointer", conv.sinRevisar && "bg-status-danger/5")}>
                    <TableCell className="p-0">
                      <Link href={`/conversaciones/${conv.id}`} className="flex items-center gap-2 px-4 py-2">
                        {conv.sinRevisar && <span className="size-2 shrink-0 rounded-full bg-status-danger" />}
                        {conv.telefono}
                      </Link>
                    </TableCell>
                    <TableCell className="p-0">
                      <Link href={`/conversaciones/${conv.id}`} className="block px-4 py-2">
                        {conv.nombreCliente ?? "Sin definir aún"}
                      </Link>
                    </TableCell>
                    <TableCell className="p-0">
                      <Link href={`/conversaciones/${conv.id}`} className="block px-4 py-2">
                        {conv.productoInteres ?? "Sin definir aún"}
                      </Link>
                    </TableCell>
                    <TableCell className="p-0">
                      <Link href={`/conversaciones/${conv.id}`} className="flex px-4 py-2">
                        <StatusBadge label={info.label} variant={info.variant} />
                      </Link>
                    </TableCell>
                    <TableCell className="p-0">
                      <Link href={`/conversaciones/${conv.id}`} className="block max-w-64 truncate px-4 py-2 text-sm text-muted-foreground">
                        {conv.ultimoMensaje ? `${conv.ultimoMensaje.rol === "cliente" ? "Cliente" : "Nosotros"}: ${conv.ultimoMensaje.contenido}` : "—"}
                      </Link>
                    </TableCell>
                    <TableCell className="p-0">
                      <Link href={`/conversaciones/${conv.id}`} className="block px-4 py-2 text-sm text-muted-foreground">
                        {tiempoRelativo(conv.actualizadaEn)}
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
