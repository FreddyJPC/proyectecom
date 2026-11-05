"use client";

import { Info, Settings2, TriangleAlert } from "lucide-react";

import { SectionCard } from "@/components/app/section-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { useValorConRetraso } from "@/hooks/use-valor-con-retraso";
import { formatMoney, formatPct, normalizarMonto } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { EvaluacionPrecio, RecomendacionPrecio } from "@/types/producto-bot";

import { AjustesPreciosDialog } from "../../ajustes-precios-dialog";
import { Campo, descripcionDe } from "./campo";

/** Pierde plata (o queda en cero) o no se podrá publicar: es lo grave. */
function esGrave(ev: EvaluacionPrecio): boolean {
  return ev.bajoPiso || ev.ganancia.startsWith("-") || ev.ganancia === "0.00";
}

/** La sección *Precio* de la ficha: el campo del precio y, debajo, lo que la
 * calculadora del backend dice de él (cuánto ganas, tres precios sugeridos y
 * avisos). Los números los calcula el backend en `Decimal`; aquí solo se
 * muestran. Se consulta con un pequeño retraso para no pedir en cada tecla. */
export function SeccionPrecio({
  sku,
  precio,
  onPrecio,
  errorPrecio,
  competencia,
  onCompetencia,
  errorCompetencia,
  onAjustesGuardados,
}: {
  sku: string;
  precio: string;
  onPrecio: (valor: string) => void;
  errorPrecio?: string;
  competencia: string;
  onCompetencia: (valor: string) => void;
  errorCompetencia?: string;
  /** Cambiar los ajustes cambia el mínimo para publicar: la ficha se vuelve a leer. */
  onAjustesGuardados: () => void;
}) {
  const montoPrecio = normalizarMonto(precio);
  const montoCompetencia = competencia.trim() ? normalizarMonto(competencia) : null;
  const precioConsulta = useValorConRetraso(montoPrecio ?? "", 400);
  const competenciaConsulta = useValorConRetraso(montoCompetencia ?? "", 400);

  const consulta = new URLSearchParams();
  if (precioConsulta) consulta.set("precio", precioConsulta);
  if (competenciaConsulta) consulta.set("competencia", competenciaConsulta);
  const qs = consulta.toString();
  const { data, error, cargando, actualizando, recargar } = useApi<RecomendacionPrecio>(
    `/productos-bot/${encodeURIComponent(sku)}/precio${qs ? `?${qs}` : ""}`,
  );

  const ev = data?.evaluacion ?? null;
  const sugerido = data?.precioSugerido ?? null;

  const botonAjustes = (
    <Button type="button" variant="outline" size="sm">
      <Settings2 /> Ajustes de precios
    </Button>
  );

  return (
    <SectionCard titulo="Precio" descripcion="Lo que pagará el cliente por cada unidad, y cuánto te queda a ti.">
      <div className="space-y-5 p-4 sm:p-5">
        {data && !data.ajustesConfirmados && (
          <div role="note" className="flex items-start gap-2.5 rounded-lg bg-status-warning-soft p-3 text-sm text-status-warning-ink">
            <Info className="mt-0.5 size-4 shrink-0" aria-hidden />
            <div className="min-w-0 space-y-2">
              <p>
                <strong className="font-semibold">Estos cálculos usan valores de partida</strong> (envío {formatMoney(data.envioEstimado)}, margen {formatPct(data.margenMinimoPct)} / {formatPct(data.margenObjetivoPct)}), no los de tu negocio.
                Revísalos y guárdalos para que las recomendaciones sean confiables.
              </p>
              <AjustesPreciosDialog
                trigger={
                  <Button type="button" variant="outline" size="sm">
                    Revisar mis ajustes
                  </Button>
                }
                onGuardado={() => {
                  recargar();
                  onAjustesGuardados();
                }}
              />
            </div>
          </div>
        )}

        <Campo
          id="precio"
          label="Precio de venta (USD)"
          error={errorPrecio}
          ayuda={
            <>
              {data && <>Mínimo para poder publicar: <span className="tabular font-medium text-foreground">{formatMoney(data.piso)}</span>. </>}
              El total del pedido lo calcula el sistema con este precio; Victoria nunca hace la cuenta.
            </>
          }
        >
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-lg font-semibold text-muted-foreground" aria-hidden>
              $
            </span>
            <Input
              id="precio"
              inputMode="decimal"
              autoComplete="off"
              value={precio}
              onChange={(e) => onPrecio(e.target.value)}
              aria-invalid={Boolean(errorPrecio)}
              aria-describedby={descripcionDe("precio", true, errorPrecio)}
              className="tabular max-w-40 text-lg font-semibold"
            />
            {sugerido && montoPrecio !== sugerido && (
              <Button type="button" variant="outline" size="sm" onClick={() => onPrecio(sugerido)}>
                Usar sugerido {formatMoney(sugerido)}
              </Button>
            )}
          </div>
        </Campo>

        {cargando && (
          <div className="space-y-2" aria-busy="true" aria-label="Calculando el precio">
            <Skeleton className="h-14 w-full" />
            <Skeleton className="h-20 w-full" />
          </div>
        )}

        {error && !data && (
          <div role="alert" className="flex items-start gap-2.5 rounded-lg bg-status-danger-soft p-3 text-sm text-status-danger-ink">
            <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
            <div className="space-y-2">
              <p className="font-medium">No se pudo calcular el precio recomendado. {error}</p>
              <Button type="button" variant="outline" size="sm" onClick={recargar}>
                Reintentar
              </Button>
            </div>
          </div>
        )}

        {data && (
          <div className={cn("space-y-4 transition-opacity", actualizando && "opacity-70")}>
            {ev && (
              <p
                className={cn(
                  "rounded-lg p-3 text-sm",
                  esGrave(ev)
                    ? "bg-status-danger-soft text-status-danger-ink"
                    : ev.bajoMargenMinimo
                      ? "bg-status-warning-soft text-status-warning-ink"
                      : "bg-status-success-soft text-status-success-ink",
                )}
              >
                {ev.ganancia.startsWith("-") ? (
                  <>
                    Con {formatMoney(ev.precio)}, por cada unidad <strong className="font-semibold">pierdes</strong>{" "}
                    <strong className="tabular font-semibold">{formatMoney(ev.ganancia.slice(1))}</strong>
                  </>
                ) : (
                  <>
                    Con {formatMoney(ev.precio)}, por cada unidad te quedan{" "}
                    <strong className="tabular font-semibold">{formatMoney(ev.ganancia)}</strong>
                  </>
                )}{" "}
                ({formatPct(ev.margenPct)} del precio), ya descontados el costo, el envío estimado y tus otros costos.
              </p>
            )}

            {data.niveles.length > 0 && (
              <div className="space-y-2">
                <p className="text-sm font-medium">Precios recomendados</p>
                <div className="grid gap-2 sm:grid-cols-3">
                  {data.niveles.map((n) => {
                    const seleccionado = montoPrecio === n.precio;
                    return (
                      <button
                        key={n.clave}
                        type="button"
                        aria-pressed={seleccionado}
                        onClick={() => onPrecio(n.precio)}
                        className={cn(
                          "flex min-h-14 flex-col items-start gap-0.5 rounded-lg border p-3 text-left outline-none transition-colors focus-visible:ring-3 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-60",
                          seleccionado ? "border-primary bg-primary/5" : "bg-card hover:bg-muted",
                        )}
                      >
                        <span className="text-xs text-muted-foreground">{n.nombre}</span>
                        <span className="tabular text-lg font-semibold">{formatMoney(n.precio)}</span>
                        <span className="text-xs text-muted-foreground">
                          Ganas <span className="tabular">{formatMoney(n.ganancia)}</span> · {formatPct(n.margenPct)}
                        </span>
                      </button>
                    );
                  })}
                </div>
                <p className="text-xs text-muted-foreground">
                  <strong className="font-medium">Mínimo</strong>: tu margen mínimo ({formatPct(data.margenMinimoPct)}). <strong className="font-medium">Recomendado</strong>: tu margen objetivo ({formatPct(data.margenObjetivoPct)}).
                  {data.niveles.some((n) => n.clave === "premium") && (
                    <>
                      {" "}
                      <strong className="font-medium">Premium</strong>: el precio sugerido por Rocketfy.
                    </>
                  )}
                </p>
              </div>
            )}

            {data.avisos.length > 0 && (
              <div className="flex items-start gap-2.5 rounded-lg bg-status-warning-soft p-3 text-sm text-status-warning-ink">
                <Info className="mt-0.5 size-4 shrink-0" aria-hidden />
                <ul className="min-w-0 list-disc space-y-1 pl-4">
                  {data.avisos.map((a) => (
                    <li key={a}>{a}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        <Campo
          id="precioCompetencia"
          label="Precio de la competencia (USD)"
          opcional
          error={errorCompetencia}
          ayuda="Si miraste cuánto cobra otra tienda por lo mismo, anótalo para compararlo. La app no lo busca ni lo inventa, y Victoria no lo ve."
        >
          <Input
            id="precioCompetencia"
            inputMode="decimal"
            autoComplete="off"
            value={competencia}
            onChange={(e) => onCompetencia(e.target.value)}
            aria-invalid={Boolean(errorCompetencia)}
            aria-describedby={descripcionDe("precioCompetencia", true, errorCompetencia)}
            className="tabular max-w-40"
          />
        </Campo>

        <div className="flex flex-wrap items-center justify-between gap-3 border-t pt-4">
          <p className="min-w-0 text-xs text-muted-foreground">
            {data ? (
              <>
                Calculado con envío {formatMoney(data.envioEstimado)}, margen mínimo {formatPct(data.margenMinimoPct)} y objetivo {formatPct(data.margenObjetivoPct)}
                {Number(data.otrosCostosFijos) > 0 && <>, otros costos {formatMoney(data.otrosCostosFijos)} por unidad</>}
                {Number(data.otrosCostosPct) > 0 && <> y {formatPct(data.otrosCostosPct)} del precio</>}.
              </>
            ) : (
              "Los precios recomendados salen de tus ajustes de precios."
            )}
          </p>
          <AjustesPreciosDialog
            trigger={botonAjustes}
            onGuardado={() => {
              recargar();
              onAjustesGuardados();
            }}
          />
        </div>
      </div>
    </SectionCard>
  );
}
