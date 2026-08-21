"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { isActiveNavPath, PRIMARY_NAV_ITEMS } from "./nav-items";

/** Mobile-only (below md:) bottom tab bar - exactly the 5 primary
 * destinations, deliberately no 6th "Continue Learning" item (approved
 * decision during V2 redesign planning: that stays a contextual card on
 * the Home/Dashboard screen, not a persistent nav slot). */
export function BottomNav() {
  const pathname = usePathname();

  return (
    <nav
      aria-label="Primary"
      className="fixed inset-x-0 bottom-0 z-20 flex border-t border-slate-800 bg-slate-950/95 backdrop-blur md:hidden"
    >
      {PRIMARY_NAV_ITEMS.map(({ href, label, icon: Icon }) => {
        const active = isActiveNavPath(pathname, href);
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={
              "flex flex-1 flex-col items-center gap-1 py-2.5 text-[11px] font-medium transition-colors duration-standard " +
              // text-slate-500 fails WCAG 4.5:1 on this dark background -
              // the exact bug Phase 12 already found and fixed elsewhere
              // (README's Phase 12 notes) - text-slate-400 clears 7-7.9:1.
              (active ? "text-cyan-300" : "text-slate-400")
            }
          >
            <Icon className={`h-5 w-5 ${active ? "text-cyan-400" : "text-slate-400"}`} />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
