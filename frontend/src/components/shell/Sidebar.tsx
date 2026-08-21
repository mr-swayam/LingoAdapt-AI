"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { isActiveNavPath, PRIMARY_NAV_ITEMS } from "./nav-items";

/** Desktop-only (md:+) persistent sidebar - design.md §4's
 * `Logo · Learn · Practice · Tutor · Progress · profile` spec. Hidden
 * below md: in favor of BottomNav.tsx. */
export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-slate-800 bg-slate-950 px-4 py-6 md:flex">
      <Link href="/dashboard" className="mb-8 flex items-center gap-2 px-2">
        <span className="text-lg font-semibold tracking-tight text-slate-50">LingoAdapt</span>
        <span className="text-cyan-400">AI</span>
      </Link>

      <nav className="flex flex-1 flex-col gap-1" aria-label="Primary">
        {PRIMARY_NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const active = isActiveNavPath(pathname, href);
          return (
            <Link
              key={href}
              href={href}
              aria-current={active ? "page" : undefined}
              className={
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors duration-standard " +
                (active
                  ? "bg-cyan-500/10 text-cyan-300"
                  : "text-slate-400 hover:bg-slate-900 hover:text-slate-200")
              }
            >
              <Icon className={`h-5 w-5 ${active ? "text-cyan-400" : "text-slate-400"}`} />
              {label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
