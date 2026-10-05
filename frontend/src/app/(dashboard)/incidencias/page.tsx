"use client";

import { AlertasTab } from "./alertas-tab";
import { EventosTab } from "./eventos-tab";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export default function IncidenciasPage() {
  return (
    <div className="flex flex-col gap-4">
      <div>
        <h2 className="text-lg font-semibold">Incidencias y Alertas</h2>
        <p className="text-sm text-muted-foreground">
          Todo lo que el sistema detectó y necesita (o necesitó) tu atención, en un solo lugar.
        </p>
      </div>

      <Tabs defaultValue="eventos">
        <TabsList>
          <TabsTrigger value="eventos">Eventos de pedidos</TabsTrigger>
          <TabsTrigger value="stock">Alertas de stock y precio</TabsTrigger>
        </TabsList>
        <TabsContent value="eventos" className="pt-4">
          <EventosTab />
        </TabsContent>
        <TabsContent value="stock" className="pt-4">
          <AlertasTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
