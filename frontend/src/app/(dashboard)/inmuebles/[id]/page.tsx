"use client";

import { Building2, CalendarDays, ChevronDown, ListChecks, Loader2 } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { EmptyState } from "@/components/app/empty-state";
import { InfoButton } from "@/components/app/info-button";
import { PageHeader } from "@/components/app/page-header";
import { SectionCard } from "@/components/app/section-card";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { apiFetch, ApiError } from "@/lib/api";
import { estadoInmuebleInfo } from "@/lib/estados";
import type { EstadoInmueble, InmuebleDetalle } from "@/types/inmueble";

import { FichaForm } from "../ficha-form";
import { AnunciosInmueble } from "./anuncios-inmueble";
import { GaleriaInmueble } from "./galeria-inmueble";

/** A qué estados se puede pasar desde cada uno (lo que se ofrece en el menú; el backend valida lo mínimo para publicar). */
const ACCIONES: Record<EstadoInmueble, { estado: EstadoInmueble; label: string }[]> = {
  borrador: [{ estado: "activo", label: "Publicar" }, { estado: "archivado", label: "Archivar" }],
  activo: [{ estado: "pausado", label: "Pausar" }, { estado: "vendido", label: "Marcar como vendida" }],
  pausado: [{ estado: "activo", label: "Volver a publicar" }, { estado: "vendido", label: "Marcar como vendida" }, { estado: "archivado", label: "Archivar" }],
  vendido: [{ estado: "activo", label: "Volver a publicar" }, { estado: "archivado", label: "Archivar" }],
  archivado: [{ estado: "borrador", label: "Recuperar como borrador" }],
};

export default function InmueblePage() {
  const { id } = useParams<{ id: string }>();
  const detalle = useApi<InmuebleDetalle>(`/inmuebles/${id}`);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cambiandoEstado, setCambiandoEstado] = useState(false);

  async function guardar(cuerpo: Record<string, unknown>) {
    setGuardando(true);
    setError(null);
    try {
      await apiFetch<InmuebleDetalle>(`/inmuebles/${id}`, { method: "PUT", body: JSON.stringify(cuerpo) });
      toast.success("Ficha guardada.");
      detalle.recargar();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo guardar la ficha.");
    } finally {
      setGuardando(false);
    }
  }

  async function cambiarEstado(estado: EstadoInmueble) {
    setCambiandoEstado(true);
    try {
      await apiFetch<InmuebleDetalle>(`/inmuebles/${id}/estado`, { method: "PUT", body: JSON.stringify({ estado }) });
      toast.success(`La propiedad quedó «${estadoInmuebleInfo(estado).label}».`);
      detalle.recargar();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "No se pudo cambiar el estado.");
    } finally {
      setCambiandoEstado(false);
    }
  }

  if (detalle.cargando && !detalle.data) {
    return (
      <div className="space-y-4 pb-28">
        <Skeleton className="h-10 w-2/3" />
        <Skeleton className="h-48 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }
  if (detalle.error || !detalle.data) {
    return (
      <EmptyState
        icon={Building2}
        tone="danger"
        title="No se pudo cargar la propiedad"
        description={detalle.error ?? "No existe esa propiedad."}
        action={
          <Button variant="outline" onClick={detalle.recargar}>
            Reintentar
          </Button>
        }
      />
    );
  }

  const inmueble = detalle.data;
  return (
    <>
      <PageHeader
        title={inmueble.titulo}
        description={
          <span className="flex flex-wrap items-center gap-2">
            <StatusBadge {...estadoInmuebleInfo(inmueble.estado)} /> <span className="text-muted-foreground">Código {inmueble.codigo}</span>
          </span>
        }
        actions={
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" asChild>
              <Link href={`/agenda?inmueble=${inmueble.id}`}>
                <CalendarDays /> Visitas
              </Link>
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button disabled={cambiandoEstado}>
                  {cambiandoEstado ? <Loader2 className="animate-spin" /> : null} Estado <ChevronDown />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {ACCIONES[inmueble.estado].map((a) => (
                  <DropdownMenuItem key={a.estado} onSelect={() => void cambiarEstado(a.estado)}>
                    {a.label}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        }
        info={
          <InfoButton titulo="La ficha de la propiedad">
            <p>Todo lo que escribas aquí es lo que el asistente de inmuebles puede responder. Lo que no esté, no lo inventa: te pasa la conversación.</p>
            <ul>
              <li><strong>Publicar</strong> pide como mínimo el título, el sector o la dirección y la descripción.</li>
              <li>Una propiedad <strong>vendida</strong> se sigue informando como vendida y no agenda visitas.</li>
              <li>Pausada o archivada, el asistente dice que no está disponible.</li>
            </ul>
          </InfoButton>
        }
      />

      <div className="flex flex-col gap-5 pb-28 md:pb-6">
        {inmueble.faltantes.length > 0 && (
          <SectionCard titulo="Para que el asistente responda mejor" descripcion="Datos que conviene completar.">
            <ul className="grid gap-1.5 p-4 text-sm sm:grid-cols-2 sm:p-5">
              {inmueble.faltantes.map((f) => (
                <li key={f} className="flex items-start gap-2">
                  <ListChecks className="mt-0.5 size-4 shrink-0 text-status-warning-ink" aria-hidden /> {f}
                </li>
              ))}
            </ul>
          </SectionCard>
        )}

        {/* Se vuelve a montar con lo guardado (si no, compararía contra los valores viejos). */}
        <FichaForm key={inmueble.actualizadoEn} inmueble={inmueble} guardando={guardando} error={error} onGuardar={(c) => void guardar(c)} textoGuardar="Guardar ficha" />
        <GaleriaInmueble inmueble={inmueble} onCambio={detalle.recargar} />
        <AnunciosInmueble inmueble={inmueble} onCambio={detalle.recargar} />
      </div>
    </>
  );
}
