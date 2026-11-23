"use client";

import { Loader2, Pencil, Phone, Plus, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";

import { InfoButton } from "@/components/app/info-button";
import { SectionCard } from "@/components/app/section-card";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { useApi } from "@/hooks/use-api";
import { apiFetch, ApiError } from "@/lib/api";
import type { NumeroWhatsapp } from "@/types/inmueble";

const NOMBRE_ASISTENTE = { ventas: "Victoria (tienda)", inmuebles: "Asistente de inmuebles" } as const;

/** Qué asistente atiende cada número de WhatsApp del negocio. El número de Victoria no hace falta registrarlo: un número que no
 * está aquí se atiende como siempre, con Victoria. */
export function NumerosWhatsapp() {
  const numeros = useApi<NumeroWhatsapp[]>("/numeros-whatsapp");

  async function quitar(n: NumeroWhatsapp) {
    try {
      await apiFetch(`/numeros-whatsapp/${encodeURIComponent(n.phoneNumberId)}`, { method: "DELETE" });
      toast.success("Número quitado: vuelve a atenderlo Victoria.");
      numeros.recargar();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo quitar el número.");
    }
  }

  return (
    <SectionCard
      titulo="Números de WhatsApp"
      descripcion="Qué asistente atiende cada número del negocio."
      info={
        <InfoButton titulo="Números de WhatsApp">
          <p>
            Si las propiedades se atienden por <strong>otro número</strong> (no el de Victoria), regístralo aquí con el asistente de
            inmuebles: todo lo que llegue a ese número lo contesta el asistente, y las respuestas salen de ese mismo número.
          </p>
          <ul>
            <li>El número tiene que estar conectado a la API de WhatsApp en la misma cuenta de Meta (no en la app del teléfono).</li>
            <li>El «Phone number ID» está en Meta: WhatsApp Manager → Números de teléfono (o en el panel de la app de Meta).</li>
            <li>Un número que no está en esta lista lo atiende Victoria, como siempre.</li>
            <li>Si el anuncio de una propiedad apunta al número de Victoria, no hace falta nada de esto: vincula el anuncio en la ficha de la propiedad.</li>
          </ul>
        </InfoButton>
      }
    >
      <div className="space-y-3 p-4 sm:p-5">
        {numeros.error ? (
          <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-status-danger-ink">
            No se pudieron cargar los números.
            <Button variant="outline" size="sm" onClick={numeros.recargar}>
              Reintentar
            </Button>
          </div>
        ) : numeros.cargando && !numeros.data ? (
          <p className="text-sm text-muted-foreground">Cargando…</p>
        ) : (numeros.data ?? []).length === 0 ? (
          <p className="text-sm text-muted-foreground">No hay números registrados: todos los mensajes los atiende Victoria salvo los anuncios vinculados a una propiedad.</p>
        ) : (
          <ul className="divide-y rounded-lg border">
            {numeros.data!.map((n) => (
              <li key={n.phoneNumberId} className="flex flex-wrap items-center justify-between gap-2 p-3">
                <div className="min-w-0">
                  <p className="flex items-center gap-1.5 font-medium">
                    <Phone className="size-3.5 text-muted-foreground" aria-hidden /> {n.nombre}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {n.telefonoVisible ? `${n.telefonoVisible} · ` : ""}ID {n.phoneNumberId}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <StatusBadge label={n.activo ? NOMBRE_ASISTENTE[n.asistente] : "Inactivo"} variant={n.activo ? (n.asistente === "inmuebles" ? "info" : "neutral") : "neutral"} />
                  <EditarNumeroDialog numero={n} onGuardado={numeros.recargar}>
                    <Button variant="ghost" size="icon" aria-label={`Editar ${n.nombre}`}>
                      <Pencil />
                    </Button>
                  </EditarNumeroDialog>
                  <Button variant="ghost" size="icon" aria-label={`Quitar ${n.nombre}`} onClick={() => void quitar(n)}>
                    <Trash2 />
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
        <EditarNumeroDialog onGuardado={numeros.recargar}>
          <Button variant="outline">
            <Plus /> Registrar un número
          </Button>
        </EditarNumeroDialog>
      </div>
    </SectionCard>
  );
}

function EditarNumeroDialog({ numero, onGuardado, children }: { numero?: NumeroWhatsapp; onGuardado: () => void; children: React.ReactNode }) {
  const [abierto, setAbierto] = useState(false);
  const [id, setId] = useState(numero?.phoneNumberId ?? "");
  const [nombre, setNombre] = useState(numero?.nombre ?? "");
  const [telefono, setTelefono] = useState(numero?.telefonoVisible ?? "");
  const [asistente, setAsistente] = useState<"ventas" | "inmuebles">(numero?.asistente ?? "inmuebles");
  const [activo, setActivo] = useState(numero?.activo ?? true);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function guardar(e: FormEvent) {
    e.preventDefault();
    setGuardando(true);
    setError(null);
    try {
      await apiFetch("/numeros-whatsapp", {
        method: "PUT",
        body: JSON.stringify({ phoneNumberId: id.trim(), nombre: nombre.trim(), telefonoVisible: telefono.trim() || null, asistente, activo }),
      });
      toast.success("Número guardado.");
      setAbierto(false);
      onGuardado();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo guardar.");
    } finally {
      setGuardando(false);
    }
  }

  return (
    <Dialog open={abierto} onOpenChange={setAbierto}>
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent>
        <form onSubmit={guardar} className="space-y-4">
          <DialogHeader>
            <DialogTitle>{numero ? "Editar número" : "Registrar un número"}</DialogTitle>
            <DialogDescription>Qué asistente contesta lo que llegue a este número.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-1.5">
            <Label htmlFor="numero-id">Phone number ID (de Meta)</Label>
            <Input id="numero-id" inputMode="numeric" value={id} onChange={(e) => setId(e.target.value)} disabled={!!numero || guardando} required />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="numero-nombre">Nombre para reconocerlo</Label>
            <Input id="numero-nombre" value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Casa Guayaquil" required disabled={guardando} />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="numero-telefono">
              Teléfono <span className="font-normal text-muted-foreground">(opcional)</span>
            </Label>
            <Input id="numero-telefono" inputMode="tel" value={telefono} onChange={(e) => setTelefono(e.target.value)} placeholder="+593 9…" disabled={guardando} />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="numero-asistente">Lo atiende</Label>
            <Select value={asistente} onValueChange={(v) => setAsistente(v as "ventas" | "inmuebles")} disabled={guardando}>
              <SelectTrigger id="numero-asistente" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="inmuebles">Asistente de inmuebles</SelectItem>
                <SelectItem value="ventas">Victoria (tienda)</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-center justify-between gap-3">
            <Label htmlFor="numero-activo">Activo</Label>
            <Switch id="numero-activo" checked={activo} onCheckedChange={setActivo} disabled={guardando} />
          </div>
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
            <Button type="submit" disabled={guardando || !id.trim() || !nombre.trim()}>
              {guardando && <Loader2 className="animate-spin" />} Guardar
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
