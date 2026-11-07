import { PublicUpload } from "@/components/condoos/PublicUpload";

/** Public upload page of a delegated request (D95): no login, upload only. */
export default async function EnviarPorLinkPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  return <PublicUpload token={token} />;
}
