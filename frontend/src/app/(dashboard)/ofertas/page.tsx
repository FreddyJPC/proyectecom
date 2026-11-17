"use client";

import { Loader2, Plus, Tag } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { EmptyState } from "@/components/app/empty-state";
import { FilterChips, type Chip } from "@/components/app/filter-chips";
import { InfoButton } from "@/components/app/info-button";
import { ListSkeleton } from "@/components/app/list-skeleton";
import { PageHeader } from "@/components/app/page-header";
import { SectionCard } from "@/components/app/section-card";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useApi } from "@/hooks/use-api";
import { apiFetch, ApiError } from "@/lib/api";
import { situacionOfertaInfo } from "@/lib/estados";
import { formatMoney, normalizarMonto, normalizarPorcentaje } from "@/lib/format";
import type { ListaOfertas, Oferta, TransferenciaNegocio } from "@/types/precios";

const FILTROS: Chip[] = [
  { value: "vigentes", label: "A la venta" },
  { value: "proximas", label: "Programadas" },
  { value: "terminadas", label: "Terminadas o pausadas" },
  { value: "todas", label: "Todas" },
];

function filtrar(ofertas: Oferta[], filtro: string): Oferta[] {
  if (filtro === "vigentes") return ofertas.filter((o) => o.situacion === "vigente");
  if (filtro === "proximas") return ofertas.filter((o) => o.situacion === "programada");
  if (filtro === "terminadas") return ofertas.filter((o) => ["vencida", "sin_cupo", "pausada"].includes(o.situacion));
  return ofertas;
}

function vigencia(o: Oferta): string {
  const f = (iso: string) => new Date(iso).toLocaleString("es-EC", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
  if (o.desde && o.hasta) return `${f(o.desde)} – ${f(o.hasta)}`;
  if (o.hasta) return `Hasta ${f(o.hasta)}`;
  if (o.desde) return `Desde ${f(o.desde)}`;
  return "Sin fecha de fin";
}

/** Ofertas y combos (ADR-017): lo que promete cada anuncio, con su precio, fechas y cupo. Victoria las vende tal cual. */
export default function OfertasPage() {
  const [filtro, setFiltro] = useState("vigentes");
  const ofertas = useApi<ListaOfertas>("/precios/ofertas");
  const lista = filtrar(ofertas.data?.ofertas ?? [], filtro);

  return (
    <>
      <PageHeader
        title="Ofertas y combos"
        description="Promociones con su precio, fechas y cupo."
        info={
          <InfoButton titulo="Cómo funcionan las ofertas">
            <p>Una <strong>oferta</strong> es lo que promete un anuncio: uno o varios productos a un precio especial (por ejemplo «linterna + cargador por $30» o «2 por $45»).</p>
            <ul>
              <li><strong>Vincúlala a sus anuncios:</strong> quien llegue por ese anuncio recibe esa oferta, y Victoria ya sabe qué incluye y cuánto cuesta.</li>
              <li><strong>Fechas y cupo:</strong> fuera de fecha o sin cupo, Victoria explica que terminó y ofrece el precio normal.</li>
              <li><strong>Quién la ve:</strong> por defecto, solo quien llega por su anuncio. Puedes hacerla pública para que Victoria la ofrezca a cualquiera.</li>
              <li><strong>Margen:</strong> si el precio queda bajo tu margen mínimo, te pedimos confirmarlo.</li>
            </ul>
            <p>Un combo no se regatea (salvo que lo permitas en la oferta).</p>
          </InfoButton>
        }
        actions={
          <Button asChild size="sm">
            <Link href="/ofertas/nueva">
              <Plus /> Nueva oferta
            </Link>
          </Button>
        }
      />

      <div className="flex flex-col gap-5 pb-28 md:pb-6">
        <TransferenciaDelNegocio />

        <FilterChips chips={FILTROS} value={filtro} onChange={setFiltro} label="Filtrar ofertas" />

        {ofertas.cargando ? (
          <ListSkeleton />
        ) : ofertas.error ? (
          <EmptyState
            icon={Tag}
            tone="danger"
            title="No se pudieron cargar las ofertas"
            description={ofertas.error}
            action={
              <Button variant="outline" onClick={ofertas.recargar}>
                Reintentar
              </Button>
            }
          />
        ) : lista.length === 0 ? (
          <EmptyState
            icon={Tag}
            title={filtro === "vigentes" ? "No hay ofertas a la venta" : "No hay ofertas aquí"}
            description="Crea una oferta y vincúlala al anuncio que la promociona."
            action={
              <Button asChild>
                <Link href="/ofertas/nueva">
                  <Plus /> Nueva oferta
                </Link>
              </Button>
            }
          />
        ) : (
          <ul className="grid gap-3 md:grid-cols-2">
            {lista.map((o) => (
              <li key={o.id}>
                <Link
                  href={`/ofertas/${o.id}`}
                  className="block h-full rounded-xl bg-card p-4 shadow-card ring-1 ring-border transition-colors outline-none hover:bg-accent/30 focus-visible:ring-3 focus-visible:ring-ring/50"
                >
                  <div className="flex items-start justify-between gap-3">
                    <h2 className="min-w-0 font-medium">{o.nombre}</h2>
                    <StatusBadge {...situacionOfertaInfo(o.situacion)} />
                  </div>
                  <p className="mt-1 text-sm text-muted-foreground">{o.items.map((i) => `${i.cantidad} × ${i.productoNombre ?? i.productoSku}`).join(" + ")}</p>
                  <p className="mt-3 flex flex-wrap items-baseline gap-x-2">
                    <span className="tabular text-lg font-semibold">{formatMoney(o.precio)}</span>
                    {o.ahorro !== "0.00" && (
                      <span className="tabular text-sm text-muted-foreground">
                        <span className="line-through">{formatMoney(o.precioLista)}</span> · ahorra {formatMoney(o.ahorro)}
                      </span>
                    )}
                  </p>
                  <dl className="mt-3 grid grid-cols-2 gap-x-3 gap-y-1 text-xs text-muted-foreground sm:grid-cols-3">
                    <div>
                      <dt className="sr-only">Vigencia</dt>
                      <dd>{vigencia(o)}</dd>
                    </div>
                    <div>
                      <dt className="sr-only">Ventas</dt>
                      <dd className="tabular">
                        {o.ventas} venta{o.ventas === 1 ? "" : "s"}
                        {o.cupo !== null ? ` de ${o.cupo}` : ""}
                      </dd>
                    </div>
                    <div>
                      <dt className="sr-only">Anuncios</dt>
                      <dd>
                        {o.anuncios.length} anuncio{o.anuncios.length === 1 ? "" : "s"} · {o.visibilidad === "publica" ? "pública" : "solo su anuncio"}
                      </dd>
                    </div>
                  </dl>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </>
  );
}

/** El precio por transferencia que vale para TODOS los productos que no tengan uno propio. */
function TransferenciaDelNegocio() {
  const actual = useApi<TransferenciaNegocio>("/precios/negocio");

  return (
    <SectionCard
      titulo="Descuento por transferencia para todos"
      descripcion="Vale para los productos que no tienen uno propio."
      info={
        <InfoButton titulo="Descuento por transferencia">
          <p>En dropshipping se suele premiar el pago por transferencia: por ejemplo, $25 contra entrega o $20 transfiriendo.</p>
          <p>Lo que pongas aquí vale para todos tus productos. Si un producto tiene su propio precio por transferencia (en su ficha, «Precios y descuentos»), manda el del producto.</p>
          <p>Victoria lo menciona sola cuando se habla del pago (puedes apagarlo en Parámetros → Precios, regateo y ofertas).</p>
        </InfoButton>
      }
    >
      {actual.cargando ? (
        <div className="p-4 sm:p-5">
          <ListSkeleton filas={1} />
        </div>
      ) : actual.error || !actual.data ? (
        <div role="alert" className="flex flex-wrap items-center gap-3 p-4 text-sm text-status-danger-ink sm:p-5">
          <span>{actual.error ?? "No se pudo leer."}</span>
          <Button size="sm" variant="outline" onClick={actual.recargar}>
            Reintentar
          </Button>
        </div>
      ) : (
        <FormTransferencia key={JSON.stringify(actual.data)} inicial={actual.data} onGuardado={actual.recargar} />
      )}
    </SectionCard>
  );
}

function FormTransferencia({ inicial, onGuardado }: { inicial: TransferenciaNegocio; onGuardado: () => void }) {
  const [tipo, setTipo] = useState<string>(inicial.transferenciaTipo ?? "ninguno");
  const [valor, setValor] = useState(inicial.transferenciaValor ?? "");
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const normal = tipo === "porcentaje" ? normalizarPorcentaje(valor) : normalizarMonto(valor);
  const cambio = tipo !== (inicial.transferenciaTipo ?? "ninguno") || (tipo !== "ninguno" && normal !== inicial.transferenciaValor);
  const invalido = tipo !== "ninguno" && normal === null;

  async function guardar() {
    if (invalido) {
      setError("Escribe un valor válido.");
      return;
    }
    setGuardando(true);
    setError(null);
    try {
      await apiFetch<TransferenciaNegocio>("/precios/negocio", {
        method: "PUT",
        body: JSON.stringify(tipo === "ninguno" ? { transferenciaTipo: null } : { transferenciaTipo: tipo, transferenciaValor: normal }),
      });
      toast.success("Descuento por transferencia guardado.");
      onGuardado();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo conectar con el servidor.");
    } finally {
      setGuardando(false);
    }
  }

  return (
    <div className="flex flex-wrap items-end gap-3 p-4 sm:p-5">
      <div className="grid min-w-0 gap-1.5">
        <Label htmlFor="neg-tipo">Descuento</Label>
        <Select value={tipo} onValueChange={setTipo} disabled={guardando}>
          <SelectTrigger id="neg-tipo" className="w-full sm:w-56">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="ninguno">Sin descuento</SelectItem>
            <SelectItem value="porcentaje">Porcentaje menos</SelectItem>
            <SelectItem value="monto">Dólares menos por unidad</SelectItem>
          </SelectContent>
        </Select>
      </div>
      {tipo !== "ninguno" && (
        <div className="grid w-32 gap-1.5">
          <Label htmlFor="neg-valor">{tipo === "porcentaje" ? "Porcentaje (%)" : "Monto ($)"}</Label>
          <Input id="neg-valor" inputMode="decimal" value={valor} onChange={(e) => setValor(e.target.value)} aria-invalid={Boolean(error)} className="tabular" disabled={guardando} />
        </div>
      )}
      <Button type="button" disabled={!cambio || guardando} onClick={() => void guardar()}>
        {guardando ? <Loader2 className="animate-spin" /> : null} Guardar
      </Button>
      {error && (
        <p role="alert" className="basis-full text-sm text-status-danger-ink">
          {error}
        </p>
      )}
    </div>
  );
}
