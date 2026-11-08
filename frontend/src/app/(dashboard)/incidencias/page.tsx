"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { InfoButton } from "@/components/app/info-button";
import { PageHeader } from "@/components/app/page-header";

import { AlertasTab } from "./alertas-tab";
import { EventosTab } from "./eventos-tab";

export default function IncidenciasPage() {
  return (
    <>
      <PageHeader
        title="Incidencias y alertas"
        description="Lo que el sistema detectó y necesita tu atención."
        info={
          <InfoButton titulo="Incidencias y alertas">
            <p>Reúne en un solo lugar todo lo que el sistema detectó y necesita (o necesitó) tu atención.</p>
            <ul>
              <li>
                <strong>Envíos:</strong> los cambios de estado que Rocketfy avisa de tus pedidos. Por defecto ves solo los que requieren atención (por ejemplo, un envío con problemas).
              </li>
              <li>
                <strong>Stock y precio:</strong> avisos de los productos que vigilas, cuando bajan de su mínimo, cambian de precio, se quedan sin stock o su margen queda en riesgo.
              </li>
            </ul>
          </InfoButton>
        }
      />

      <Tabs defaultValue="eventos" className="gap-5">
        <TabsList className="w-full sm:w-fit">
          <TabsTrigger value="eventos" className="px-4">
            Envíos
          </TabsTrigger>
          <TabsTrigger value="stock" className="px-4">
            Stock y precio
          </TabsTrigger>
        </TabsList>
        <TabsContent value="eventos" className="flex flex-col gap-4">
          <EventosTab />
        </TabsContent>
        <TabsContent value="stock" className="flex flex-col gap-4">
          <AlertasTab />
        </TabsContent>
      </Tabs>
    </>
  );
}
