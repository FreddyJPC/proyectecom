"use client";

import { Filter } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { CANALES } from "@/lib/canales";
import { ETAPAS_LEAD } from "@/lib/leads";

const ETAPAS: Record<string, string> = { todas: "Todas", ...ETAPAS_LEAD };
const ORIGENES: Record<string, string> = { todos: "Todos", anuncio: "Anuncio", directo: "Directo", web_formulario: "Formulario web" };
const CANALES_FILTRO: Record<string, string> = { todos: "Todos", ...CANALES };
const SILENCIO: Record<string, string> = { "0": "Cualquiera", "2": "2 días o más", "5": "5 días o más", "14": "14 días o más" };

function Campo({ id, etiqueta, valor, opciones, onCambio }: { id: string; etiqueta: string; valor: string; opciones: Record<string, string>; onCambio: (v: string) => void }) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{etiqueta}</Label>
      <Select value={valor} onValueChange={onCambio}>
        <SelectTrigger id={id} className="w-full">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {Object.entries(opciones).map(([v, t]) => (
            <SelectItem key={v} value={v}>
              {t}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

/** Los filtros finos de Leads (etapa, cómo llegó, canal y silencio del cliente) en un cuadro: en el móvil son muchas
 * opciones para un menú desplegable. Cada cambio se aplica al instante; la temperatura se elige con los chips de la pantalla. */
export function FiltrosLeads({
  etapa,
  origen,
  canal,
  silencio,
  onEtapa,
  onOrigen,
  onCanal,
  onSilencio,
  onQuitar,
  activos,
}: {
  etapa: string;
  origen: string;
  canal: string;
  silencio: string;
  onEtapa: (v: string) => void;
  onOrigen: (v: string) => void;
  onCanal: (v: string) => void;
  onSilencio: (v: string) => void;
  onQuitar: () => void;
  activos: number;
}) {
  const [abierto, setAbierto] = useState(false);
  return (
    <Dialog open={abierto} onOpenChange={setAbierto}>
      <DialogTrigger asChild>
        <Button variant="outline" aria-label={activos > 0 ? `Filtros (${activos} activos)` : "Filtros"} className="relative shrink-0 max-sm:size-9">
          <Filter /> <span className="max-sm:hidden">Filtros</span>
          {activos > 0 && (
            <span className="tabular flex h-5 min-w-5 items-center justify-center rounded-full bg-primary px-1.5 text-xs font-semibold text-primary-foreground max-sm:absolute max-sm:-top-1.5 max-sm:-right-1.5">
              {activos}
            </span>
          )}
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Filtros</DialogTitle>
          <DialogDescription>Se aplican al instante. La temperatura se elige con los botones de la pantalla.</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <Campo id="filtro-etapa" etiqueta="Etapa" valor={etapa} opciones={ETAPAS} onCambio={onEtapa} />
          <Campo id="filtro-origen" etiqueta="Cómo llegó" valor={origen} opciones={ORIGENES} onCambio={onOrigen} />
          <Campo id="filtro-canal" etiqueta="Canal" valor={canal} opciones={CANALES_FILTRO} onCambio={onCanal} />
          <Campo id="filtro-silencio" etiqueta="Sin respuesta del cliente" valor={silencio} opciones={SILENCIO} onCambio={onSilencio} />
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onQuitar} disabled={activos === 0}>
            Quitar filtros
          </Button>
          <DialogClose asChild>
            <Button type="button">Listo</Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
