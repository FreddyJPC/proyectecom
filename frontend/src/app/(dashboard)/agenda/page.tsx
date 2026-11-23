"use client";

import { CalendarCheck, CalendarClock, CalendarDays, CalendarX2, Plus } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { EmptyState } from "@/components/app/empty-state";
import { FilterChips, type Chip } from "@/components/app/filter-chips";
import { InfoButton } from "@/components/app/info-button";
import { ListSkeleton } from "@/components/app/list-skeleton";
import { PageHeader } from "@/components/app/page-header";
import { StatCard } from "@/components/app/stat-card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { diaEcuador, hoyEcuador, sumarDias, tituloDia } from "@/lib/inmuebles";
import type { InmuebleResumen, ResumenVisitas, Visita } from "@/types/inmueble";

import { NuevaVisitaDialog } from "./nueva-visita-dialog";
import { TarjetaVisita } from "./tarjeta-visita";

const VISTAS: Chip[] = [
  { value: "por_confirmar", label: "Por confirmar" },
  { value: "proximas", label: "Próximas" },
  { value: "pasadas", label: "Pasadas" },
  { value: "canceladas", label: "Canceladas" },
  { value: "todas", label: "Todas" },
];

function consultaDe(vista: string, inmueble: string): string {
  const q = new URLSearchParams();
  const hoy = hoyEcuador();
  if (vista === "por_confirmar") q.set("estado", "solicitada");
  if (vista === "proximas") {
    q.set("estado", "confirmada");
    q.set("desde", hoy);
  }
  if (vista === "pasadas") {
    q.set("estado", "confirmada,realizada,no_asistio");
    q.set("desde", sumarDias(hoy, -90));
    q.set("hasta", sumarDias(hoy, -1));
  }
  if (vista === "canceladas") q.set("estado", "cancelada");
  if (inmueble !== "todas") q.set("inmuebleId", inmueble);
  return `/visitas?${q.toString()}`;
}

/** Agrupa por día de Ecuador; las que aún no tienen fecha (por confirmar) van primero. En «Pasadas», lo más reciente arriba. */
function porDia(visitas: Visita[], vista: string): { clave: string; titulo: string; visitas: Visita[] }[] {
  const grupos = new Map<string, Visita[]>();
  for (const v of visitas) {
    const clave = v.fechaHora ? diaEcuador(v.fechaHora) : "sin_fecha";
    grupos.set(clave, [...(grupos.get(clave) ?? []), v]);
  }
  const claves = [...grupos.keys()].sort((a, b) => (a === "sin_fecha" ? -1 : b === "sin_fecha" ? 1 : a.localeCompare(b)));
  if (vista === "pasadas") claves.reverse();
  return claves.map((clave) => ({
    clave,
    titulo: clave === "sin_fecha" ? "Esperando que confirmes día y hora" : tituloDia(clave),
    visitas: grupos.get(clave)!,
  }));
}

export default function AgendaPage() {
  return (
    // useSearchParams() exige un límite <Suspense> (si no, `next build` falla).
    <Suspense fallback={<Skeleton className="h-96 w-full" />}>
      <Agenda />
    </Suspense>
  );
}

function Agenda() {
  const router = useRouter();
  const params = useSearchParams();
  const [vista, setVista] = useState(params.get("vista") ?? "por_confirmar");
  const inmueble = params.get("inmueble") ?? "todas";
  const visitas = useApi<Visita[]>(consultaDe(vista, inmueble));
  const resumen = useApi<ResumenVisitas>("/visitas/resumen");
  const inmuebles = useApi<InmuebleResumen[]>("/inmuebles");

  function recargar() {
    visitas.recargar();
    resumen.recargar();
  }

  function elegirInmueble(valor: string) {
    const q = new URLSearchParams(params.toString());
    if (valor === "todas") q.delete("inmueble");
    else q.set("inmueble", valor);
    router.replace(`/agenda${q.toString() ? `?${q.toString()}` : ""}`);
  }

  const grupos = porDia(visitas.data ?? [], vista);

  return (
    <>
      <PageHeader
        title="Agenda de visitas"
        description="Quién quiere ver cada propiedad y cuándo."
        actions={
          <NuevaVisitaDialog inmuebles={inmuebles.data ?? []} inmuebleInicial={inmueble !== "todas" ? Number(inmueble) : undefined} onCreada={recargar}>
            <Button>
              <Plus /> Nueva visita
            </Button>
          </NuevaVisitaDialog>
        }
        info={
          <InfoButton titulo="Cómo funciona la agenda">
            <p>
              Cuando un interesado quiere visitar una propiedad, el asistente anota el día y la hora que <strong>prefiere</strong> y te
              avisa por Telegram. Él nunca confirma: lo haces tú aquí.
            </p>
            <ol>
              <li><strong>Por confirmar:</strong> coordina con quien enseña la propiedad y toca «Confirmar» con el día y la hora.</li>
              <li><strong>Avisar al cliente:</strong> le manda el mensaje de confirmación por WhatsApp (puedes ajustarlo antes de enviar).</li>
              <li>Después de la visita, márcala como realizada o «no asistió».</li>
            </ol>
            <p>
              WhatsApp solo deja escribirle al cliente dentro de las 24 horas desde su último mensaje: si pasó más tiempo, llámalo. Las
              horas se muestran siempre en hora de Ecuador. Si alguien llama por teléfono, agrega la visita con «Nueva visita».
            </p>
          </InfoButton>
        }
      />

      <div className="flex flex-col gap-5 pb-28 md:pb-6">
        <div className="grid gap-3 sm:grid-cols-3">
          <StatCard label="Por confirmar" value={resumen.data?.porConfirmar ?? "—"} icon={CalendarClock} tono="warning" cargando={resumen.cargando} />
          <StatCard label="Hoy" value={resumen.data?.hoy ?? "—"} icon={CalendarCheck} tono="success" cargando={resumen.cargando} />
          <StatCard label="Próximas" value={resumen.data?.proximas ?? "—"} icon={CalendarDays} tono="info" cargando={resumen.cargando} />
        </div>

        <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <FilterChips chips={VISTAS} value={vista} onChange={setVista} label="Qué visitas ver" />
          <div className="grid gap-1.5 md:w-64">
            <Label htmlFor="filtro-inmueble">Propiedad</Label>
            <Select value={inmueble} onValueChange={elegirInmueble}>
              <SelectTrigger id="filtro-inmueble" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="todas">Todas las propiedades</SelectItem>
                {(inmuebles.data ?? []).map((i) => (
                  <SelectItem key={i.id} value={String(i.id)}>
                    {i.titulo}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {visitas.cargando && !visitas.data ? (
          <ListSkeleton />
        ) : visitas.error ? (
          <EmptyState
            icon={CalendarX2}
            tone="danger"
            title="No se pudo cargar la agenda"
            description={visitas.error}
            action={
              <Button variant="outline" onClick={visitas.recargar}>
                Reintentar
              </Button>
            }
          />
        ) : grupos.length === 0 ? (
          <EmptyState
            icon={CalendarDays}
            title={vista === "por_confirmar" ? "No hay visitas por confirmar" : "No hay visitas aquí"}
            description="Los pedidos de visita que tome el asistente aparecerán aquí."
            action={
              <Button variant="outline" asChild>
                <Link href="/inmuebles">Ver propiedades</Link>
              </Button>
            }
          />
        ) : (
          <div className="flex flex-col gap-5">
            {grupos.map((g) => (
              <section key={g.clave} aria-labelledby={`dia-${g.clave}`} className="space-y-2">
                <h2 id={`dia-${g.clave}`} className="text-sm font-semibold first-letter:uppercase">
                  {g.titulo}
                </h2>
                <ul className="grid gap-3 lg:grid-cols-2">
                  {g.visitas.map((v) => (
                    <li key={v.id}>
                      <TarjetaVisita visita={v} onCambio={recargar} />
                    </li>
                  ))}
                </ul>
              </section>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
