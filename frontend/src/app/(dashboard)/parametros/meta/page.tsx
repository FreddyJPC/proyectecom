"use client";

import { ArrowLeft, Database, KeyRound, Loader2, Megaphone, MessageCircle, Plug, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { EmptyState } from "@/components/app/empty-state";
import { InfoButton } from "@/components/app/info-button";
import { ListSkeleton } from "@/components/app/list-skeleton";
import { PageHeader } from "@/components/app/page-header";
import { SectionCard } from "@/components/app/section-card";
import { CuentaPublicitariaCard } from "./cuenta-publicitaria";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { useApi } from "@/hooks/use-api";
import { apiFetch, ApiError } from "@/lib/api";
import type { StatusVariant } from "@/lib/estados";
import { formatFechaHora, formatMoney } from "@/lib/format";
import type { EstadoEventoMeta, EstadoMeta } from "@/types/meta";

const ESTADO_EVENTO: Record<EstadoEventoMeta, { label: string; variant: StatusVariant }> = {
  pendiente: { label: "Por enviar", variant: "warning" },
  enviando: { label: "Enviando", variant: "info" },
  enviado: { label: "Enviado", variant: "success" },
  fallido: { label: "Falló", variant: "danger" },
  dudoso: { label: "Dudoso", variant: "warning" },
  descartado: { label: "No aplica", variant: "neutral" },
};

function FilaEstado({ icono: Icono, titulo, detalle, badge }: { icono: typeof Database; titulo: string; detalle: string; badge: React.ReactNode }) {
  return (
    <li className="flex flex-wrap items-center gap-3 px-4 py-4 sm:px-5">
      <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-status-neutral-soft text-status-neutral-ink">
        <Icono className="size-[1.1rem]" aria-hidden />
      </span>
      <div className="min-w-0 flex-1 space-y-0.5">
        <p className="text-sm font-semibold">{titulo}</p>
        <p className="break-words text-sm text-muted-foreground">{detalle}</p>
      </div>
      {badge}
    </li>
  );
}

export default function ConexionMetaPage() {
  const { data, error, cargando, recargar } = useApi<EstadoMeta>("/meta/estado");
  const [preparando, setPreparando] = useState(false);

  async function preparar() {
    setPreparando(true);
    try {
      const r = await apiFetch<{ datasetId: string }>("/meta/preparar", { method: "POST" });
      toast.success(`Meta preparado. Dataset ${r.datasetId}.`);
      recargar();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo preparar Meta.");
    } finally {
      setPreparando(false);
    }
  }

  const faltaBase = data ? !data.tokenConfigurado || !data.cuentaWhatsappConfigurada : false;
  const conProblema = data ? data.eventos.fallido + data.eventos.dudoso : 0;

  return (
    <>
      <Button asChild variant="ghost" size="sm" className="-ml-2 w-fit text-muted-foreground">
        <Link href="/parametros">
          <ArrowLeft /> Parámetros
        </Link>
      </Button>

      <PageHeader
        title="Conexión con Meta"
        description="Que Meta sepa qué anuncios terminan en una venta."
        info={
          <InfoButton titulo="Para qué sirve esta conexión">
            <p>
              Cuando alguien toca un anuncio y luego compra, el sistema puede avisarle a Meta que <strong>ese anuncio produjo una venta</strong>. Con el tiempo, Meta
              aprende qué anuncios traen compradores y no solo conversaciones.
            </p>
            <h3>Qué hace «Preparar Meta»</h3>
            <p>
              Le pide a Meta el <strong>dataset</strong> de tu cuenta de WhatsApp: el buzón donde se reciben las ventas. Usa el token que está guardado en el servidor, así
              que nadie tiene que verlo ni copiarlo. Es seguro repetirlo: si el dataset ya existe, Meta devuelve el mismo.
            </p>
            <h3>Qué se envía y cuándo</h3>
            <ul>
              <li>Solo el valor de la venta, la moneda, la hora y el código del clic del anuncio. Ningún dato del cliente.</li>
              <li>Solo ventas de anuncios ya confirmadas, y con una espera antes de avisar por si se cancelan (Meta no deja borrar un aviso).</li>
              <li>Las ventas de clics sin código del anuncio (por ejemplo, del Estado de WhatsApp) no se pueden avisar y quedan como «No aplica».</li>
            </ul>
            <p>
              El interruptor para empezar a avisar está en <strong>Parámetros → Avisar a Meta de las ventas</strong> y viene apagado.
            </p>
          </InfoButton>
        }
        actions={
          <Button onClick={() => void preparar()} disabled={preparando || cargando || faltaBase}>
            {preparando ? <Loader2 className="animate-spin" /> : <Plug />} Preparar Meta
          </Button>
        }
      />

      {error && !data ? (
        <div role="alert" className="flex flex-wrap items-center gap-3 rounded-xl border border-status-danger/30 bg-status-danger-soft p-4 text-status-danger-ink">
          <TriangleAlert className="size-5 shrink-0" aria-hidden />
          <p className="flex-1 text-sm">No se pudo cargar el estado. {error}</p>
          <Button variant="outline" size="sm" onClick={recargar} className="bg-card text-foreground">
            Reintentar
          </Button>
        </div>
      ) : cargando || !data ? (
        <SectionCard titulo="Estado" descripcion="Un momento…">
          <ListSkeleton filas={4} />
        </SectionCard>
      ) : (
        <>
          {faltaBase && (
            <div role="alert" className="flex items-start gap-3 rounded-xl border border-status-warning/30 bg-status-warning-soft p-4 text-status-warning-ink">
              <TriangleAlert className="mt-0.5 size-5 shrink-0" aria-hidden />
              <p className="text-sm">
                Falta configurar en el servidor: {[!data.tokenConfigurado && "META_CAPI_TOKEN", !data.cuentaWhatsappConfigurada && "WHATSAPP_WABA_ID"].filter(Boolean).join(", ")}.
              </p>
            </div>
          )}

          <SectionCard titulo="Estado" descripcion={data.listo ? "Todo listo para avisar ventas a Meta." : "Faltan pasos para poder avisar ventas."}>
            <ul className="divide-y">
              <FilaEstado
                icono={KeyRound}
                titulo="Token de Meta en el servidor"
                detalle="Nunca se muestra."
                badge={<StatusBadge label={data.tokenConfigurado ? "Configurado" : "Falta"} variant={data.tokenConfigurado ? "success" : "danger"} />}
              />
              <FilaEstado
                icono={MessageCircle}
                titulo="Cuenta de WhatsApp"
                detalle="WhatsApp Business de AzoShop."
                badge={<StatusBadge label={data.cuentaWhatsappConfigurada ? "Configurada" : "Falta"} variant={data.cuentaWhatsappConfigurada ? "success" : "danger"} />}
              />
              <FilaEstado
                icono={Database}
                titulo="Dataset de Meta"
                detalle={data.datasetId ? `Número ${data.datasetId}` : "Aún sin preparar."}
                badge={<StatusBadge label={data.datasetId ? "Preparado" : "Sin preparar"} variant={data.datasetId ? "success" : "warning"} />}
              />
              <FilaEstado
                icono={Megaphone}
                titulo="Avisar las ventas a Meta"
                detalle="Se enciende en Parámetros."
                badge={<StatusBadge label={data.avisosActivos ? "Encendido" : "Apagado"} variant={data.avisosActivos ? "success" : "neutral"} />}
              />
            </ul>
          </SectionCard>

          <CuentaPublicitariaCard />

          <SectionCard
            titulo="Ventas avisadas"
            descripcion={
              conProblema > 0
                ? `${conProblema} con problema: revísalas abajo.`
                : `${data.eventos.enviado} enviadas · ${data.eventos.pendiente} por enviar · ${data.eventos.descartado} no aplican.`
            }
          >
            {data.ultimosEventos.length === 0 ? (
              <EmptyState icon={Megaphone} title="Aún no se ha avisado ninguna venta" description="Aparecerán aquí cuando el aviso esté encendido y haya ventas de anuncios confirmadas." />
            ) : (
              <ul className="divide-y">
                {data.ultimosEventos.map((e) => {
                  const estado = ESTADO_EVENTO[e.estado];
                  return (
                    <li key={e.id} className="flex flex-wrap items-center gap-3 px-4 py-4 sm:px-5">
                      <div className="min-w-0 flex-1 space-y-0.5">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="text-sm font-semibold">Venta #{e.ventaId}</p>
                          <StatusBadge label={estado.label} variant={estado.variant} />
                        </div>
                        <p className="tabular text-sm text-muted-foreground">
                          {formatMoney(e.valor)} · {formatFechaHora(e.enviadoEn ?? e.creadoEn)}
                        </p>
                        {e.motivo && <p className="break-words text-sm text-muted-foreground">{e.motivo}</p>}
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </SectionCard>
        </>
      )}
    </>
  );
}
