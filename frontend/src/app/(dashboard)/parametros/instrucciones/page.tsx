"use client";

import { TriangleAlert } from "lucide-react";

import { ListSkeleton } from "@/components/app/list-skeleton";
import { PageHeader } from "@/components/app/page-header";
import { SectionCard } from "@/components/app/section-card";
import { Button } from "@/components/ui/button";
import { useApi } from "@/hooks/use-api";
import type { Instrucciones } from "@/types/instrucciones";

import { EditorInstrucciones } from "./editor-instrucciones";

export default function InstruccionesDeVictoriaPage() {
  const { data, error, cargando, recargar } = useApi<Instrucciones>("/instrucciones-victoria");

  return (
    <>
      <PageHeader
        title="Instrucciones de Victoria"
        description="Cómo habla Victoria y qué reglas sigue. Edita un borrador, pruébalo con «Probar con Victoria» y recién entonces publícalo: los clientes no ven nada hasta que publiques."
      />

      {error && !data ? (
        <div role="alert" className="flex flex-wrap items-center gap-3 rounded-xl border border-status-danger/30 bg-status-danger-soft p-4 text-status-danger-ink">
          <TriangleAlert className="size-5 shrink-0" aria-hidden />
          <p className="flex-1 text-sm">No se pudieron cargar las instrucciones. {error}</p>
          <Button variant="outline" size="sm" onClick={recargar} className="bg-card text-foreground">
            Reintentar
          </Button>
        </div>
      ) : cargando || !data ? (
        <SectionCard titulo="Cargando instrucciones" descripcion="Un momento…">
          <ListSkeleton filas={4} />
        </SectionCard>
      ) : (
        // La clave hace que el editor arranque de cero con lo guardado cada vez que algo se guarda, publica o descarta.
        <EditorInstrucciones
          key={`${data.publicada?.id ?? "original"}:${data.borrador?.id ?? "sin"}:${data.borrador?.creadoEn ?? ""}`}
          data={data}
          onCambiado={recargar}
        />
      )}
    </>
  );
}
