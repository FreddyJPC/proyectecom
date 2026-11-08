"use client";

import { CircleCheck, History, Info, Loader2, RefreshCw, TriangleAlert } from "lucide-react";
import { useState, type ReactNode } from "react";
import { toast } from "sonner";

import { InfoButton } from "@/components/app/info-button";
import { SectionCard } from "@/components/app/section-card";
import { Button } from "@/components/ui/button";
import { apiFetch, ApiError } from "@/lib/api";
import { ACCIONES_HISTORIAL, CAMPOS_HISTORIAL, ETIQUETAS_CAMPOS_REDACTABLES, estadoProductoBotInfo } from "@/lib/estados";
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
      info={
        <InfoButton titulo={vendiendo ? "Revisión del producto" : "Antes de publicar"}>
          <p>Es una revisión automática de la ficha: se actualiza sola cada vez que guardas.</p>
          <ul>
            <li>
              <strong>Falta resolver:</strong> {vendiendo ? "datos que conviene corregir; el producto sigue a la venta mientras tanto." : "cosas que impiden publicar el producto. Corrígelas y el botón «Publicar» se habilita."}
            </li>
            <li>
              <strong>Ten en cuenta:</strong> avisos que no impiden {vendiendo ? "vender" : "publicar"}, pero conviene conocer.
            </li>
          </ul>
        </InfoButton>
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
    <SectionCard
      titulo="Datos de Rocketfy"
      descripcion="Del catálogo del proveedor."
      info={
        <InfoButton titulo="Datos de Rocketfy">
          <p>Son datos de solo lectura: el costo, el precio sugerido y el stock los define Rocketfy y aquí no se editan.</p>
          <p>«Actualizar desde Rocketfy» vuelve a leerlos en ese momento. Si tienes cambios sin guardar en la ficha, primero guárdalos o descártalos, porque al actualizar se recarga la ficha.</p>
        </InfoButton>
      }
    >
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

/** Resumen de un producto propio (no está en Rocketfy): lo que se edita está en las secciones de la izquierda. */
export function DatosProductoPropio({ detalle }: { detalle: ProductoBotDetalle }) {
  const sinControl = !detalle.controlaStock;
  return (
    <SectionCard
      titulo="Producto propio"
      descripcion="Resumen de lo que vendes tú."
      info={
        <InfoButton titulo="Producto propio">
          <p>Este producto lo vendes tú, no Rocketfy: cuando un cliente lo compra, el pedido no se crea en Rocketfy sino que te llega a «Por gestionar» para que lo gestiones tú.</p>
          <p>Lo que se edita está en las secciones de la izquierda; aquí solo ves un resumen.</p>
        </InfoButton>
      }
    >
      <dl className="grid grid-cols-2 gap-x-4 gap-y-3 p-4 sm:p-5">
        <Dato label="SKU">
          <span className="tabular break-all">{detalle.sku}</span>
        </Dato>
        <Dato label="Categoría">{detalle.categoria}</Dato>
        <Dato label="Lo que te cuesta">{detalle.costoPropio ? <span className="tabular font-medium">{formatMoney(detalle.costoPropio)}</span> : null}</Dato>
        <Dato label="Stock">
          {sinControl ? (
            <span className="text-muted-foreground">Sin control</span>
          ) : (
            <>
              <span className="tabular">{detalle.stockUltimo ?? "—"}</span>
              {detalle.stockActualizadoEn && <span className="text-xs text-muted-foreground"> · {tiempoRelativo(detalle.stockActualizadoEn)}</span>}
            </>
          )}
        </Dato>
        <Dato label="Envío">
          {detalle.envioIncluido ? "Incluido en el precio" : `Aparte (${detalle.entregas.filter((e) => e.activo).length} ${detalle.entregas.filter((e) => e.activo).length === 1 ? "opción activa" : "opciones activas"})`}
        </Dato>
        <Dato label="Fotos">{detalle.imagenes.length > 0 ? `${detalle.imagenes.length}` : "Ninguna"}</Dato>
      </dl>
    </SectionCard>
  );
}

const CAMPOS_DINERO = new Set(["precio", "costo_rocketfy", "precio_sugerido_rocketfy", "costo_propio", "costo_flete_estimado"]);

function textoDeValor(campo: string, valor: unknown): string {
  if (valor == null || valor === "") return "vacío";
  if (campo === "estado") return estadoProductoBotInfo(String(valor)).label;
  if (typeof valor === "boolean") return valor ? "sí" : "no";
  if (CAMPOS_DINERO.has(campo)) return formatMoney(String(valor));
  return String(valor);
}

// Nombres de columna (como los guarda el historial) -> nombre legible.
const CAMPOS_IA_DEL_HISTORIAL: Record<string, string> = {
  nombre: ETIQUETAS_CAMPOS_REDACTABLES.nombre,
  descripcion: ETIQUETAS_CAMPOS_REDACTABLES.descripcion,
  variantes: ETIQUETAS_CAMPOS_REDACTABLES.variantes,
  preguntas_frecuentes: ETIQUETAS_CAMPOS_REDACTABLES.preguntasFrecuentes,
  temas_no_responder: "Temas que no debe responder",
};

function Cambios({ cambios }: { cambios: Record<string, unknown> }) {
  // «Redactado con IA» guarda qué campos se pidieron, no pares «antes → después».
  if (Array.isArray(cambios.campos)) {
    const nombres = cambios.campos.filter((c): c is string => typeof c === "string").map((c) => CAMPOS_IA_DEL_HISTORIAL[c] ?? c);
    return nombres.length > 0 ? <p className="mt-1 text-xs text-muted-foreground">Campos: {nombres.join(", ")}.</p> : null;
  }
  // Las acciones sin pares «antes → después» (p. ej. "creado") no tienen detalle que mostrar.
  const filas = Object.entries(cambios).filter(([, v]) => Array.isArray(v) && v.length === 2);
  if (filas.length === 0) return null;
  // Los cambios que hace el sistema (p. ej. la pausa por agotado) explican su motivo.
  const motivo = typeof cambios.motivo === "string" ? cambios.motivo : null;
  return (
    <ul className="mt-1 space-y-0.5 text-xs text-muted-foreground">
      {motivo && <li className="break-words">Motivo: {motivo}</li>}
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
    <SectionCard
      titulo="Historial de cambios"
      descripcion="Quién cambió qué y cuándo."
      info={
        <InfoButton titulo="Historial de cambios">
          <p>Aquí queda registrado cada cambio de la ficha, con quién lo hizo y cuándo; lo más reciente va primero. Los cambios que hace el sistema (por ejemplo, pausar un producto agotado) figuran como «Sistema» e indican su motivo.</p>
          <p>
            «Redactado con IA» guarda qué campos se pidieron, no el texto. Lo que propone la IA es un borrador: cuando aceptas y guardas algo, ese cambio aparece aparte como «Editado».
          </p>
        </InfoButton>
      }
    >
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
