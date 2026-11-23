"use client";

import { Bot, Building2, Loader2 } from "lucide-react";
import Link from "next/link";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";

import { InfoButton } from "@/components/app/info-button";
import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useApi } from "@/hooks/use-api";
import { apiFetch, ApiError } from "@/lib/api";
import type { ConversacionDetalle } from "@/types/conversacion";
import type { InmuebleResumen } from "@/types/inmueble";

/** Quién atiende esta conversación: Victoria (la tienda) o el asistente de inmuebles (y de qué propiedad). Lo decide el anuncio
 * o el número por el que llegó el cliente; aquí se puede cambiar a mano. */
export function AsistenteConversacion({ conversacion, onCambio }: { conversacion: ConversacionDetalle; onCambio: () => void }) {
  const esInmuebles = conversacion.asistente === "inmuebles";
  return (
    <section aria-labelledby="t-asistente" className="space-y-3">
      <div className="flex items-center gap-1">
        <h2 id="t-asistente" className="flex items-center gap-2 text-sm font-semibold">
          {esInmuebles ? <Building2 className="size-4 text-muted-foreground" aria-hidden /> : <Bot className="size-4 text-muted-foreground" aria-hidden />} Atiende
        </h2>
        <InfoButton titulo="Quién atiende esta conversación">
          <p>
            <strong>Victoria</strong> atiende la tienda. El <strong>asistente de inmuebles</strong> atiende a los interesados en una
            propiedad: informa, manda la ubicación y las fotos y anota los pedidos de visita, sin vender ni negociar.
          </p>
          <p>Lo decide el anuncio o el número por el que llegó el cliente. Cámbialo si un interesado en una propiedad escribió por otro lado.</p>
        </InfoButton>
      </div>
      <p className="text-sm">
        {esInmuebles ? (
          <>
            Asistente de inmuebles
            {conversacion.inmuebleId ? (
              <>
                {" · "}
                <Link href={`/inmuebles/${conversacion.inmuebleId}`} className="text-primary underline-offset-2 hover:underline">
                  {conversacion.inmuebleTitulo ?? "Ver propiedad"}
                </Link>
              </>
            ) : (
              " · todavía no se sabe qué propiedad"
            )}
          </>
        ) : (
          "Victoria (tienda)"
        )}
      </p>
      <CambiarAsistenteDialog conversacion={conversacion} onCambio={onCambio} />
    </section>
  );
}

function CambiarAsistenteDialog({ conversacion, onCambio }: { conversacion: ConversacionDetalle; onCambio: () => void }) {
  const [abierto, setAbierto] = useState(false);
  const [asistente, setAsistente] = useState(conversacion.asistente ?? "ventas");
  const [inmueble, setInmueble] = useState(conversacion.inmuebleId ? String(conversacion.inmuebleId) : "sin_definir");
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inmuebles = useApi<InmuebleResumen[]>(abierto ? "/inmuebles" : null);

  async function guardar(e: FormEvent) {
    e.preventDefault();
    setGuardando(true);
    setError(null);
    try {
      await apiFetch(`/inmuebles/conversaciones/${conversacion.id}/asistente`, {
        method: "PUT",
        body: JSON.stringify({ asistente, inmuebleId: asistente === "inmuebles" && inmueble !== "sin_definir" ? Number(inmueble) : null }),
      });
      toast.success(asistente === "inmuebles" ? "Ahora la atiende el asistente de inmuebles." : "Ahora la atiende Victoria.");
      setAbierto(false);
      onCambio();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo cambiar.");
    } finally {
      setGuardando(false);
    }
  }

  return (
    <Dialog open={abierto} onOpenChange={setAbierto}>
      <DialogTrigger asChild>
        <Button type="button" variant="outline" className="w-full">
          Cambiar quién atiende
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={guardar} className="space-y-4">
          <DialogHeader>
            <DialogTitle>Quién atiende esta conversación</DialogTitle>
            <DialogDescription>Desde el próximo mensaje del cliente.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-1.5">
            <Label htmlFor="asistente-select">Asistente</Label>
            <Select value={asistente} onValueChange={(v) => setAsistente(v as "ventas" | "inmuebles")} disabled={guardando}>
              <SelectTrigger id="asistente-select" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="ventas">Victoria (tienda)</SelectItem>
                <SelectItem value="inmuebles">Asistente de inmuebles</SelectItem>
              </SelectContent>
            </Select>
          </div>
          {asistente === "inmuebles" && (
            <div className="grid gap-1.5">
              <Label htmlFor="asistente-inmueble">Propiedad</Label>
              <Select value={inmueble} onValueChange={setInmueble} disabled={guardando}>
                <SelectTrigger id="asistente-inmueble" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="sin_definir">Que pregunte cuál (o la única publicada)</SelectItem>
                  {(inmuebles.data ?? []).map((i) => (
                    <SelectItem key={i.id} value={String(i.id)}>
                      {i.titulo}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
          {error && (
            <p role="alert" className="text-sm font-medium text-status-danger-ink">
              {error}
            </p>
          )}
          <DialogFooter>
            <DialogClose asChild>
              <Button type="button" variant="outline" disabled={guardando}>
                Cancelar
              </Button>
            </DialogClose>
            <Button type="submit" disabled={guardando}>
              {guardando && <Loader2 className="animate-spin" />} Guardar
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
