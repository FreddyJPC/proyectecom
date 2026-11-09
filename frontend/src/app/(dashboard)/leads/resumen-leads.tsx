"use client";

import { Flame, Snowflake, Sun, Target, Wallet, type LucideIcon } from "lucide-react";

import { InfoButton } from "@/components/app/info-button";
import { SectionCard } from "@/components/app/section-card";
import { StatCard, type Tono } from "@/components/app/stat-card";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatMoney } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { ResumenLeads, Temperatura } from "@/types/leads";

const TONOS: Record<Tono, string> = {
  primary: "bg-accent text-accent-foreground",
  success: "bg-status-success-soft text-status-success-ink",
  warning: "bg-status-warning-soft text-status-warning-ink",
  danger: "bg-status-danger-soft text-status-danger-ink",
  info: "bg-status-info-soft text-status-info-ink",
  neutral: "bg-status-neutral-soft text-status-neutral-ink",
};

type Pieza = { temperatura: Temperatura; label: string; icon: LucideIcon; tono: Tono; valor: number | undefined };

/** Las cifras de arriba de Leads: cuántos hay en cada temperatura (de AHORA, cada una abre su lista), cuánto dinero está en
 * juego y cómo va el cierre en el periodo elegido. Las tres temperaturas comparten una tarjeta: así ocupan poco en el móvil
 * y la lista queda a la vista. */
export function ResumenLeadsCards({
  resumen,
  cargando,
  onElegir,
}: {
  resumen: ResumenLeads | null;
  cargando: boolean;
  /** Se llama con la temperatura elegida para filtrar la lista. */
  onElegir: (temperatura: Temperatura) => void;
}) {
  const cerrados = resumen ? resumen.ganados + resumen.perdidos : 0;
  const piezas: Pieza[] = [
    { temperatura: "caliente", label: "Calientes", icon: Flame, tono: "warning", valor: resumen?.calientes },
    { temperatura: "tibio", label: "Tibios", icon: Sun, tono: "info", valor: resumen?.tibios },
    { temperatura: "frio", label: "Fríos", icon: Snowflake, tono: "neutral", valor: resumen?.frios },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
      <Card className="col-span-2 gap-0 py-0 shadow-card ring-1 ring-border lg:col-span-3">
        <ul className="grid h-full grid-cols-3 divide-x">
          {piezas.map((p) => (
            <li key={p.temperatura}>
              <button
                type="button"
                onClick={() => onElegir(p.temperatura)}
                aria-label={`Ver los leads ${p.label.toLowerCase()}${p.valor !== undefined ? `: ${p.valor}` : ""}`}
                className="flex h-full w-full flex-col items-start gap-2 rounded-xl p-4 text-left outline-none transition-colors hover:bg-accent/30 focus-visible:ring-3 focus-visible:ring-ring/50 sm:p-5"
              >
                <span className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                  <span className={cn("hidden size-7 shrink-0 items-center justify-center rounded-lg sm:flex", TONOS[p.tono])}>
                    <p.icon className="size-4" aria-hidden />
                  </span>
                  {p.label}
                </span>
                {cargando ? <Skeleton className="h-8 w-12" /> : <span className="tabular text-2xl font-semibold tracking-tight sm:text-3xl">{p.valor ?? 0}</span>}
              </button>
            </li>
          ))}
        </ul>
      </Card>
      <StatCard label="Valor en juego" value={formatMoney(resumen?.valorEnJuego)} icon={Wallet} cargando={cargando} hint="Leads abiertos" />
      <StatCard
        label="Tasa de cierre"
        value={resumen?.tasaDeCierre != null ? `${resumen.tasaDeCierre} %` : "—"}
        icon={Target}
        tono="success"
        cargando={cargando}
        hint={cerrados > 0 ? `${resumen?.ganados} ganados · ${resumen?.perdidos} perdidos` : "Sin leads cerrados aún"}
      />
    </div>
  );
}

/** Por qué se pierden los leads del periodo: para saber qué arreglar (precio, seguimiento, cobertura…). */
export function MotivosDePerdida({ motivos }: { motivos: ResumenLeads["motivosDePerdida"] }) {
  if (motivos.length === 0) return null;
  const mayor = Math.max(...motivos.map((m) => m.leads));
  return (
    <SectionCard
      titulo="Por qué se pierden"
      descripcion="Leads perdidos en el periodo, por motivo."
      info={
        <InfoButton titulo="Por qué se pierden los leads">
          <p>
            Cada lead perdido guarda su <strong>motivo</strong>: lo anota Victoria al conversar, lo pone el sistema cuando el cliente deja de responder, o lo eliges tú al marcarlo.
          </p>
          <p>Sirve para saber qué arreglar: si domina «El precio», revisa tus precios; si domina «No respondió», mejora el seguimiento.</p>
        </InfoButton>
      }
    >
      <ul className="space-y-3 px-4 py-4 sm:px-5">
        {motivos.map((m) => (
          <li key={m.motivo} className="space-y-1.5">
            <div className="flex items-baseline justify-between gap-3 text-sm">
              <span>{m.etiqueta}</span>
              <span className="tabular font-medium">{m.leads}</span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-muted" aria-hidden>
              <div className="h-full rounded-full bg-status-danger" style={{ width: `${Math.max(4, Math.round((m.leads / mayor) * 100))}%` }} />
            </div>
          </li>
        ))}
      </ul>
    </SectionCard>
  );
}
