"use client";

import { Loader2, PackageCheck, RefreshCw, TriangleAlert } from "lucide-react";
import { useState, type FormEvent, type ReactNode } from "react";
import { toast } from "sonner";

import { InfoButton } from "@/components/app/info-button";
import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiFetch, ApiError } from "@/lib/api";
import { formatFechaHora, formatMoney } from "@/lib/format";

/** Un pedido de Rocketfy del que llegó aviso y que todavía no es de ninguna conversación (hecho a mano en su panel). */
interface PedidoSinVincular {
  idRocketfy: number;
  estado: string | null;
  transportadora: string | null;
  total: string | null;
  ultimoAviso: string | null;
}

interface Resultado {
  idLocal: number;
  idRocketfy: number;
  total: string;
  avisos: string[];
}

const OTRO = "otro";

/** «Ya hice el pedido en Rocketfy»: une a esta venta un pedido que el dueño creó a mano en el panel de Rocketfy, para que la
 * venta quede cerrada (sin riesgo de un segundo pedido) y los avisos de Rocketfy lleguen a este cliente. */
export function PedidoRocketfyDialog({ conversacionId, trigger, onListo }: { conversacionId: string; trigger: ReactNode; onListo: () => void }) {
  const [abierto, setAbierto] = useState(false);
  const [lista, setLista] = useState<PedidoSinVincular[] | null>(null);
  const [cargando, setCargando] = useState(false);
  const [errorLista, setErrorLista] = useState<string | null>(null);
  const [elegido, setElegido] = useState<string>(OTRO);
  const [numero, setNumero] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function cargar() {
    setCargando(true);
    setErrorLista(null);
    try {
      const datos = await apiFetch<{ items: PedidoSinVincular[] }>(`/conversaciones/${conversacionId}/pedidos-rocketfy`);
      setLista(datos.items);
      setElegido(datos.items.length > 0 ? String(datos.items[0].idRocketfy) : OTRO);
    } catch (err) {
      setLista([]);
      setElegido(OTRO);
      setErrorLista(err instanceof ApiError ? err.message : "No se pudo cargar la lista.");
    } finally {
      setCargando(false);
    }
  }

  function alCambiarApertura(valor: boolean) {
    setAbierto(valor);
    if (valor) {
      setNumero("");
      setError(null);
      void cargar();
    }
  }

  async function registrar(e: FormEvent) {
    e.preventDefault();
    const id = elegido === OTRO ? Number(numero.trim()) : Number(elegido);
    if (!Number.isInteger(id) || id <= 0) {
      setError("Escribe el número del pedido tal como aparece en Rocketfy (solo números).");
      return;
    }
    setGuardando(true);
    setError(null);
    try {
      const r = await apiFetch<Resultado>(`/conversaciones/${conversacionId}/pedido-rocketfy`, {
        method: "POST",
        body: JSON.stringify({ idRocketfy: id }),
      });
      if (r.avisos.length > 0) {
        toast.warning(`Pedido ${r.idRocketfy} registrado. Revisa:`, { description: r.avisos.join(" "), duration: 12000 });
      } else {
        toast.success(`Pedido ${r.idRocketfy} registrado.`, { description: "La venta quedó cerrada en el sistema." });
      }
      setAbierto(false);
      onListo();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo conectar con el servidor.");
    } finally {
      setGuardando(false);
    }
  }

  return (
    <Dialog open={abierto} onOpenChange={alCambiarApertura}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="max-h-[92dvh] overflow-y-auto">
        <form onSubmit={(e) => void registrar(e)} noValidate>
          <DialogHeader>
            <div className="flex items-center gap-1 pr-8">
              <DialogTitle>Ya hice el pedido en Rocketfy</DialogTitle>
              <InfoButton titulo="Pedido hecho a mano">
                <p>Úsalo cuando creaste el pedido de este cliente directamente en el panel de Rocketfy.</p>
                <ul>
                  <li>La venta queda cerrada: Victoria ya no puede crear otro pedido para este cliente.</li>
                  <li>Los avisos de Rocketfy (por ejemplo, «paquete en agencia») ya saben de quién es el pedido.</li>
                  <li>La venta cuenta en tus métricas.</li>
                </ul>
                <p>
                  Antes de unirlo, el sistema consulta a Rocketfy que el pedido exista y que sea del mismo teléfono de este cliente. No crea ni
                  cambia nada en Rocketfy.
                </p>
              </InfoButton>
            </div>
            <DialogDescription>Elige el pedido que creaste para este cliente.</DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            {cargando ? (
              <p className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="size-4 animate-spin" aria-hidden /> Buscando pedidos recientes…
              </p>
            ) : (
              <fieldset className="grid gap-2" disabled={guardando}>
                <legend className="mb-1 text-sm font-medium">Pedidos recientes sin cliente en el sistema</legend>
                {errorLista && (
                  <div role="alert" className="flex items-center justify-between gap-2 rounded-lg bg-status-danger-soft p-3 text-sm text-status-danger-ink">
                    <span>{errorLista}</span>
                    <Button type="button" variant="outline" size="sm" onClick={() => void cargar()} className="bg-card text-foreground">
                      <RefreshCw /> Reintentar
                    </Button>
                  </div>
                )}
                {lista && lista.length === 0 && !errorLista && (
                  <p className="text-sm text-muted-foreground">No llegó aviso de ningún pedido nuevo. Escribe su número abajo.</p>
                )}
                {lista?.map((p) => (
                  <label
                    key={p.idRocketfy}
                    className="flex min-h-11 cursor-pointer items-start gap-3 rounded-lg border p-3 text-sm has-[:checked]:border-primary has-[:checked]:bg-primary/5"
                  >
                    <input
                      type="radio"
                      name="pedido-rocketfy"
                      value={String(p.idRocketfy)}
                      checked={elegido === String(p.idRocketfy)}
                      onChange={() => setElegido(String(p.idRocketfy))}
                      className="mt-0.5 size-4 accent-primary"
                    />
                    <span className="min-w-0 flex-1">
                      <span className="flex flex-wrap items-baseline justify-between gap-x-3">
                        <span className="font-medium tabular">Pedido {p.idRocketfy}</span>
                        {p.total && <span className="tabular font-semibold">{formatMoney(p.total)}</span>}
                      </span>
                      <span className="block text-muted-foreground">
                        {[p.estado, p.transportadora, p.ultimoAviso ? formatFechaHora(p.ultimoAviso) : null].filter(Boolean).join(" · ")}
                      </span>
                    </span>
                  </label>
                ))}
                <label className="flex min-h-11 cursor-pointer items-start gap-3 rounded-lg border p-3 text-sm has-[:checked]:border-primary has-[:checked]:bg-primary/5">
                  <input
                    type="radio"
                    name="pedido-rocketfy"
                    value={OTRO}
                    checked={elegido === OTRO}
                    onChange={() => setElegido(OTRO)}
                    className="mt-0.5 size-4 accent-primary"
                  />
                  <span className="font-medium">Escribir el número</span>
                </label>
              </fieldset>
            )}

            {elegido === OTRO && !cargando && (
              <div className="grid gap-1.5">
                <Label htmlFor="pedido-rocketfy-numero">Número del pedido en Rocketfy</Label>
                <Input
                  id="pedido-rocketfy-numero"
                  inputMode="numeric"
                  value={numero}
                  onChange={(e) => setNumero(e.target.value.replace(/\D/g, ""))}
                  maxLength={12}
                  placeholder="Ej.: 413585"
                  disabled={guardando}
                  autoComplete="off"
                />
              </div>
            )}

            {error && (
              <div role="alert" className="flex items-start gap-2 rounded-lg bg-status-danger-soft p-3 text-sm text-status-danger-ink">
                <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
                <p className="min-w-0">{error}</p>
              </div>
            )}
          </div>

          <DialogFooter>
            <DialogClose asChild>
              <Button type="button" variant="outline" disabled={guardando}>
                Cancelar
              </Button>
            </DialogClose>
            <Button type="submit" disabled={guardando || cargando}>
              {guardando ? <Loader2 className="animate-spin" /> : <PackageCheck />}
              {guardando ? "Registrando…" : "Registrar pedido"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
