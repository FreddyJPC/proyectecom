import { ChevronLeft, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";

/** Paginación con rango legible ("21–40 de 87") y botones de tamaño táctil. */
export function PaginationBar({
  page,
  pageSize,
  total,
  onPage,
  disabled,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPage: (page: number) => void;
  disabled?: boolean;
}) {
  const totalPaginas = Math.max(1, Math.ceil(total / pageSize));
  const desde = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const hasta = Math.min(page * pageSize, total);

  if (total <= pageSize) {
    return total > 0 ? (
      <p className="px-1 text-sm text-muted-foreground tabular">
        {total} {total === 1 ? "resultado" : "resultados"}
      </p>
    ) : null;
  }

  return (
    <div className="flex items-center justify-between gap-3">
      <p className="text-sm text-muted-foreground tabular">
        {desde}–{hasta} de {total}
      </p>
      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="icon"
          className="size-10 md:size-8"
          disabled={disabled || page <= 1}
          onClick={() => onPage(page - 1)}
          aria-label="Página anterior"
        >
          <ChevronLeft />
        </Button>
        <span className="min-w-14 text-center text-sm tabular text-muted-foreground">
          {page} / {totalPaginas}
        </span>
        <Button
          variant="outline"
          size="icon"
          className="size-10 md:size-8"
          disabled={disabled || page >= totalPaginas}
          onClick={() => onPage(page + 1)}
          aria-label="Página siguiente"
        >
          <ChevronRight />
        </Button>
      </div>
    </div>
  );
}
