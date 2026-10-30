"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Fragment } from "react";

import { BackendStatus } from "@/components/backend-status";
import { ThemeToggle } from "@/components/theme-toggle";
import { Separator } from "@/components/ui/separator";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { UserMenu } from "@/components/user-menu";
import { migasDe } from "@/config/site";

/** Cabecera fija. En escritorio: botón del menú + migas de pan. En móvil: el
 * título de la página y, en subpáginas, una flecha para volver a la lista
 * (el menú ya está en la barra inferior). */
export function SiteHeader() {
  const pathname = usePathname();
  const migas = migasDe(pathname);
  const actual = migas[migas.length - 1];
  const padre = migas.length > 1 ? migas[migas.length - 2] : null;

  return (
    <header className="sticky top-0 z-30 flex h-14 shrink-0 items-center gap-2 border-b bg-background/85 px-3 backdrop-blur supports-[backdrop-filter]:bg-background/70 md:px-5">
      <SidebarTrigger className="-ml-1 hidden md:inline-flex" aria-label="Mostrar u ocultar el menú" />
      <Separator orientation="vertical" className="mr-1 hidden h-4 md:block" />

      {/* Móvil */}
      <div className="flex min-w-0 flex-1 items-center gap-1 md:hidden">
        {padre?.href && (
          <Link
            href={padre.href}
            aria-label={`Volver a ${padre.label}`}
            className="-ml-1 flex size-10 shrink-0 items-center justify-center rounded-full text-muted-foreground active:bg-muted"
          >
            <ChevronLeft className="size-5" />
          </Link>
        )}
        <p className="truncate text-base font-semibold tracking-tight">{actual.label}</p>
      </div>

      {/* Escritorio: migas de pan */}
      <nav aria-label="Ruta" className="hidden min-w-0 flex-1 md:block">
        <ol className="flex items-center gap-1.5 text-sm">
          {migas.map((miga, i) => {
            const esUltima = i === migas.length - 1;
            return (
              <Fragment key={i}>
                {i > 0 && <ChevronRight className="size-3.5 shrink-0 text-muted-foreground/60" aria-hidden />}
                <li className="min-w-0">
                  {miga.href && !esUltima ? (
                    <Link href={miga.href} className="text-muted-foreground transition-colors hover:text-foreground">
                      {miga.label}
                    </Link>
                  ) : (
                    <span aria-current={esUltima ? "page" : undefined} className="truncate font-medium">
                      {miga.label}
                    </span>
                  )}
                </li>
              </Fragment>
            );
          })}
        </ol>
      </nav>

      <div className="flex items-center gap-1.5">
        <BackendStatus />
        <ThemeToggle />
        <UserMenu />
      </div>
    </header>
  );
}
