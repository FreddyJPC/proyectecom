"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

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

type ValorDelContexto = Contadores & {
  /** Vuelve a consultar los contadores ya (p. ej. justo después de atender o cancelar algo en «Por gestionar»). */
  refrescar: () => void;
};

const ContadoresContext = createContext<ValorDelContexto>({ escaladasSinRevisar: 0, gestionPendiente: 0, refrescar: () => {} });

/** Consulta UNA sola vez cada 30 s cuántas conversaciones escaladas siguen
 * sin revisar y cuántas solicitudes esperan en «Por gestionar», y lo comparte
 * con el sidebar y la barra inferior del móvil (antes cada uno hacía su propio poll). */
export function EscaladasProvider({ children }: { children: ReactNode }) {
  const [contadores, setContadores] = useState<Contadores>({ escaladasSinRevisar: 0, gestionPendiente: 0 });

  const consultar = useCallback(() => {
    // Best-effort: si falla, simplemente no se muestra el contador --
    // no es motivo para un toast de error en cada carga de página.
    apiFetch<ConversacionesListado>("/conversaciones?estado=escalada&pageSize=1")
      .then((data) => setContadores((c) => ({ ...c, escaladasSinRevisar: data.totalesPorFiltroRapido.escaladasSinRevisar })))
      .catch(() => {});
    apiFetch<{ pendientes: number }>("/gestion/resumen")
      .then((data) => setContadores((c) => ({ ...c, gestionPendiente: data.pendientes })))
      .catch(() => {});
  }, []);

  useEffect(() => {
    consultar();
    const intervalo = setInterval(consultar, INTERVALO_POLL_MS);
    return () => clearInterval(intervalo);
  }, [consultar]);

  return <ContadoresContext.Provider value={{ ...contadores, refrescar: consultar }}>{children}</ContadoresContext.Provider>;
}

export function useEscaladasSinRevisar(): number {
  return useContext(ContadoresContext).escaladasSinRevisar;
}

export function useGestionPendiente(): number {
  return useContext(ContadoresContext).gestionPendiente;
}

/** Para refrescar los contadores del menú sin esperar al siguiente poll. */
export function useRefrescarContadores(): () => void {
  return useContext(ContadoresContext).refrescar;
}
