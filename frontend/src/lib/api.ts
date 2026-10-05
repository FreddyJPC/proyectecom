import { createClient } from "@/lib/supabase/client";

const API_URL = process.env.NEXT_PUBLIC_API_URL;

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
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
    throw new ApiError(body.error ?? `Error ${res.status} llamando a ${path}`, res.status);
  }

  return res.json() as Promise<T>;
}
