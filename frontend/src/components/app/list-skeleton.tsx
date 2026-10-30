import { Skeleton } from "@/components/ui/skeleton";

/** Esqueleto de lista (tarjetas) para estados de carga en móvil y escritorio. */
export function ListSkeleton({ filas = 6 }: { filas?: number }) {
  return (
    <div className="divide-y" aria-busy="true" aria-label="Cargando">
      {Array.from({ length: filas }).map((_, i) => (
        <div key={i} className="flex items-center gap-3 p-4">
          <Skeleton className="size-10 shrink-0 rounded-full" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-4 w-2/5" />
            <Skeleton className="h-3 w-3/5" />
          </div>
          <Skeleton className="h-6 w-20 rounded-full" />
        </div>
      ))}
    </div>
  );
}
