import Image from "next/image";

import { cn } from "@/lib/utils";

/** Marca de la app: el logo de AzoShop sobre un cuadrado blanco. El logo es negro, así que el fondo blanco es fijo (no
 * sigue el tema): sobre el modo oscuro, o sobre el panel oscuro del login, un logo negro sin fondo no se vería. */
export function BrandMark({ className }: { className?: string }) {
  return (
    <span
      aria-hidden
      className={cn(
        "flex shrink-0 items-center justify-center rounded-[22%] bg-white p-1 shadow-card ring-1 ring-black/10",
        className,
      )}
    >
      {/* SVG propio de /public: no necesita optimización de Next. */}
      <Image src="/azoshop-logo.svg" alt="" width={709} height={554} unoptimized className="h-auto w-full" priority />
    </span>
  );
}
