import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

import { ThemeProvider } from "@/components/theme-provider";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { SITE } from "@/config/site";

// Nombrada "--font-sans" a propósito: es la variable que globals.css espera
// (@theme inline -> --font-sans). Geist se eligió por su legibilidad en
// tablas y cifras (los montos y teléfonos alinean bien); cambiarla es tan
// simple como cambiar esta importación, sin tocar nada más.
const fontSans = Geist({
  variable: "--font-sans",
  subsets: ["latin"],
});

const fontMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: SITE.title,
  description: SITE.description,
  applicationName: SITE.name,
};

// `viewportFit: cover` deja que la barra inferior respete el "notch" de los
// celulares; themeColor tiñe la barra del navegador móvil según el tema.
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f7f7fb" },
    { media: "(prefers-color-scheme: dark)", color: "#14141d" },
  ],
};

// Layout raíz: SOLO lo que aplica a TODAS las páginas, autenticadas o no
// (login incluido). El shell del dashboard (sidebar/header) vive en
// src/app/(dashboard)/layout.tsx -- login no lo lleva.
export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="es"
      suppressHydrationWarning
      className={`${fontSans.variable} ${fontMono.variable} h-full antialiased`}
    >
      <body className="min-h-full">
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
          <TooltipProvider>{children}</TooltipProvider>
          <Toaster position="top-center" closeButton />
        </ThemeProvider>
      </body>
    </html>
  );
}
