import { HomeIcon, LearnIcon, PracticeIcon, ProgressIcon, TutorIcon } from "./icons";

/** The 5 primary destinations, approved explicitly during V2 redesign
 * planning. Settings/Profile are deliberately NOT here - they're secondary
 * nav, reached via the TopBar's settings icon instead, so BottomNav stays
 * at exactly 5 items on mobile. */
export const PRIMARY_NAV_ITEMS = [
  { href: "/dashboard", label: "Home", icon: HomeIcon },
  { href: "/learn", label: "Learn", icon: LearnIcon },
  { href: "/practice", label: "Practice", icon: PracticeIcon },
  { href: "/tutor", label: "AI Tutor", icon: TutorIcon },
  { href: "/progress", label: "Progress", icon: ProgressIcon },
] as const;

export function isActiveNavPath(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}
