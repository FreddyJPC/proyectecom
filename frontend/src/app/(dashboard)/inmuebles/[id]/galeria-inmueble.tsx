"use client";

import { ArrowLeftToLine, Clapperboard, ImagePlus, Loader2, Trash2, TriangleAlert } from "lucide-react";
import { useRef, useState, type ChangeEvent } from "react";
import { toast } from "sonner";

import { InfoButton } from "@/components/app/info-button";
import { SectionCard } from "@/components/app/section-card";
import { Button } from "@/components/ui/button";
import { apiFetch, ApiError } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";
import type { InmuebleDetalle, MaterialInmueble } from "@/types/inmueble";

import { BUCKET, esVideo, prepararFoto, revisarVideo } from "../../catalogo/producto/[sku]/galeria-fotos";

/** Máximo de fotos y videos por propiedad (espejo de `MAXIMO_MATERIAL` del backend). */
const MAXIMO = 20;

/** Las fotos y videos de la propiedad: los mismos cuidados que la galería de un producto (fotos reducidas a JPG, videos MP4 de
 * hasta 16 MB), en la carpeta de la propiedad dentro del bucket «productos». */
export function GaleriaInmueble({ inmueble, onCambio }: { inmueble: InmuebleDetalle; onCambio: () => void }) {
  const entrada = useRef<HTMLInputElement>(null);
  const [trabajando, setTrabajando] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const material = [...inmueble.material].sort((a, b) => a.orden - b.orden);
  const ruta = `/inmuebles/${inmueble.id}`;

  async function subir(e: ChangeEvent<HTMLInputElement>) {
    const archivos = Array.from(e.target.files ?? []);
    e.target.value = "";
    if (archivos.length === 0) return;
    setError(null);
    const supabase = createClient();
    let subidas = 0;
    for (const archivo of archivos.slice(0, MAXIMO - material.length)) {
      setTrabajando(`Subiendo ${archivo.name}…`);
      let rutaArchivo: string | null = null;
      try {
        const video = archivo.type.startsWith("video/") || /\.(mp4|3gp|mov)$/i.test(archivo.name);
        const extension = video ? revisarVideo(archivo) : "jpg";
        const contenido: Blob = video ? archivo : await prepararFoto(archivo);
        rutaArchivo = `${inmueble.carpeta}/${crypto.randomUUID()}.${extension}`;
        const { error: errorSubida } = await supabase.storage
          .from(BUCKET)
          .upload(rutaArchivo, contenido, { contentType: video ? archivo.type : "image/jpeg", upsert: false });
        if (errorSubida) throw new Error(errorSubida.message);
        await apiFetch(`${ruta}/material`, { method: "POST", body: JSON.stringify({ storagePath: rutaArchivo }) });
        subidas += 1;
      } catch (err) {
        if (rutaArchivo) void supabase.storage.from(BUCKET).remove([rutaArchivo]);
        setError(err instanceof ApiError ? err.message : err instanceof Error ? err.message : "No se pudo subir el archivo.");
        break;
      }
    }
    setTrabajando(null);
    if (subidas > 0) {
      toast.success(subidas === 1 ? "Archivo subido." : `${subidas} archivos subidos.`);
      onCambio();
    }
  }

  async function primero(m: MaterialInmueble) {
    setTrabajando("Guardando el orden…");
    try {
      await apiFetch(`${ruta}/material/orden`, { method: "PUT", body: JSON.stringify({ ids: [m.id, ...material.filter((x) => x.id !== m.id).map((x) => x.id)] }) });
      onCambio();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo cambiar el orden.");
    } finally {
      setTrabajando(null);
    }
  }

  async function quitar(m: MaterialInmueble) {
    setTrabajando("Quitando el archivo…");
    try {
      await apiFetch(`${ruta}/material/${m.id}`, { method: "DELETE" });
      void createClient().storage.from(BUCKET).remove([m.storagePath]);
      toast.success("Archivo quitado.");
      onCambio();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo quitar el archivo.");
    } finally {
      setTrabajando(null);
    }
  }

  return (
    <SectionCard
      titulo="Fotos y videos"
      descripcion="Lo que el asistente manda cuando piden ver la propiedad."
      info={
        <InfoButton titulo="Fotos y videos">
          <p>El asistente las manda en este orden cuando el cliente pide fotos o videos, sin repetir lo que ya le mandó. La primera es la portada.</p>
          <ul>
            <li>Las fotos se reducen y se convierten a JPG al subirlas.</li>
            <li>Los videos deben ser MP4 (o 3GP) de hasta 16 MB: un .MOV del iPhone no sirve.</li>
            <li>Hasta {MAXIMO} archivos por propiedad.</li>
          </ul>
        </InfoButton>
      }
    >
      <div className="space-y-4 p-4 sm:p-5">
        {material.length === 0 ? (
          <p className="rounded-lg bg-muted/50 p-3 text-sm text-muted-foreground">Todavía no hay fotos ni videos.</p>
        ) : (
          <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            {material.map((m, i) => {
              const video = esVideo(m);
              const nombre = `${video ? "Video" : "Foto"} ${i + 1} de ${material.length}`;
              return (
                <li key={m.id} className="space-y-2 rounded-xl border bg-card p-2">
                  <div className="relative aspect-square overflow-hidden rounded-lg border bg-muted">
                    {video ? (
                      <video src={m.url} aria-label={nombre} controls muted playsInline preload="metadata" className="size-full bg-black object-contain" />
                    ) : (
                      // eslint-disable-next-line @next/next/no-img-element -- la foto viene del bucket público de Supabase
                      <img src={m.url} alt={nombre} loading="lazy" className="size-full object-cover" />
                    )}
                    {i === 0 && <span className="absolute top-1.5 left-1.5 rounded-full bg-primary px-2 py-0.5 text-[0.7rem] font-medium text-primary-foreground">Portada</span>}
                    {video && (
                      <span className="absolute top-1.5 right-1.5 flex items-center gap-1 rounded-full bg-foreground/80 px-2 py-0.5 text-[0.7rem] font-medium text-background">
                        <Clapperboard className="size-3" aria-hidden /> Video
                      </span>
                    )}
                  </div>
                  <div className="flex items-center justify-between gap-1">
                    <Button type="button" variant="ghost" size="sm" disabled={trabajando !== null || i === 0} onClick={() => void primero(m)} aria-label={`Poner primero ${nombre}`}>
                      <ArrowLeftToLine /> Primero
                    </Button>
                    <Button type="button" variant="ghost" size="icon" disabled={trabajando !== null} onClick={() => void quitar(m)} aria-label={`Quitar ${nombre}`}>
                      <Trash2 />
                    </Button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
        <div className="flex flex-wrap items-center gap-3">
          <input ref={entrada} type="file" accept="image/jpeg,image/png,image/webp,image/heic,image/heif,video/mp4,video/3gpp" multiple className="sr-only" tabIndex={-1} aria-hidden onChange={(e) => void subir(e)} />
          <Button type="button" variant="outline" disabled={trabajando !== null || material.length >= MAXIMO} onClick={() => entrada.current?.click()}>
            {trabajando ? <Loader2 className="animate-spin" /> : <ImagePlus />}
            {trabajando ?? "Subir fotos o videos"}
          </Button>
          <p className="text-xs text-muted-foreground">
            {material.length} de {MAXIMO} archivos.
          </p>
        </div>
        {error && (
          <p role="alert" className="flex items-start gap-2 rounded-lg bg-status-danger-soft p-3 text-sm text-status-danger-ink">
            <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
            {error}
          </p>
        )}
      </div>
    </SectionCard>
  );
}
