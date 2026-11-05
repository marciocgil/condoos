import { ChatPanel } from "@/components/condoos/ChatPanel";
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
  const [condo, history] = await Promise.all([
    apiGet<Condominium>(`/condominiums/${id}`),
    apiGet<ChatMessage[]>(`/condominiums/${id}/chat`),
  ]);
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
