"use client";

import { ExternalLink, Link2, Link2Off, Loader2, Megaphone } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { StatusBadge } from "@/components/status-badge";
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
import { formatMoney, tiempoRelativo } from "@/lib/format";
import type { Anuncio } from "@/types/anuncios";
import type { ProductoBotResumen } from "@/types/producto-bot";

import { VincularAnuncioDialog } from "./vincular-dialog";

function Cifra({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-0.5">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="tabular text-sm font-semibold">{children}</dd>
    </div>
  );
}

/** Un anuncio: lo que Meta dijo de él, su producto y cuánto ha vendido. Aquí se vincula o se quita el vínculo. */
export function AnuncioCard({ anuncio: a, productos, onCambio }: { anuncio: Anuncio; productos: ProductoBotResumen[]; onCambio: () => void }) {
  const [imagenFalla, setImagenFalla] = useState(false);
  const [quitando, setQuitando] = useState(false);
  const imagen = a.miniaturaUrl ?? a.imagenUrl;
  const vinculado = a.productoSku !== null;
  const nombre = a.titulo ?? a.nombreVinculo ?? `Anuncio ${a.idAnuncio}`;

  async function quitarVinculo() {
    setQuitando(true);
    try {
      await apiFetch(`/anuncios/${encodeURIComponent(a.idAnuncio)}/producto`, { method: "DELETE" });
      toast.success("Vínculo quitado: Victoria volverá a preguntar el producto.");
      onCambio();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo quitar el vínculo.");
    } finally {
      setQuitando(false);
    }
  }

  return (
    <li className="space-y-4 p-4 sm:p-5">
      <div className="flex items-start gap-3">
        {imagen && !imagenFalla ? (
          // eslint-disable-next-line @next/next/no-img-element -- la imagen viene de la CDN de Meta
          <img src={imagen} alt="" width={64} height={64} referrerPolicy="no-referrer" onError={() => setImagenFalla(true)} className="size-16 shrink-0 rounded-lg border bg-muted object-cover" />
        ) : (
          <span className="flex size-16 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground" aria-hidden>
            <Megaphone className="size-6" />
          </span>
        )}
        <div className="min-w-0 flex-1 space-y-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="min-w-0 text-sm font-semibold break-words">{nombre}</h3>
            {vinculado ? <StatusBadge label="Vinculado" variant="success" /> : <StatusBadge label="Sin vincular" variant="warning" />}
          </div>
          {a.texto && <p className="line-clamp-2 text-xs text-muted-foreground break-words">{a.texto}</p>}
          <p className="text-xs text-muted-foreground">
            ID <span className="tabular break-all">{a.idAnuncio}</span>
            {a.ultimaLlegada ? <> · última llegada {tiempoRelativo(a.ultimaLlegada)}</> : <> · todavía no ha traído a nadie</>}
          </p>
          <p className="text-sm">
            {vinculado ? (
              <>
                Producto:{" "}
                <Link href={`/catalogo/producto/${encodeURIComponent(a.productoSku!)}`} className="font-medium text-primary underline-offset-2 hover:underline">
                  {a.productoNombre}
                </Link>
              </>
            ) : (
              <span className="text-status-warning-ink">Victoria no sabe de qué producto habla este anuncio: pregunta al cliente.</span>
            )}
          </p>
        </div>
      </div>

      <dl className="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-4">
        <Cifra label="Clientes">{a.conversaciones}</Cifra>
        <Cifra label="Ventas">{a.ventas}</Cifra>
        <Cifra label="Ingresos">{formatMoney(a.ingresos)}</Cifra>
        <Cifra label="Ganancia">
          {formatMoney(a.ganancia)}
          {a.ventasSinCosto > 0 && <span className="block text-xs font-normal text-muted-foreground">sin costo en {a.ventasSinCosto}</span>}
        </Cifra>
      </dl>

      <div className="flex flex-wrap items-center gap-2">
        <VincularAnuncioDialog
          productos={productos}
          idAnuncio={a.idAnuncio}
          productoActual={a.productoSku}
          nombreActual={a.nombreVinculo}
          onVinculado={onCambio}
          trigger={
            <Button type="button" size="sm" variant={vinculado ? "outline" : "default"}>
              <Link2 /> {vinculado ? "Cambiar producto" : "Vincular con un producto"}
            </Button>
          }
        />
        {vinculado && (
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button type="button" size="sm" variant="ghost" disabled={quitando} className="text-muted-foreground hover:text-destructive">
                {quitando ? <Loader2 className="animate-spin" /> : <Link2Off />} Quitar vínculo
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>¿Quitar el vínculo de este anuncio?</AlertDialogTitle>
                <AlertDialogDescription>
                  Victoria dejará de saber de qué producto habla «{nombre}» y volverá a preguntárselo al cliente. Las ventas ya hechas no cambian.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancelar</AlertDialogCancel>
                <AlertDialogAction onClick={() => void quitarVinculo()}>Sí, quitar el vínculo</AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        )}
        {a.urlAnuncio && (
          <Button asChild size="sm" variant="ghost">
            <a href={a.urlAnuncio} target="_blank" rel="noopener noreferrer">
              <ExternalLink /> Ver el anuncio
              <span className="sr-only">(se abre en otra pestaña)</span>
            </a>
          </Button>
        )}
      </div>
    </li>
  );
}
