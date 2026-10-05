"use client";

import { useEffect, useState } from "react";

type Estado = "verificando" | "conectado" | "sin-conexion" | "sin-configurar";

const API_URL = process.env.NEXT_PUBLIC_API_URL;

export function BackendStatus() {
  const [estado, setEstado] = useState<Estado>(API_URL ? "verificando" : "sin-configurar");

  useEffect(() => {
    if (!API_URL) return;

    let cancelado = false;
    fetch(`${API_URL}/health`)
      .then((res) => {
        if (!cancelado) setEstado(res.ok ? "conectado" : "sin-conexion");
      })
      .catch(() => {
        if (!cancelado) setEstado("sin-conexion");
      });

    return () => {
      cancelado = true;
    };
  }, []);

  const config: Record<Estado, { color: string; texto: string }> = {
    verificando: { color: "bg-muted-foreground", texto: "Verificando conexión con el backend…" },
    conectado: { color: "bg-emerald-500", texto: "Backend conectado" },
    "sin-conexion": { color: "bg-destructive", texto: "No se pudo conectar con el backend" },
    "sin-configurar": { color: "bg-amber-500", texto: "NEXT_PUBLIC_API_URL no configurada" },
  };

  const { color, texto } = config[estado];

  return (
    <div className="flex items-center gap-2 text-sm text-muted-foreground">
      <span className={`size-2 rounded-full ${color}`} />
      {texto}
    </div>
  );
}
