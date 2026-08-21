"use client";

import { motion, useReducedMotion, type Variants } from "framer-motion";

/** An original character for this app - a small rounded "spark" creature,
 * not modeled on any existing brand mascot (no owl, no bird, no feathers).
 * Six states cover every moment the Listening Practice flow needs to
 * communicate without extra text: idle, speaking, listening, happy,
 * encouraging (never sad - incorrect answers get warmth, not a frown), and
 * thinking (loading). */
export type MascotState = "idle" | "speaking" | "listening" | "happy" | "encouraging" | "thinking";

const BODY_COLOR: Record<MascotState, string> = {
  idle: "#22d3ee", // cyan-400, matches the app's existing accent color
  speaking: "#22d3ee",
  listening: "#38bdf8", // sky-400
  happy: "#34d399", // emerald-400
  encouraging: "#fbbf24", // amber-400
  thinking: "#94a3b8", // slate-400
};

const bodyVariants: Variants = {
  idle: { scale: [1, 1.04, 1], rotate: 0, transition: { duration: 2.4, repeat: Infinity, ease: "easeInOut" } },
  speaking: { scale: [1, 1.08, 0.98, 1.05, 1], rotate: 0, transition: { duration: 0.6, repeat: Infinity, ease: "easeInOut" } },
  listening: { scale: [1, 1.02, 1], rotate: [0, -2, 2, 0], transition: { duration: 1.4, repeat: Infinity, ease: "easeInOut" } },
  happy: { scale: [1, 1.2, 0.95, 1.05, 1], rotate: [0, -4, 4, 0], transition: { duration: 0.7, ease: "easeOut" } },
  encouraging: { scale: 1, rotate: [0, -6, 0], transition: { duration: 0.8, ease: "easeInOut" } },
  thinking: { scale: [1, 1.03, 1], rotate: 0, transition: { duration: 1.2, repeat: Infinity, ease: "easeInOut" } },
};

const reducedBodyVariants: Variants = {
  idle: { scale: 1, rotate: 0 },
  speaking: { scale: 1.04, rotate: 0 },
  listening: { scale: 1, rotate: -2 },
  happy: { scale: 1.08, rotate: 0 },
  encouraging: { scale: 1, rotate: -4 },
  thinking: { scale: 1, rotate: 0 },
};

function Eyes({ state }: { state: MascotState }) {
  if (state === "thinking") {
    return (
      <>
        <path d="M36 46 q6 -6 12 0" stroke="#0f172a" strokeWidth="3" strokeLinecap="round" fill="none" />
        <path d="M52 46 q6 -6 12 0" stroke="#0f172a" strokeWidth="3" strokeLinecap="round" fill="none" />
      </>
    );
  }
  if (state === "happy") {
    return (
      <>
        <path d="M34 46 q6 -8 12 0" stroke="#0f172a" strokeWidth="3.5" strokeLinecap="round" fill="none" />
        <path d="M54 46 q6 -8 12 0" stroke="#0f172a" strokeWidth="3.5" strokeLinecap="round" fill="none" />
      </>
    );
  }
  if (state === "encouraging") {
    return (
      <>
        <circle cx="40" cy="46" r="4" fill="#0f172a" />
        <circle cx="60" cy="46" r="4" fill="#0f172a" />
        <path d="M34 38 q6 -3 12 0" stroke="#0f172a" strokeWidth="2.5" strokeLinecap="round" fill="none" />
        <path d="M54 38 q6 -3 12 0" stroke="#0f172a" strokeWidth="2.5" strokeLinecap="round" fill="none" />
      </>
    );
  }
  return (
    <>
      <circle cx="40" cy="46" r="4.5" fill="#0f172a" />
      <circle cx="60" cy="46" r="4.5" fill="#0f172a" />
    </>
  );
}

function Mouth({ state }: { state: MascotState }) {
  if (state === "speaking") return <ellipse cx="50" cy="62" rx="7" ry="6" fill="#0f172a" />;
  if (state === "happy") return <path d="M38 60 q12 12 24 0" stroke="#0f172a" strokeWidth="3.5" strokeLinecap="round" fill="none" />;
  if (state === "encouraging") return <path d="M40 64 q10 4 20 0" stroke="#0f172a" strokeWidth="3" strokeLinecap="round" fill="none" />;
  if (state === "thinking") return <circle cx="50" cy="62" r="2.5" fill="#0f172a" />;
  return <path d="M42 61 q8 5 16 0" stroke="#0f172a" strokeWidth="3" strokeLinecap="round" fill="none" />;
}

/** A little antenna that perks up while "listening" - the closest thing
 * this creature has to an ear, kept abstract on purpose. */
function Antenna({ state }: { state: MascotState }) {
  const perked = state === "listening" || state === "speaking";
  return (
    <motion.line
      x1="50"
      y1="18"
      x2="50"
      animate={{ y2: perked ? 6 : 10 }}
      transition={{ duration: 0.3 }}
      stroke="#0f172a"
      strokeWidth="2.5"
      strokeLinecap="round"
    />
  );
}

export function Mascot({ state, label }: { state: MascotState; label?: string }) {
  const reduceMotion = useReducedMotion();
  const variants = reduceMotion ? reducedBodyVariants : bodyVariants;

  return (
    <div
      role="img"
      aria-label={label ?? `Tutor mascot: ${state}`}
      className="flex h-20 w-20 items-center justify-center"
    >
      <motion.svg
        viewBox="0 0 100 100"
        width="80"
        height="80"
        initial={false}
        animate={state}
        variants={variants}
      >
        <circle cx="50" cy="7" r="3" fill={BODY_COLOR[state]} />
        <Antenna state={state} />
        <circle cx="50" cy="52" r="38" fill={BODY_COLOR[state]} />
        <circle cx="50" cy="52" r="38" fill="none" stroke="#0f172a" strokeOpacity="0.15" strokeWidth="2" />
        <Eyes state={state} />
        <Mouth state={state} />
        {state === "thinking" && (
          <motion.g
            animate={reduceMotion ? {} : { opacity: [0.3, 1, 0.3] }}
            transition={{ duration: 1.2, repeat: Infinity }}
          >
            <circle cx="72" cy="30" r="2.5" fill="#94a3b8" />
            <circle cx="80" cy="24" r="2" fill="#94a3b8" />
          </motion.g>
        )}
        {state === "happy" && (
          <motion.g
            initial={{ opacity: 0, scale: 0.5 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.4 }}
          >
            <path d="M18 20 l2 6 l-6 -2 z" fill="#fde047" />
            <path d="M82 18 l-2 6 l6 -2 z" fill="#fde047" />
          </motion.g>
        )}
      </motion.svg>
    </div>
  );
}
