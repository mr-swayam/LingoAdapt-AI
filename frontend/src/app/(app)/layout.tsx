import { BottomNav } from "@/components/shell/BottomNav";
import { Sidebar } from "@/components/shell/Sidebar";
import { TopBar } from "@/components/shell/TopBar";

/** Shell for every authenticated, non-admin page - a Next.js route group
 * ((app)), which is transparent to the URL (this changes no route paths:
 * /dashboard, /learn, etc. are unaffected). Each page still owns its own
 * auth gate via useRequireAuth() (unchanged) - this layout only adds
 * chrome around whatever a page renders, it doesn't own auth state.
 *
 * No nested <main> here deliberately - the root layout.tsx already
 * provides the single <main> landmark; a second one would be an
 * accessibility regression (Phase 12 fixed a missing-landmark issue,
 * this must not reintroduce a duplicate one). */
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex flex-1">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <div className="flex flex-1 flex-col pb-16 md:pb-0">{children}</div>
      </div>
      <BottomNav />
    </div>
  );
}
