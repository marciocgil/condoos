import type { ReactNode } from "react";

import { AdminNav } from "@/components/AdminNav";
import { LogoutButton } from "@/components/LogoutButton";
import { apiGet } from "@/lib/api";
import type { Me, QueueCount } from "@/lib/types";

export default async function AdminLayout({ children }: { children: ReactNode }) {
  const [me, queue] = await Promise.all([apiGet<Me>("/me"), apiGet<QueueCount>("/queue/count")]);
  const company = me.management_companies[0];
  return (
    <div className="flex min-h-dvh">
      <aside className="flex w-64 shrink-0 flex-col bg-brand-900 p-4 text-white">
        <p className="text-xs tracking-wide text-brand-100 uppercase">CondoOS</p>
        <p className="mt-1 mb-6 text-sm font-medium">{company?.name ?? "Administradora"}</p>
        <AdminNav queueCount={queue.total} />
        <div className="mt-auto border-t border-white/10 pt-4 text-sm">
          <p className="truncate">{me.name}</p>
          <LogoutButton className="mt-1 text-brand-100 underline" />
        </div>
      </aside>
      <main className="flex-1 p-8">{children}</main>
    </div>
  );
}
