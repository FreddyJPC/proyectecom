"use client";

import { Loader2, TriangleAlert } from "lucide-react";
import { useState, type FormEvent, type ReactNode } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { apiFetch, ApiError } from "@/lib/api";
import type { CuentaBancaria } from "@/types/cuentas-bancarias";

import { Campo } from "../../catalogo/producto/[sku]/campo";

type Formulario = { banco: string; tipoCuenta: string; numero: string; titular: string; identificacion: string; activa: boolean };

function inicial(c?: CuentaBancaria): Formulario {
  return {
    banco: c?.banco ?? "",
    tipoCuenta: c?.tipoCuenta ?? "",
    numero: c?.numero ?? "",
    titular: c?.titular ?? "",
    identificacion: c?.identificacion ?? "",
    activa: c?.activa ?? true,
  };
}

/** Agrega o edita una cuenta para transferir. Con `cuenta` edita; sin ella, crea. */
export function CuentaDialog({ trigger, cuenta, onGuardado }: { trigger: ReactNode; cuenta?: CuentaBancaria; onGuardado: () => void }) {
  const [abierto, setAbierto] = useState(false);
  const [f, setF] = useState<Formulario>(inicial(cuenta));
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const completo = f.banco.trim() !== "" && f.tipoCuenta.trim() !== "" && f.numero.trim() !== "" && f.titular.trim() !== "";

  function alCambiarApertura(valor: boolean) {
    setAbierto(valor);
    if (valor) {
      setF(inicial(cuenta));
      setError(null);
    }
  }

  async function guardar(e: FormEvent) {
    e.preventDefault();
    if (!completo || guardando) return;
    setGuardando(true);
    setError(null);
    const cuerpo = { ...f, banco: f.banco.trim(), tipoCuenta: f.tipoCuenta.trim(), numero: f.numero.trim(), titular: f.titular.trim(), identificacion: f.identificacion.trim() };
    try {
      await apiFetch(cuenta ? `/cuentas-bancarias/${cuenta.id}` : "/cuentas-bancarias", {
        method: cuenta ? "PATCH" : "POST",
        body: JSON.stringify(cuerpo),
      });
      toast.success(cuenta ? "Cuenta actualizada." : "Cuenta agregada.");
      setAbierto(false);
      onGuardado();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo guardar la cuenta.");
    } finally {
      setGuardando(false);
    }
  }

  const cambiar = (campo: keyof Formulario) => (e: { target: { value: string } }) => setF((x) => ({ ...x, [campo]: e.target.value }));

  return (
    <Dialog open={abierto} onOpenChange={alCambiarApertura}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-md">
        <form onSubmit={guardar} className="grid gap-4">
          <DialogHeader>
            <DialogTitle>{cuenta ? "Editar cuenta" : "Agregar cuenta"}</DialogTitle>
            <DialogDescription>Los datos que Victoria le mandará al cliente para transferir.</DialogDescription>
          </DialogHeader>

          <Campo id="cuenta-banco" label="Banco" ayuda="Como lo verá el cliente. Ej.: Banco Pichincha">
            <Input id="cuenta-banco" value={f.banco} onChange={cambiar("banco")} maxLength={60} autoComplete="off" aria-describedby="cuenta-banco-ayuda" />
          </Campo>
          <Campo id="cuenta-tipo" label="Tipo de cuenta" ayuda="Ej.: Cuenta de ahorros">
            <Input id="cuenta-tipo" value={f.tipoCuenta} onChange={cambiar("tipoCuenta")} maxLength={60} autoComplete="off" aria-describedby="cuenta-tipo-ayuda" />
          </Campo>
          <Campo id="cuenta-numero" label="Número de cuenta">
            <Input id="cuenta-numero" value={f.numero} onChange={cambiar("numero")} maxLength={40} inputMode="numeric" autoComplete="off" />
          </Campo>
          <Campo id="cuenta-titular" label="Titular">
            <Input id="cuenta-titular" value={f.titular} onChange={cambiar("titular")} maxLength={120} autoComplete="off" />
          </Campo>
          <Campo id="cuenta-identificacion" label="Cédula o RUC" opcional ayuda="Se le muestra al cliente">
            <Input id="cuenta-identificacion" value={f.identificacion} onChange={cambiar("identificacion")} maxLength={30} inputMode="numeric" autoComplete="off" aria-describedby="cuenta-identificacion-ayuda" />
          </Campo>
          <div className="flex items-center justify-between gap-3 rounded-lg border px-3 py-2.5">
            <label htmlFor="cuenta-activa" className="text-sm font-medium">
              Cuenta activa
            </label>
            <Switch id="cuenta-activa" checked={f.activa} onCheckedChange={(v) => setF((x) => ({ ...x, activa: v }))} />
          </div>

          {error && (
            <div role="alert" className="flex items-start gap-2 rounded-lg border border-status-danger/30 bg-status-danger-soft p-3 text-sm text-status-danger-ink">
              <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
              <p>{error}</p>
            </div>
          )}

          <DialogFooter className="gap-2 sm:gap-2">
            <DialogClose asChild>
              <Button type="button" variant="outline">
                Cancelar
              </Button>
            </DialogClose>
            <Button type="submit" disabled={!completo || guardando}>
              {guardando && <Loader2 className="animate-spin" />}
              {guardando ? "Guardando…" : "Guardar"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
