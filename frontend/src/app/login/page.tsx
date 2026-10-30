"use client";

import { AlertCircle, Eye, EyeOff, Loader2, MessageCircle, Package, ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState, type FormEvent } from "react";

import { BrandMark } from "@/components/brand-mark";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { SITE } from "@/config/site";
import { createClient } from "@/lib/supabase/client";

const PUNTOS = [
  { icon: MessageCircle, texto: "Conversaciones de WhatsApp atendidas por Victoria, con tu mano cuando hace falta." },
  { icon: Package, texto: "Pedidos, envíos y novedades de Rocketfy en un solo lugar." },
  { icon: ShieldCheck, texto: "Alertas de stock para proteger tu inversión en publicidad." },
];

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [verPassword, setVerPassword] = useState(false);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const supabase = useMemo(() => createClient(), []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setCargando(true);
    setError(null);

    const { error } = await supabase.auth.signInWithPassword({ email, password });

    if (error) {
      setCargando(false);
      // El mensaje de Supabase llega en inglés ("Invalid login credentials"):
      // se traduce el caso más común y se conserva el original para el resto.
      setError(
        /invalid login credentials/i.test(error.message)
          ? "Correo o contraseña incorrectos. Revísalos e inténtalo de nuevo."
          : error.message,
      );
      return;
    }

    router.push("/");
    router.refresh();
  }

  return (
    <div className="grid min-h-dvh lg:grid-cols-[1.05fr_1fr]">
      {/* Panel de marca: solo en pantallas anchas. */}
      <aside className="relative hidden overflow-hidden bg-gradient-to-br from-[oklch(0.42_0.2_275)] via-[oklch(0.36_0.18_278)] to-[oklch(0.25_0.12_280)] p-12 text-white lg:flex lg:flex-col lg:justify-between">
        <div
          aria-hidden
          className="pointer-events-none absolute -top-32 -right-24 size-96 rounded-full bg-[oklch(0.7_0.17_280)]/25 blur-3xl"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute -bottom-40 -left-24 size-[28rem] rounded-full bg-[oklch(0.65_0.18_250)]/20 blur-3xl"
        />

        <div className="relative flex items-center gap-3">
          <BrandMark className="size-10 bg-white/15 from-white/20 to-white/10 text-base ring-1 ring-white/25" />
          <span className="text-lg font-semibold tracking-tight">{SITE.name}</span>
        </div>

        <div className="relative max-w-md space-y-8">
          <div className="space-y-3">
            <h2 className="text-3xl leading-tight font-semibold tracking-tight text-balance">
              Todo tu negocio de WhatsApp, bajo control.
            </h2>
            <p className="text-white/75">Del primer mensaje del cliente a la entrega del paquete.</p>
          </div>
          <ul className="space-y-4">
            {PUNTOS.map(({ icon: Icon, texto }) => (
              <li key={texto} className="flex items-start gap-3 text-sm text-white/85">
                <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg bg-white/10 ring-1 ring-white/15">
                  <Icon className="size-4" aria-hidden />
                </span>
                <span className="pt-1">{texto}</span>
              </li>
            ))}
          </ul>
        </div>

        <p className="relative text-xs text-white/50">AzoShop · Ecuador</p>
      </aside>

      <main className="flex items-center justify-center px-5 py-10 sm:px-8">
        <div className="w-full max-w-sm space-y-8">
          <div className="space-y-4">
            <BrandMark className="size-11 text-lg lg:hidden" />
            <div className="space-y-1.5">
              <h1 className="text-2xl font-semibold tracking-tight">Inicia sesión</h1>
              <p className="text-sm text-muted-foreground">Accede al panel operativo de {SITE.name}.</p>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-5" noValidate>
            {error && (
              <div
                role="alert"
                className="flex items-start gap-2.5 rounded-lg border border-status-danger/30 bg-status-danger-soft px-3.5 py-3 text-sm text-status-danger-ink"
              >
                <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden />
                <p>{error}</p>
              </div>
            )}

            <div className="flex flex-col gap-2">
              <Label htmlFor="email">Correo electrónico</Label>
              <Input
                id="email"
                type="email"
                inputMode="email"
                autoComplete="email"
                autoFocus
                required
                placeholder="tu@correo.com"
                value={email}
                aria-invalid={error ? true : undefined}
                onChange={(e) => setEmail(e.target.value)}
                className="h-11 md:h-10"
              />
            </div>

            <div className="flex flex-col gap-2">
              <Label htmlFor="password">Contraseña</Label>
              <div className="relative">
                <Input
                  id="password"
                  type={verPassword ? "text" : "password"}
                  autoComplete="current-password"
                  required
                  value={password}
                  aria-invalid={error ? true : undefined}
                  onChange={(e) => setPassword(e.target.value)}
                  className="h-11 pr-11 md:h-10"
                />
                <button
                  type="button"
                  onClick={() => setVerPassword((v) => !v)}
                  aria-label={verPassword ? "Ocultar contraseña" : "Mostrar contraseña"}
                  aria-pressed={verPassword}
                  className="absolute top-0 right-0 flex h-11 w-11 items-center justify-center rounded-lg text-muted-foreground transition-colors outline-none hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50 md:h-10 md:w-10"
                >
                  {verPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </button>
              </div>
            </div>

            <Button type="submit" size="lg" disabled={cargando || !email || !password} className="mt-1">
              {cargando ? (
                <>
                  <Loader2 className="animate-spin" /> Entrando…
                </>
              ) : (
                "Entrar"
              )}
            </Button>
          </form>

          <p className="text-center text-xs text-muted-foreground">
            ¿No puedes entrar? Pide a quien administra el panel que revise tu cuenta de acceso.
          </p>
        </div>
      </main>
    </div>
  );
}
