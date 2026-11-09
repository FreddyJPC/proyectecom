"use client";

import { Loader2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, apiFetch } from "@/lib/api";
import { MOTIVOS_PERDIDA, TEMPERATURAS, temperaturaInfo } from "@/lib/leads";
import { cn } from "@/lib/utils";
import type { Lead, MotivoPerdida, Temperatura } from "@/types/leads";

const ORDEN: Temperatura[] = ["caliente", "tibio", "frio", "perdido", "ganado"];
const NOTA_MAX = 300;

/** El dueño corrige la temperatura a mano. Queda fijada unos días: ni el enfriamiento automático ni Victoria la cambian. */
export function CambiarTemperaturaDialog({
  lead,
  abierto,
  onAbiertoChange,
  onGuardado,
}: {
  lead: Lead;
  abierto: boolean;
  onAbiertoChange: (abierto: boolean) => void;
  onGuardado: () => void;
}) {
  const [temperatura, setTemperatura] = useState<Temperatura>(lead.temperatura);
  const [motivoPerdida, setMotivoPerdida] = useState<MotivoPerdida>(lead.motivoPerdida ?? "no_le_interesa");
  const [nota, setNota] = useState("");
  const [guardando, setGuardando] = useState(false);

  function cambiarAbierto(valor: boolean) {
    if (valor) {
      // Cada vez que se abre parte de lo que tiene el lead ahora.
      setTemperatura(lead.temperatura);
      setMotivoPerdida(lead.motivoPerdida ?? "no_le_interesa");
      setNota("");
    }
    onAbiertoChange(valor);
  }

  async function guardar() {
    setGuardando(true);
    try {
      await apiFetch(`/leads/${lead.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          temperatura,
          motivoPerdida: temperatura === "perdido" ? motivoPerdida : null,
          motivo: nota.trim() || null,
        }),
      });
      toast.success(`Lead marcado como ${temperaturaInfo(temperatura).label.toLowerCase()}.`);
      onAbiertoChange(false);
      onGuardado();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo cambiar la temperatura.");
    } finally {
      setGuardando(false);
    }
  }

  const sinCambios = temperatura === lead.temperatura && (temperatura !== "perdido" || motivoPerdida === (lead.motivoPerdida ?? motivoPerdida)) && nota.trim() === "";

  return (
    <Dialog open={abierto} onOpenChange={cambiarAbierto}>
      <DialogContent className="max-h-[90dvh] gap-0 overflow-hidden p-0 sm:max-w-md">
        <DialogHeader className="border-b px-4 py-3.5 pr-12">
          <DialogTitle>Cambiar la temperatura</DialogTitle>
          <DialogDescription>Queda fijada unos días: Victoria y el enfriamiento automático no la cambian.</DialogDescription>
        </DialogHeader>

        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-4">
          <fieldset className="space-y-2">
            <legend className="mb-2 text-sm font-medium">¿Qué tan probable es que compre?</legend>
            {ORDEN.map((t) => {
              const info = TEMPERATURAS[t];
              return (
                <label
                  key={t}
                  className={cn(
                    "flex min-h-12 cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors hover:bg-muted/60",
                    "has-[:checked]:border-primary has-[:checked]:bg-accent has-[:focus-visible]:ring-3 has-[:focus-visible]:ring-ring/50",
                  )}
                >
                  <input
                    type="radio"
                    name="temperatura"
                    value={t}
                    checked={temperatura === t}
                    onChange={() => setTemperatura(t)}
                    className="mt-1 size-4 shrink-0 accent-[var(--primary)]"
                  />
                  <span className="min-w-0">
                    <span className="block text-sm font-medium">{info.label}</span>
                    <span className="block text-xs text-muted-foreground">{info.explicacion}</span>
                  </span>
                </label>
              );
            })}
          </fieldset>

          {temperatura === "perdido" && (
            <div className="space-y-1.5">
              <Label htmlFor="motivo-perdida">¿Por qué se perdió?</Label>
              <Select value={motivoPerdida} onValueChange={(v) => setMotivoPerdida(v as MotivoPerdida)}>
                <SelectTrigger id="motivo-perdida" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(MOTIVOS_PERDIDA).map(([clave, etiqueta]) => (
                    <SelectItem key={clave} value={clave}>
                      {etiqueta}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          <div className="space-y-1.5">
            <Label htmlFor="nota-temperatura">Nota (opcional)</Label>
            <Textarea
              id="nota-temperatura"
              rows={2}
              maxLength={NOTA_MAX}
              placeholder="Por ejemplo: me confirmó por llamada que compra el viernes"
              value={nota}
              onChange={(e) => setNota(e.target.value)}
            />
          </div>
        </div>

        <DialogFooter className="m-0 shrink-0 rounded-b-xl">
          <DialogClose asChild>
            <Button type="button" variant="outline" disabled={guardando}>
              Cancelar
            </Button>
          </DialogClose>
          <Button type="button" onClick={guardar} disabled={guardando || sinCambios}>
            {guardando && <Loader2 className="animate-spin" />} Guardar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** Marcar o quitar «no contactar» en la PERSONA (vale para todos sus canales y leads). */
export function NoContactarDialog({
  contactoId,
  nombre,
  activar,
  abierto,
  onAbiertoChange,
  onGuardado,
}: {
  contactoId: number;
  nombre: string;
  /** true = marcar «no contactar»; false = volver a permitir que se le escriba. */
  activar: boolean;
  abierto: boolean;
  onAbiertoChange: (abierto: boolean) => void;
  onGuardado: () => void;
}) {
  const [motivo, setMotivo] = useState("");
  const [guardando, setGuardando] = useState(false);

  async function guardar() {
    setGuardando(true);
    try {
      await apiFetch(`/contactos/${contactoId}/no-contactar`, {
        method: "PUT",
        body: JSON.stringify({ noContactar: activar, motivo: activar ? motivo.trim() || null : null }),
      });
      toast.success(activar ? `${nombre} quedó como «no contactar».` : `A ${nombre} se le puede volver a escribir.`);
      onAbiertoChange(false);
      setMotivo("");
      onGuardado();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo guardar el cambio.");
    } finally {
      setGuardando(false);
    }
  }

  return (
    <Dialog open={abierto} onOpenChange={onAbiertoChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{activar ? "¿Marcar como «no contactar»?" : "¿Volver a permitir mensajes?"}</DialogTitle>
          <DialogDescription>
            {activar
              ? `Nadie del sistema le escribirá a ${nombre} por iniciativa propia, en ningún canal, y sus leads abiertos pasan a «perdido». Si él escribe, Victoria seguirá atendiéndolo.`
              : `Los seguimientos automáticos podrán volver a escribirle a ${nombre}. Sus leads perdidos no se reabren solos.`}
          </DialogDescription>
        </DialogHeader>
        {activar && (
          <div className="space-y-1.5">
            <Label htmlFor="motivo-no-contactar">Motivo (opcional)</Label>
            <Textarea
              id="motivo-no-contactar"
              rows={2}
              maxLength={NOTA_MAX}
              placeholder="Por ejemplo: pidió que no le escribamos más"
              value={motivo}
              onChange={(e) => setMotivo(e.target.value)}
            />
          </div>
        )}
        <DialogFooter>
          <DialogClose asChild>
            <Button type="button" variant="outline" disabled={guardando}>
              Cancelar
            </Button>
          </DialogClose>
          {/* El rojo «destructive» no llega a contraste AA sobre el fondo del cuadro en modo oscuro: va el par «status-danger». */}
          <Button
            type="button"
            variant={activar ? "outline" : "default"}
            className={activar ? "border-status-danger/40 bg-status-danger-soft text-status-danger-ink hover:bg-status-danger-soft/70 hover:text-status-danger-ink dark:bg-status-danger-soft dark:hover:bg-status-danger-soft/70" : undefined}
            onClick={guardar}
            disabled={guardando}
          >
            {guardando && <Loader2 className="animate-spin" />} {activar ? "Sí, no contactar" : "Sí, permitir"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
