import { StatusBadge } from "@/components/status-badge";
import { temperaturaInfo } from "@/lib/leads";

/** La temperatura de un lead como insignia (color + texto: nunca solo color). */
export function TemperaturaBadge({ temperatura, className }: { temperatura: string; className?: string }) {
  const info = temperaturaInfo(temperatura);
  return <StatusBadge label={info.label} variant={info.variant} className={className} />;
}
