"use client";

import { Filter, Inbox, MessageCircle, Search, X } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { AvatarInitials } from "@/components/app/avatar-initials";
import { EmptyState } from "@/components/app/empty-state";
import { FilterChips, type Chip } from "@/components/app/filter-chips";
import { ListSkeleton } from "@/components/app/list-skeleton";
import { PaginationBar } from "@/components/app/pagination-bar";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { useApi } from "@/hooks/use-api";
import { estadoConversacionInfo } from "@/lib/estados";
import { formatPhone, tiempoRelativo } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { ConversacionesListado } from "@/types/conversacion";

const PAGE_SIZE = 20;
const REFRESCO_MS = 20_000;

const ORIGENES: Record<string, string> = {
  todos: "Todos los orígenes",
  directo: "Directo",
  fep: "Anuncio (FEP)",
  web_formulario: "Formulario web",
};

/** Lista de conversaciones con búsqueda, filtros rápidos y refresco
 * automático. Vive en el layout, así que no pierde su estado al abrir un
 * chat. */
export function InboxList() {
  const { id: idActivo } = useParams<{ id?: string }>();
  const [vista, setVista] = useState("todas");
  const [origen, setOrigen] = useState("todos");
  const [entrada, setEntrada] = useState("");
  const [busqueda, setBusqueda] = useState("");
  const [page, setPage] = useState(1);

  // Espera a que se deje de escribir para no consultar en cada tecla.
  useEffect(() => {
    const t = setTimeout(() => {
      setBusqueda(entrada.trim());
      setPage(1);
    }, 300);
    return () => clearTimeout(t);
  }, [entrada]);

  const params = new URLSearchParams({ page: String(page), pageSize: String(PAGE_SIZE) });
  if (vista !== "todas") params.set("estado", vista);
  if (origen !== "todos") params.set("origen", origen);
  if (busqueda) params.set("q", busqueda);

  const { data, error, cargando, actualizando, recargar } = useApi<ConversacionesListado>(`/conversaciones?${params}`, {
    intervalo: REFRESCO_MS,
  });

  const totales = data?.totalesPorFiltroRapido;
  const chips: Chip[] = [
    { value: "todas", label: "Todas" },
    {
      value: "escalada",
      label: "Escaladas",
      count: totales ? (totales.escaladasSinRevisar > 0 ? totales.escaladasSinRevisar : totales.escaladas) : undefined,
      tone: totales && totales.escaladasSinRevisar > 0 ? "danger" : "default",
    },
    { value: "esperando_pago", label: "Esperando pago", count: totales?.esperandoPago },
  ];

  const hayFiltros = vista !== "todas" || origen !== "todos" || busqueda !== "";

  return (
    <>
      <div className="space-y-3 border-b p-4">
        <div className="flex items-center justify-between gap-2">
          <h1 className="text-xl font-semibold tracking-tight">Conversaciones</h1>
          {data && (
            <span className="tabular text-xs text-muted-foreground">
              {data.total} {data.total === 1 ? "chat" : "chats"}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <div className="relative min-w-0 flex-1">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
            <Input
              type="search"
              inputMode="search"
              placeholder="Buscar teléfono o nombre"
              aria-label="Buscar conversaciones"
              className="pr-9 pl-9"
              value={entrada}
              onChange={(e) => setEntrada(e.target.value)}
            />
            {entrada && (
              <button
                type="button"
                onClick={() => setEntrada("")}
                aria-label="Borrar búsqueda"
                className="absolute top-1/2 right-1 flex size-8 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground hover:text-foreground"
              >
                <X className="size-4" />
              </button>
            )}
          </div>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="icon" aria-label="Filtrar por origen" className="relative shrink-0">
                <Filter />
                {origen !== "todos" && <span className="absolute top-1.5 right-1.5 size-2 rounded-full bg-primary" aria-hidden />}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="min-w-48">
              <DropdownMenuLabel>Origen del cliente</DropdownMenuLabel>
              <DropdownMenuRadioGroup
                value={origen}
                onValueChange={(v) => {
                  setOrigen(v);
                  setPage(1);
                }}
              >
                {Object.entries(ORIGENES).map(([valor, etiqueta]) => (
                  <DropdownMenuRadioItem key={valor} value={valor}>
                    {etiqueta}
                  </DropdownMenuRadioItem>
                ))}
              </DropdownMenuRadioGroup>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        <FilterChips
          label="Filtrar conversaciones"
          chips={chips}
          value={vista}
          onChange={(v) => {
            setVista(v);
            setPage(1);
          }}
        />
      </div>

      <div className={cn("min-h-0 flex-1 overflow-y-auto transition-opacity", actualizando && data && "opacity-70")}>
        {cargando ? (
          <ListSkeleton />
        ) : error && !data ? (
          <EmptyState
            icon={MessageCircle}
            tone="danger"
            title="No se pudieron cargar las conversaciones"
            description={error}
            action={
              <Button variant="outline" onClick={recargar}>
                Reintentar
              </Button>
            }
          />
        ) : data && data.items.length === 0 ? (
          <EmptyState
            icon={Inbox}
            title={hayFiltros ? "Sin resultados" : "Aún no hay conversaciones"}
            description={
              hayFiltros ? "Prueba con otro filtro o borra la búsqueda." : "Cuando un cliente escriba por WhatsApp, aparecerá aquí."
            }
            action={
              hayFiltros ? (
                <Button
                  variant="outline"
                  onClick={() => {
                    setVista("todas");
                    setOrigen("todos");
                    setEntrada("");
                  }}
                >
                  Quitar filtros
                </Button>
              ) : undefined
            }
          />
        ) : (
          <ul className="divide-y">
            {data?.items.map((c) => {
              const info = estadoConversacionInfo(c.estado);
              const activa = String(c.id) === idActivo;
              const nombre = c.nombreCliente ?? formatPhone(c.telefono);
              const deCliente = c.ultimoMensaje?.rol === "cliente";
              return (
                <li key={c.id}>
                  <Link
                    href={`/conversaciones/${c.id}`}
                    aria-current={activa ? "page" : undefined}
                    className={cn(
                      "relative flex gap-3 px-4 py-3.5 outline-none transition-colors focus-visible:bg-muted",
                      activa ? "bg-accent" : "hover:bg-muted/60 active:bg-muted",
                    )}
                  >
                    {c.sinRevisar && <span className="absolute inset-y-0 left-0 w-1 bg-status-danger" aria-hidden />}
                    <AvatarInitials nombre={c.nombreCliente ?? c.telefono} semilla={c.telefono} className="size-11" />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-baseline justify-between gap-2">
                        <p className={cn("truncate", c.sinRevisar ? "font-semibold" : "font-medium")}>{nombre}</p>
                        <span className={cn("shrink-0 text-xs", c.sinRevisar ? "font-medium text-status-danger-ink" : "text-muted-foreground")}>
                          {tiempoRelativo(c.actualizadaEn)}
                        </span>
                      </div>
                      <p className={cn("mt-0.5 line-clamp-1 text-sm", deCliente ? "text-foreground/80" : "text-muted-foreground")}>
                        {c.ultimoMensaje ? (
                          <>
                            {!deCliente && <span className="text-muted-foreground">{c.ultimoMensaje.rol === "bot" ? "Victoria: " : "Tú: "}</span>}
                            {c.ultimoMensaje.contenido}
                          </>
                        ) : (
                          "Sin mensajes"
                        )}
                      </p>
                      <div className="mt-2 flex flex-wrap items-center gap-1.5">
                        <StatusBadge label={info.label} variant={info.variant} className="h-5 px-2 text-[0.7rem]" />
                        {c.productoInteres && (
                          <span className="max-w-full truncate rounded-full bg-muted px-2 py-0.5 text-[0.7rem] text-muted-foreground">
                            {c.productoInteres}
                          </span>
                        )}
                      </div>
                    </div>
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {data && data.total > PAGE_SIZE && (
        <div className="border-t p-3">
          <PaginationBar page={page} pageSize={PAGE_SIZE} total={data.total} onPage={setPage} disabled={actualizando} />
        </div>
      )}
    </>
  );
}
