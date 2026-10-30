"use client";

import { Banknote, CheckCircle2, CircleDollarSign, Package, PackageCheck, TriangleAlert, Truck, Wallet } from "lucide-react";

import { PageHeader } from "@/components/app/page-header";
import { StatCard } from "@/components/app/stat-card";
import { Button } from "@/components/ui/button";
import { useApi } from "@/hooks/use-api";
import { formatMoney } from "@/lib/format";
import type { MetricasGenerales } from "@/types/metricas";

function Grupo({ titulo, descripcion, children, columnas = "lg:grid-cols-4" }: { titulo: string; descripcion?: string; children: React.ReactNode; columnas?: string }) {
  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-sm font-semibold">{titulo}</h2>
        {descripcion && <p className="text-xs text-muted-foreground">{descripcion}</p>}
      </div>
      <div className={`grid grid-cols-2 gap-3 lg:gap-4 ${columnas}`}>{children}</div>
    </section>
  );
}

export default function MetricasPage() {
  const { data: m, error, cargando, recargar } = useApi<MetricasGenerales>("/metricas/generales");

  return (
    <>
      <PageHeader title="Métricas" description="Cómo va tu negocio hoy y en total, según los pedidos de Rocketfy." />

      <div className="flex items-start gap-3 rounded-xl border bg-card p-4 shadow-card">
        <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-status-info-soft text-status-info-ink">
          <Wallet className="size-[1.1rem]" aria-hidden />
        </span>
        <div className="space-y-0.5">
          <p className="text-sm font-semibold">Esto no es el saldo de tu billetera</p>
          <p className="text-sm text-muted-foreground">
            {m?.avisoImportante ?? "El detalle de liquidaciones y el saldo disponible para retiro no los expone Rocketfy todavía: revísalos en su propio panel."}
          </p>
        </div>
      </div>

      {error && !m && (
        <div role="alert" className="flex flex-wrap items-center gap-3 rounded-xl border border-status-danger/30 bg-status-danger-soft p-4 text-status-danger-ink">
          <TriangleAlert className="size-5 shrink-0" aria-hidden />
          <p className="flex-1 text-sm">No se pudieron cargar las métricas. {error}</p>
          <Button variant="outline" size="sm" onClick={recargar} className="bg-card text-foreground">
            Reintentar
          </Button>
        </div>
      )}

      <Grupo titulo="Hoy" descripcion="Lo que ha entrado desde las 00:00.">
        <StatCard label="Pedidos" value={m?.pedidosHoy ?? "—"} icon={Package} tono="primary" href="/pedidos" cargando={cargando} />
        <StatCard label="Confirmados" value={m?.confirmadosHoy ?? "—"} icon={PackageCheck} tono="success" hint="Ya enviados a Rocketfy" cargando={cargando} />
        <StatCard label="Monto de pedidos" value={formatMoney(m?.montoTotalPedidosHoy)} icon={CircleDollarSign} tono="info" hint="Suma de lo vendido hoy" cargando={cargando} />
        <StatCard label="Ingreso de hoy" value={formatMoney(m?.ingresoHoy)} icon={Banknote} tono="success" hint="Cobros entregados hoy" cargando={cargando} />
      </Grupo>

      <Grupo titulo="Ingresos" descripcion="Acumulado de todos tus pedidos." columnas="lg:grid-cols-2">
        <StatCard label="Ingreso total" value={formatMoney(m?.ingresoTotal)} icon={Wallet} tono="primary" cargando={cargando} />
        <StatCard label="Ingreso confirmado" value={formatMoney(m?.ingresoConfirmado)} icon={CheckCircle2} tono="success" cargando={cargando} />
      </Grupo>

      <Grupo titulo="En camino" descripcion="Pedidos que ya salieron y todavía no se cobran." columnas="lg:grid-cols-3">
        <StatCard label="Ingreso en tránsito" value={formatMoney(m?.ingresoEnTransito)} icon={Truck} tono="warning" hint="Se cobra al entregar" cargando={cargando} />
        <StatCard label="Costo de productos en tránsito" value={formatMoney(m?.costoProductosEnTransito)} icon={Truck} tono="neutral" hint="Lo que cuestan los productos en camino" cargando={cargando} />
        <StatCard label="Retenido por novedad" value={formatMoney(m?.ingresoRetenidoPorNovedad)} icon={TriangleAlert} tono="danger" hint="Detenido por un problema en la entrega" href="/incidencias" cargando={cargando} />
      </Grupo>
    </>
  );
}
