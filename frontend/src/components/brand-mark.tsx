import { cn } from "@/lib/utils";

/** Marca de la app: cuadrado redondeado con degradado negro y la inicial. Es
 * el mismo diseño que app/icon.svg (el favicon). */
export function BrandMark({ className }: { className?: string }) {
  return (
    <span
      aria-hidden
      className={cn(
        "flex shrink-0 items-center justify-center rounded-[28%] bg-gradient-to-br from-[oklch(0.38_0_0)] to-[oklch(0.15_0_0)] text-sm font-bold text-white shadow-card",
        className,
      )}
    >
      P
    </span>
  );
}
