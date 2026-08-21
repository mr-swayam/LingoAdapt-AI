"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";

/** Replaces the previous hard remount (instant swap, zero animation)
 * between exercises and between the last exercise and the complete
 * screen - design.md §12 calls for exercise transitions via Framer
 * Motion. Grading/submission logic is untouched; this only wraps
 * presentation. `useReducedMotion()` collapses to an instant swap for
 * users with that preference, same pattern already established by
 * Mascot.tsx. */
export function ExerciseTransition({
  transitionKey,
  children,
}: {
  transitionKey: string;
  children: React.ReactNode;
}) {
  const reduceMotion = useReducedMotion();

  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div
        key={transitionKey}
        initial={reduceMotion ? undefined : { opacity: 0, x: 16 }}
        animate={{ opacity: 1, x: 0 }}
        exit={reduceMotion ? undefined : { opacity: 0, x: -16 }}
        transition={{ duration: 0.3, ease: "easeOut" }}
      >
        {children}
      </motion.div>
    </AnimatePresence>
  );
}
