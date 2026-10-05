"use client";

import { useState } from "react";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { CatalogoTab } from "./catalogo-tab";
import { MonitoreadosTab } from "./monitoreados-tab";

export default function CatalogoPage() {
  const [refrescarKey, setRefrescarKey] = useState(0);

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h2 className="text-lg font-semibold">Catálogo y Stock</h2>
        <p className="text-sm text-muted-foreground">
          Explora el catálogo de Rocketfy y elige qué SKUs vigilar para proteger tu inversión publicitaria.
        </p>
      </div>

      <Tabs defaultValue="catalogo">
        <TabsList>
          <TabsTrigger value="catalogo">Catálogo</TabsTrigger>
          <TabsTrigger value="monitoreados">SKUs monitoreados</TabsTrigger>
        </TabsList>
        <TabsContent value="catalogo" className="pt-4">
          <CatalogoTab onCambio={() => setRefrescarKey((k) => k + 1)} />
        </TabsContent>
        <TabsContent value="monitoreados" className="pt-4">
          <MonitoreadosTab refrescarKey={refrescarKey} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
