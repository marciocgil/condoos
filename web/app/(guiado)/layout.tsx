import type { ReactNode } from "react";

import { Logo } from "@/components/layout/Logo";
import { LogoutButton } from "@/components/LogoutButton";

/** The guided shell of the síndico (D127): the logo, leaving, and one task per screen. No
 * tabs: each screen says what to do next. */
export default function GuidedLayout({ children }: { children: ReactNode }) {
  return (
    <div className="mx-auto min-h-dvh max-w-md px-4 pb-16">
      <header className="flex items-center justify-between pt-5 pb-2">
        <Logo />
        <LogoutButton className="text-[13px] text-fg-2 hover:text-fg" />
      </header>
      <main className="grid gap-4 pt-2">{children}</main>
    </div>
  );
}
