"use client";

import { useState, type FormEvent, type ReactNode } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiFetch, ApiError } from "@/lib/api";

/** Agregar o editar un SKU monitoreado. POST /productos/monitoreados hace
 * upsert -- reutilizarlo para "editar umbral" es el mismo endpoint. */
export function MonitorearDialog({
  sku,
  umbralInicial = 5,
  onSuccess,
  trigger,
}: {
  sku: string;
  umbralInicial?: number;
  onSuccess: () => void;
  trigger: ReactNode;
}) {
  const [abierto, setAbierto] = useState(false);
  const [umbral, setUmbral] = useState(umbralInicial);
  const [guardando, setGuardando] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setGuardando(true);
    try {
      await apiFetch("/productos/monitoreados", {
        method: "POST",
        body: JSON.stringify({ sku, umbralStockMinimo: umbral }),
      });
      toast.success(`SKU '${sku}' monitoreado con umbral ${umbral}.`);
      setAbierto(false);
      onSuccess();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo guardar el SKU monitoreado.");
    } finally {
      setGuardando(false);
    }
  }

  return (
    <Dialog open={abierto} onOpenChange={setAbierto}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent>
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Monitorear SKU</DialogTitle>
            <DialogDescription>
              Se avisará en Incidencias cuando el stock de <strong>{sku}</strong> caiga a este umbral o menos.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-1.5 py-4">
            <Label htmlFor="umbral">Umbral de stock mínimo</Label>
            <Input
              id="umbral"
              type="number"
              min={0}
              value={umbral}
              onChange={(e) => setUmbral(Number(e.target.value))}
              required
            />
          </div>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline" type="button">
                Cancelar
              </Button>
            </DialogClose>
            <Button type="submit" disabled={guardando}>
              {guardando ? "Guardando…" : "Guardar"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
