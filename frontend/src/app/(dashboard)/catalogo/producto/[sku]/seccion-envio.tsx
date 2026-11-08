"use client";

import { Copy, Loader2, TriangleAlert } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { SectionCard } from "@/components/app/section-card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useApi } from "@/hooks/use-api";
import { apiFetch, ApiError } from "@/lib/api";
import { normalizarMonto } from "@/lib/format";
import type { ProductoBotDetalle, ProductoBotResumen } from "@/types/producto-bot";

import { EditorEntregas, aOpciones, desdeOpciones } from "../../editor-entregas";

/** Resumen de lo guardado, para saber si lo editado cambió algo. */
function firma(d: ProductoBotDetalle): string {
  return JSON.stringify([d.envioIncluido, d.costoFleteEstimado, d.entregas]);
}

/** El envío de este producto (ADR-012): incluido en el precio o con opciones propias (envío, retiro, costo y a
 * quién aplica). Se guarda aparte del resto de la ficha, con su propio botón. */
export function SeccionEnvio({ detalle, sinCambiosPendientes, onCambio }: { detalle: ProductoBotDetalle; sinCambiosPendientes: boolean; onCambio: () => void }) {
  const soloLectura = detalle.estado === "archivado";
  const [incluido, setIncluido] = useState(detalle.envioIncluido);
  const [entregas, setEntregas] = useState(() => desdeOpciones(detalle.entregas));
  const [flete, setFlete] = useState(detalle.costoFleteEstimado ?? "");
  const [intento, setIntento] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<{ mensaje: string; motivos: string[] } | null>(null);
  const [origen, setOrigen] = useState<string>("");

  const productos = useApi<ProductoBotResumen[]>("/productos-bot");
  const candidatos = (productos.data ?? []).filter((p) => p.sku !== detalle.sku && !p.envioIncluido);

  const { opciones, errores } = aOpciones(entregas);
  const fleteNormalizado = flete.trim() === "" ? null : normalizarMonto(flete, true);
  const errorFlete = incluido && flete.trim() !== "" && fleteNormalizado === null ? "Escribe un monto válido, por ejemplo 4.50." : undefined;
  const hayErrores = (!incluido && errores.some(Boolean)) || Boolean(errorFlete);

  // ¿Lo editado difiere de lo guardado?
  const guardadoComoOpciones = aOpciones(desdeOpciones(detalle.entregas)).opciones;
  const cambioEntregas = !incluido && JSON.stringify(opciones) !== JSON.stringify(guardadoComoOpciones);
  const cambioIncluido = incluido !== detalle.envioIncluido;
  const cambioFlete = incluido && (fleteNormalizado ?? null) !== (detalle.costoFleteEstimado ?? null);
  const hayCambios = cambioEntregas || cambioIncluido || cambioFlete;

  async function guardar() {
    setIntento(true);
    setError(null);
    if (hayErrores) return;
    setGuardando(true);
    const ruta = `/productos-bot/${encodeURIComponent(detalle.sku)}`;
    try {
      if (!incluido) {
        // Primero las opciones y después marcar «cobrar aparte»: así un producto a la venta nunca queda sin envío definido.
        if (cambioEntregas || cambioIncluido) {
          await apiFetch<ProductoBotDetalle>(`${ruta}/entregas`, { method: "PUT", body: JSON.stringify({ entregas: opciones }) });
        }
        if (cambioIncluido) await apiFetch<ProductoBotDetalle>(ruta, { method: "PATCH", body: JSON.stringify({ envioIncluido: false }) });
      } else if (cambioIncluido || cambioFlete) {
        await apiFetch<ProductoBotDetalle>(ruta, {
          method: "PATCH",
          body: JSON.stringify({ ...(cambioIncluido ? { envioIncluido: true } : {}), ...(cambioFlete ? { costoFleteEstimado: fleteNormalizado } : {}) }),
        });
      }
      toast.success("Envío guardado.");
      onCambio();
    } catch (err) {
      setError(err instanceof ApiError ? { mensaje: err.message, motivos: err.bloqueos } : { mensaje: "No se pudo conectar con el servidor.", motivos: [] });
    } finally {
      setGuardando(false);
    }
  }

  async function copiar() {
    if (!origen) return;
    setGuardando(true);
    setError(null);
    try {
      await apiFetch<ProductoBotDetalle>(`/productos-bot/${encodeURIComponent(detalle.sku)}/entregas/copiar`, { method: "POST", body: JSON.stringify({ desdeSku: origen }) });
      if (detalle.envioIncluido) await apiFetch<ProductoBotDetalle>(`/productos-bot/${encodeURIComponent(detalle.sku)}`, { method: "PATCH", body: JSON.stringify({ envioIncluido: false }) });
      toast.success("Opciones de envío copiadas.");
      onCambio();
    } catch (err) {
      setError(err instanceof ApiError ? { mensaje: err.message, motivos: err.bloqueos } : { mensaje: "No se pudo copiar el envío.", motivos: [] });
    } finally {
      setGuardando(false);
    }
  }

  function descartar() {
    setIncluido(detalle.envioIncluido);
    setEntregas(desdeOpciones(detalle.entregas));
    setFlete(detalle.costoFleteEstimado ?? "");
    setIntento(false);
    setError(null);
  }

  return (
    <SectionCard titulo="Envío" descripcion="Cómo se entrega ESTE producto y cuánto se cobra. Cada producto tiene el suyo.">
      <div className="space-y-4 p-4 sm:p-5">
        <EditorEntregas
          envioIncluido={incluido}
          onEnvioIncluido={setIncluido}
          entregas={entregas}
          onEntregas={setEntregas}
          errores={intento ? errores : []}
          costoFlete={flete}
          onCostoFlete={setFlete}
          errorFlete={intento ? errorFlete : undefined}
          deshabilitado={soloLectura || guardando}
        />

        {!soloLectura && !incluido && candidatos.length > 0 && (
          <div className="flex flex-wrap items-end gap-2 border-t pt-4">
            <div className="grid min-w-0 gap-1.5">
              <Label htmlFor="copiar-envio">Copiar el envío de otro producto</Label>
              <Select value={origen} onValueChange={setOrigen} disabled={guardando || hayCambios}>
                <SelectTrigger id="copiar-envio" className="w-full sm:w-72">
                  <SelectValue placeholder="Elige un producto" />
                </SelectTrigger>
                <SelectContent>
                  {candidatos.map((p) => (
                    <SelectItem key={p.sku} value={p.sku}>
                      {p.nombre}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button type="button" variant="outline" size="sm" disabled={!origen || guardando || hayCambios} onClick={() => void copiar()}>
              <Copy /> Copiar
            </Button>
            {hayCambios && <p className="basis-full text-xs text-muted-foreground">Guarda o descarta tus cambios de envío antes de copiar.</p>}
          </div>
        )}

        {error && (
          <div role="alert" className="flex items-start gap-2.5 rounded-lg bg-status-danger-soft p-3 text-sm text-status-danger-ink">
            <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
            <div className="min-w-0 space-y-1">
              <p className="font-medium">{error.mensaje}</p>
              {error.motivos.length > 0 && (
                <ul className="list-disc space-y-1 pl-4">
                  {error.motivos.map((m) => (
                    <li key={m}>{m}</li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}

        {!soloLectura && (
          <div className="flex flex-wrap items-center justify-end gap-2 border-t pt-4">
            {!sinCambiosPendientes && hayCambios && <p className="mr-auto text-xs text-muted-foreground">El envío se guarda aparte del resto de la ficha.</p>}
            <Button type="button" variant="outline" disabled={!hayCambios || guardando} onClick={descartar}>
              Descartar
            </Button>
            <Button type="button" disabled={!hayCambios || guardando} onClick={() => void guardar()}>
              {guardando ? (
                <>
                  <Loader2 className="animate-spin" /> Guardando…
                </>
              ) : (
                "Guardar envío"
              )}
            </Button>
          </div>
        )}
      </div>
    </SectionCard>
  );
}

export { firma as firmaDelEnvio };
