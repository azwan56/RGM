"use client";

interface RaceTime {
  seconds: number;
  formatted: string;
  pace: string;
}

interface RacePredictions {
  vdot: number;
  "5K": RaceTime;
  "10K": RaceTime;
  HM: RaceTime;
  FM: RaceTime;
}

interface Props {
  data: RacePredictions;
}

const RACES = [
  { key: "5K",  label: "5K",     icon: "⚡", color: "#3b82f6" },
  { key: "10K", label: "10K",    icon: "🏃", color: "#22c55e" },
  { key: "HM",  label: "半马",   icon: "🌟", color: "#f59e0b" },
  { key: "FM",  label: "全马",   icon: "🏆", color: "#ef4444" },
] as const;

export default function RacePredictor({ data }: Props) {
  return (
    <div className="bg-white/5 border border-white/10 rounded-3xl p-6 space-y-5 relative overflow-hidden">
      <div className="absolute top-0 left-0 w-40 h-40 bg-green-500/5 blur-3xl rounded-full pointer-events-none" />

      <div>
        <h3 className="text-white font-bold text-lg">比赛成绩预测</h3>
        <p className="text-zinc-500 text-xs mt-0.5">
          基于 VDOT {data.vdot} — Daniels Running Formula
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3">
        {RACES.map(({ key, label, icon, color }) => {
          const race = data[key];
          return (
            <div
              key={key}
              className="bg-black/20 border border-white/5 rounded-2xl p-4 hover:border-white/10 transition-all group"
            >
              <div className="flex items-center gap-2 mb-3">
                <span className="text-base">{icon}</span>
                <span
                  className="text-xs font-bold px-2 py-0.5 rounded-md"
                  style={{ backgroundColor: color + "30", color }}
                >
                  {label}
                </span>
              </div>

              {/* Time */}
              <div className="text-2xl font-black text-white leading-none mb-1">
                {race.formatted}
              </div>

              {/* Pace */}
              <div className="text-xs text-zinc-500">
                均速 {race.pace}<span className="text-zinc-600">/km</span>
              </div>
            </div>
          );
        })}
      </div>

      <p className="text-[10px] text-zinc-600 text-center">
        预测值基于理想状态，实际成绩因训练、天气、赛道等因素而异
      </p>
    </div>
  );
}
