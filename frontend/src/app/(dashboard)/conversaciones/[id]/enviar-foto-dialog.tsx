"use client";

import { ImagePlus, Loader2, SendHorizontal, TriangleAlert, Upload } from "lucide-react";
import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from "react";
import { toast } from "sonner";

import { InfoButton } from "@/components/app/info-button";
import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { apiFormulario, ApiError } from "@/lib/api";

import { prepararFoto } from "../../catalogo/producto/[sku]/galeria-fotos";

/** Lo que acepta WhatsApp para una foto (el servidor lo vuelve a revisar). */
const MAXIMO_BYTES = 5 * 1024 * 1024;

/** El dueño elige una foto de su teléfono o computadora (no del catálogo) y se la manda al cliente. La foto se achica y se pasa a
 * JPG en el navegador (también las del iPhone), y el servidor la sube a WhatsApp sin publicarla en ningún enlace abierto. */
export function EnviarFotoDialog({ conversacionId, deshabilitado, onEnviado }: { conversacionId: string; deshabilitado: boolean; onEnviado: () => void }) {
  const [abierto, setAbierto] = useState(false);
  const [foto, setFoto] = useState<Blob | null>(null);
  const [vista, setVista] = useState<string | null>(null);
  const [descripcion, setDescripcion] = useState("");
  const [preparando, setPreparando] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const entrada = useRef<HTMLInputElement>(null);

  // La vista previa es un enlace local del navegador: se libera al cambiar de foto o al cerrar.
  useEffect(() => {
    return () => {
      if (vista) URL.revokeObjectURL(vista);
    };
  }, [vista]);

  function limpiar() {
    setFoto(null);
    setVista(null);
    setDescripcion("");
    setError(null);
    if (entrada.current) entrada.current.value = "";
  }

  function alCambiarApertura(valor: boolean) {
    setAbierto(valor);
    if (!valor) limpiar();
  }

  async function alElegir(e: ChangeEvent<HTMLInputElement>) {
    const archivo = e.target.files?.[0];
    if (!archivo) return;
    setError(null);
    setPreparando(true);
    try {
      let lista: Blob;
      try {
        lista = await prepararFoto(archivo);
      } catch (err) {
        // Si el navegador no la pudo convertir pero ya es JPG o PNG, se manda tal cual.
        if (archivo.type === "image/jpeg" || archivo.type === "image/png") lista = archivo;
        else throw err;
      }
      if (lista.size > MAXIMO_BYTES) throw new Error("La foto pesa más de 5 MB. Elige otra o tómala con menos resolución.");
      setFoto(lista);
      setVista(URL.createObjectURL(lista));
    } catch (err) {
      setFoto(null);
      setVista(null);
      setError(err instanceof Error ? err.message : "No se pudo leer esa foto.");
    } finally {
      setPreparando(false);
    }
  }

  async function enviar(e: FormEvent) {
    e.preventDefault();
    if (!foto) {
      setError("Primero elige una foto.");
      return;
    }
    setEnviando(true);
    setError(null);
    try {
      const datos = new FormData();
      datos.append("archivo", foto, foto.type === "image/png" ? "foto.png" : "foto.jpg");
      if (descripcion.trim()) datos.append("descripcion", descripcion.trim());
      await apiFormulario(`/conversaciones/${conversacionId}/foto`, datos);
      toast.success("Foto enviada.");
      setAbierto(false);
      limpiar();
      onEnviado();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo conectar con el servidor.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Dialog open={abierto} onOpenChange={alCambiarApertura}>
      <DialogTrigger asChild>
        <Button type="button" variant="outline" size="icon-lg" disabled={deshabilitado} aria-label="Enviar una foto de tu teléfono o computadora" title="Enviar una foto de tu teléfono o computadora" className="shrink-0 rounded-full">
          <ImagePlus />
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[92dvh] overflow-y-auto">
        <form onSubmit={(e) => void enviar(e)} noValidate>
          <DialogHeader>
            <div className="flex items-center gap-1 pr-8">
              <DialogTitle>Enviar una foto</DialogTitle>
              <InfoButton titulo="Enviar una foto">
                <p>Elige cualquier foto de tu teléfono o computadora (una guía, un comprobante, una foto que tomaste) y se la mandas al cliente.</p>
                <ul>
                  <li>Solo fotos (JPG o PNG; las del iPhone se convierten solas). Hasta 5 MB.</li>
                  <li>La foto no queda publicada en ningún enlace: se sube directo a WhatsApp.</li>
                  <li>Queda en el chat y la puedes volver a ver mientras WhatsApp la guarde (unos 30 días).</li>
                  <li>Si Victoria atendía este chat, al enviar la foto pasas a atenderlo tú.</li>
                </ul>
              </InfoButton>
            </div>
            <DialogDescription>Elige una foto de tu dispositivo.</DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            <input
              ref={entrada}
              id="foto-propia-archivo"
              type="file"
              accept="image/*"
              aria-label="Elegir una foto de tu dispositivo"
              tabIndex={-1}
              className="sr-only"
              onChange={(e) => void alElegir(e)}
              disabled={preparando || enviando}
            />
            {vista ? (
              <div className="space-y-2">
                {/* eslint-disable-next-line @next/next/no-img-element -- vista previa local (blob) de la foto elegida */}
                <img src={vista} alt="Vista previa de la foto que vas a enviar" className="max-h-72 w-full rounded-lg border bg-muted object-contain" />
                <Button type="button" variant="outline" size="sm" className="h-10" onClick={() => entrada.current?.click()} disabled={enviando}>
                  <Upload /> Elegir otra
                </Button>
              </div>
            ) : (
              <Button
                type="button"
                variant="outline"
                className="h-28 flex-col gap-2 border-dashed"
                onClick={() => entrada.current?.click()}
                disabled={preparando}
              >
                {preparando ? <Loader2 className="size-6 animate-spin" aria-hidden /> : <Upload className="size-6" aria-hidden />}
                {preparando ? "Preparando la foto…" : "Elegir una foto"}
              </Button>
            )}

            <div className="grid gap-1.5">
              <Label htmlFor="foto-propia-descripcion">
                Texto debajo de la foto <span className="font-normal text-muted-foreground">(opcional)</span>
              </Label>
              <Textarea
                id="foto-propia-descripcion"
                rows={2}
                value={descripcion}
                onChange={(e) => setDescripcion(e.target.value)}
                maxLength={1000}
                placeholder="Ej.: Esta es la guía de su pedido"
                disabled={enviando}
              />
            </div>

            {error && (
              <div role="alert" className="flex items-start gap-2 rounded-lg bg-status-danger-soft p-3 text-sm text-status-danger-ink">
                <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
                <p className="min-w-0">{error}</p>
              </div>
            )}
          </div>

          <DialogFooter>
            <DialogClose asChild>
              <Button type="button" variant="outline" disabled={enviando}>
                Cancelar
              </Button>
            </DialogClose>
            <Button type="submit" disabled={!foto || enviando || preparando}>
              {enviando ? <Loader2 className="animate-spin" /> : <SendHorizontal />}
              {enviando ? "Enviando…" : "Enviar foto"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
