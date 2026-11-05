"use client";

import { CircleCheck, History, Info, Loader2, RefreshCw, TriangleAlert } from "lucide-react";
import { useState, type ReactNode } from "react";
import { toast } from "sonner";

import { SectionCard } from "@/components/app/section-card";
import { Button } from "@/components/ui/button";
import { apiFetch, ApiError } from "@/lib/api";
import { ACCIONES_HISTORIAL, CAMPOS_HISTORIAL, estadoProductoBotInfo } from "@/lib/estados";
import { formatFechaHora, formatMoney, tiempoRelativo } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { EntradaHistorial, ProductoBotDetalle, Verificacion } from "@/types/producto-bot";

function Dato({ label, children }: { label: string; children?: ReactNode }) {
  const vacio = children === undefined || children === null || children === "";
  return (
    <div className="space-y-0.5">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className={cn("text-sm", vacio && "text-muted-foreground/70")}>{vacio ? "—" : children}</dd>
    </div>
  );
}

/** Lista de lo que impide vender (bloqueos) y lo que conviene saber (avisos),
 * calculada por el backend con las mismas reglas con que decide publicar. */
export function RevisionPanel({ verificacion, vendiendo }: { verificacion: Verificacion; vendiendo: boolean }) {
  const { bloqueos, avisos } = verificacion;
  const todoBien = bloqueos.length === 0 && avisos.length === 0;

  return (
    <SectionCard
      titulo={vendiendo ? "Revisión del producto" : "Antes de publicar"}
      descripcion={
        bloqueos.length > 0
          ? vendiendo
            ? "Hay datos por corregir; el producto sigue a la venta."
            : "Corrige esto para poder publicar."
          : vendiendo
            ? "Lo que conviene saber de este producto."
            : "Cumple lo mínimo para publicarse."
      }
    >
      <div className="space-y-3 p-4 sm:p-5">
        {todoBien && (
          <p className="flex items-start gap-2.5 rounded-lg bg-status-success-soft p-3 text-sm text-status-success-ink">
            <CircleCheck className="mt-0.5 size-4 shrink-0" aria-hidden />
            Todo en orden: no hay nada pendiente.
          </p>
        )}

        {bloqueos.length > 0 && (
          <div role="alert" className="flex items-start gap-2.5 rounded-lg bg-status-danger-soft p-3 text-sm text-status-danger-ink">
            <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
            <div className="min-w-0 space-y-1">
              <p className="font-medium">{bloqueos.length === 1 ? "Falta resolver 1 cosa" : `Faltan resolver ${bloqueos.length} cosas`}</p>
              <ul className="list-disc space-y-1 pl-4">
                {bloqueos.map((b) => (
                  <li key={b}>{b}</li>
                ))}
              </ul>
            </div>
          </div>
        )}

        {avisos.length > 0 && (
          <div className="flex items-start gap-2.5 rounded-lg bg-status-warning-soft p-3 text-sm text-status-warning-ink">
            <Info className="mt-0.5 size-4 shrink-0" aria-hidden />
            <div className="min-w-0 space-y-1">
              <p className="font-medium">Ten en cuenta</p>
              <ul className="list-disc space-y-1 pl-4">
                {avisos.map((a) => (
                  <li key={a}>{a}</li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </div>
    </SectionCard>
  );
}

/** Lo que dice Rocketfy del producto. Es de solo lectura: el costo y el stock
 * son de Rocketfy; "Actualizar" los vuelve a leer en ese momento. */
export function DatosRocketfy({
  detalle,
  sinCambiosPendientes,
  onActualizado,
}: {
  detalle: ProductoBotDetalle;
  /** Falso si hay ediciones sin guardar: actualizar recargaría la ficha y las perdería. */
  sinCambiosPendientes: boolean;
  onActualizado: () => void;
}) {
  const [actualizando, setActualizando] = useState(false);
  const [imagenFalla, setImagenFalla] = useState(false);

  async function actualizar() {
    setActualizando(true);
    try {
      await apiFetch<ProductoBotDetalle>(`/productos-bot/${encodeURIComponent(detalle.sku)}/actualizar-rocketfy`, { method: "POST" });
      toast.success("Datos de Rocketfy actualizados.");
      onActualizado();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo consultar Rocketfy.");
    } finally {
      setActualizando(false);
    }
  }

  return (
    <SectionCard titulo="Datos de Rocketfy" descripcion="Solo lectura: vienen del catálogo del proveedor.">
      <div className="space-y-4 p-4 sm:p-5">
        <div className="flex items-start gap-4">
          {detalle.imagenUrl && !imagenFalla && (
            // eslint-disable-next-line @next/next/no-img-element -- la imagen viene de un CDN externo de Rocketfy
            <img
              src={detalle.imagenUrl}
              alt={`Foto de ${detalle.nombre}`}
              width={72}
              height={72}
              referrerPolicy="no-referrer"
              onError={() => setImagenFalla(true)}
              className="size-[4.5rem] shrink-0 rounded-lg border bg-muted object-cover"
            />
          )}
          <dl className="grid min-w-0 flex-1 grid-cols-2 gap-x-4 gap-y-3">
            <Dato label="SKU">
              <span className="tabular break-all">{detalle.sku}</span>
            </Dato>
            <Dato label="Tu costo">
              <span className="tabular font-medium">{formatMoney(detalle.costoRocketfy)}</span>
            </Dato>
            <Dato label="Precio sugerido">
              <span className="tabular">{formatMoney(detalle.precioSugeridoRocketfy)}</span>
            </Dato>
            <Dato label="Stock">
              <span className="tabular">{detalle.stockUltimo ?? "—"}</span>
              {detalle.stockActualizadoEn && <span className="text-xs text-muted-foreground"> · {tiempoRelativo(detalle.stockActualizadoEn)}</span>}
            </Dato>
            <Dato label="Peso">{detalle.pesoKg ? <span className="tabular">{detalle.pesoKg} kg</span> : null}</Dato>
            <Dato label="ID en Rocketfy">{detalle.rocketfyProductId ? <span className="tabular">{detalle.rocketfyProductId}</span> : null}</Dato>
          </dl>
        </div>

        <div className="space-y-2 border-t pt-4">
          <Button variant="outline" size="sm" onClick={actualizar} disabled={actualizando || !sinCambiosPendientes} className="w-full sm:w-auto">
            {actualizando ? <Loader2 className="animate-spin" /> : <RefreshCw />}
            {actualizando ? "Consultando Rocketfy…" : "Actualizar desde Rocketfy"}
          </Button>
          {!sinCambiosPendientes && <p className="text-xs text-muted-foreground">Guarda o descarta tus cambios antes de actualizar.</p>}
        </div>
      </div>
    </SectionCard>
  );
}

const CAMPOS_DINERO = new Set(["precio", "costo_rocketfy", "precio_sugerido_rocketfy"]);

function textoDeValor(campo: string, valor: unknown): string {
  if (valor == null || valor === "") return "vacío";
  if (campo === "estado") return estadoProductoBotInfo(String(valor)).label;
  if (CAMPOS_DINERO.has(campo)) return formatMoney(String(valor));
  return String(valor);
}

function Cambios({ cambios }: { cambios: Record<string, unknown> }) {
  // Las acciones sin pares «antes → después» (p. ej. "creado") no tienen detalle que mostrar.
  const filas = Object.entries(cambios).filter(([, v]) => Array.isArray(v) && v.length === 2);
  if (filas.length === 0) return null;
  return (
    <ul className="mt-1 space-y-0.5 text-xs text-muted-foreground">
      {filas.map(([campo, par]) => {
        const [antes, despues] = par as [unknown, unknown];
        return (
          <li key={campo} className="break-words">
            <span className="font-medium text-foreground/80">{CAMPOS_HISTORIAL[campo] ?? campo}:</span> {textoDeValor(campo, antes)} → {textoDeValor(campo, despues)}
          </li>
        );
      })}
    </ul>
  );
}

const HISTORIAL_VISIBLE = 6;

/** Quién cambió qué y cuándo (lo más reciente primero). */
export function HistorialCard({ historial }: { historial: EntradaHistorial[] }) {
  const [todo, setTodo] = useState(false);
  const visibles = todo ? historial : historial.slice(0, HISTORIAL_VISIBLE);

  return (
    <SectionCard titulo="Historial de cambios" descripcion="Quién cambió qué y cuándo.">
      {historial.length === 0 ? (
        <p className="flex items-center gap-2 p-4 text-sm text-muted-foreground sm:p-5">
          <History className="size-4" aria-hidden /> Todavía no hay cambios registrados.
        </p>
      ) : (
        <>
          <ol className="divide-y">
            {visibles.map((h, i) => (
              <li key={`${h.creadoEn}-${i}`} className="px-4 py-3 sm:px-5">
                <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                  <p className="text-sm font-medium">{ACCIONES_HISTORIAL[h.accion] ?? h.accion}</p>
                  <p className="text-xs text-muted-foreground">{formatFechaHora(h.creadoEn)}</p>
                </div>
                <p className="text-xs text-muted-foreground">{h.usuario ?? "Sistema"}</p>
                {h.cambios && <Cambios cambios={h.cambios} />}
              </li>
            ))}
          </ol>
          {historial.length > HISTORIAL_VISIBLE && (
            <div className="border-t p-2">
              <Button variant="ghost" size="sm" className="w-full" onClick={() => setTodo((v) => !v)}>
                {todo ? "Ver menos" : `Ver los ${historial.length} cambios`}
              </Button>
            </div>
          )}
        </>
      )}
    </SectionCard>
  );
}
