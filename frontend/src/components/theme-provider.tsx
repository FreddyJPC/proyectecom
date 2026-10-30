"use client";

import { ThemeProvider as NextThemesProvider } from "next-themes";
import type { ComponentProps } from "react";

/** Tema claro/oscuro/sistema. Aplica la clase `dark` en <html>, que es lo
 * que globals.css espera (@custom-variant dark). */
export function ThemeProvider(props: ComponentProps<typeof NextThemesProvider>) {
  return <NextThemesProvider {...props} />;
}
