"use client";

import { Loader2, Minus, Plus } from "lucide-react";
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
import { cn } from "@/lib/utils";

const SUGERIDOS = [5, 10, 20, 50];

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
      toast.success(`Vigilando ${sku}: te avisamos si quedan ${umbral} o menos.`);
      setAbierto(false);
      onSuccess();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo guardar el producto vigilado.");
    } finally {
      setGuardando(false);
    }
  }

  return (
    <Dialog
      open={abierto}
      onOpenChange={(v) => {
        if (v) setUmbral(umbralInicial);
        setAbierto(v);
      }}
    >
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent>
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Vigilar stock</DialogTitle>
            <DialogDescription>
              Te avisamos en Incidencias cuando el stock de <strong className="tabular text-foreground">{sku}</strong> baje a este mínimo o menos, para que pauses la publicidad a tiempo.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-3 py-5">
            <Label htmlFor="umbral">Avisarme cuando queden…</Label>
            <div className="flex items-center gap-2">
              <Button type="button" variant="outline" size="icon" onClick={() => setUmbral((u) => Math.max(0, u - 1))} aria-label="Menos">
                <Minus />
              </Button>
              <Input id="umbral" type="number" inputMode="numeric" min={0} required value={umbral} onChange={(e) => setUmbral(Math.max(0, Number(e.target.value)))} className="tabular w-24 text-center text-lg font-semibold" />
              <Button type="button" variant="outline" size="icon" onClick={() => setUmbral((u) => u + 1)} aria-label="Más">
                <Plus />
              </Button>
              <span className="text-sm text-muted-foreground">unidades</span>
            </div>
            <div className="flex flex-wrap gap-2" role="group" aria-label="Valores sugeridos">
              {SUGERIDOS.map((n) => (
                <button
                  key={n}
                  type="button"
                  onClick={() => setUmbral(n)}
                  className={cn(
                    "tabular h-9 min-w-12 rounded-full border px-3 text-sm font-medium transition-colors outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
                    umbral === n ? "border-primary bg-primary text-primary-foreground" : "bg-card hover:bg-muted",
                  )}
                >
                  {n}
                </button>
              ))}
            </div>
          </div>

          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline" type="button">
                Cancelar
              </Button>
            </DialogClose>
            <Button type="submit" disabled={guardando}>
              {guardando ? (
                <>
                  <Loader2 className="animate-spin" /> Guardando…
                </>
              ) : (
                "Guardar"
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
