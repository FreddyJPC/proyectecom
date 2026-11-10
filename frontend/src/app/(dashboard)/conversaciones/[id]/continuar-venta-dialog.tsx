"use client";

import { Loader2 } from "lucide-react";
import { useState, type ReactNode } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { apiFetch, ApiError } from "@/lib/api";

const LIMITE_NOTA = 500;

/** Le devuelve la conversación a Victoria para que SIGA CERRANDO LA VENTA. Con `pagoConfirmado`, además deja constancia de que el
 * dueño vio el pago en su banco (Victoria ya no pide comprobante y puede cerrar el pedido). La nota es una indicación opcional
 * para ella; el cliente nunca la ve. */
export function ContinuarVentaDialog({
  conversacionId,
  pagoConfirmado,
  total,
  trigger,
  onListo,
}: {
  conversacionId: string;
  pagoConfirmado: boolean;
  total?: string | null;
  trigger: ReactNode;
  onListo: () => void;
}) {
  const [abierto, setAbierto] = useState(false);
  const [nota, setNota] = useState("");
  const [enviando, setEnviando] = useState(false);

  async function confirmar() {
    setEnviando(true);
    try {
      const r = await apiFetch<{ victoriaContinua: boolean }>(`/conversaciones/${conversacionId}/continuar`, {
        method: "POST",
        body: JSON.stringify({ pagoConfirmado, nota: nota.trim() || null }),
      });
      if (r.victoriaContinua) {
        toast.success(pagoConfirmado ? "Pago confirmado. Victoria le avisa al cliente y sigue con el pedido." : "Victoria continúa con la venta.");
      } else {
        toast.warning(
          `${pagoConfirmado ? "Pago confirmado. " : ""}La ventana de 24 h está cerrada: Victoria no puede escribirle ahora y seguirá apenas el cliente escriba.`,
        );
      }
      setAbierto(false);
      setNota("");
      onListo();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo continuar con la venta.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Dialog open={abierto} onOpenChange={setAbierto}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{pagoConfirmado ? "¿Confirmas que llegó el pago?" : "Que Victoria continúe con la venta"}</DialogTitle>
          <DialogDescription>
            {pagoConfirmado
              ? `Revisa tu banco antes de confirmar${total ? ` (valor esperado: ${total})` : ""}. Victoria le avisará al cliente que recibimos su pago y seguirá con el pedido.`
              : "Victoria retoma la conversación: pide lo que falte y cierra el pedido hasta donde pueda. Cuando no pueda avanzar, te la pasa de nuevo."}
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-1.5">
          <Label htmlFor="nota-victoria">
            Indicación para Victoria <span className="font-normal text-muted-foreground">(opcional)</span>
          </Label>
          <Textarea
            id="nota-victoria"
            value={nota}
            onChange={(e) => setNota(e.target.value.slice(0, LIMITE_NOTA))}
            rows={3}
            placeholder="Ej.: pídele su cédula y confirma que la entrega es en Cuenca"
          />
          <p className="text-xs text-muted-foreground">El cliente no la ve.</p>
        </div>
        <DialogFooter className="gap-2 sm:gap-2">
          <DialogClose asChild>
            <Button type="button" variant="outline">
              Cancelar
            </Button>
          </DialogClose>
          <Button type="button" onClick={() => void confirmar()} disabled={enviando}>
            {enviando && <Loader2 className="animate-spin" />}
            {pagoConfirmado ? "Sí, confirmar pago" : "Continuar"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
