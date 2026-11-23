"use client";

import { FileText, Film, Loader2, Paperclip, SendHorizontal, TriangleAlert, Upload } from "lucide-react";
import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from "react";
import { toast } from "sonner";

import { InfoButton } from "@/components/app/info-button";
import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { apiFormulario, ApiError } from "@/lib/api";

import { prepararFoto } from "../../catalogo/producto/[sku]/galeria-fotos";

const MB = 1024 * 1024;
/** Lo que acepta WhatsApp (el servidor lo vuelve a revisar por el contenido del archivo). */
const MAXIMO_FOTO = 5 * MB;
const MAXIMO_OTROS = 16 * MB;
const ACEPTADOS = "image/*,application/pdf,video/mp4,video/3gpp,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.mp4";
const EXTENSIONES_DOCUMENTO = /\.(pdf|docx?|xlsx?|pptx?)$/i;

type Clase = "foto" | "video" | "documento";

interface Elegido {
  datos: Blob;
  nombre: string;
  clase: Clase;
  vista: string | null; // enlace local para ver la foto antes de enviarla
}

function claseDe(archivo: File): Clase | null {
  if (archivo.type.startsWith("image/")) return "foto";
  if (archivo.type === "video/mp4" || archivo.type === "video/3gpp" || /\.(mp4|3gp)$/i.test(archivo.name)) return "video";
  if (archivo.type === "application/pdf" || EXTENSIONES_DOCUMENTO.test(archivo.name)) return "documento";
  if (archivo.type === "video/quicktime" || /\.mov$/i.test(archivo.name)) throw new Error("Los videos .MOV (iPhone) no los acepta WhatsApp: envíalo como MP4.");
  return null;
}

function tamano(bytes: number) {
  return bytes >= MB ? `${(bytes / MB).toFixed(1).replace(".", ",")} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

/** El dueño elige un archivo de su teléfono o computadora (una foto, un video o un documento como un catálogo en PDF) y se lo
 * manda al cliente. Las fotos se achican y se pasan a JPG en el navegador (también las del iPhone). El servidor sube el archivo a
 * WhatsApp sin publicarlo en ningún enlace abierto. */
export function EnviarArchivoDialog({ conversacionId, deshabilitado, onEnviado }: { conversacionId: string; deshabilitado: boolean; onEnviado: () => void }) {
  const [abierto, setAbierto] = useState(false);
  const [elegido, setElegido] = useState<Elegido | null>(null);
  const [descripcion, setDescripcion] = useState("");
  const [preparando, setPreparando] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const entrada = useRef<HTMLInputElement>(null);

  // La vista previa es un enlace local del navegador: se libera al cambiar de archivo o al cerrar.
  useEffect(() => {
    const vista = elegido?.vista;
    return () => {
      if (vista) URL.revokeObjectURL(vista);
    };
  }, [elegido]);

  function limpiar() {
    setElegido(null);
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
      const clase = claseDe(archivo);
      if (!clase) throw new Error("Ese tipo de archivo no se puede enviar. Se aceptan fotos, PDF, Word, Excel, PowerPoint o videos MP4.");
      let datos: Blob = archivo;
      let nombre = archivo.name;
      if (clase === "foto") {
        try {
          datos = await prepararFoto(archivo);
          nombre = nombre.replace(/\.[^.]+$/, "") + ".jpg";
        } catch (err) {
          // Si el navegador no la pudo convertir pero ya es JPG o PNG, se manda tal cual.
          if (archivo.type !== "image/jpeg" && archivo.type !== "image/png") throw err;
        }
      }
      const limite = clase === "foto" ? MAXIMO_FOTO : MAXIMO_OTROS;
      if (datos.size > limite) throw new Error(`El archivo pesa más de ${limite / MB} MB: WhatsApp no lo acepta.`);
      setElegido({ datos, nombre, clase, vista: clase === "foto" ? URL.createObjectURL(datos) : null });
    } catch (err) {
      setElegido(null);
      setError(err instanceof Error ? err.message : "No se pudo leer ese archivo.");
      if (entrada.current) entrada.current.value = "";
    } finally {
      setPreparando(false);
    }
  }

  async function enviar(e: FormEvent) {
    e.preventDefault();
    if (!elegido) {
      setError("Primero elige un archivo.");
      return;
    }
    setEnviando(true);
    setError(null);
    try {
      const datos = new FormData();
      datos.append("archivo", elegido.datos, elegido.nombre);
      if (descripcion.trim()) datos.append("descripcion", descripcion.trim());
      await apiFormulario(`/conversaciones/${conversacionId}/archivo`, datos);
      toast.success(elegido.clase === "foto" ? "Foto enviada." : elegido.clase === "video" ? "Video enviado." : "Archivo enviado.");
      setAbierto(false);
      limpiar();
      onEnviado();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo conectar con el servidor.");
    } finally {
      setEnviando(false);
    }
  }

  const Icono = elegido?.clase === "video" ? Film : FileText;

  return (
    <Dialog open={abierto} onOpenChange={alCambiarApertura}>
      <DialogTrigger asChild>
        <Button
          type="button"
          variant="outline"
          size="icon-lg"
          disabled={deshabilitado}
          aria-label="Enviar un archivo de tu teléfono o computadora"
          title="Enviar un archivo (foto, PDF, documento o video)"
          className="shrink-0 rounded-full"
        >
          <Paperclip />
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[92dvh] overflow-y-auto">
        <form onSubmit={(e) => void enviar(e)} noValidate>
          <DialogHeader>
            <div className="flex items-center gap-1 pr-8">
              <DialogTitle>Enviar un archivo</DialogTitle>
              <InfoButton titulo="Enviar un archivo">
                <p>Elige un archivo de tu teléfono o computadora y se lo mandas al cliente: un catálogo en PDF, una guía, un comprobante, una foto o un video.</p>
                <ul>
                  <li>Fotos (JPG o PNG; las del iPhone se convierten solas): hasta 5 MB.</li>
                  <li>PDF, Word, Excel, PowerPoint y videos MP4: hasta 16 MB. Los videos .MOV del iPhone no los acepta WhatsApp.</li>
                  <li>El archivo no queda publicado en ningún enlace: se sube directo a WhatsApp.</li>
                  <li>Queda en el chat y lo puedes volver a abrir mientras WhatsApp lo guarde (unos 30 días).</li>
                  <li>Si Victoria atendía este chat, al enviar el archivo pasas a atenderlo tú.</li>
                </ul>
              </InfoButton>
            </div>
            <DialogDescription>Foto, PDF, documento o video de tu dispositivo.</DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            <input
              ref={entrada}
              id="archivo-propio"
              type="file"
              accept={ACEPTADOS}
              aria-label="Elegir un archivo de tu dispositivo"
              tabIndex={-1}
              className="sr-only"
              onChange={(e) => void alElegir(e)}
              disabled={preparando || enviando}
            />
            {elegido ? (
              <div className="space-y-2">
                {elegido.vista ? (
                  // eslint-disable-next-line @next/next/no-img-element -- vista previa local (blob) de la foto elegida
                  <img src={elegido.vista} alt="Vista previa de la foto que vas a enviar" className="max-h-72 w-full rounded-lg border bg-muted object-contain" />
                ) : (
                  <div className="flex items-center gap-3 rounded-lg border bg-muted/40 p-3">
                    <Icono className="size-8 shrink-0 text-muted-foreground" aria-hidden />
                    <div className="min-w-0">
                      <p className="truncate font-medium">{elegido.nombre}</p>
                      <p className="text-sm text-muted-foreground">{tamano(elegido.datos.size)}</p>
                    </div>
                  </div>
                )}
                <Button type="button" variant="outline" size="sm" className="h-10" onClick={() => entrada.current?.click()} disabled={enviando}>
                  <Upload /> Elegir otro
                </Button>
              </div>
            ) : (
              <Button type="button" variant="outline" className="h-28 flex-col gap-2 border-dashed" onClick={() => entrada.current?.click()} disabled={preparando}>
                {preparando ? <Loader2 className="size-6 animate-spin" aria-hidden /> : <Upload className="size-6" aria-hidden />}
                {preparando ? "Preparando el archivo…" : "Elegir un archivo"}
              </Button>
            )}

            <div className="grid gap-1.5">
              <Label htmlFor="archivo-propio-descripcion">
                Texto que acompaña al archivo <span className="font-normal text-muted-foreground">(opcional)</span>
              </Label>
              <Textarea
                id="archivo-propio-descripcion"
                rows={2}
                value={descripcion}
                onChange={(e) => setDescripcion(e.target.value)}
                maxLength={1000}
                placeholder="Ej.: Le comparto nuestro catálogo"
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
            <Button type="submit" disabled={!elegido || enviando || preparando}>
              {enviando ? <Loader2 className="animate-spin" /> : <SendHorizontal />}
              {enviando ? "Enviando…" : "Enviar"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
