"use client";

import { useEffect, useState } from "react";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

type Estado = "verificando" | "conectado" | "sin-conexion" | "sin-configurar";

const API_URL = process.env.NEXT_PUBLIC_API_URL;

const CONFIG: Record<Estado, { punto: string; texto: string; corto: string }> = {
  verificando: { punto: "bg-muted-foreground animate-pulse", texto: "Verificando conexión con el backend…", corto: "Verificando" },
  conectado: { punto: "bg-status-success", texto: "Backend conectado", corto: "En línea" },
  "sin-conexion": { punto: "bg-status-danger", texto: "No se pudo conectar con el backend", corto: "Sin conexión" },
  "sin-configurar": { punto: "bg-status-warning", texto: "NEXT_PUBLIC_API_URL no configurada", corto: "Sin configurar" },
};

/** Indicador compacto del estado del backend: un punto de color (con texto en
 * pantallas anchas) y el detalle completo en un tooltip. Pregunta a /health,
 * que además informa si los jobs automáticos están encendidos. */
export function BackendStatus() {
  const [estado, setEstado] = useState<Estado>(API_URL ? "verificando" : "sin-configurar");
  const [jobs, setJobs] = useState<boolean | null>(null);

  useEffect(() => {
    if (!API_URL) return;

    let cancelado = false;
    fetch(`${API_URL}/health`)
      .then(async (res) => {
        if (cancelado) return;
        setEstado(res.ok ? "conectado" : "sin-conexion");
        if (res.ok) {
          const data = (await res.json().catch(() => null)) as { scheduler?: boolean } | null;
          if (!cancelado && typeof data?.scheduler === "boolean") setJobs(data.scheduler);
        }
      })
      .catch(() => {
        if (!cancelado) setEstado("sin-conexion");
      });

    return () => {
      cancelado = true;
    };
  }, []);

  const { punto, texto, corto } = CONFIG[estado];

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div
          role="status"
          tabIndex={0}
          className="flex h-8 items-center gap-2 rounded-full border bg-card px-2.5 text-xs font-medium text-muted-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <span className={cn("size-2 rounded-full", punto)} aria-hidden />
          <span className="hidden lg:inline">{corto}</span>
          <span className="sr-only lg:hidden">{texto}</span>
        </div>
      </TooltipTrigger>
      <TooltipContent>
        {texto}
        {estado === "conectado" && jobs !== null && <> · Tareas automáticas {jobs ? "activas" : "apagadas"}</>}
      </TooltipContent>
    </Tooltip>
  );
}
