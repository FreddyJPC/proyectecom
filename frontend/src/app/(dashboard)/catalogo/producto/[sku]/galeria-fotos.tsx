"use client";

import { ArrowLeftToLine, Clapperboard, ImagePlus, Loader2, Trash2, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { useRef, useState, type ChangeEvent } from "react";
import { toast } from "sonner";

import { InfoAviso, InfoButton } from "@/components/app/info-button";
import { SectionCard } from "@/components/app/section-card";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { apiFetch, ApiError } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";
import type { ImagenProducto, ProductoBotDetalle } from "@/types/producto-bot";

/** Bucket público de Supabase Storage donde viven las fotos de los productos (migración 021). */
export const BUCKET = "productos";
/** Máximo de fotos y videos por producto (espejo de `MAXIMO_POR_PRODUCTO` en el backend). */
const MAXIMO_FOTOS = 12;
/** WhatsApp solo envía video MP4 o 3GP de hasta 16 MB (el mismo límite tiene el bucket, migración 036). */
const TIPOS_VIDEO: Record<string, string> = { "video/mp4": "mp4", "video/3gpp": "3gp" };
const MAXIMO_VIDEO_MB = 16;

export function esVideo(material: { tipo?: string; storagePath: string }): boolean {
  return material.tipo === "video" || /\.(mp4|3gp)$/i.test(material.storagePath);
}

/** Revisa un video antes de subirlo: el formato y el peso que WhatsApp acepta. Devuelve la extensión o lanza un error claro. */
export function revisarVideo(archivo: File): string {
  const extension = TIPOS_VIDEO[archivo.type];
  if (!extension) {
    const esMov = archivo.type === "video/quicktime" || /\.mov$/i.test(archivo.name);
    throw new Error(
      esMov
        ? `«${archivo.name}» es un video .MOV (del iPhone) y WhatsApp no lo acepta. Conviértelo a MP4 o grábalo con otra app y vuelve a subirlo.`
        : `«${archivo.name}» no es un video MP4. WhatsApp solo acepta videos MP4 o 3GP.`,
    );
  }
  if (archivo.size > MAXIMO_VIDEO_MB * 1024 * 1024) {
    const mb = (archivo.size / 1024 / 1024).toFixed(1).replace(".", ",");
    throw new Error(`«${archivo.name}» pesa ${mb} MB y WhatsApp acepta hasta ${MAXIMO_VIDEO_MB} MB. Grábalo más corto o en menor calidad (720p).`);
  }
  return extension;
}
/** WhatsApp muestra fotos de ~1600 px sin problema y las del celular pesan varios MB: se reducen antes de subir. */
const LADO_MAXIMO = 1600;
const CALIDAD_JPEG = 0.85;

/** Reduce la foto y la convierte a JPEG (WhatsApp solo acepta JPEG y PNG; el celular puede dar HEIC o fotos enormes). */
export async function prepararFoto(archivo: File): Promise<Blob> {
  let imagen: ImageBitmap;
  try {
    imagen = await createImageBitmap(archivo, { imageOrientation: "from-image" });
  } catch {
    throw new Error("No se pudo leer esa imagen. Prueba con una foto JPG o PNG.");
  }
  const escala = Math.min(1, LADO_MAXIMO / Math.max(imagen.width, imagen.height));
  const ancho = Math.max(1, Math.round(imagen.width * escala));
  const alto = Math.max(1, Math.round(imagen.height * escala));
  const lienzo = document.createElement("canvas");
  lienzo.width = ancho;
  lienzo.height = alto;
  const ctx = lienzo.getContext("2d");
  if (!ctx) throw new Error("Tu navegador no puede preparar la foto.");
  // Fondo blanco: un PNG con transparencia no debe quedar negro al pasar a JPEG.
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, ancho, alto);
  ctx.drawImage(imagen, 0, 0, ancho, alto);
  imagen.close();
  return new Promise((resolver, rechazar) => {
    lienzo.toBlob((blob) => (blob ? resolver(blob) : rechazar(new Error("No se pudo preparar la foto."))), "image/jpeg", CALIDAD_JPEG);
  });
}

function Miniatura({ foto, indice, total, deshabilitado, ocupada, onPrincipal, onQuitar }: {
  foto: ImagenProducto;
  indice: number;
  total: number;
  deshabilitado: boolean;
  ocupada: boolean;
  onPrincipal: () => void;
  onQuitar: () => void;
}) {
  const [falla, setFalla] = useState(false);
  const video = esVideo(foto);
  const nombre = `${video ? "Video" : "Foto"} ${indice + 1} de ${total}`;
  return (
    <li className="space-y-2 rounded-xl border bg-card p-2">
      <div className="relative aspect-square overflow-hidden rounded-lg border bg-muted">
        {falla ? (
          <p className="flex size-full items-center justify-center p-2 text-center text-xs text-muted-foreground">No se pudo mostrar {video ? "el video" : "la foto"}</p>
        ) : video ? (
          <video src={foto.url} aria-label={nombre} controls muted playsInline preload="metadata" onError={() => setFalla(true)} className="size-full bg-black object-contain" />
        ) : (
          // eslint-disable-next-line @next/next/no-img-element -- la foto viene del bucket público de Supabase
          <img src={foto.url} alt={nombre} loading="lazy" onError={() => setFalla(true)} className="size-full object-cover" />
        )}
        {indice === 0 && (
          <span className="absolute top-1.5 left-1.5 rounded-full bg-primary px-2 py-0.5 text-[0.7rem] font-medium text-primary-foreground">Principal</span>
        )}
        {video && (
          <span className="absolute top-1.5 right-1.5 flex items-center gap-1 rounded-full bg-foreground/80 px-2 py-0.5 text-[0.7rem] font-medium text-background">
            <Clapperboard className="size-3" aria-hidden /> Video
          </span>
        )}
      </div>
      <div className="flex items-center justify-between gap-1">
        <Button type="button" variant="ghost" size="sm" disabled={deshabilitado || ocupada || indice === 0} onClick={onPrincipal} aria-label={`Hacer principal ${video ? "el video" : "la foto"} ${indice + 1}`}>
          <ArrowLeftToLine /> Principal
        </Button>
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button type="button" variant="ghost" size="icon" disabled={deshabilitado || ocupada} aria-label={`Quitar ${video ? "el video" : "la foto"} ${indice + 1}`}>
              <Trash2 />
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>¿Quitar {video ? "este video" : "esta foto"}?</AlertDialogTitle>
              <AlertDialogDescription>Se borra de la galería y del almacenamiento. Victoria dejará de enviarla.</AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancelar</AlertDialogCancel>
              <AlertDialogAction onClick={onQuitar}>Sí, quitar</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </li>
  );
}

/** El material del producto: fotos y videos (ADR-012, entrega 2; videos desde la entrada 0.0.163). Se suben desde aquí con tu
 * sesión al bucket público de Supabase (las fotos ya reducidas; los videos tal cual, si WhatsApp los acepta); el primero es el
 * principal. Victoria manda TODO el material por WhatsApp cuando el cliente pide fotos o videos. */
export function GaleriaFotos({ detalle, onCambio }: { detalle: ProductoBotDetalle; onCambio: () => void }) {
  const entrada = useRef<HTMLInputElement>(null);
  const [trabajando, setTrabajando] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const soloLectura = detalle.estado === "archivado";
  const fotos = [...detalle.imagenes].sort((a, b) => a.orden - b.orden);
  const lleno = fotos.length >= MAXIMO_FOTOS;
  const ruta = `/productos-bot/${encodeURIComponent(detalle.sku)}`;

  async function subir(e: ChangeEvent<HTMLInputElement>) {
    const archivos = Array.from(e.target.files ?? []);
    e.target.value = ""; // permite volver a elegir el mismo archivo
    if (archivos.length === 0) return;
    setError(null);
    const supabase = createClient();
    let subidas = 0;
    for (const archivo of archivos.slice(0, MAXIMO_FOTOS - fotos.length)) {
      setTrabajando(`Subiendo ${archivo.name}…`);
      let ruta_storage: string | null = null;
      try {
        // Un video se sube tal cual (no se puede reducir en el navegador): solo se revisa que WhatsApp lo acepte.
        const video = archivo.type.startsWith("video/") || /\.(mp4|3gp|mov)$/i.test(archivo.name);
        const extension = video ? revisarVideo(archivo) : "jpg";
        const contenido: Blob = video ? archivo : await prepararFoto(archivo);
        ruta_storage = `${detalle.carpetaFotos}/${crypto.randomUUID()}.${extension}`;
        const { error: errorSubida } = await supabase.storage
          .from(BUCKET)
          .upload(ruta_storage, contenido, { contentType: video ? archivo.type : "image/jpeg", upsert: false });
        if (errorSubida) throw new Error(errorSubida.message);
        await apiFetch<ProductoBotDetalle>(`${ruta}/imagenes`, { method: "POST", body: JSON.stringify({ storagePath: ruta_storage }) });
        subidas += 1;
      } catch (err) {
        // Si el archivo quedó subido pero no se pudo anotar, no se deja huérfano.
        if (ruta_storage) void supabase.storage.from(BUCKET).remove([ruta_storage]);
        setError(err instanceof ApiError ? err.message : err instanceof Error ? err.message : "No se pudo subir el archivo.");
        break;
      }
    }
    if (archivos.length > MAXIMO_FOTOS - fotos.length) toast.info(`Solo caben ${MAXIMO_FOTOS} fotos y videos por producto: se subieron los primeros.`);
    setTrabajando(null);
    if (subidas > 0) {
      toast.success(subidas === 1 ? "Archivo subido." : `${subidas} archivos subidos.`);
      onCambio();
    }
  }

  async function hacerPrincipal(foto: ImagenProducto) {
    setTrabajando("Guardando el orden…");
    setError(null);
    try {
      await apiFetch<ProductoBotDetalle>(`${ruta}/imagenes/orden`, { method: "PUT", body: JSON.stringify({ ids: [foto.id, ...fotos.filter((f) => f.id !== foto.id).map((f) => f.id)] }) });
      onCambio();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo cambiar el orden.");
    } finally {
      setTrabajando(null);
    }
  }

  async function quitar(foto: ImagenProducto) {
    setTrabajando("Quitando el archivo…");
    setError(null);
    try {
      await apiFetch<ProductoBotDetalle>(`${ruta}/imagenes/${foto.id}`, { method: "DELETE" });
      // El archivo se borra con tu sesión; si falla, solo queda un archivo suelto que no se usa.
      void createClient().storage.from(BUCKET).remove([foto.storagePath]);
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
      titulo="Fotos y videos del producto"
      descripcion="El material que Victoria manda por WhatsApp."
      info={
        <InfoButton titulo="Fotos y videos del producto">
          <p>
            Todo lo que subes aquí es material del producto. Cuando el cliente pide fotos o videos (cualquiera de los dos), Victoria
            le manda todo el material, en este orden. El primero es el principal.
          </p>
          <ul>
            <li>No repite lo que ya le mandó al mismo cliente.</li>
            <li>
              Cuántos archivos manda de una vez se cambia en{" "}
              <Link href="/parametros">Parámetros → «Material por envío»</Link>.
            </li>
            <li>Las fotos se reducen y se convierten a JPG al subirlas, para que pesen poco.</li>
            <li>
              Los videos deben ser MP4 (o 3GP) de hasta {MAXIMO_VIDEO_MB} MB: es lo que acepta WhatsApp. Un video .MOV del iPhone no
              sirve; grábalo corto o en 720p si pesa mucho.
            </li>
            <li>Puedes tener hasta {MAXIMO_FOTOS} fotos y videos por producto.</li>
          </ul>
          <p>Si el producto no tiene material y un cliente lo pide, Victoria le dice que por ahora no hay fotos ni videos.</p>
          <InfoAviso>
            <p>El envío por WhatsApp debe estar encendido en el parámetro «Enviar fotos y videos del producto».</p>
          </InfoAviso>
        </InfoButton>
      }
    >
      <div className="space-y-4 p-4 sm:p-5">
        {fotos.length === 0 ? (
          <div className="space-y-3 rounded-lg bg-muted/50 p-3">
            <p className="text-sm text-muted-foreground">Este producto todavía no tiene fotos ni videos. Victoria solo envía lo que subas aquí.</p>
          </div>
        ) : (
          <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            {fotos.map((f, i) => (
              <Miniatura
                key={f.id}
                foto={f}
                indice={i}
                total={fotos.length}
                deshabilitado={soloLectura}
                ocupada={trabajando !== null}
                onPrincipal={() => void hacerPrincipal(f)}
                onQuitar={() => void quitar(f)}
              />
            ))}
          </ul>
        )}

        {!soloLectura && (
          <div className="flex flex-wrap items-center gap-3">
            <input ref={entrada} type="file" accept="image/jpeg,image/png,image/webp,image/heic,image/heif,video/mp4,video/3gpp" multiple className="sr-only" tabIndex={-1} aria-hidden onChange={(e) => void subir(e)} />
            <Button type="button" variant="outline" disabled={trabajando !== null || lleno} onClick={() => entrada.current?.click()}>
              {trabajando ? <Loader2 className="animate-spin" /> : <ImagePlus />}
              {trabajando ?? "Subir fotos o videos"}
            </Button>
            <p className="text-xs text-muted-foreground">
              {fotos.length} de {MAXIMO_FOTOS} archivos.
            </p>
          </div>
        )}

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
