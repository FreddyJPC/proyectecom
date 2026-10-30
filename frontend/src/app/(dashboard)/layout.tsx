import { AppSidebar } from "@/components/app-sidebar";
import { EscaladasProvider } from "@/components/escaladas-context";
import { MobileNav } from "@/components/mobile-nav";
import { SiteHeader } from "@/components/site-header";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <SidebarProvider>
      {/* Primer elemento enfocable: quien navega con teclado puede saltar el
          menú y la cabecera e ir directo al contenido. */}
      <a
        href="#contenido"
        className="sr-only fixed top-3 left-3 z-50 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-pop focus:not-sr-only focus:outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
      >
        Saltar al contenido
      </a>
      <EscaladasProvider>
        <AppSidebar />
        <SidebarInset className="min-w-0">
          <SiteHeader />
          {/* El padding inferior en móvil deja espacio a la barra de
              navegación fija (4rem + área segura) para que no tape contenido. */}
          <main id="contenido" className="flex flex-1 flex-col gap-5 p-4 pb-28 md:gap-6 md:p-6 md:pb-8">{children}</main>
        </SidebarInset>
        <MobileNav />
      </EscaladasProvider>
    </SidebarProvider>
  );
}
