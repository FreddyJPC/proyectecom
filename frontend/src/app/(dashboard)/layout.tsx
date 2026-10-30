import { AppSidebar } from "@/components/app-sidebar";
import { EscaladasProvider } from "@/components/escaladas-context";
import { MobileNav } from "@/components/mobile-nav";
import { SiteHeader } from "@/components/site-header";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <SidebarProvider>
      <EscaladasProvider>
        <AppSidebar />
        <SidebarInset className="min-w-0">
          <SiteHeader />
          {/* El padding inferior en móvil deja espacio a la barra de
              navegación fija (4rem + área segura) para que no tape contenido. */}
          <main className="flex flex-1 flex-col gap-5 p-4 pb-28 md:gap-6 md:p-6 md:pb-8">{children}</main>
        </SidebarInset>
        <MobileNav />
      </EscaladasProvider>
    </SidebarProvider>
  );
}
