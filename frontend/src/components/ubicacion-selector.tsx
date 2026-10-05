"use client";

import { useEffect, useState } from "react";

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { apiFetch } from "@/lib/api";

/** Selector en cascada Provincia -> Cantón contra el catálogo cerrado de
 * Rocketfy (GET /catalogos/ubicaciones, respaldado por el CSV del
 * proveedor -- ver PROGRESS.md, análisis de la Fase 2 Etapa 2). Reutilizable
 * en cualquier formulario que capture una dirección de entrega. */
export function UbicacionSelector({
  provincia,
  canton,
  onProvinciaChange,
  onCantonChange,
}: {
  provincia: string;
  canton: string;
  onProvinciaChange: (provincia: string) => void;
  onCantonChange: (canton: string) => void;
}) {
  const [provincias, setProvincias] = useState<string[]>([]);
  const [cantones, setCantones] = useState<string[]>([]);
  const [cargandoCantones, setCargandoCantones] = useState(false);

  useEffect(() => {
    apiFetch<{ provincias: string[] }>("/catalogos/ubicaciones")
      .then((data) => setProvincias(data.provincias))
      .catch(() => setProvincias([]));
  }, []);

  useEffect(() => {
    if (!provincia) return;
    let cancelado = false;
    apiFetch<{ cantones: string[] }>(`/catalogos/ubicaciones/${encodeURIComponent(provincia)}/cantones`)
      .then((data) => {
        if (!cancelado) setCantones(data.cantones);
      })
      .catch(() => {
        if (!cancelado) setCantones([]);
      })
      .finally(() => {
        if (!cancelado) setCargandoCantones(false);
      });
    return () => {
      cancelado = true;
    };
  }, [provincia]);

  return (
    <div className="grid grid-cols-2 gap-3">
      <div className="grid gap-1.5">
        <label className="text-sm font-medium">Provincia</label>
        <Select
          value={provincia}
          onValueChange={(v) => {
            setCargandoCantones(true);
            setCantones([]);
            onProvinciaChange(v);
            onCantonChange("");
          }}
        >
          <SelectTrigger className="w-full">
            <SelectValue placeholder="Selecciona…" />
          </SelectTrigger>
          <SelectContent>
            {provincias.map((p) => (
              <SelectItem key={p} value={p}>
                {p}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="grid gap-1.5">
        <label className="text-sm font-medium">Cantón</label>
        <Select value={canton} onValueChange={onCantonChange} disabled={!provincia || cargandoCantones}>
          <SelectTrigger className="w-full">
            <SelectValue placeholder={provincia ? "Selecciona…" : "Elige provincia primero"} />
          </SelectTrigger>
          <SelectContent>
            {cantones.map((c) => (
              <SelectItem key={c} value={c}>
                {c}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}
