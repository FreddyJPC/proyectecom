import type { NextRequest } from "next/server";

import { updateSession } from "@/lib/supabase/middleware";

// Next.js 16 renombró `middleware.ts` a `proxy.ts` y la función a `proxy`
// (ver node_modules/next/dist/docs/.../upgrading/version-16.md). La lógica
// real vive en src/lib/supabase/middleware.ts, siguiendo el patrón oficial
// de Supabase para Next.js.
export async function proxy(request: NextRequest) {
  return updateSession(request);
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
