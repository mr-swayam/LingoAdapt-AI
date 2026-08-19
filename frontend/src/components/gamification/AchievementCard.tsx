import type { Achievement } from "@/types/progress";

export function AchievementCard({ achievement }: { achievement: Achievement }) {
  return (
    <div
      className={`flex flex-col gap-1 rounded-xl border p-4 ${
        achievement.earned ? "border-amber-700 bg-amber-950/30" : "border-slate-800 bg-slate-950"
      }`}
    >
      <div className="flex items-center gap-2">
        <span aria-hidden>{achievement.earned ? "🏆" : "🔒"}</span>
        <p
          className={`text-sm font-semibold ${
            achievement.earned ? "text-amber-300" : "text-slate-400"
          }`}
        >
          {achievement.name}
        </p>
      </div>
      <p className="text-xs text-slate-400">{achievement.description}</p>
    </div>
  );
}
