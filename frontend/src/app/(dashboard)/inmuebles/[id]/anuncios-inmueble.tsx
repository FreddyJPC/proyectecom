"use client";

import { Link2, Loader2, Megaphone, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";

import { InfoButton } from "@/components/app/info-button";
import { SectionCard } from "@/components/app/section-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiFetch, ApiError } from "@/lib/api";
import { formatFecha } from "@/lib/format";
import type { InmuebleDetalle } from "@/types/inmueble";

/** Los anuncios de Meta que hablan de esta propiedad: quien llega por uno de ellos lo atiende el asistente de inmuebles, con
 * esta ficha, aunque el anuncio apunte al número de Victoria. */
export function AnunciosInmueble({ inmueble, onCambio }: { inmueble: InmuebleDetalle; onCambio: () => void }) {
  const [idAnuncio, setIdAnuncio] = useState("");
  const [nombre, setNombre] = useState("");
  const [trabajando, setTrabajando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function vincular(e: FormEvent) {
    e.preventDefault();
    setTrabajando(true);
    setError(null);
    try {
      await apiFetch(`/inmuebles/${inmueble.id}/anuncios`, { method: "POST", body: JSON.stringify({ idAnuncio: idAnuncio.trim(), nombre: nombre.trim() || null }) });
      toast.success("Anuncio vinculado.");
      setIdAnuncio("");
      setNombre("");
      onCambio();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo vincular el anuncio.");
    } finally {
      setTrabajando(false);
    }
  }

  async function desvincular(id: string) {
    setTrabajando(true);
    try {
      await apiFetch(`/inmuebles/${inmueble.id}/anuncios/${encodeURIComponent(id)}`, { method: "DELETE" });
      toast.success("Anuncio desvinculado.");
      onCambio();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo desvincular.");
    } finally {
      setTrabajando(false);
    }
  }

  return (
    <SectionCard
      titulo="Anuncios de esta propiedad"
      descripcion="Quien llega por ellos lo atiende el asistente de inmuebles."
      info={
        <InfoButton titulo="Anuncios de esta propiedad">
          <p>
            Vincula aquí cada anuncio de Meta que habla de esta propiedad. Quien escriba desde uno de ellos lo atiende el asistente de
            inmuebles con esta ficha, aunque el anuncio lleve al número de WhatsApp de Victoria.
          </p>
          <p>El identificador del anuncio son solo números: está en el Administrador de anuncios (columna «Identificador del anuncio»).</p>
        </InfoButton>
      }
    >
      <div className="space-y-4 p-4 sm:p-5">
        {inmueble.anuncios.length === 0 ? (
          <p className="text-sm text-muted-foreground">No hay anuncios vinculados.</p>
        ) : (
          <ul className="divide-y rounded-lg border">
            {inmueble.anuncios.map((a) => (
              <li key={a.idAnuncio} className="flex items-center justify-between gap-2 p-3">
                <div className="min-w-0">
                  <p className="flex items-center gap-1.5 font-medium">
                    <Megaphone className="size-3.5 text-muted-foreground" aria-hidden /> {a.nombre ?? "Anuncio"}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    ID {a.idAnuncio} · desde {formatFecha(a.creadoEn)}
                  </p>
                </div>
                <Button variant="ghost" size="icon" disabled={trabajando} onClick={() => void desvincular(a.idAnuncio)} aria-label={`Desvincular el anuncio ${a.idAnuncio}`}>
                  <Trash2 />
                </Button>
              </li>
            ))}
          </ul>
        )}
        <form onSubmit={vincular} className="grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
          <div className="grid gap-1.5">
            <Label htmlFor="anuncio-id">Identificador del anuncio</Label>
            <Input id="anuncio-id" inputMode="numeric" value={idAnuncio} onChange={(e) => setIdAnuncio(e.target.value)} placeholder="120252118114240418" disabled={trabajando} />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="anuncio-nombre">
              Nombre <span className="font-normal text-muted-foreground">(opcional)</span>
            </Label>
            <Input id="anuncio-nombre" value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Video Casa Guayaquil 1" disabled={trabajando} />
          </div>
          <Button type="submit" variant="outline" disabled={trabajando || !idAnuncio.trim()}>
            {trabajando ? <Loader2 className="animate-spin" /> : <Link2 />} Vincular
          </Button>
        </form>
        {error && (
          <p role="alert" className="text-sm font-medium text-status-danger-ink">
            {error}
          </p>
        )}
      </div>
    </SectionCard>
  );
}
