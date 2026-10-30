"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { apiFetch } from "@/lib/api";
import type { ConversacionesListado } from "@/types/conversacion";

// Poll simple (no tiempo real, a propósito -- ver decisiones de alcance
// del módulo de Conversaciones): suficiente para que el contador no quede
// desactualizado por mucho tiempo sin agregar websockets.
const INTERVALO_POLL_MS = 30_000;

const EscaladasContext = createContext(0);

/** Consulta UNA sola vez cada 30 s cuántas conversaciones escaladas siguen
 * sin revisar y lo comparte con el sidebar y la barra inferior del móvil
 * (antes cada uno hacía su propio poll). */
export function EscaladasProvider({ children }: { children: ReactNode }) {
  const [escaladasSinRevisar, setEscaladasSinRevisar] = useState(0);

  useEffect(() => {
    let cancelado = false;

    function consultar() {
      apiFetch<ConversacionesListado>("/conversaciones?estado=escalada&pageSize=1")
        .then((data) => {
          if (!cancelado) setEscaladasSinRevisar(data.totalesPorFiltroRapido.escaladasSinRevisar);
        })
        .catch(() => {
          // Best-effort: si falla, simplemente no se muestra el contador --
          // no es motivo para un toast de error en cada carga de página.
        });
    }

    consultar();
    const intervalo = setInterval(consultar, INTERVALO_POLL_MS);
    return () => {
      cancelado = true;
      clearInterval(intervalo);
    };
  }, []);

  return <EscaladasContext.Provider value={escaladasSinRevisar}>{children}</EscaladasContext.Provider>;
}

export function useEscaladasSinRevisar(): number {
  return useContext(EscaladasContext);
}
