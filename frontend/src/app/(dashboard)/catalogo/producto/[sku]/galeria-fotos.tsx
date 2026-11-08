"use client";

import { ArrowLeftToLine, ImagePlus, Loader2, Trash2, TriangleAlert } from "lucide-react";
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
const BUCKET = "productos";
/** Máximo de fotos por producto (espejo de `MAXIMO_POR_PRODUCTO` en el backend). */
const MAXIMO_FOTOS = 8;
/** WhatsApp muestra fotos de ~1600 px sin problema y las del celular pesan varios MB: se reducen antes de subir. */
const LADO_MAXIMO = 1600;
const CALIDAD_JPEG = 0.85;

/** Reduce la foto y la convierte a JPEG (WhatsApp solo acepta JPEG y PNG; el celular puede dar HEIC o fotos enormes). */
async function prepararFoto(archivo: File): Promise<Blob> {
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
  return (
    <li className="space-y-2 rounded-xl border bg-card p-2">
      <div className="relative aspect-square overflow-hidden rounded-lg border bg-muted">
        {falla ? (
          <p className="flex size-full items-center justify-center p-2 text-center text-xs text-muted-foreground">No se pudo mostrar la foto</p>
        ) : (
          // eslint-disable-next-line @next/next/no-img-element -- la foto viene del bucket público de Supabase
          <img src={foto.url} alt={`Foto ${indice + 1} de ${total}`} loading="lazy" onError={() => setFalla(true)} className="size-full object-cover" />
        )}
        {indice === 0 && (
          <span className="absolute top-1.5 left-1.5 rounded-full bg-primary px-2 py-0.5 text-[0.7rem] font-medium text-primary-foreground">Principal</span>
        )}
      </div>
      <div className="flex items-center justify-between gap-1">
        <Button type="button" variant="ghost" size="sm" disabled={deshabilitado || ocupada || indice === 0} onClick={onPrincipal} aria-label={`Hacer principal la foto ${indice + 1}`}>
          <ArrowLeftToLine /> Principal
        </Button>
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button type="button" variant="ghost" size="icon" disabled={deshabilitado || ocupada} aria-label={`Quitar la foto ${indice + 1}`}>
              <Trash2 />
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>¿Quitar esta foto?</AlertDialogTitle>
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

/** Las fotos del producto (ADR-012, entrega 2). Se suben desde aquí con tu sesión al bucket público de Supabase, ya
 * reducidas; la primera es la principal. Victoria las manda por WhatsApp cuando el cliente las pide. */
export function GaleriaFotos({ detalle, onCambio }: { detalle: ProductoBotDetalle; onCambio: () => void }) {
  const entrada = useRef<HTMLInputElement>(null);
  const [trabajando, setTrabajando] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [imagenFalla, setImagenFalla] = useState(false);
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
        const blob = await prepararFoto(archivo);
        ruta_storage = `${detalle.carpetaFotos}/${crypto.randomUUID()}.jpg`;
        const { error: errorSubida } = await supabase.storage.from(BUCKET).upload(ruta_storage, blob, { contentType: "image/jpeg", upsert: false });
        if (errorSubida) throw new Error(errorSubida.message);
        await apiFetch<ProductoBotDetalle>(`${ruta}/imagenes`, { method: "POST", body: JSON.stringify({ storagePath: ruta_storage }) });
        subidas += 1;
      } catch (err) {
        // Si el archivo quedó subido pero no se pudo anotar, no se deja huérfano.
        if (ruta_storage) void supabase.storage.from(BUCKET).remove([ruta_storage]);
        setError(err instanceof ApiError ? err.message : err instanceof Error ? err.message : "No se pudo subir la foto.");
        break;
      }
    }
    if (archivos.length > MAXIMO_FOTOS - fotos.length) toast.info(`Solo caben ${MAXIMO_FOTOS} fotos por producto: se subieron las primeras.`);
    setTrabajando(null);
    if (subidas > 0) {
      toast.success(subidas === 1 ? "Foto subida." : `${subidas} fotos subidas.`);
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
    setTrabajando("Quitando la foto…");
    setError(null);
    try {
      await apiFetch<ProductoBotDetalle>(`${ruta}/imagenes/${foto.id}`, { method: "DELETE" });
      // El archivo se borra con tu sesión; si falla, solo queda un archivo suelto que no se usa.
      void createClient().storage.from(BUCKET).remove([foto.storagePath]);
      toast.success("Foto quitada.");
      onCambio();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo quitar la foto.");
    } finally {
      setTrabajando(null);
    }
  }

  return (
    <SectionCard
      titulo="Fotos del producto"
      descripcion="Las que Victoria manda por WhatsApp."
      info={
        <InfoButton titulo="Fotos del producto">
          <p>Son las fotos que Victoria manda por WhatsApp cuando el cliente pide ver el producto. La primera es la principal.</p>
          <ul>
            <li>Victoria manda unas pocas fotos cada vez y, si el cliente quiere más, sigue con las siguientes.</li>
            <li>
              Cuántas manda cada vez se cambia en{" "}
              <Link href="/parametros">Parámetros → «Fotos por envío»</Link>.
            </li>
            <li>Al subirlas, se reducen y se convierten a JPG para que pesen poco.</li>
            <li>Puedes tener hasta {MAXIMO_FOTOS} fotos por producto.</li>
          </ul>
          <p>Si el producto no tiene fotos y un cliente las pide, Victoria le dice que por ahora no hay imágenes disponibles.</p>
          <InfoAviso>
            <p>El envío de fotos por WhatsApp debe estar encendido en el parámetro «Enviar fotos del producto».</p>
          </InfoAviso>
        </InfoButton>
      }
    >
      <div className="space-y-4 p-4 sm:p-5">
        {fotos.length === 0 ? (
          <div className="space-y-3 rounded-lg bg-muted/50 p-3">
            <p className="text-sm text-muted-foreground">
              {detalle.imagenUrl && detalle.proveedor === "rocketfy"
                ? "Todavía no subiste fotos. Mientras tanto Victoria usa la foto de Rocketfy:"
                : "Este producto todavía no tiene fotos."}
            </p>
            {detalle.imagenUrl && detalle.proveedor === "rocketfy" && !imagenFalla && (
              // eslint-disable-next-line @next/next/no-img-element -- la imagen viene de un CDN externo de Rocketfy
              <img src={detalle.imagenUrl} alt={`Foto de Rocketfy de ${detalle.nombre}`} width={96} height={96} referrerPolicy="no-referrer" onError={() => setImagenFalla(true)} className="size-24 rounded-lg border bg-muted object-cover" />
            )}
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
            <input ref={entrada} type="file" accept="image/jpeg,image/png,image/webp,image/heic,image/heif" multiple className="sr-only" tabIndex={-1} aria-hidden onChange={(e) => void subir(e)} />
            <Button type="button" variant="outline" disabled={trabajando !== null || lleno} onClick={() => entrada.current?.click()}>
              {trabajando ? <Loader2 className="animate-spin" /> : <ImagePlus />}
              {trabajando ?? "Subir fotos"}
            </Button>
            <p className="text-xs text-muted-foreground">
              {fotos.length} de {MAXIMO_FOTOS} fotos.
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
