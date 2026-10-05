"use client";

import {
  AlertTriangle,
  Banknote,
  CheckCircle2,
  CircleDollarSign,
  Package,
  PackageCheck,
  Truck,
  Wallet,
} from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { apiFetch, ApiError } from "@/lib/api";
import type { MetricasGenerales } from "@/types/metricas";

import { MetricCard } from "./metric-card";

export default function MetricasPage() {
  const [datos, setDatos] = useState<MetricasGenerales | null>(null);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    let cancelado = false;
    apiFetch<MetricasGenerales>("/metricas/generales")
      .then((data) => {
        if (!cancelado) setDatos(data);
      })
      .catch((err: unknown) => {
        if (cancelado) return;
        toast.error(err instanceof ApiError ? err.message : "No se pudo cargar las métricas.");
      })
      .finally(() => {
        if (!cancelado) setCargando(false);
      });
    return () => {
      cancelado = true;
    };
  }, []);

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h2 className="text-lg font-semibold">Métricas</h2>
        <p className="text-sm text-muted-foreground">Agregados operativos del negocio en Rocketfy.</p>
      </div>

      <Alert>
        <Wallet />
        <AlertTitle>Esto no es tu saldo de billetera</AlertTitle>
        <AlertDescription>
          {cargando
            ? "Cargando aviso…"
            : (datos?.avisoImportante ??
              "El detalle de liquidaciones y el saldo disponible para retiro no los expone Rocketfy todavía — revísalos en su propio panel.")}
        </AlertDescription>
      </Alert>

      <div>
        <h3 className="mb-2 text-sm font-medium text-muted-foreground">Hoy</h3>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {cargando ? (
            <>
              <Skeleton className="h-24" />
              <Skeleton className="h-24" />
              <Skeleton className="h-24" />
              <Skeleton className="h-24" />
            </>
          ) : (
            <>
              <MetricCard icon={Package} label="Pedidos hoy" value={datos?.pedidosHoy ?? null} />
              <MetricCard icon={PackageCheck} label="Confirmados hoy" value={datos?.confirmadosHoy ?? null} />
              <MetricCard
                icon={CircleDollarSign}
                label="Monto total de pedidos hoy"
                value={datos?.montoTotalPedidosHoy ?? null}
                money
              />
              <MetricCard icon={Banknote} label="Ingreso hoy" value={datos?.ingresoHoy ?? null} money />
            </>
          )}
        </div>
      </div>

      <div>
        <h3 className="mb-2 text-sm font-medium text-muted-foreground">General</h3>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {cargando ? (
            <>
              <Skeleton className="h-24" />
              <Skeleton className="h-24" />
              <Skeleton className="h-24" />
              <Skeleton className="h-24" />
            </>
          ) : (
            <>
              <MetricCard icon={CheckCircle2} label="Ingreso confirmado" value={datos?.ingresoConfirmado ?? null} money />
              <MetricCard icon={Wallet} label="Ingreso total" value={datos?.ingresoTotal ?? null} money />
              <MetricCard icon={Truck} label="Ingreso en tránsito" value={datos?.ingresoEnTransito ?? null} money />
              <MetricCard
                icon={AlertTriangle}
                label="Ingreso retenido por novedad"
                value={datos?.ingresoRetenidoPorNovedad ?? null}
                money
              />
            </>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {cargando ? (
          <Skeleton className="h-24" />
        ) : (
          <MetricCard
            icon={Truck}
            label="Costo de productos en tránsito"
            value={datos?.costoProductosEnTransito ?? null}
            money
          />
        )}
      </div>
    </div>
  );
}
