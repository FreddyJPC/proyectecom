"use client";

import {
  AlertTriangle,
  BellRing,
  CheckCircle2,
  CloudOff,
  CreditCard,
  Inbox,
  MessageCircle,
  Package,
  PackageOpen,
  Plus,
  Truck,
  Wallet,
} from "lucide-react";
import Link from "next/link";

import { AvatarInitials } from "@/components/app/avatar-initials";
import { EmptyState } from "@/components/app/empty-state";
import { PageHeader } from "@/components/app/page-header";
import { SectionCard } from "@/components/app/section-card";
import { StatCard } from "@/components/app/stat-card";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { estadoConversacionInfo, estadoLocalInfo, rocketfyStatusInfo, tipoAlertaStockInfo } from "@/lib/estados";
import { formatFecha, formatMoney, formatPhone, tiempoRelativo } from "@/lib/format";
import type { ConversacionesListado } from "@/types/conversacion";
import type { AlertaStock, EventoWebhook, Paginado } from "@/types/incidencia";
import type { MetricasGenerales } from "@/types/metricas";
import type { PedidosListado } from "@/types/pedido";

function saludo(): string {
  const h = new Date().getHours();
  if (h < 12) return "Buenos días";
  if (h < 19) return "Buenas tardes";
  return "Buenas noches";
}

function fechaLarga(): string {
  const f = new Intl.DateTimeFormat("es-EC", { weekday: "long", day: "numeric", month: "long" }).format(new Date());
  return f.charAt(0).toUpperCase() + f.slice(1);
}

function FilasCargando({ n = 4 }: { n?: number }) {
  return (
    <div className="divide-y" aria-busy="true">
      {Array.from({ length: n }).map((_, i) => (
        <div key={i} className="flex items-center gap-3 px-4 py-3.5 sm:px-5">
          <Skeleton className="size-10 shrink-0 rounded-full" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-4 w-1/2" />
            <Skeleton className="h-3 w-2/3" />
          </div>
        </div>
      ))}
    </div>
  );
}

function SeccionError({ onReintentar }: { onReintentar: () => void }) {
  return (
    <EmptyState
      icon={CloudOff}
      tone="danger"
      title="No se pudo cargar"
      description="Revisa tu conexión e inténtalo de nuevo."
      className="py-10"
      action={
        <Button variant="outline" size="sm" onClick={onReintentar}>
          Reintentar
        </Button>
      }
    />
  );
}

export default function Home() {
  const metricas = useApi<MetricasGenerales>("/metricas/generales");
  const escaladas = useApi<ConversacionesListado>("/conversaciones?estado=escalada&pageSize=4");
  const pagos = useApi<ConversacionesListado>("/conversaciones?estado=esperando_pago&pageSize=1");
  const pedidos = useApi<PedidosListado>("/pedidos?pageSize=5");
  const alertas = useApi<Paginado<AlertaStock>>("/incidencias/stock?pageSize=4");
  const novedades = useApi<Paginado<EventoWebhook>>("/incidencias/eventos?pageSize=4");

  const totales = escaladas.data?.totalesPorFiltroRapido;
  const m = metricas.data;

  return (
    <>
      <PageHeader
        title={
          <>
            <span suppressHydrationWarning>{saludo()}</span> 👋
          </>
        }
        description={<span suppressHydrationWarning>{fechaLarga()} · Esto es lo que pasa hoy en tu negocio.</span>}
        actions={
          <Button asChild>
            <Link href="/pedidos/nuevo">
              <Plus /> Nuevo pedido
            </Link>
          </Button>
        }
      />

      {/* Lo que necesita acción humana va primero: es lo único urgente. */}
      {totales && totales.escaladasSinRevisar > 0 && (
        <Link
          href="/conversaciones"
          className="group flex items-center gap-3 rounded-xl border border-status-danger/30 bg-status-danger-soft p-4 text-status-danger-ink outline-none transition-colors hover:border-status-danger/50 focus-visible:ring-3 focus-visible:ring-ring/50"
        >
          <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-status-danger text-status-danger-foreground">
            <BellRing className="size-5" aria-hidden />
          </span>
          <div className="min-w-0 flex-1">
            <p className="font-semibold">
              {totales.escaladasSinRevisar === 1
                ? "1 cliente espera tu respuesta"
                : `${totales.escaladasSinRevisar} clientes esperan tu respuesta`}
            </p>
            <p className="text-sm opacity-80">Victoria pasó estas conversaciones a una persona.</p>
          </div>
          <span className="hidden text-sm font-medium group-hover:underline sm:inline">Atender ahora</span>
        </Link>
      )}

      <section aria-label="Cifras de hoy" className="grid grid-cols-2 gap-3 lg:grid-cols-4 lg:gap-4">
        <StatCard
          label="Pedidos hoy"
          value={m?.pedidosHoy ?? "—"}
          hint={m ? `${formatMoney(m.montoTotalPedidosHoy)} en total` : undefined}
          icon={Package}
          tono="primary"
          href="/pedidos"
          cargando={metricas.cargando && !m}
        />
        <StatCard
          label="Confirmados hoy"
          value={m?.confirmadosHoy ?? "—"}
          hint="Ya enviados a Rocketfy"
          icon={CheckCircle2}
          tono="success"
          href="/pedidos?estado=confirmado"
          cargando={metricas.cargando && !m}
        />
        <StatCard
          label="Ingreso de hoy"
          value={formatMoney(m?.ingresoHoy)}
          hint="Cobros entregados hoy"
          icon={Wallet}
          tono="info"
          href="/metricas"
          cargando={metricas.cargando && !m}
        />
        <StatCard
          label="En tránsito"
          value={formatMoney(m?.ingresoEnTransito)}
          hint="Por cobrar al entregar"
          icon={Truck}
          tono="warning"
          href="/metricas"
          cargando={metricas.cargando && !m}
        />
      </section>
      {metricas.error && !m && (
        <p role="alert" className="-mt-2 text-sm text-status-danger-ink">
          No se pudieron cargar las cifras. {metricas.error}
        </p>
      )}

      <div className="grid gap-5 lg:grid-cols-2">
        <SectionCard
          titulo="Conversaciones que necesitan atención"
          descripcion={totales ? `${totales.escaladas} escaladas · ${pagos.data?.totalesPorFiltroRapido.esperandoPago ?? 0} esperando pago` : undefined}
          enlace={{ href: "/conversaciones" }}
        >
          {escaladas.cargando && !escaladas.data ? (
            <FilasCargando />
          ) : escaladas.error && !escaladas.data ? (
            <SeccionError onReintentar={escaladas.recargar} />
          ) : escaladas.data && escaladas.data.items.length === 0 ? (
            <EmptyState
              icon={Inbox}
              title="Todo al día"
              description="Ninguna conversación espera a una persona. Victoria está atendiendo."
              className="py-10"
            />
          ) : (
            <ul className="divide-y">
              {escaladas.data?.items.map((c) => {
                const info = estadoConversacionInfo(c.estado);
                return (
                  <li key={c.id}>
                    <Link
                      href={`/conversaciones/${c.id}`}
                      className="flex items-center gap-3 px-4 py-3.5 outline-none transition-colors hover:bg-muted/60 focus-visible:bg-muted sm:px-5"
                    >
                      <AvatarInitials nombre={c.nombreCliente ?? c.telefono} semilla={c.telefono} />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <p className="truncate font-medium">{c.nombreCliente ?? formatPhone(c.telefono)}</p>
                          {c.sinRevisar && <span className="size-2 shrink-0 rounded-full bg-status-danger" aria-label="Sin revisar" />}
                        </div>
                        <p className="truncate text-sm text-muted-foreground">{c.ultimoMensaje?.contenido ?? "Sin mensajes"}</p>
                      </div>
                      <div className="flex shrink-0 flex-col items-end gap-1">
                        <StatusBadge label={info.label} variant={info.variant} />
                        <span className="text-xs text-muted-foreground">{tiempoRelativo(c.actualizadaEn)}</span>
                      </div>
                    </Link>
                  </li>
                );
              })}
            </ul>
          )}
        </SectionCard>

        <SectionCard titulo="Últimos pedidos" enlace={{ href: "/pedidos" }}>
          {pedidos.cargando && !pedidos.data ? (
            <FilasCargando n={5} />
          ) : pedidos.error && !pedidos.data ? (
            <SeccionError onReintentar={pedidos.recargar} />
          ) : pedidos.data && pedidos.data.items.length === 0 ? (
            <EmptyState icon={PackageOpen} title="Aún no hay pedidos" description="Cuando Victoria cierre una venta, aparecerá aquí." className="py-10" />
          ) : (
            <ul className="divide-y">
              {pedidos.data?.items.map((p) => {
                const info = estadoLocalInfo(p.estadoLocal);
                const rocket = rocketfyStatusInfo(p.statusIdRocketfy);
                return (
                  <li key={p.idLocal}>
                    <Link
                      href={`/pedidos/${p.idLocal}`}
                      className="flex items-center gap-3 px-4 py-3.5 outline-none transition-colors hover:bg-muted/60 focus-visible:bg-muted sm:px-5"
                    >
                      <AvatarInitials nombre={p.nombreCliente} />
                      <div className="min-w-0 flex-1">
                        <p className="truncate font-medium">{p.nombreCliente}</p>
                        <p className="truncate text-sm text-muted-foreground">
                          #{p.idLocal} · {p.canton} · {formatFecha(p.creadoEn)}
                        </p>
                      </div>
                      <div className="flex shrink-0 flex-col items-end gap-1">
                        <span className="tabular font-semibold">{formatMoney(p.total)}</span>
                        <StatusBadge label={rocket?.label ?? info.label} variant={rocket?.variant ?? info.variant} />
                      </div>
                    </Link>
                  </li>
                );
              })}
            </ul>
          )}
        </SectionCard>

        <SectionCard titulo="Alertas de stock y precio" enlace={{ href: "/incidencias" }}>
          {alertas.cargando && !alertas.data ? (
            <FilasCargando n={3} />
          ) : alertas.error && !alertas.data ? (
            <SeccionError onReintentar={alertas.recargar} />
          ) : alertas.data && alertas.data.items.length === 0 ? (
            <EmptyState icon={CheckCircle2} title="Sin alertas" description="Tus productos vigilados están en orden." className="py-10" />
          ) : (
            <ul className="divide-y">
              {alertas.data?.items.map((a) => {
                const info = tipoAlertaStockInfo(a.tipo);
                return (
                  <li key={a.id} className="flex items-center gap-3 px-4 py-3.5 sm:px-5">
                    <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-status-warning-soft text-status-warning-ink">
                      {a.tipo === "stock_bajo" ? <AlertTriangle className="size-[1.1rem]" aria-hidden /> : <CreditCard className="size-[1.1rem]" aria-hidden />}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="tabular truncate font-medium">{a.sku}</p>
                      <p className="truncate text-sm text-muted-foreground">
                        {a.tipo === "stock_bajo"
                          ? `Quedan ${a.detalle.stock} (mínimo ${a.detalle.umbral})`
                          : `De ${formatMoney(String(a.detalle.precioAnterior))} a ${formatMoney(String(a.detalle.precioNuevo))}`}
                      </p>
                    </div>
                    <div className="flex shrink-0 flex-col items-end gap-1">
                      <StatusBadge label={info.label} variant={info.variant} />
                      <span className="text-xs text-muted-foreground">{tiempoRelativo(a.creadoEn)}</span>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </SectionCard>

        <SectionCard titulo="Novedades de envío" enlace={{ href: "/incidencias" }}>
          {novedades.cargando && !novedades.data ? (
            <FilasCargando n={3} />
          ) : novedades.error && !novedades.data ? (
            <SeccionError onReintentar={novedades.recargar} />
          ) : novedades.data && novedades.data.items.length === 0 ? (
            <EmptyState icon={MessageCircle} title="Sin novedades" description="Aquí verás los cambios de estado que reporta Rocketfy." className="py-10" />
          ) : (
            <ul className="divide-y">
              {novedades.data?.items.map((e) => {
                const info = rocketfyStatusInfo(e.statusId);
                return (
                  <li key={e.id} className="flex items-start gap-3 px-4 py-3.5 sm:px-5">
                    <span className="mt-0.5 flex size-10 shrink-0 items-center justify-center rounded-full bg-status-info-soft text-status-info-ink">
                      <Truck className="size-[1.1rem]" aria-hidden />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="font-medium">
                        Pedido {e.idLocal ? `#${e.idLocal}` : `Rocketfy ${e.idRocketfy}`}
                      </p>
                      <p className="line-clamp-2 text-sm text-muted-foreground">{e.details ?? e.statusName ?? "Cambio de estado"}</p>
                    </div>
                    <div className="flex shrink-0 flex-col items-end gap-1">
                      {info && <StatusBadge label={info.label} variant={info.variant} />}
                      <span className="text-xs text-muted-foreground">{tiempoRelativo(e.eventDate)}</span>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </SectionCard>
      </div>
    </>
  );
}
