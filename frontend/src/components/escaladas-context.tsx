"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { apiFetch } from "@/lib/api";
import type { ConversacionesListado } from "@/types/conversacion";

// Poll simple (no tiempo real, a propósito -- ver decisiones de alcance
// del módulo de Conversaciones): suficiente para que el contador no quede
// desactualizado por mucho tiempo sin agregar websockets.
const INTERVALO_POLL_MS = 30_000;

type Contadores = {
  /** Conversaciones escaladas por Victoria que nadie ha revisado. */
  escaladasSinRevisar: number;
  /** Solicitudes de gestión pendientes (ADR-012): lo que espera al dueño en «Por gestionar». */
  gestionPendiente: number;
};

const ContadoresContext = createContext<Contadores>({ escaladasSinRevisar: 0, gestionPendiente: 0 });

/** Consulta UNA sola vez cada 30 s cuántas conversaciones escaladas siguen
 * sin revisar y cuántas solicitudes esperan en «Por gestionar», y lo comparte
 * con el sidebar y la barra inferior del móvil (antes cada uno hacía su propio poll). */
export function EscaladasProvider({ children }: { children: ReactNode }) {
  const [contadores, setContadores] = useState<Contadores>({ escaladasSinRevisar: 0, gestionPendiente: 0 });

  useEffect(() => {
    let cancelado = false;

    function consultar() {
      // Best-effort: si falla, simplemente no se muestra el contador --
      // no es motivo para un toast de error en cada carga de página.
      apiFetch<ConversacionesListado>("/conversaciones?estado=escalada&pageSize=1")
        .then((data) => {
          if (!cancelado) setContadores((c) => ({ ...c, escaladasSinRevisar: data.totalesPorFiltroRapido.escaladasSinRevisar }));
        })
        .catch(() => {});
      apiFetch<{ pendientes: number }>("/gestion/resumen")
        .then((data) => {
          if (!cancelado) setContadores((c) => ({ ...c, gestionPendiente: data.pendientes }));
        })
        .catch(() => {});
    }

    consultar();
    const intervalo = setInterval(consultar, INTERVALO_POLL_MS);
    return () => {
      cancelado = true;
      clearInterval(intervalo);
    };
  }, []);

  return <ContadoresContext.Provider value={contadores}>{children}</ContadoresContext.Provider>;
}

export function useEscaladasSinRevisar(): number {
  return useContext(ContadoresContext).escaladasSinRevisar;
}

export function useGestionPendiente(): number {
  return useContext(ContadoresContext).gestionPendiente;
}
