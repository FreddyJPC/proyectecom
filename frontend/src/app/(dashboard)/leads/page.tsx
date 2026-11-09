"use client";

import { ArrowUpDown, BellOff, Search, TriangleAlert, Users, X } from "lucide-react";
import { useEffect, useState } from "react";

import { AvatarInitials } from "@/components/app/avatar-initials";
import { EmptyState } from "@/components/app/empty-state";
import { FilterChips, type Chip } from "@/components/app/filter-chips";
import { InfoButton } from "@/components/app/info-button";
import { ListSkeleton } from "@/components/app/list-skeleton";
import { PageHeader } from "@/components/app/page-header";
import { PaginationBar } from "@/components/app/pagination-bar";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useApi } from "@/hooks/use-api";
import { lineaDeCanal, nombreCanal, nombreDeCliente } from "@/lib/canales";
import { formatMoney, tiempoRelativo } from "@/lib/format";
import { etapaLead, nombreOrigen } from "@/lib/leads";
import { cn } from "@/lib/utils";
import type { Lead, LeadsListado, PeriodoLeads, ResumenLeads } from "@/types/leads";

import { FiltrosLeads } from "./filtros-leads";
import { LeadDetalleSheet } from "./lead-detalle";
import { MotivosDePerdida, ResumenLeadsCards } from "./resumen-leads";
import { TemperaturaBadge } from "./temperatura-badge";

const PAGE_SIZE = 20;
const REFRESCO_MS = 30_000;

const PERIODOS: Chip[] = [
  { value: "7", label: "7 días" },
  { value: "30", label: "30 días" },
  { value: "90", label: "90 días" },
  { value: "todo", label: "Todo" },
];

const ORDENES: Record<string, string> = {
  actividad: "Actividad reciente",
  temperatura: "Más calientes primero",
  valor: "Mayor valor",
  antiguedad: "Más antiguos primero",
};


/** Temperaturas que recorre cada chip: «abiertos» son los que todavía se pueden vender. */
const VISTAS: Record<string, string> = {
  abiertos: "caliente,tibio,frio",
  todos: "",
  caliente: "caliente",
  tibio: "tibio",
  frio: "frio",
  perdido: "perdido",
  ganado: "ganado",
  no_contactar: "",
};

function productoDe(l: Lead): string {
  if (!l.productoNombre) return "Aún sin producto";
  return `${l.cantidad && l.cantidad > 1 ? `${l.cantidad} × ` : ""}${l.productoNombre}${l.productoVariante ? ` (${l.productoVariante})` : ""}`;
}

/** Leads (CRM): cada intención de compra con su temperatura, quién es el cliente y qué hacer con él. */
export default function LeadsPage() {
  const [periodo, setPeriodo] = useState<PeriodoLeads>("30");
  const [vista, setVista] = useState("abiertos");
  const [etapa, setEtapa] = useState("todas");
  const [origen, setOrigen] = useState("todos");
  const [canal, setCanal] = useState("todos");
  const [silencio, setSilencio] = useState("0");
  const [orden, setOrden] = useState("actividad");
  const [entrada, setEntrada] = useState("");
  const [busqueda, setBusqueda] = useState("");
  const [page, setPage] = useState(1);
  const [seleccionado, setSeleccionado] = useState<number | null>(null);

  // Espera a que se deje de escribir para no consultar en cada tecla.
  useEffect(() => {
    const t = setTimeout(() => {
      setBusqueda(entrada.trim());
      setPage(1);
    }, 300);
    return () => clearTimeout(t);
  }, [entrada]);

  const resumen = useApi<ResumenLeads>(`/leads/resumen?dias=${periodo}`, { intervalo: REFRESCO_MS });

  const params = new URLSearchParams({ page: String(page), pageSize: String(PAGE_SIZE), orden });
  if (VISTAS[vista]) params.set("temperatura", VISTAS[vista]);
  if (etapa !== "todas") params.set("etapa", etapa);
  if (origen !== "todos") params.set("origen", origen);
  if (canal !== "todos") params.set("canal", canal);
  if (vista === "no_contactar") params.set("noContactar", "true");
  if (silencio !== "0") params.set("sinRespuestaDias", silencio);
  if (busqueda) params.set("q", busqueda);
  const leads = useApi<LeadsListado>(`/leads?${params}`, { intervalo: REFRESCO_MS });

  const r = resumen.data;
  const chips: Chip[] = [
    { value: "abiertos", label: "Abiertos", count: r ? r.calientes + r.tibios + r.frios : undefined },
    { value: "caliente", label: "Calientes", count: r?.calientes },
    { value: "tibio", label: "Tibios", count: r?.tibios },
    { value: "frio", label: "Fríos", count: r?.frios },
    { value: "ganado", label: "Ganados" },
    { value: "perdido", label: "Perdidos" },
    { value: "no_contactar", label: "No contactar", count: r?.noContactar },
    { value: "todos", label: "Todos" },
  ];

  const filtrosActivos = [etapa !== "todas", origen !== "todos", canal !== "todos", silencio !== "0"].filter(Boolean).length;
  const hayFiltros = vista !== "abiertos" || filtrosActivos > 0 || busqueda !== "";

  function quitarFiltros() {
    setVista("abiertos");
    setEtapa("todas");
    setOrigen("todos");
    setCanal("todos");
    setSilencio("0");
    setEntrada("");
    setPage(1);
  }

  function quitarFiltrosDelCuadro() {
    setEtapa("todas");
    setOrigen("todos");
    setCanal("todos");
    setSilencio("0");
    setPage(1);
  }

  /** Cambiar un filtro siempre vuelve a la primera página. */
  const cambiar = (poner: (v: string) => void) => (v: string) => {
    poner(v);
    setPage(1);
  };

  function recargarTodo() {
    leads.recargar();
    resumen.recargar();
  }

  const data = leads.data;

  return (
    <>
      <PageHeader
        title="Leads"
        description="Quién quiere comprar y qué tan en serio."
        info={
          <InfoButton titulo="Cómo funcionan los leads">
            <p>
              Un <strong>lead</strong> es una intención de compra: un cliente interesado en un producto. Un mismo cliente puede tener varios con el tiempo, pero solo uno abierto a la vez.
            </p>
            <h3>La temperatura</h3>
            <ul>
              <li><strong>Caliente:</strong> va en serio (pide precio, datos de envío o cómo pagar).</li>
              <li><strong>Tibio:</strong> hay interés, pero no se decide.</li>
              <li><strong>Frío:</strong> dejó de responder. Aún se puede recuperar.</li>
              <li><strong>Perdido:</strong> ya no compra; queda guardado el motivo.</li>
              <li><strong>Ganado:</strong> compró.</li>
            </ul>
            <h3>Quién la decide</h3>
            <p>
              Victoria la ajusta al leer cada conversación, las ventas la cierran (venta cerrada = ganado, cancelada = perdido) y el tiempo la enfría si el cliente deja de responder. <strong>Tú siempre mandas:</strong> lo que cambies a mano queda fijado unos días.
            </p>
            <h3>Las cifras de arriba</h3>
            <p>
              Calientes, tibios, fríos y el valor en juego son de <strong>ahora</strong>. La tasa de cierre (ganados entre ganados y perdidos) y los motivos de pérdida son del periodo que elijas.
            </p>
            <h3>Seguimiento automático</h3>
            <p>
              Si lo activas en <strong>Parámetros</strong>, el sistema le escribe por su cuenta al cliente interesado que dejó de contestar: un <strong>empujón</strong> dentro de las 24 horas y, a los de anuncio, una <strong>plantilla</strong> después. Solo una vez de cada uno por cliente, con tope diario y horario. Viene apagado.
            </p>
            <h3>No contactar</h3>
            <p>Protege a la persona: ningún mensaje automático le llega, en ningún canal. Se ve en el detalle de cada lead.</p>
          </InfoButton>
        }
      />

      <FilterChips chips={PERIODOS} value={periodo} onChange={(v) => setPeriodo(v as PeriodoLeads)} label="Periodo de las cifras de cierre" />

      <ResumenLeadsCards resumen={resumen.data} cargando={resumen.cargando} onElegir={cambiar(setVista)} />

      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <div className="relative min-w-0 flex-1">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
            <Input
              type="search"
              inputMode="search"
              placeholder="Buscar cliente o producto"
              aria-label="Buscar leads"
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

          <FiltrosLeads
            etapa={etapa}
            origen={origen}
            canal={canal}
            silencio={silencio}
            onEtapa={cambiar(setEtapa)}
            onOrigen={cambiar(setOrigen)}
            onCanal={cambiar(setCanal)}
            onSilencio={cambiar(setSilencio)}
            onQuitar={quitarFiltrosDelCuadro}
            activos={filtrosActivos}
          />

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" aria-label={`Ordenar: ${ORDENES[orden]}`} className="shrink-0 max-sm:size-9">
                <ArrowUpDown /> <span className="max-sm:hidden">{ORDENES[orden]}</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="min-w-52">
              <DropdownMenuLabel>Ordenar por</DropdownMenuLabel>
              <DropdownMenuRadioGroup value={orden} onValueChange={cambiar(setOrden)}>
                {Object.entries(ORDENES).map(([v, t]) => (
                  <DropdownMenuRadioItem key={v} value={v}>
                    {t}
                  </DropdownMenuRadioItem>
                ))}
              </DropdownMenuRadioGroup>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        <FilterChips label="Filtrar por temperatura" chips={chips} value={vista} onChange={cambiar(setVista)} />
      </div>

      <Card className={cn("gap-0 overflow-hidden py-0 transition-opacity", leads.actualizando && data && "opacity-70")}>
        {leads.cargando ? (
          <ListSkeleton filas={6} />
        ) : leads.error && !data ? (
          <EmptyState
            icon={TriangleAlert}
            tone="danger"
            title="No se pudieron cargar los leads"
            description={leads.error}
            action={
              <Button variant="outline" onClick={leads.recargar}>
                Reintentar
              </Button>
            }
          />
        ) : data && data.items.length === 0 ? (
          <EmptyState
            icon={Users}
            title={hayFiltros ? "Sin resultados" : "Aún no hay leads"}
            description={
              hayFiltros
                ? "Prueba con otro filtro o borra la búsqueda."
                : "Cuando un cliente muestre interés en un producto, aparecerá aquí con su temperatura."
            }
            action={
              hayFiltros ? (
                <Button variant="outline" onClick={quitarFiltros}>
                  Quitar filtros
                </Button>
              ) : undefined
            }
          />
        ) : (
          <>
            {/* Móvil: tarjetas con lo esencial a la vista */}
            <ul className="divide-y md:hidden">
              {data?.items.map((l) => (
                <li key={l.id}>
                  <button
                    type="button"
                    onClick={() => setSeleccionado(l.id)}
                    className="flex w-full items-start gap-3 px-4 py-3.5 text-left outline-none transition-colors active:bg-muted focus-visible:bg-muted"
                  >
                    <AvatarInitials nombre={l.nombre ?? l.telefono} semilla={l.idExterno} className="size-11" />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-baseline justify-between gap-2">
                        <p className="truncate font-medium">{nombreDeCliente({ nombre: l.nombre, telefono: l.telefono, idExterno: l.idExterno })}</p>
                        <span className="shrink-0 text-xs text-muted-foreground">{tiempoRelativo(l.actualizadoEn)}</span>
                      </div>
                      <p className="mt-0.5 flex items-baseline justify-between gap-2 text-sm">
                        <span className="truncate text-muted-foreground">{productoDe(l)}</span>
                        {l.total && <span className="tabular shrink-0 font-semibold">{formatMoney(l.total)}</span>}
                      </p>
                      <div className="mt-2 flex flex-wrap items-center gap-1.5">
                        <TemperaturaBadge temperatura={l.temperatura} className="h-5 px-2 text-[0.7rem]" />
                        {l.noContactar && <StatusBadge label="No contactar" variant="danger" className="h-5 px-2 text-[0.7rem]" />}
                        <span className="rounded-full bg-muted px-2 py-0.5 text-[0.7rem] text-muted-foreground">{etapaLead(l.etapa)}</span>
                        {l.origen === "anuncio" && <span className="rounded-full border px-2 py-0.5 text-[0.7rem] text-muted-foreground">Anuncio</span>}
                        {l.ultimoSeguimiento && (
                          <span className="rounded-full border px-2 py-0.5 text-[0.7rem] text-muted-foreground">
                            Seguimiento · {tiempoRelativo(l.ultimoSeguimiento.enviadoEn)}
                          </span>
                        )}
                        {l.canal !== "whatsapp" && <span className="rounded-full border px-2 py-0.5 text-[0.7rem] text-muted-foreground">{nombreCanal(l.canal)}</span>}
                      </div>
                    </div>
                  </button>
                </li>
              ))}
            </ul>

            {/* Escritorio: tabla con la fila completa clicable */}
            <Table className="hidden md:table">
              <TableHeader>
                <TableRow className="bg-muted/40 hover:bg-muted/40">
                  <TableHead className="pl-5">Cliente</TableHead>
                  <TableHead>Interés</TableHead>
                  <TableHead className="text-right">Total</TableHead>
                  <TableHead>Temperatura</TableHead>
                  <TableHead className="hidden xl:table-cell">Llegó por</TableHead>
                  <TableHead className="pr-5 text-right">Actividad</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.items.map((l) => {
                  const nombre = nombreDeCliente({ nombre: l.nombre, telefono: l.telefono, idExterno: l.idExterno });
                  return (
                    <TableRow key={l.id} className="relative cursor-pointer">
                      <TableCell className="pl-5">
                        <div className="flex items-center gap-3">
                          <AvatarInitials nombre={l.nombre ?? l.telefono} semilla={l.idExterno} className="size-9" />
                          <div className="min-w-0">
                            {/* Botón "estirado": cubre toda la fila (un solo control por lead, accesible con teclado). */}
                            <button
                              type="button"
                              onClick={() => setSeleccionado(l.id)}
                              className="block max-w-48 truncate text-left font-medium text-primary outline-none before:absolute before:inset-0 focus-visible:before:ring-2 focus-visible:before:ring-ring focus-visible:before:ring-inset"
                            >
                              {nombre}
                            </button>
                            <p className="tabular truncate text-xs text-muted-foreground">{lineaDeCanal({ canal: l.canal, telefono: l.telefono, idExterno: l.idExterno })}</p>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <p className="max-w-56 truncate">{productoDe(l)}</p>
                        <p className="text-xs text-muted-foreground">{etapaLead(l.etapa)}</p>
                      </TableCell>
                      <TableCell className="tabular text-right font-semibold">{l.total ? formatMoney(l.total) : "—"}</TableCell>
                      <TableCell>
                        <div className="flex flex-col items-start gap-1">
                          <div className="flex items-center gap-1.5">
                            <TemperaturaBadge temperatura={l.temperatura} />
                            {l.noContactar && <BellOff className="size-4 text-status-danger-ink" aria-label="No contactar" />}
                          </div>
                          {l.motivoPerdidaEtiqueta && <span className="text-xs text-muted-foreground">{l.motivoPerdidaEtiqueta}</span>}
                        </div>
                      </TableCell>
                      <TableCell className="hidden text-sm xl:table-cell">
                        {nombreOrigen(l.origen)}
                        {l.tituloAnuncio && <p className="max-w-40 truncate text-xs text-muted-foreground">{l.tituloAnuncio}</p>}
                      </TableCell>
                      <TableCell className="pr-5 text-right text-sm text-muted-foreground">
                        {tiempoRelativo(l.actualizadoEn)}
                        {l.ultimoSeguimiento && <p className="text-xs">Seguimiento {tiempoRelativo(l.ultimoSeguimiento.enviadoEn)}</p>}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </>
        )}
      </Card>

      {data && <PaginationBar page={page} pageSize={PAGE_SIZE} total={data.total} onPage={setPage} disabled={leads.actualizando} />}

      {r && <MotivosDePerdida motivos={r.motivosDePerdida} />}

      <LeadDetalleSheet leadId={seleccionado} onCerrar={() => setSeleccionado(null)} onCambio={recargarTodo} />
    </>
  );
}
