import type { ReactNode } from "react";
import { TopBar } from "@/components/shell/TopBar";
import { LeftRail } from "@/components/shell/LeftRail";
import { RightRail } from "@/components/shell/RightRail";

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen overflow-hidden bg-[var(--color-bg)] text-[var(--color-text)]">
      <TopBar />
      <div className="grid h-[calc(100vh-56px)] grid-cols-[248px_minmax(0,1fr)_304px] max-xl:h-auto max-xl:grid-cols-1">
        <LeftRail />
        <main className="min-w-0 overflow-auto">{children}</main>
        <RightRail />
      </div>
    </div>
  );
}
