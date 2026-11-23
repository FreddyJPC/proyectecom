"use client";

import { BedDouble, Building2, CalendarClock, MapPin, Plus } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { EmptyState } from "@/components/app/empty-state";
import { FilterChips, type Chip } from "@/components/app/filter-chips";
import { InfoButton } from "@/components/app/info-button";
import { ListSkeleton } from "@/components/app/list-skeleton";
import { PageHeader } from "@/components/app/page-header";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { useApi } from "@/hooks/use-api";
import { estadoInmuebleInfo } from "@/lib/estados";
import { formatMoney } from "@/lib/format";
import { NOMBRE_TIPO_INMUEBLE, type InmuebleResumen } from "@/types/inmueble";

import { NumerosWhatsapp } from "./numeros-whatsapp";

const FILTROS: Chip[] = [
  { value: "todas", label: "Todas" },
  { value: "activo", label: "Publicadas" },
  { value: "borrador", label: "Borradores" },
  { value: "pausado", label: "Pausadas" },
  { value: "vendido", label: "Vendidas" },
];

/** «Propiedades»: el portafolio de inmuebles que atiende el asistente de propiedades (aparte de Victoria). */
export default function InmueblesPage() {
  const [filtro, setFiltro] = useState("todas");
  const lista = useApi<InmuebleResumen[]>("/inmuebles");
  const visibles = (lista.data ?? []).filter((i) => filtro === "todas" || i.estado === filtro);

  return (
    <>
      <PageHeader
        title="Propiedades"
        description="Las casas, terrenos y locales que atiende el asistente de inmuebles."
        actions={
          <Button asChild>
            <Link href="/inmuebles/nueva">
              <Plus /> Nueva propiedad
            </Link>
          </Button>
        }
        info={
          <InfoButton titulo="Para qué sirve">
            <p>
              Cada propiedad tiene su ficha: lo que el <strong>asistente de inmuebles</strong> puede responder (medidas, habitaciones,
              ubicación, precio si quieres decirlo, horarios de visita), sus fotos y videos, y los anuncios de Meta que hablan de ella.
            </p>
            <ul>
              <li>El asistente no es Victoria: informa, manda la ubicación y las fotos y anota los pedidos de visita. No vende ni negocia.</li>
              <li>Atiende a quien llega por un anuncio vinculado a una propiedad, o a quien escribe a un número de WhatsApp asignado a inmuebles.</li>
              <li>Solo las propiedades <strong>publicadas</strong> se ofrecen; una vendida se informa como vendida.</li>
              <li>Los pedidos de visita llegan a la <Link href="/agenda">Agenda de visitas</Link>, donde los confirmas tú.</li>
            </ul>
          </InfoButton>
        }
      />

      <div className="flex flex-col gap-5 pb-28 md:pb-6">
        <FilterChips chips={FILTROS} value={filtro} onChange={setFiltro} label="Filtrar propiedades" />

        {lista.cargando && !lista.data ? (
          <ListSkeleton />
        ) : lista.error ? (
          <EmptyState
            icon={Building2}
            tone="danger"
            title="No se pudieron cargar las propiedades"
            description={lista.error}
            action={
              <Button variant="outline" onClick={lista.recargar}>
                Reintentar
              </Button>
            }
          />
        ) : visibles.length === 0 ? (
          <EmptyState
            icon={Building2}
            title={filtro === "todas" ? "Todavía no hay propiedades" : "No hay propiedades aquí"}
            description="Crea la ficha de una propiedad para que el asistente pueda atender sus anuncios."
            action={
              filtro === "todas" ? (
                <Button asChild>
                  <Link href="/inmuebles/nueva">
                    <Plus /> Nueva propiedad
                  </Link>
                </Button>
              ) : undefined
            }
          />
        ) : (
          <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {visibles.map((i) => (
              <li key={i.id}>
                <TarjetaInmueble inmueble={i} />
              </li>
            ))}
          </ul>
        )}

        <NumerosWhatsapp />
      </div>
    </>
  );
}

function TarjetaInmueble({ inmueble }: { inmueble: InmuebleResumen }) {
  const lugar = [inmueble.sector, inmueble.ciudad].filter(Boolean).join(", ");
  return (
    <Link
      href={`/inmuebles/${inmueble.id}`}
      className="flex h-full flex-col overflow-hidden rounded-xl bg-card shadow-card ring-1 ring-border transition-colors outline-none hover:ring-primary/40 focus-visible:ring-3 focus-visible:ring-ring/50"
    >
      <div className="relative aspect-[16/9] overflow-hidden bg-muted">
        {inmueble.portadaUrl && !/\.(mp4|3gp)$/i.test(inmueble.portadaPath ?? "") ? (
          // eslint-disable-next-line @next/next/no-img-element -- la foto viene del bucket público de Supabase
          <img src={inmueble.portadaUrl} alt="" loading="lazy" className="absolute inset-0 size-full object-cover" />
        ) : (
          <div className="flex size-full items-center justify-center text-muted-foreground">
            <Building2 className="size-8" aria-hidden />
          </div>
        )}
        <span className="absolute top-2 left-2">
          <StatusBadge {...estadoInmuebleInfo(inmueble.estado)} />
        </span>
      </div>
      <div className="flex flex-1 flex-col gap-1.5 p-4">
        <p className="text-xs text-muted-foreground">
          {NOMBRE_TIPO_INMUEBLE[inmueble.tipo]} en {inmueble.operacion} · {inmueble.codigo}
        </p>
        <h2 className="font-medium leading-snug">{inmueble.titulo}</h2>
        {lugar && (
          <p className="flex items-center gap-1 text-sm text-muted-foreground">
            <MapPin className="size-3.5 shrink-0" aria-hidden /> {lugar}
          </p>
        )}
        <div className="mt-auto flex flex-wrap items-center gap-x-3 gap-y-1 pt-2 text-sm">
          {inmueble.precio && <span className="tabular font-medium">{formatMoney(inmueble.precio)}</span>}
          {inmueble.habitaciones != null && (
            <span className="flex items-center gap-1 text-muted-foreground">
              <BedDouble className="size-3.5" aria-hidden /> {inmueble.habitaciones} hab.
            </span>
          )}
          {inmueble.visitasPorConfirmar > 0 && (
            <span className="flex items-center gap-1 rounded-full bg-status-warning-soft px-2 py-0.5 text-xs font-medium text-status-warning-ink">
              <CalendarClock className="size-3.5" aria-hidden /> {inmueble.visitasPorConfirmar} por confirmar
            </span>
          )}
        </div>
      </div>
    </Link>
  );
}
