"use client";

import { Loader2 } from "lucide-react";
import { useState, type FormEvent, type ReactNode } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { apiFetch, ApiError } from "@/lib/api";
import { instanteEcuador } from "@/lib/inmuebles";
import type { InmuebleResumen } from "@/types/inmueble";

/** Una visita que agendas tú (p. ej. alguien que llamó por teléfono). Con día y hora queda confirmada; sin ellos, por confirmar. */
export function NuevaVisitaDialog({
  inmuebles,
  inmuebleInicial,
  onCreada,
  children,
}: {
  inmuebles: InmuebleResumen[];
  inmuebleInicial?: number;
  onCreada: () => void;
  children: ReactNode;
}) {
  const [abierto, setAbierto] = useState(false);
  const [inmueble, setInmueble] = useState<string>(inmuebleInicial ? String(inmuebleInicial) : "");
  const [nombre, setNombre] = useState("");
  const [telefono, setTelefono] = useState("");
  const [dia, setDia] = useState("");
  const [hora, setHora] = useState("");
  const [preferencia, setPreferencia] = useState("");
  const [notas, setNotas] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const disponibles = inmuebles.filter((i) => i.estado !== "archivado");

  async function guardar(e: FormEvent) {
    e.preventDefault();
    if ((dia && !hora) || (!dia && hora)) {
      setError("Pon el día y la hora juntos (o ninguno, si todavía no está confirmada).");
      return;
    }
    setGuardando(true);
    setError(null);
    try {
      await apiFetch("/visitas", {
        method: "POST",
        body: JSON.stringify({
          inmuebleId: Number(inmueble),
          nombreCliente: nombre.trim() || null,
          telefono: telefono.trim() || null,
          fechaHora: dia && hora ? instanteEcuador(dia, hora) : null,
          preferenciaCliente: preferencia.trim() || null,
          notas: notas.trim() || null,
        }),
      });
      toast.success("Visita agregada a la agenda.");
      setAbierto(false);
      setNombre("");
      setTelefono("");
      setDia("");
      setHora("");
      setPreferencia("");
      setNotas("");
      onCreada();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo agregar la visita.");
    } finally {
      setGuardando(false);
    }
  }

  return (
    <Dialog open={abierto} onOpenChange={setAbierto}>
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent className="max-h-[92dvh] overflow-y-auto">
        <form onSubmit={guardar} className="space-y-4">
          <DialogHeader>
            <DialogTitle>Nueva visita</DialogTitle>
            <DialogDescription>Con día y hora queda confirmada; sin ellos, por confirmar.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-1.5">
            <Label htmlFor="visita-inmueble">Propiedad</Label>
            <Select value={inmueble} onValueChange={setInmueble} disabled={guardando}>
              <SelectTrigger id="visita-inmueble" className="w-full">
                <SelectValue placeholder="Elige la propiedad" />
              </SelectTrigger>
              <SelectContent>
                {disponibles.map((i) => (
                  <SelectItem key={i.id} value={String(i.id)}>
                    {i.titulo}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="grid gap-1.5">
              <Label htmlFor="visita-nombre">Nombre del cliente</Label>
              <Input id="visita-nombre" value={nombre} onChange={(e) => setNombre(e.target.value)} disabled={guardando} />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="visita-telefono">Teléfono</Label>
              <Input id="visita-telefono" inputMode="tel" value={telefono} onChange={(e) => setTelefono(e.target.value)} disabled={guardando} />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="visita-dia">Día</Label>
              <Input id="visita-dia" type="date" value={dia} onChange={(e) => setDia(e.target.value)} disabled={guardando} />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="visita-hora">Hora</Label>
              <Input id="visita-hora" type="time" value={hora} onChange={(e) => setHora(e.target.value)} disabled={guardando} />
            </div>
          </div>
          {!dia && (
            <div className="grid gap-1.5">
              <Label htmlFor="visita-preferencia">Qué día y hora prefiere</Label>
              <Input id="visita-preferencia" value={preferencia} onChange={(e) => setPreferencia(e.target.value)} placeholder="El sábado en la mañana" disabled={guardando} />
            </div>
          )}
          <div className="grid gap-1.5">
            <Label htmlFor="visita-notas">
              Notas <span className="font-normal text-muted-foreground">(opcional)</span>
            </Label>
            <Textarea id="visita-notas" value={notas} onChange={(e) => setNotas(e.target.value)} rows={2} disabled={guardando} />
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
            <Button type="submit" disabled={guardando || !inmueble}>
              {guardando && <Loader2 className="animate-spin" />} Agregar
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
