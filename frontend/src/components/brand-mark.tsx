import { cn } from "@/lib/utils";

/** Marca de la app: cuadrado redondeado con degradado índigo y la inicial. Es
 * el mismo diseño que app/icon.svg (el favicon). */
export function BrandMark({ className }: { className?: string }) {
  return (
    <span
      aria-hidden
      className={cn(
        "flex shrink-0 items-center justify-center rounded-[28%] bg-gradient-to-br from-[oklch(0.62_0.19_280)] to-[oklch(0.45_0.2_275)] text-sm font-bold text-white shadow-card",
        className,
      )}
    >
      P
    </span>
  );
}
