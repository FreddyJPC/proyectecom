"use client"

import * as React from "react"
import { cn } from "cn"
import { Switch as SwitchPrimitive } from "radix-ui"

/** Interruptor encendido/apagado. Siempre va con una etiqueta de texto al lado
 * (un `Label htmlFor`): el estado nunca depende solo del color o de la posición. */
function Switch({
  className,
  ...props
}: React.ComponentProps<typeof SwitchPrimitive.Root>) {
  return (
    <SwitchPrimitive.Root
      data-slot="switch"
      className={cn(
        "peer relative inline-flex h-6 w-11 shrink-0 items-center rounded-full border border-input transition-colors outline-none after:absolute after:-inset-x-1 after:-inset-y-2 focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:border-primary data-[state=checked]:bg-primary data-[state=unchecked]:bg-muted",
        className
      )}
      {...props}
    >
      <SwitchPrimitive.Thumb
        data-slot="switch-thumb"
        className="pointer-events-none block size-[1.1rem] rounded-full bg-background shadow-sm ring-1 ring-foreground/10 transition-transform data-[state=checked]:translate-x-[1.35rem] data-[state=unchecked]:translate-x-[0.2rem]"
      />
    </SwitchPrimitive.Root>
  )
}

export { Switch }
