import type { Metadata } from "next";
import { Geist_Mono, Poppins } from "next/font/google";
import "./globals.css";

import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { SITE } from "@/config/site";

// Nombrada "--font-sans" a propósito: es la variable que globals.css espera
// (@theme inline -> --font-sans). Cambiar la fuente del proyecto entero es
// tan simple como cambiar esta importación, sin tocar nada más.
const fontSans = Poppins({
  variable: "--font-sans",
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
});

const fontMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: SITE.title,
  description: SITE.description,
};

// Layout raíz: SOLO lo que aplica a TODAS las páginas, autenticadas o no
// (login incluido). El shell del dashboard (sidebar/header) vive en
// src/app/(dashboard)/layout.tsx -- login no lo lleva.
export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="es"
      className={`${fontSans.variable} ${fontMono.variable} h-full antialiased`}
    >
      <body className="min-h-full">
        <TooltipProvider>{children}</TooltipProvider>
        <Toaster />
      </body>
    </html>
  );
}
