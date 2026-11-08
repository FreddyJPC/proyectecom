"use client";

import { TriangleAlert } from "lucide-react";

import { InfoButton } from "@/components/app/info-button";
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
        description="Cómo habla Victoria y qué reglas sigue."
        info={
          <InfoButton titulo="Cómo funcionan las instrucciones de Victoria">
            <p>
              Aquí cambias la personalidad de Victoria, su objetivo y las reglas que nunca rompe. Se hace en tres pasos, para que ningún cambio llegue a un cliente sin
              haberse probado:
            </p>
            <ol>
              <li>
                <strong>Edita un borrador.</strong> Los clientes no ven nada hasta que publiques.
              </li>
              <li>
                <strong>Pruébalo</strong> con «Probar con Victoria», que usa el mismo cerebro pero sin tocar nada real.
              </li>
              <li>
                <strong>Publícalo.</strong> Desde el siguiente mensaje, Victoria habla con ese texto.
              </li>
            </ol>
            <h3>Si algo sale mal</h3>
            <ul>
              <li>La versión anterior queda guardada: puedes cargarla de nuevo en el borrador.</li>
              <li>«Volver a las originales» hace que Victoria use al instante el texto que trae el programa.</li>
              <li>Si las instrucciones guardadas fallan o dejan de ser válidas, Victoria usa las originales: nunca se queda sin instrucciones.</li>
            </ul>
            <h3>Lo que no se puede cambiar</h3>
            <p>
              El total a cobrar, el stock, la cantidad máxima por pedido y la pausa de productos los decide el sistema, no el texto. Un texto peor puede empeorar el trato
              con un cliente, pero no puede saltarse esas reglas.
            </p>
          </InfoButton>
        }
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
