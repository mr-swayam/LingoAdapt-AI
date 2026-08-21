"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { isActiveNavPath, PRIMARY_NAV_ITEMS } from "./nav-items";
import { SettingsIcon } from "./icons";

/** Contextual page header - labels which primary section the learner is
 * in (most useful on mobile, where the sidebar's active-state labeling
 * isn't visible) and hosts the settings/profile link, which is
 * deliberately secondary nav (not one of the 5 primary destinations, per
 * the approved V2 redesign navigation decision). Individual pages keep
 * rendering their own in-content heading for anything more specific
 * (a lesson title, a conversation's scenario) - this bar only ever shows
 * the coarse section name. */
export function TopBar() {
  const pathname = usePathname();
  const activeItem = PRIMARY_NAV_ITEMS.find((item) => isActiveNavPath(pathname, item.href));

  return (
    <div className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-800 bg-slate-950/95 px-6 py-3 backdrop-blur">
      <span className="text-sm font-semibold text-slate-300">{activeItem?.label ?? "LingoAdapt AI"}</span>
      <Link
        href="/settings"
        aria-label="Settings and profile"
        aria-current={pathname === "/settings" ? "page" : undefined}
        className="rounded-full p-2 text-slate-400 transition-colors duration-standard hover:bg-slate-900 hover:text-slate-200"
      >
        <SettingsIcon className="h-5 w-5" />
      </Link>
    </div>
  );
}
