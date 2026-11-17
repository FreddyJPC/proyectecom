import type { MetadataRoute } from "next";

import { SITE } from "@/config/site";

/** Manifest de la PWA: lo que el teléfono lee para instalar el panel como una app (ícono en la pantalla de inicio, abre a
 * pantalla completa, sin la barra del navegador). Next lo publica en /manifest.webmanifest y lo enlaza solo. */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: SITE.name,
    short_name: "AzoShop",
    description: SITE.description,
    // Abre el resumen del negocio; si no hay sesión, el proxy manda al login y vuelve.
    start_url: "/",
    scope: "/",
    display: "standalone",
    orientation: "portrait",
    lang: "es",
    // Mientras carga, la pantalla de arranque usa estos colores (los mismos del tema claro del panel).
    background_color: "#fafafa",
    theme_color: "#fafafa",
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      // Android recorta este ícono (círculo, gota…): el logo va más pequeño para que no se corte.
      { src: "/icons/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
