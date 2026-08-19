import { ProgressBar } from "@/components/ui/ProgressBar";
import type { Quest } from "@/types/gamification";

export function QuestCard({ quest }: { quest: Quest }) {
  return (
    <div
      className={`flex flex-col gap-2 rounded-xl border p-4 ${
        quest.completed
          ? "border-emerald-800 bg-emerald-950/30"
          : "border-slate-800 bg-slate-950"
      }`}
    >
      <div className="flex items-center justify-between">
        <p
          className={`text-sm font-semibold ${
            quest.completed ? "text-emerald-300" : "text-slate-200"
          }`}
        >
          {quest.completed ? "✓ " : ""}
          {quest.name}
        </p>
        <span className="flex items-center gap-1 text-xs text-slate-400">
          <span aria-hidden>💎</span>
          {quest.reward_gems}
        </span>
      </div>
      <p className="text-xs text-slate-400">{quest.description}</p>
      <div className="flex items-center gap-2">
        <ProgressBar
          value={quest.progress}
          max={quest.target}
          colorClassName={quest.completed ? "bg-emerald-500" : "bg-cyan-500"}
          label={`${quest.name} progress`}
        />
        <span className="shrink-0 text-xs text-slate-400">
          {quest.progress}/{quest.target}
        </span>
      </div>
    </div>
  );
}
