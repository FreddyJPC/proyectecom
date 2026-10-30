import { UserRound } from "lucide-react";

import { iniciales } from "@/lib/format";
import { cn } from "@/lib/utils";

// Paleta fija de tonos suaves: el mismo nombre siempre da el mismo color, así
// cada cliente se reconoce de un vistazo en la lista sin elegir colores a mano.
const TONOS = [
  "bg-[oklch(0.93_0.05_275)] text-[oklch(0.38_0.14_275)] dark:bg-[oklch(0.33_0.07_275)] dark:text-[oklch(0.9_0.05_275)]",
  "bg-[oklch(0.93_0.05_190)] text-[oklch(0.38_0.09_190)] dark:bg-[oklch(0.33_0.05_190)] dark:text-[oklch(0.9_0.06_190)]",
  "bg-[oklch(0.94_0.06_80)] text-[oklch(0.42_0.1_70)] dark:bg-[oklch(0.35_0.06_80)] dark:text-[oklch(0.9_0.08_85)]",
  "bg-[oklch(0.94_0.04_20)] text-[oklch(0.42_0.14_20)] dark:bg-[oklch(0.34_0.07_20)] dark:text-[oklch(0.9_0.07_20)]",
  "bg-[oklch(0.94_0.05_150)] text-[oklch(0.4_0.1_150)] dark:bg-[oklch(0.33_0.06_150)] dark:text-[oklch(0.9_0.08_150)]",
  "bg-[oklch(0.94_0.04_330)] text-[oklch(0.42_0.13_330)] dark:bg-[oklch(0.34_0.07_330)] dark:text-[oklch(0.9_0.06_330)]",
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
