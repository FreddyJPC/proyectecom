"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageHeader } from "@/components/app/page-header";

import { AlertasTab } from "./alertas-tab";
import { EventosTab } from "./eventos-tab";

export default function IncidenciasPage() {
  return (
    <>
      <PageHeader
        title="Incidencias y alertas"
        description="Todo lo que el sistema detectó y necesita (o necesitó) tu atención, en un solo lugar."
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
