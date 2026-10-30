"use client";

import { PackageOpen, Plus, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";

import { AvatarInitials } from "@/components/app/avatar-initials";
import { EmptyState } from "@/components/app/empty-state";
import { FilterChips, type Chip } from "@/components/app/filter-chips";
import { ListSkeleton } from "@/components/app/list-skeleton";
import { PageHeader } from "@/components/app/page-header";
import { PaginationBar } from "@/components/app/pagination-bar";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useApi } from "@/hooks/use-api";
import { estadoLocalInfo, rocketfyStatusInfo } from "@/lib/estados";
import { formatFecha, formatMoney, formatPhone } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { PedidoResumen, PedidosListado } from "@/types/pedido";

const PAGE_SIZE = 20;

// Etiquetas cortas para los chips (las completas viven en lib/estados.ts y
// se usan en las insignias de cada pedido).
const CHIPS: Chip[] = [
  { value: "todos", label: "Todos" },
  { value: "confirmado", label: "Confirmados" },
  { value: "creado", label: "Por confirmar" },
  { value: "error", label: "Con error" },
  { value: "incompleto", label: "Incompletos" },
  { value: "pendiente_creacion", label: "Pendientes" },
  { value: "rechazado", label: "Rechazados" },
];

/** Estado más informativo de un pedido: el de Rocketfy (dónde va el paquete)
 * si ya existe; si no, el local (creado, error, etc.). */
function estadoVisible(p: PedidoResumen) {
  return rocketfyStatusInfo(p.statusIdRocketfy) ?? estadoLocalInfo(p.estadoLocal);
}

export default function PedidosPage() {
  // useSearchParams() exige un límite <Suspense> (si no, `next build` falla).
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full" />}>
      <PedidosContenido />
    </Suspense>
  );
}

function PedidosContenido() {
  const router = useRouter();
  const searchParams = useSearchParams();

  // El filtro y la página viven en la URL: se pueden compartir/guardar, y el
  // botón "atrás" del navegador devuelve a la misma vista.
  const estado = searchParams.get("estado") ?? "todos";
  const page = Math.max(1, Number(searchParams.get("page") ?? "1") || 1);

  function navegar(nuevo: { estado?: string; page?: number }) {
    const p = new URLSearchParams(searchParams.toString());
    const e = nuevo.estado ?? estado;
    if (e === "todos") p.delete("estado");
    else p.set("estado", e);
    const pg = nuevo.page ?? 1;
    if (pg <= 1) p.delete("page");
    else p.set("page", String(pg));
    const qs = p.toString();
    router.replace(qs ? `/pedidos?${qs}` : "/pedidos", { scroll: false });
  }

  const params = new URLSearchParams({ page: String(page), pageSize: String(PAGE_SIZE) });
  if (estado !== "todos") params.set("estado", estado);
  const { data, error, cargando, actualizando, recargar } = useApi<PedidosListado>(`/pedidos?${params}`);

  const vacio = data && data.items.length === 0;

  return (
    <>
      <PageHeader
        title="Pedidos"
        description={data ? `${data.total} ${data.total === 1 ? "pedido" : "pedidos"}${estado !== "todos" ? " con este filtro" : ""}` : "Los pedidos que Victoria y tú han creado en Rocketfy."}
        actions={
          <Button asChild>
            <Link href="/pedidos/nuevo">
              <Plus /> Nuevo pedido
            </Link>
          </Button>
        }
      />

      <FilterChips label="Filtrar pedidos por estado" chips={CHIPS} value={estado} onChange={(v) => navegar({ estado: v })} />

      <Card className={cn("gap-0 overflow-hidden py-0 transition-opacity", actualizando && data && "opacity-70")}>
        {cargando ? (
          <ListSkeleton filas={7} />
        ) : error && !data ? (
          <EmptyState
            icon={TriangleAlert}
            tone="danger"
            title="No se pudieron cargar los pedidos"
            description={error}
            action={
              <Button variant="outline" onClick={recargar}>
                Reintentar
              </Button>
            }
          />
        ) : vacio ? (
          <EmptyState
            icon={PackageOpen}
            title={estado !== "todos" ? "No hay pedidos con este estado" : "Aún no hay pedidos"}
            description={estado !== "todos" ? "Prueba con otro filtro." : "Cuando Victoria cierre una venta o crees un pedido a mano, aparecerá aquí."}
            action={
              estado !== "todos" ? (
                <Button variant="outline" onClick={() => navegar({ estado: "todos" })}>
                  Ver todos
                </Button>
              ) : (
                <Button asChild>
                  <Link href="/pedidos/nuevo">Crear un pedido</Link>
                </Button>
              )
            }
          />
        ) : (
          <>
            {/* Móvil: tarjetas con lo esencial a la vista */}
            <ul className="divide-y md:hidden">
              {data?.items.map((p) => {
                const info = estadoVisible(p);
                return (
                  <li key={p.idLocal}>
                    <Link href={`/pedidos/${p.idLocal}`} className="flex items-center gap-3 px-4 py-3.5 outline-none active:bg-muted focus-visible:bg-muted">
                      <AvatarInitials nombre={p.nombreCliente} />
                      <div className="min-w-0 flex-1">
                        <p className="truncate font-medium">{p.nombreCliente}</p>
                        <p className="truncate text-sm text-muted-foreground">
                          #{p.idLocal} · {p.canton} · {formatFecha(p.creadoEn)}
                        </p>
                      </div>
                      <div className="flex shrink-0 flex-col items-end gap-1.5">
                        <span className="tabular font-semibold">{formatMoney(p.total)}</span>
                        <StatusBadge label={info.label} variant={info.variant} className="h-5 px-2 text-[0.7rem]" />
                      </div>
                    </Link>
                  </li>
                );
              })}
            </ul>

            {/* Escritorio: tabla con la fila completa clicable */}
            <Table className="hidden md:table">
              <TableHeader>
                <TableRow className="bg-muted/40 hover:bg-muted/40">
                  <TableHead className="w-28 pl-5">Pedido</TableHead>
                  <TableHead>Cliente</TableHead>
                  <TableHead>Ubicación</TableHead>
                  <TableHead className="text-right">Total</TableHead>
                  <TableHead className="pr-5">Estado</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.items.map((p) => {
                  const info = estadoVisible(p);
                  const local = estadoLocalInfo(p.estadoLocal);
                  return (
                    <TableRow key={p.idLocal} className="relative cursor-pointer">
                      <TableCell className="pl-5">
                        {/* Enlace "estirado": cubre toda la fila (un solo enlace
                            por pedido, accesible con teclado). */}
                        <Link
                          href={`/pedidos/${p.idLocal}`}
                          className="tabular font-medium text-primary outline-none before:absolute before:inset-0 focus-visible:before:ring-2 focus-visible:before:ring-ring focus-visible:before:ring-inset"
                        >
                          #{p.idLocal}
                        </Link>
                        <p className="text-xs text-muted-foreground">{formatFecha(p.creadoEn)}</p>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-3">
                          <AvatarInitials nombre={p.nombreCliente} className="size-9" />
                          <div className="min-w-0">
                            <p className="truncate font-medium">{p.nombreCliente}</p>
                            <p className="tabular text-xs text-muted-foreground">{formatPhone(p.telefono)}</p>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <p>{p.canton}</p>
                        <p className="text-xs text-muted-foreground">{p.provincia}</p>
                      </TableCell>
                      <TableCell className="tabular text-right font-semibold">{formatMoney(p.total)}</TableCell>
                      <TableCell className="pr-5">
                        <div className="flex flex-col items-start gap-1">
                          <StatusBadge label={info.label} variant={info.variant} />
                          {p.statusIdRocketfy != null && p.estadoLocal !== "confirmado" && (
                            <span className="text-xs text-muted-foreground">Local: {local.label}</span>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </>
        )}
      </Card>

      {data && <PaginationBar page={page} pageSize={PAGE_SIZE} total={data.total} onPage={(pg) => navegar({ page: pg })} disabled={actualizando} />}
    </>
  );
}
