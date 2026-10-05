import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

/** Cliente de Supabase para Server Components/Actions. `cookies()` es
 * async desde Next.js 16 (Async Request APIs) -- por eso esta función
 * también lo es. */
export async function createClient() {
  const cookieStore = await cookies();

  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(cookiesToSet) {
          try {
            cookiesToSet.forEach(({ name, value, options }) => cookieStore.set(name, value, options));
          } catch {
            // Se llama desde un Server Component (no puede escribir cookies) --
            // inofensivo si el proxy (src/proxy.ts) ya refresca la sesión.
          }
        },
      },
    },
  );
}
