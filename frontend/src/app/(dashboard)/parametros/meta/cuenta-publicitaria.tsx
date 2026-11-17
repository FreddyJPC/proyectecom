"use client";

import { Loader2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { InfoButton } from "@/components/app/info-button";
import { ListSkeleton } from "@/components/app/list-skeleton";
import { SectionCard } from "@/components/app/section-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useApi } from "@/hooks/use-api";
import { apiFetch, ApiError } from "@/lib/api";
import type { CuentaPublicitaria } from "@/types/meta";

/** La cuenta publicitaria de la que se leen los anuncios y su gasto (ADR-017). No es un secreto: es un número de Meta. */
export function CuentaPublicitariaCard() {
  const cuenta = useApi<CuentaPublicitaria>("/meta/cuenta");

  return (
    <SectionCard
      titulo="Cuenta publicitaria"
      descripcion="De dónde se leen tus anuncios y su gasto."
      info={
        <InfoButton titulo="Cuenta publicitaria">
          <p>Es el número de tu cuenta en el Administrador de anuncios de Meta (puede empezar con «act_»). Con él, el sistema lee cada hora tus anuncios y cuánto gastó cada uno.</p>
          <p>Para que funcione, la app de Meta necesita permiso de anuncios y el usuario del sistema tiene que tener asignada esta cuenta. Después enciende «Leer mis anuncios de Meta» en Parámetros.</p>
          <p>Solo lee. Pausar un anuncio solo pasa si tú lo pides o si encendiste la pausa automática.</p>
        </InfoButton>
      }
    >
      {cuenta.cargando ? (
        <div className="p-4 sm:p-5">
          <ListSkeleton filas={1} />
        </div>
      ) : cuenta.error || !cuenta.data ? (
        <div role="alert" className="flex flex-wrap items-center gap-3 p-4 text-sm text-status-danger-ink sm:p-5">
          <span>{cuenta.error ?? "No se pudo leer."}</span>
          <Button size="sm" variant="outline" onClick={cuenta.recargar}>
            Reintentar
          </Button>
        </div>
      ) : (
        <Formulario key={cuenta.data.cuentaPublicitaria ?? ""} inicial={cuenta.data.cuentaPublicitaria ?? ""} onGuardado={cuenta.recargar} />
      )}
    </SectionCard>
  );
}

function Formulario({ inicial, onGuardado }: { inicial: string; onGuardado: () => void }) {
  const [valor, setValor] = useState(inicial);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function guardar() {
    setGuardando(true);
    setError(null);
    try {
      await apiFetch<CuentaPublicitaria>("/meta/cuenta", { method: "PUT", body: JSON.stringify({ cuentaPublicitaria: valor.trim() || null }) });
      toast.success("Cuenta publicitaria guardada.");
      onGuardado();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo conectar con el servidor.");
    } finally {
      setGuardando(false);
    }
  }

  return (
    <div className="flex flex-wrap items-end gap-3 p-4 sm:p-5">
      <div className="grid min-w-0 flex-1 gap-1.5 sm:max-w-xs">
        <Label htmlFor="cuenta-publicitaria">Número de la cuenta</Label>
        <Input id="cuenta-publicitaria" inputMode="numeric" value={valor} onChange={(e) => setValor(e.target.value)} placeholder="act_1445728047079452" aria-invalid={Boolean(error)} className="tabular" disabled={guardando} />
      </div>
      <Button type="button" disabled={guardando || valor.trim() === inicial} onClick={() => void guardar()}>
        {guardando ? <Loader2 className="animate-spin" /> : null} Guardar
      </Button>
      {error && (
        <p role="alert" className="basis-full text-sm text-status-danger-ink">
          {error}
        </p>
      )}
    </div>
  );
}
