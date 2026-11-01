import { UserRound } from "lucide-react";

import { iniciales } from "@/lib/format";
import { cn } from "@/lib/utils";

// Paleta fija de grises: el mismo nombre siempre da el mismo tono, así cada
// cliente se reconoce de un vistazo en la lista sin elegir colores a mano. Son
// neutros a propósito: el color queda reservado para los estados.
const TONOS = [
  "bg-[oklch(0.93_0_0)] text-[oklch(0.3_0_0)] dark:bg-[oklch(0.32_0_0)] dark:text-[oklch(0.92_0_0)]",
  "bg-[oklch(0.89_0_0)] text-[oklch(0.28_0_0)] dark:bg-[oklch(0.37_0_0)] dark:text-[oklch(0.94_0_0)]",
  "bg-[oklch(0.84_0_0)] text-[oklch(0.25_0_0)] dark:bg-[oklch(0.42_0_0)] dark:text-[oklch(0.96_0_0)]",
  "bg-[oklch(0.3_0_0)] text-[oklch(0.96_0_0)] dark:bg-[oklch(0.82_0_0)] dark:text-[oklch(0.2_0_0)]",
  "bg-[oklch(0.4_0_0)] text-[oklch(0.97_0_0)] dark:bg-[oklch(0.74_0_0)] dark:text-[oklch(0.18_0_0)]",
  "bg-[oklch(0.96_0_0)] text-[oklch(0.35_0_0)] ring-1 ring-inset ring-border dark:bg-[oklch(0.25_0_0)] dark:text-[oklch(0.88_0_0)]",
];

function tono(semilla: string): string {
  let h = 0;
  for (let i = 0; i < semilla.length; i++) h = (h * 31 + semilla.charCodeAt(i)) >>> 0;
  return TONOS[h % TONOS.length];
}

export function AvatarInitials({
  nombre,
  semilla,
  className,
}: {
  nombre: string | null | undefined;
  semilla?: string;
  className?: string;
}) {
  // Un contacto sin nombre (solo teléfono) muestra un ícono de persona: las
  // "iniciales" de un número ("5") no ayudan a reconocer a nadie.
  const sinNombre = !nombre || /^[\d+\s()-]+$/.test(nombre);
  return (
    <span
      aria-hidden
      className={cn(
        "flex size-10 shrink-0 items-center justify-center rounded-full text-sm font-semibold",
        tono(semilla ?? nombre ?? "?"),
        className,
      )}
    >
      {sinNombre ? <UserRound className="size-[45%]" /> : iniciales(nombre)}
    </span>
  );
}
