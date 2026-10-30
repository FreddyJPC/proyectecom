import { MessageCircle } from "lucide-react";

import { EmptyState } from "@/components/app/empty-state";

// Panel derecho cuando no hay ninguna conversación abierta (solo se ve en
// pantallas anchas; en móvil la lista ocupa toda la pantalla).
export default function ConversacionesPage() {
  return (
    <div className="flex flex-1 items-center justify-center">
      <EmptyState
        icon={MessageCircle}
        title="Elige una conversación"
        description="Selecciona un chat de la lista para ver la transcripción, los datos del cliente y responder."
      />
    </div>
  );
}
