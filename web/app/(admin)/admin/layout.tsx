import { type ReactNode, Suspense } from "react";

import { AdminNav } from "@/components/AdminNav";
import { AdminHeader } from "@/components/layout/AdminHeader";
import { apiGet } from "@/lib/api";
import type { Me, QueueCount } from "@/lib/types";

export default async function AdminLayout({ children }: { children: ReactNode }) {
  const [me, queue] = await Promise.all([apiGet<Me>("/me"), apiGet<QueueCount>("/queue/count")]);
  // CondoOS staff (D77) see "CondoOS"; the management company sees its own name.
  const company =
    me.management_companies[0]?.name ??
    (me.platform_roles.length > 0 ? "CondoOS" : "Administradora");
  return (
    <div className="flex min-h-dvh">
      <Suspense fallback={<div className="w-[232px] shrink-0 border-r border-line bg-bg-2" />}>
        <AdminNav
          queueCount={queue.total}
          companyName={company}
          access={{
            permissions: [...new Set(me.condominiums.flatMap((c) => c.permissions))],
            platform: me.platform_roles.length > 0,
          }}
        />
      </Suspense>
      <div className="min-w-0 flex-1">
        <AdminHeader companyName={company} userName={me.name} />
        <main className="mx-auto max-w-[1280px] px-8 py-8">{children}</main>
      </div>
    </div>
  );
}
