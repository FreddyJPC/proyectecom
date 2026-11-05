import { createClient } from "@/lib/supabase/client";

const API_URL = process.env.NEXT_PUBLIC_API_URL;

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    /** Motivos concretos por los que el backend rechazó una acción (p. ej.
     * por qué un producto no se puede publicar). Vacío si no los hay. */
    public bloqueos: string[] = [],
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** Los errores de validación del backend llegan como `detalle: { campo: [mensajes] }`;
 * se aplanan a "campo: mensaje" para poder mostrarlos como lista. */
function aplanarDetalle(detalle: unknown): string[] {
  if (!detalle || typeof detalle !== "object") return [];
  return Object.entries(detalle as Record<string, unknown>).flatMap(([campo, mensajes]) =>
    (Array.isArray(mensajes) ? mensajes : [mensajes])
      .filter((m): m is string => typeof m === "string")
      .map((m) => `${campo}: ${m}`),
  );
}

/** Cliente mínimo hacia el backend Flask, desde Client Components. Adjunta
 * el token de sesión de Supabase (Fase 2 - Etapa 1) en cada llamada; el
 * backend lo verifica contra `${SUPABASE_URL}/auth/v1/user`. */
export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  if (!API_URL) {
    throw new Error("NEXT_PUBLIC_API_URL no está configurada (ver .env.example)");
  }

  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(session ? { Authorization: `Bearer ${session.access_token}` } : {}),
      ...init?.headers,
    },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const motivos = Array.isArray(body.bloqueos) ? body.bloqueos.filter((b: unknown) => typeof b === "string") : aplanarDetalle(body.detalle);
    throw new ApiError(body.error ?? `Error ${res.status} llamando a ${path}`, res.status, motivos);
  }

  return res.json() as Promise<T>;
}
