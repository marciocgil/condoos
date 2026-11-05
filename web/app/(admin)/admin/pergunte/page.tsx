import { MessageSquare } from "lucide-react";

import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/ui/EmptyState";

export default function PerguntePage() {
  return (
    <>
      <PageHeader title="Pergunte à IA" />
      <EmptyState icon={<MessageSquare size={28} />} title="Disponível em breve">
        O assistente vai responder com os dados de cada condomínio, sempre citando a nota, a
        cláusula ou o extrato de origem.
      </EmptyState>
    </>
  );
}
