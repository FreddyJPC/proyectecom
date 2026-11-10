"use client";

import { ArrowLeft, Landmark, Loader2, Pencil, Plus, Trash2, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { EmptyState } from "@/components/app/empty-state";
import { InfoButton } from "@/components/app/info-button";
import { ListSkeleton } from "@/components/app/list-skeleton";
import { PageHeader } from "@/components/app/page-header";
import { SectionCard } from "@/components/app/section-card";
import { StatusBadge } from "@/components/status-badge";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { useApi } from "@/hooks/use-api";
import { apiFetch, ApiError } from "@/lib/api";
import type { CuentaBancaria } from "@/types/cuentas-bancarias";

import { CuentaDialog } from "./cuenta-dialog";

export default function CuentasParaTransferirPage() {
  const { data, error, cargando, recargar } = useApi<CuentaBancaria[]>("/cuentas-bancarias");
  const [ocupada, setOcupada] = useState<number | null>(null);

  async function cambiarActiva(c: CuentaBancaria, activa: boolean) {
    setOcupada(c.id);
    try {
      await apiFetch(`/cuentas-bancarias/${c.id}`, { method: "PATCH", body: JSON.stringify({ activa }) });
      toast.success(activa ? "Cuenta activada." : "Cuenta apagada: Victoria ya no la da.");
      recargar();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo cambiar la cuenta.");
    } finally {
      setOcupada(null);
    }
  }

  async function borrar(c: CuentaBancaria) {
    setOcupada(c.id);
    try {
      await apiFetch(`/cuentas-bancarias/${c.id}`, { method: "DELETE" });
      toast.success("Cuenta borrada.");
      recargar();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo borrar la cuenta.");
    } finally {
      setOcupada(null);
    }
  }

  const activas = (data ?? []).filter((c) => c.activa).length;

  return (
    <>
      <Button asChild variant="ghost" size="sm" className="-ml-2 w-fit text-muted-foreground">
        <Link href="/parametros">
          <ArrowLeft /> Parámetros
        </Link>
      </Button>

      <PageHeader
        title="Cuentas para transferir"
        description="Las cuentas que Victoria le da al cliente que paga por transferencia."
        info={
          <InfoButton titulo="Cómo usa Victoria estas cuentas">
            <p>
              Cuando un cliente elige pagar por <strong>transferencia</strong>, Victoria le pregunta desde qué banco va a transferir. Si tienes una cuenta en ese banco, le manda
              esa; si no, le dice que por ahora no hay cuenta ahí y le ofrece los bancos que sí tienes, para que elija uno.
            </p>
            <h3>Para que nunca se equivoque</h3>
            <ul>
              <li>El mensaje con los datos lo arma el sistema con lo que escribes aquí; Victoria solo lo envía, nunca escribe un número de cuenta ella.</li>
              <li>Entiende el banco aunque el cliente lo escriba mal («Bano Pichncha», «la jep»). El nombre que pongas aquí es el que verá el cliente.</li>
              <li>Con la cédula o RUC el cliente puede verificar a quién le transfiere.</li>
            </ul>
            <h3>Orden y apagado</h3>
            <p>
              Si el cliente dice que le da igual el banco, Victoria da la cuenta de arriba (la principal). Una cuenta apagada no se da, pero no se pierde. Solo aplica a productos
              de Rocketfy que aceptan transferencia: en tus productos propios el pago lo coordinas tú.
            </p>
          </InfoButton>
        }
        actions={
          <CuentaDialog
            trigger={
              <Button>
                <Plus /> Agregar cuenta
              </Button>
            }
            onGuardado={recargar}
          />
        }
      />

      {error && !data ? (
        <div role="alert" className="flex flex-wrap items-center gap-3 rounded-xl border border-status-danger/30 bg-status-danger-soft p-4 text-status-danger-ink">
          <TriangleAlert className="size-5 shrink-0" aria-hidden />
          <p className="flex-1 text-sm">No se pudieron cargar las cuentas. {error}</p>
          <Button variant="outline" size="sm" onClick={recargar} className="bg-card text-foreground">
            Reintentar
          </Button>
        </div>
      ) : cargando || !data ? (
        <SectionCard titulo="Cuentas" descripcion="Un momento…">
          <ListSkeleton filas={3} />
        </SectionCard>
      ) : data.length === 0 ? (
        <SectionCard titulo="Cuentas">
          <EmptyState
            icon={Landmark}
            title="Aún no hay cuentas"
            description="Sin cuentas, si un cliente quiere transferir Victoria pasa la conversación a una persona."
            action={
              <CuentaDialog
                trigger={
                  <Button>
                    <Plus /> Agregar la primera cuenta
                  </Button>
                }
                onGuardado={recargar}
              />
            }
          />
        </SectionCard>
      ) : (
        <SectionCard titulo="Cuentas" descripcion={`${activas} de ${data.length} activas. La de arriba es la principal.`}>
          <ul className="divide-y">
            {data.map((c, i) => (
              <li key={c.id} className="flex flex-wrap items-center gap-3 px-4 py-4 sm:px-5">
                <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-status-neutral-soft text-status-neutral-ink">
                  <Landmark className="size-[1.1rem]" aria-hidden />
                </span>
                <div className="min-w-0 flex-1 space-y-0.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-semibold">{c.banco}</p>
                    {i === 0 && c.activa && <StatusBadge label="Principal" variant="info" />}
                    {!c.activa && <StatusBadge label="Apagada" variant="neutral" />}
                  </div>
                  <p className="tabular text-sm text-muted-foreground">
                    {c.tipoCuenta} · {c.numero}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    {c.titular}
                    {c.identificacion ? ` · ${c.identificacion}` : ""}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-1">
                  <Switch
                    checked={c.activa}
                    disabled={ocupada === c.id}
                    onCheckedChange={(v) => void cambiarActiva(c, v)}
                    aria-label={`${c.activa ? "Apagar" : "Activar"} la cuenta de ${c.banco}`}
                  />
                  <CuentaDialog
                    cuenta={c}
                    trigger={
                      <Button variant="ghost" size="icon" aria-label={`Editar la cuenta de ${c.banco}`}>
                        <Pencil />
                      </Button>
                    }
                    onGuardado={recargar}
                  />
                  <AlertDialog>
                    <AlertDialogTrigger asChild>
                      <Button variant="ghost" size="icon" disabled={ocupada === c.id} aria-label={`Borrar la cuenta de ${c.banco}`} className="text-muted-foreground hover:text-destructive">
                        {ocupada === c.id ? <Loader2 className="animate-spin" /> : <Trash2 />}
                      </Button>
                    </AlertDialogTrigger>
                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle>¿Borrar la cuenta de {c.banco}?</AlertDialogTitle>
                        <AlertDialogDescription>Victoria dejará de ofrecerla. Si solo quieres pausarla, apágala con el interruptor.</AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel>Cancelar</AlertDialogCancel>
                        <AlertDialogAction onClick={() => void borrar(c)}>Sí, borrar</AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                </div>
              </li>
            ))}
          </ul>
        </SectionCard>
      )}
    </>
  );
}
