"use client";

import { Info } from "lucide-react";
import type { ReactNode } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

/**
 * Botón ⓘ que abre un cuadro con la explicación de lo que tienes delante (una pantalla, una sección o un campo).
 *
 * Para qué existe: las explicaciones de «para qué sirve esto» son valiosas, pero puestas en la pantalla la saturan.
 * Aquí viven en un cuadro, con espacio para explicar bien, y la pantalla se queda solo con lo esencial.
 *
 * Qué va en la pantalla y qué va aquí:
 *   - En la pantalla: títulos, etiquetas cortas, la unidad y el rango («mensajes, de 10 a 100»), errores, avisos que
 *     piden una acción y advertencias de algo difícil de deshacer.
 *   - Aquí: el «para qué sirve», el «cómo funciona», ejemplos, reglas y avisos que solo informan.
 *
 * `titulo` es lo que se explica (aparece como título del cuadro y en el nombre accesible del botón).
 */
export function InfoButton({
  titulo,
  children,
  className,
}: {
  titulo: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <Dialog>
      {/* Un <span role="button"> y no un <button>: dentro de un <fieldset disabled> (la ficha de un producto archivado, o mientras
          se guarda) todo <button> queda deshabilitado, y la explicación tiene que poder leerse siempre. */}
      <DialogTrigger asChild>
        <span
          role="button"
          tabIndex={0}
          aria-label={`Más información: ${titulo}`}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              e.currentTarget.click();
            }
          }}
          className={cn(buttonVariants({ variant: "ghost", size: "icon" }), "-my-1.5 size-9 cursor-pointer rounded-full text-muted-foreground hover:text-foreground md:size-7", className)}
        >
          <Info className="size-4" aria-hidden />
        </span>
      </DialogTrigger>
      <DialogContent className="flex max-h-[85dvh] flex-col gap-0 p-0 sm:max-w-lg">
        <DialogHeader className="shrink-0 border-b px-4 py-3.5 pr-12">
          <DialogTitle className="flex items-center gap-2 leading-snug">
            <Info className="size-4 shrink-0 text-primary" aria-hidden />
            {titulo}
          </DialogTitle>
          <DialogDescription className="sr-only">Explicación de «{titulo}».</DialogDescription>
        </DialogHeader>
        {/* tabIndex=0: si el texto no cabe, quien navega con teclado puede enfocar esta zona y desplazarla (regla de accesibilidad). */}
        <div tabIndex={0} className="min-h-0 flex-1 space-y-3 overflow-y-auto px-4 py-4 text-sm leading-relaxed text-muted-foreground outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring/60 [&_a]:text-primary [&_a]:underline [&_a]:underline-offset-2 [&_h3]:pt-1 [&_h3]:text-sm [&_h3]:font-semibold [&_h3]:text-foreground [&_li]:pl-0.5 [&_ol]:list-decimal [&_ol]:space-y-1.5 [&_ol]:pl-5 [&_strong]:font-semibold [&_strong]:text-foreground [&_ul]:list-disc [&_ul]:space-y-1.5 [&_ul]:pl-5">
          {children}
        </div>
        <DialogFooter className="m-0 shrink-0 rounded-b-xl">
          <DialogClose asChild>
            <Button type="button" variant="outline">
              Entendido
            </Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** Un ejemplo dentro del cuadro de información: destaca del texto corrido. */
export function InfoEjemplo({ children, titulo = "Ejemplo" }: { children: ReactNode; titulo?: string }) {
  return (
    <div className="rounded-lg border bg-muted/50 p-3 text-foreground">
      <p className="mb-1 text-xs font-medium text-muted-foreground">{titulo}</p>
      <div className="space-y-1.5">{children}</div>
    </div>
  );
}

/** Un aviso dentro del cuadro de información (algo a tener en cuenta). */
export function InfoAviso({ children }: { children: ReactNode }) {
  return <div className="rounded-lg bg-status-warning-soft p-3 text-status-warning-ink">{children}</div>;
}
