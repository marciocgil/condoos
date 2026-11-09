import { MessageSquareOff } from "lucide-react";

import { ChatPanel } from "@/components/condoos/ChatPanel";
import { EmptyState } from "@/components/ui/EmptyState";
import { apiGet } from "@/lib/api";
import type { ChatMessage, ChatScreen, Condominium } from "@/lib/types";

const SCREENS = new Set(["resumo", "achados", "achado", "contratos", "historico"]);
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export default async function PerguntePage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ tela?: string; achado?: string; competencia?: string }>;
}) {
  const { id } = await params;
  const sp = await searchParams;
  const [condo, history, chat] = await Promise.all([
    apiGet<Condominium>(`/condominiums/${id}`),
    apiGet<ChatMessage[]>(`/condominiums/${id}/chat`),
    apiGet<{ available: boolean }>(`/condominiums/${id}/chat/status`),
  ]);
  if (!chat.available) {
    // Reached by a saved link while the model is off (LB-085, D108).
    return (
      <>
        <h1 className="text-xl font-semibold">Pergunte ao CondoOS</h1>
        <EmptyState icon={<MessageSquareOff size={28} />} title="Indisponível no momento">
          As perguntas livres voltam assim que o assistente estiver ligado. Enquanto isso, as telas
          de Achados, Contratos e Histórico mostram os dados com as evidências.
        </EmptyState>
      </>
    );
  }
  const screen: ChatScreen = {
    screen: SCREENS.has(sp.tela ?? "") ? (sp.tela as ChatScreen["screen"]) : "resumo",
  };
  if (sp.achado && UUID.test(sp.achado)) screen.finding_id = sp.achado;
  if (sp.competencia && /^\d{4}-\d{2}$/.test(sp.competencia)) screen.competence = sp.competencia;
  return (
    <ChatPanel
      condominiumId={id}
      condominiumName={condo.name}
      initial={history}
      screen={screen}
      variant="sindico"
    />
  );
}
