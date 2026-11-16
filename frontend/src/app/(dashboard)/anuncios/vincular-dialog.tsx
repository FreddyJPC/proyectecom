"use client";

import { Loader2, TriangleAlert } from "lucide-react";
import { useState, type FormEvent, type ReactNode } from "react";
import { toast } from "sonner";

import { InfoButton } from "@/components/app/info-button";
import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { apiFetch, ApiError } from "@/lib/api";
import type { VinculoAnuncio } from "@/types/anuncios";
import type { Oferta } from "@/types/precios";
import type { ProductoBotResumen } from "@/types/producto-bot";

/** Vincula un anuncio con un producto o con una oferta (ADR-017). Sirve para los anuncios que ya llegaron (el ID viene dado) y para uno NUEVO que aún
 * no ha traído a nadie (se escribe el ID que muestra el Administrador de anuncios de Meta). */
export function VincularAnuncioDialog({
  trigger,
  productos,
  idAnuncio,
  productoActual,
  ofertas = [],
  ofertaActual,
  nombreActual,
  onVinculado,
}: {
  trigger: ReactNode;
  productos: ProductoBotResumen[];
  /** Ofertas (combos y promos) que el anuncio puede vender en vez de un producto suelto (ADR-017). */
  ofertas?: Oferta[];
  ofertaActual?: number | null;
  /** Si viene, el ID no se puede cambiar (es un anuncio que ya está en la lista). */
  idAnuncio?: string;
  productoActual?: string | null;
  nombreActual?: string | null;
  onVinculado: () => void;
}) {
  const [abierto, setAbierto] = useState(false);
  const [id, setId] = useState(idAnuncio ?? "");
  const [sku, setSku] = useState(productoActual ?? "");
  const [tipo, setTipo] = useState<"producto" | "oferta">(ofertaActual ? "oferta" : "producto");
  const [ofertaId, setOfertaId] = useState(ofertaActual ? String(ofertaActual) : "");
  const [nombre, setNombre] = useState(nombreActual ?? "");
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Si el anuncio ya está vinculado a OTRO producto, el servidor responde 409 y hay que confirmar el cambio.
  const [confirmarCambio, setConfirmarCambio] = useState<string | null>(null);

  const elegibles = productos.filter((p) => p.estado !== "archivado");
  const idLimpio = id.trim();
  const ofertasElegibles = ofertas.filter((o) => o.estado !== "archivada");
  const puedeGuardar = idLimpio !== "" && (tipo === "producto" ? sku !== "" : ofertaId !== "") && !guardando;

  function alCambiarApertura(valor: boolean) {
    setAbierto(valor);
    if (valor) {
      setId(idAnuncio ?? "");
      setSku(productoActual ?? "");
      setTipo(ofertaActual ? "oferta" : "producto");
      setOfertaId(ofertaActual ? String(ofertaActual) : "");
      setNombre(nombreActual ?? "");
      setError(null);
      setConfirmarCambio(null);
    }
  }

  async function guardar(e: FormEvent, reasignar = false) {
    e.preventDefault();
    e.stopPropagation();
    if (!puedeGuardar) return;
    setGuardando(true);
    setError(null);
    try {
      if (tipo === "oferta") {
        const vinculo = await apiFetch<{ ofertaNombre: string }>(
          `/precios/ofertas/${encodeURIComponent(ofertaId)}/anuncios/${encodeURIComponent(idLimpio)}`,
          { method: "PUT", body: JSON.stringify({ nombre: nombre.trim() || null, reasignar }) },
        );
        toast.success(`Anuncio vinculado a la oferta «${vinculo.ofertaNombre}».`);
      } else {
        const vinculo = await apiFetch<VinculoAnuncio>(`/anuncios/${encodeURIComponent(idLimpio)}/producto`, {
          method: "PUT",
          body: JSON.stringify({ sku, nombre: nombre.trim() || null, reasignar }),
        });
        toast.success(`Anuncio vinculado a «${vinculo.productoNombre}».`);
      }
      setAbierto(false);
      onVinculado();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) setConfirmarCambio(err.message);
      else setError(err instanceof ApiError ? err.message : "No se pudo conectar con el servidor.");
    } finally {
      setGuardando(false);
    }
  }

  return (
    <Dialog open={abierto} onOpenChange={alCambiarApertura}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="max-h-[92dvh] overflow-y-auto">
        <form onSubmit={(e) => void guardar(e)} noValidate>
          <DialogHeader>
            <div className="flex items-center gap-1 pr-8">
              <DialogTitle>{idAnuncio ? "Qué vende este anuncio" : "Vincular un anuncio"}</DialogTitle>
              <InfoButton titulo="Vincular un anuncio">
                <p>
                  Cuando un cliente llega tocando un anuncio vinculado, Victoria ya sabe <strong>de qué producto u oferta hablar</strong> y no tiene que preguntárselo.
                </p>
                <ul>
                  <li>
                    <strong>ID del anuncio:</strong> lo ves en el Administrador de anuncios de Meta, en la columna «ID del anuncio». Son unos 15 a 17 dígitos.
                  </li>
                  <li>
                    <strong>Puedes vincularlo antes de que llegue el primer cliente:</strong> así Victoria acierta desde el primer mensaje.
                  </li>
                  <li>
                    <strong>Nombre (opcional):</strong> para reconocer el anuncio en la lista mientras Meta no mande su título.
                  </li>
                </ul>
                <p>Un anuncio vende una sola cosa: un producto a su precio o una oferta (combo, 2x1, precio especial). Si ya vendía otra, te pedimos confirmar el cambio.</p>
              </InfoButton>
            </div>
            <DialogDescription>Elige qué vende este anuncio: un producto o una oferta.</DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            <div className="grid gap-1.5">
              <Label htmlFor="anuncio-id">ID del anuncio</Label>
              <Input
                id="anuncio-id"
                value={id}
                onChange={(e) => setId(e.target.value)}
                readOnly={Boolean(idAnuncio)}
                inputMode="numeric"
                autoComplete="off"
                placeholder="120210000123456"
                maxLength={64}
                className="tabular"
              />
            </div>
            {ofertasElegibles.length > 0 && (
              <div className="grid gap-1.5">
                <Label htmlFor="anuncio-tipo">Este anuncio vende</Label>
                <Select value={tipo} onValueChange={(v) => setTipo(v as "producto" | "oferta")}>
                  <SelectTrigger id="anuncio-tipo" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="producto">Un producto a su precio</SelectItem>
                    <SelectItem value="oferta">Una oferta o combo</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            )}
            {tipo === "oferta" ? (
              <div className="grid gap-1.5">
                <Label htmlFor="anuncio-oferta">Oferta</Label>
                <Select value={ofertaId} onValueChange={setOfertaId}>
                  <SelectTrigger id="anuncio-oferta" className="w-full">
                    <SelectValue placeholder="Elige una oferta" />
                  </SelectTrigger>
                  <SelectContent>
                    {ofertasElegibles.map((o) => (
                      <SelectItem key={o.id} value={String(o.id)}>
                        {o.nombre}
                        {o.situacion !== "vigente" ? " (no está a la venta)" : ""}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            ) : (
            <div className="grid gap-1.5">
              <Label htmlFor="anuncio-producto">Producto</Label>
              <Select value={sku} onValueChange={setSku}>
                <SelectTrigger id="anuncio-producto" className="w-full">
                  <SelectValue placeholder="Elige un producto" />
                </SelectTrigger>
                <SelectContent>
                  {elegibles.map((p) => (
                    <SelectItem key={p.sku} value={p.sku}>
                      {p.nombre}
                      {p.estado !== "activo" ? " (no está a la venta)" : ""}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            )}
            <div className="grid gap-1.5">
              <Label htmlFor="anuncio-nombre">
                Nombre <span className="font-normal text-muted-foreground">(opcional)</span>
              </Label>
              <Input id="anuncio-nombre" value={nombre} onChange={(e) => setNombre(e.target.value)} maxLength={120} placeholder="Video de los audífonos" />
            </div>

            {confirmarCambio && (
              <div role="alert" className="space-y-2 rounded-lg bg-status-warning-soft p-3 text-sm text-status-warning-ink">
                <p className="flex items-start gap-2 font-medium">
                  <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
                  {confirmarCambio}
                </p>
                <p>¿Quieres cambiarlo a lo que elegiste?</p>
                <Button type="button" size="sm" variant="outline" className="bg-card text-foreground" disabled={guardando} onClick={(e) => void guardar(e, true)}>
                  Sí, cambiarlo
                </Button>
              </div>
            )}
            {error && (
              <p role="alert" className="flex items-start gap-2 rounded-lg bg-status-danger-soft p-3 text-sm text-status-danger-ink">
                <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
                {error}
              </p>
            )}
          </div>

          <DialogFooter>
            <DialogClose asChild>
              <Button type="button" variant="outline" disabled={guardando}>
                Cancelar
              </Button>
            </DialogClose>
            <Button type="submit" disabled={!puedeGuardar}>
              {guardando ? (
                <>
                  <Loader2 className="animate-spin" /> Guardando…
                </>
              ) : (
                "Vincular"
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
