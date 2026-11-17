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
import { Textarea } from "@/components/ui/textarea";
import { apiFetch, ApiError } from "@/lib/api";
import type { LeadConversacion } from "@/types/conversacion";

/** La indicación para el repartidor que se propone en un retiro en agencia (la misma del parámetro de fábrica). */
const INDICACION_AGENCIA = "RETIRO EN AGENCIA SERVIENTREGA: el cliente retira con su cédula.";

type Tipo = "domicilio" | "agencia" | "sin_definir";

/** El dueño corrige o completa los datos de envío del pedido en curso: p. ej. escribe la agencia de Servientrega que acordó
 * con el cliente. Después, con «Que Victoria continúe», ella le muestra el resumen al cliente para que lo confirme. */
export function DatosEnvioDialog({ conversacionId, lead, trigger, onGuardado }: { conversacionId: string; lead: LeadConversacion; trigger: ReactNode; onGuardado: () => void }) {
  const [abierto, setAbierto] = useState(false);
  const [tipo, setTipo] = useState<Tipo>(lead.tipoEntrega ?? "sin_definir");
  const [nombre, setNombre] = useState(lead.nombreCliente ?? "");
  const [direccion, setDireccion] = useState(lead.direccion ?? "");
  const [referencia, setReferencia] = useState(lead.referencia ?? "");
  const [indicaciones, setIndicaciones] = useState(lead.indicacionesEntrega ?? "");
  const [canton, setCanton] = useState(lead.canton ?? "");
  const [provincia, setProvincia] = useState(lead.provincia ?? "");
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<{ mensaje: string; sugerencias: string[] } | null>(null);

  function alCambiarApertura(valor: boolean) {
    setAbierto(valor);
    if (valor) {
      const t: Tipo = lead.tipoEntrega ?? "sin_definir";
      setTipo(t);
      setNombre(lead.nombreCliente ?? "");
      // Con retiro en agencia todavía sin definir, la dirección que haya es la de la casa: se deja vacía para escribir la de la agencia.
      setDireccion(t === "agencia" && !lead.agenciaDefinidaEn ? "" : lead.direccion ?? "");
      setReferencia(lead.referencia ?? "");
      setIndicaciones(lead.indicacionesEntrega ?? (t === "agencia" ? INDICACION_AGENCIA : ""));
      setCanton(lead.canton ?? "");
      setProvincia(lead.provincia ?? "");
      setError(null);
    }
  }

  function cambiarTipo(valor: string) {
    const t = valor as Tipo;
    setTipo(t);
    if (t === "agencia" && !indicaciones.trim()) setIndicaciones(INDICACION_AGENCIA);
    if (t !== "agencia" && indicaciones === INDICACION_AGENCIA) setIndicaciones("");
  }

  async function guardar(e: FormEvent) {
    e.preventDefault();
    if (tipo === "agencia" && !direccion.trim()) {
      setError({ mensaje: "Escribe la dirección de la agencia de Servientrega.", sugerencias: [] });
      return;
    }
    setGuardando(true);
    setError(null);
    try {
      await apiFetch(`/conversaciones/${conversacionId}/datos-envio`, {
        method: "PUT",
        body: JSON.stringify({
          tipoEntrega: tipo === "sin_definir" ? null : tipo,
          nombreCliente: nombre,
          direccion,
          referencia,
          indicacionesEntrega: indicaciones,
          canton,
          provincia,
        }),
      });
      toast.success("Datos de envío guardados.", { description: "Pulsa «Que Victoria continúe» para que le muestre el resumen al cliente." });
      setAbierto(false);
      onGuardado();
    } catch (err) {
      if (err instanceof ApiError) {
        // En un 422 de ciudad/provincia, los nombres parecidos llegan como «bloqueos».
        setError({ mensaje: err.message, sugerencias: err.status === 422 ? err.bloqueos.filter((b) => !b.includes(":")) : [] });
      } else {
        setError({ mensaje: "No se pudo conectar con el servidor.", sugerencias: [] });
      }
    } finally {
      setGuardando(false);
    }
  }

  const esAgencia = tipo === "agencia";

  return (
    <Dialog open={abierto} onOpenChange={alCambiarApertura}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="max-h-[92dvh] overflow-y-auto">
        <form onSubmit={(e) => void guardar(e)} noValidate>
          <DialogHeader>
            <div className="flex items-center gap-1 pr-8">
              <DialogTitle>Datos de envío</DialogTitle>
              <InfoButton titulo="Datos de envío">
                <p>Aquí corriges o completas los datos con los que se creará el pedido en Rocketfy.</p>
                <ul>
                  <li>
                    <strong>Retiro en agencia:</strong> escribe la dirección de la agencia de Servientrega que acordaste con el cliente. Esa es la dirección del pedido.
                  </li>
                  <li>
                    <strong>Indicaciones:</strong> lo que lee el repartidor. En un retiro en agencia viene propuesto «retira con su cédula».
                  </li>
                  <li>
                    <strong>Después:</strong> pulsa «Que Victoria continúe». Ella le muestra el resumen al cliente; cuando él confirma, se crea el pedido.
                  </li>
                </ul>
                <p>Si cambias algo que el cliente ya había confirmado, Victoria se lo vuelve a mostrar para que confirme otra vez.</p>
              </InfoButton>
            </div>
            <DialogDescription>Lo que quede aquí es lo que se enviará a Rocketfy.</DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            {lead.agenciaIndicada && (
              <p className="rounded-lg bg-status-info-soft p-3 text-sm text-status-info-ink">
                El cliente dijo: «{lead.agenciaIndicada}»
              </p>
            )}
            <div className="grid gap-1.5">
              <Label htmlFor="envio-tipo">Entrega</Label>
              <Select value={tipo} onValueChange={cambiarTipo} disabled={guardando}>
                <SelectTrigger id="envio-tipo" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="agencia">Retiro en agencia de Servientrega</SelectItem>
                  <SelectItem value="domicilio">A domicilio</SelectItem>
                  <SelectItem value="sin_definir">Sin definir</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="envio-nombre">Nombre del cliente</Label>
              <Input id="envio-nombre" value={nombre} onChange={(e) => setNombre(e.target.value)} maxLength={120} disabled={guardando} autoComplete="off" />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="envio-direccion">{esAgencia ? "Dirección de la agencia" : "Dirección"}</Label>
              <Textarea
                id="envio-direccion"
                rows={2}
                value={direccion}
                onChange={(e) => setDireccion(e.target.value)}
                maxLength={300}
                placeholder={esAgencia ? "Ej.: Servientrega Centro, Av. 9 de Octubre 100 y Pedro Carbo" : "Calle, número e intersección"}
                disabled={guardando}
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="envio-referencia">
                Referencia <span className="font-normal text-muted-foreground">(opcional)</span>
              </Label>
              <Input id="envio-referencia" value={referencia} onChange={(e) => setReferencia(e.target.value)} maxLength={300} placeholder="Ej.: frente al parque" disabled={guardando} />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="grid gap-1.5">
                <Label htmlFor="envio-canton">Ciudad (cantón)</Label>
                <Input id="envio-canton" value={canton} onChange={(e) => setCanton(e.target.value)} maxLength={80} disabled={guardando} />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="envio-provincia">Provincia</Label>
                <Input id="envio-provincia" value={provincia} onChange={(e) => setProvincia(e.target.value)} maxLength={80} disabled={guardando} />
              </div>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="envio-indicaciones">
                Indicaciones para el repartidor <span className="font-normal text-muted-foreground">(opcional)</span>
              </Label>
              <Textarea id="envio-indicaciones" rows={2} value={indicaciones} onChange={(e) => setIndicaciones(e.target.value)} maxLength={500} disabled={guardando} />
            </div>

            {error && (
              <div role="alert" className="flex items-start gap-2 rounded-lg bg-status-danger-soft p-3 text-sm text-status-danger-ink">
                <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
                <div className="min-w-0 space-y-1">
                  <p>{error.mensaje}</p>
                  {error.sugerencias.length > 0 && <p>¿Quisiste decir: {error.sugerencias.join(", ")}?</p>}
                </div>
              </div>
            )}
          </div>

          <DialogFooter>
            <DialogClose asChild>
              <Button type="button" variant="outline" disabled={guardando}>
                Cancelar
              </Button>
            </DialogClose>
            <Button type="submit" disabled={guardando}>
              {guardando ? (
                <>
                  <Loader2 className="animate-spin" /> Guardando…
                </>
              ) : (
                "Guardar datos de envío"
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
