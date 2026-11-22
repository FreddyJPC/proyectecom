"use client";

import { Check, ImageOff, Images, Loader2, Play } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { InfoButton } from "@/components/app/info-button";
import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { apiFetch, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { ImagenProducto, ProductoBotDetalle, ProductoBotResumen } from "@/types/producto-bot";

function esVideo(f: ImagenProducto) {
  return f.tipo === "video" || /\.(mp4|3gp)$/i.test(f.storagePath);
}

/** Una miniatura que se marca o desmarca con un toque (todas vienen marcadas). */
function Miniatura({ foto, posicion, elegida, onCambiar }: { foto: ImagenProducto; posicion: number; elegida: boolean; onCambiar: () => void }) {
  const video = esVideo(foto);
  const nombre = `${video ? "Video" : "Foto"} ${posicion}`;
  return (
    <button
      type="button"
      aria-pressed={elegida}
      aria-label={nombre}
      onClick={onCambiar}
      className={cn(
        "relative aspect-square overflow-hidden rounded-lg border-2 bg-muted outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
        elegida ? "border-primary" : "border-transparent opacity-60",
      )}
    >
      {video ? (
        <video src={foto.url} muted playsInline preload="metadata" aria-hidden className="pointer-events-none size-full bg-black object-cover" />
      ) : (
        // eslint-disable-next-line @next/next/no-img-element -- la foto viene del bucket público de Supabase
        <img src={foto.url} alt="" loading="lazy" className="size-full object-cover" />
      )}
      {video && (
        <span className="absolute bottom-1 left-1 flex size-6 items-center justify-center rounded-full bg-background/90 text-foreground">
          <Play className="size-3.5" aria-hidden />
        </span>
      )}
      {elegida && (
        <span className="absolute top-1 right-1 flex size-6 items-center justify-center rounded-full bg-primary text-primary-foreground">
          <Check className="size-3.5" aria-hidden />
        </span>
      )}
    </button>
  );
}

/** Lo de adentro del cuadro: se monta solo al abrirlo, así la lista de productos y la galería se piden en ese momento. */
function Contenido({ conversacionId, skuInicial, onEnviado }: { conversacionId: string; skuInicial: string | null; onEnviado: () => void }) {
  const productos = useApi<ProductoBotResumen[]>("/productos-bot");
  const [sku, setSku] = useState<string | null>(skuInicial);
  const detalle = useApi<ProductoBotDetalle>(sku ? `/productos-bot/${encodeURIComponent(sku)}` : null);
  const [quitadas, setQuitadas] = useState<Set<number>>(new Set());
  const [enviando, setEnviando] = useState(false);

  const disponibles = (productos.data ?? []).filter((p) => p.estado !== "archivado");
  const galeria = detalle.data && detalle.data.sku === sku ? [...detalle.data.imagenes].sort((a, b) => a.orden - b.orden) : [];
  const elegidas = galeria.filter((f) => !quitadas.has(f.id));

  function cambiarProducto(valor: string) {
    setSku(valor);
    setQuitadas(new Set());
  }

  function alternar(id: number) {
    setQuitadas((prev) => {
      const nuevo = new Set(prev);
      if (nuevo.has(id)) nuevo.delete(id);
      else nuevo.add(id);
      return nuevo;
    });
  }

  async function enviar() {
    if (!sku || elegidas.length === 0 || enviando) return;
    setEnviando(true);
    try {
      const r = await apiFetch<{ fotos: number; videos: number }>(`/conversaciones/${conversacionId}/material`, {
        method: "POST",
        body: JSON.stringify({ sku, imagenIds: elegidas.map((f) => f.id) }),
      });
      const partes = [r.fotos && `${r.fotos} ${r.fotos === 1 ? "foto" : "fotos"}`, r.videos && `${r.videos} ${r.videos === 1 ? "video" : "videos"}`].filter(Boolean);
      toast.success(`Enviaste ${partes.join(" y ")} al cliente.`);
      onEnviado();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo enviar el material.");
      onEnviado(); // lo que sí salió ya quedó en el historial: se recarga igual
    } finally {
      setEnviando(false);
    }
  }

  return (
    <>
      <div className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="material-producto">Producto</Label>
          {productos.cargando && !productos.data ? (
            <Skeleton className="h-10 w-full" />
          ) : productos.error ? (
            <div className="flex items-center justify-between gap-2 text-sm text-destructive">
              No se pudo cargar la lista de productos.
              <Button type="button" variant="outline" size="sm" onClick={productos.recargar}>Reintentar</Button>
            </div>
          ) : (
            <Select value={sku ?? undefined} onValueChange={cambiarProducto} disabled={enviando}>
              <SelectTrigger id="material-producto" className="h-10 w-full">
                <SelectValue placeholder="Elige el producto" />
              </SelectTrigger>
              <SelectContent>
                {disponibles.map((p) => (
                  <SelectItem key={p.sku} value={p.sku}>{p.nombre}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </div>

        {sku && (
          <div className="space-y-1.5">
            <p className="text-sm font-medium">
              Material {galeria.length > 0 && <span className="font-normal text-muted-foreground">· {elegidas.length} de {galeria.length} elegidos</span>}
            </p>
            {detalle.cargando && galeria.length === 0 ? (
              <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
                {[0, 1, 2].map((i) => <Skeleton key={i} className="aspect-square rounded-lg" />)}
              </div>
            ) : detalle.error ? (
              <div className="flex items-center justify-between gap-2 text-sm text-destructive">
                No se pudo cargar el material.
                <Button type="button" variant="outline" size="sm" onClick={detalle.recargar}>Reintentar</Button>
              </div>
            ) : galeria.length === 0 ? (
              <p className="flex items-center gap-2 rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
                <ImageOff className="size-4 shrink-0" aria-hidden />
                Este producto no tiene fotos ni videos. Súbelos en su ficha del catálogo.
              </p>
            ) : (
              <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
                {galeria.map((f, i) => (
                  <Miniatura key={f.id} foto={f} posicion={i + 1} elegida={!quitadas.has(f.id)} onCambiar={() => alternar(f.id)} />
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      <DialogFooter>
        <DialogClose asChild>
          <Button type="button" variant="outline" disabled={enviando}>Cancelar</Button>
        </DialogClose>
        <Button type="button" onClick={enviar} disabled={!sku || elegidas.length === 0 || enviando}>
          {enviando && <Loader2 className="animate-spin" aria-hidden />}
          {enviando ? "Enviando…" : elegidas.length > 0 ? `Enviar ${elegidas.length}` : "Enviar"}
        </Button>
      </DialogFooter>
    </>
  );
}

/** El dueño le manda al cliente las fotos y los videos del producto, igual que lo hace Victoria, cuando atiende él. */
export function EnviarMaterialDialog({
  conversacionId,
  skuInicial,
  deshabilitado,
  onEnviado,
}: {
  conversacionId: string;
  skuInicial: string | null;
  deshabilitado: boolean;
  onEnviado: () => void;
}) {
  const [abierto, setAbierto] = useState(false);
  return (
    <Dialog open={abierto} onOpenChange={setAbierto}>
      <DialogTrigger asChild>
        <Button type="button" variant="outline" size="icon-lg" disabled={deshabilitado} aria-label="Enviar fotos y videos del producto" className="shrink-0 rounded-full">
          <Images />
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[92dvh] overflow-y-auto">
        <DialogHeader>
          <div className="flex items-center gap-1">
            <DialogTitle>Enviar fotos y videos</DialogTitle>
            <InfoButton titulo="Enviar fotos y videos">
              <p>Se envía el material que subiste a la ficha del producto, en el orden de su galería. Toca una miniatura para quitarla o volver a elegirla.</p>
              <p>Si Victoria retoma la conversación, sabe lo que ya mandaste y no lo repite.</p>
              <p>Solo funciona dentro de las 24 horas desde el último mensaje del cliente.</p>
            </InfoButton>
          </div>
          <DialogDescription>Elige el producto y lo que quieres mandar.</DialogDescription>
        </DialogHeader>
        {abierto && (
          <Contenido
            conversacionId={conversacionId}
            skuInicial={skuInicial}
            onEnviado={() => {
              setAbierto(false);
              onEnviado();
            }}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}
