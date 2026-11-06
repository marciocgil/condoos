import { NewCondoForm } from "@/components/condoos/NewCondoForm";
import { PageHeader } from "@/components/layout/PageHeader";

export default function NovoCondominioPage() {
  return (
    <>
      <PageHeader
        title="Novo condomínio"
        subtitle="Depois de cadastrar, envie primeiro os contratos e, em seguida, as notas, contas e o extrato."
      />
      <NewCondoForm />
    </>
  );
}
