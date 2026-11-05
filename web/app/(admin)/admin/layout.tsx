import type { ReactNode } from "react";

import { AdminNav } from "@/components/AdminNav";
import { AdminHeader } from "@/components/layout/AdminHeader";
import { apiGet } from "@/lib/api";
import type { Me, QueueCount } from "@/lib/types";

export default async function AdminLayout({ children }: { children: ReactNode }) {
  const [me, queue] = await Promise.all([apiGet<Me>("/me"), apiGet<QueueCount>("/queue/count")]);
  const company = me.management_companies[0]?.name ?? "Administradora";
  return (
    <div className="flex min-h-dvh">
      <AdminNav queueCount={queue.total} companyName={company} />
      <div className="min-w-0 flex-1">
        <AdminHeader companyName={company} userName={me.name} />
        <main className="mx-auto max-w-[1280px] px-8 py-8">{children}</main>
      </div>
    </div>
  );
}
