"use client";

interface Zone {
  zone: number;
  name: string;
  color: string;
  pace_min: string;
  pace_max: string;
  hr_min: number;
  hr_max: number;
  description: string;
}

interface Props {
  zones: Zone[];
  vdot: number;
}

export default function TrainingZones({ zones, vdot }: Props) {
  return (
    <div className="bg-white/5 border border-white/10 rounded-3xl p-6 space-y-5 relative overflow-hidden">
      {/* Background glow */}
      <div className="absolute -bottom-10 -right-10 w-48 h-48 bg-orange-500/5 blur-3xl rounded-full pointer-events-none" />

      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-white font-bold text-lg">训练配速区间</h3>
          <p className="text-zinc-500 text-xs mt-0.5">基于 Jack Daniels VDOT {vdot} 公式</p>
        </div>
        <div className="text-right">
          <div className="text-2xl font-black text-white">{vdot}</div>
          <div className="text-[10px] text-zinc-500 uppercase font-bold tracking-wider">VDOT</div>
        </div>
      </div>

      <div className="space-y-2">
        {zones.map((zone) => (
          <div
            key={zone.zone}
            className="flex items-center gap-4 p-3 rounded-2xl bg-black/20 border border-white/5 hover:border-white/10 transition-colors group"
          >
            {/* Zone indicator */}
            <div
              className="w-1.5 self-stretch rounded-full flex-shrink-0"
              style={{ backgroundColor: zone.color }}
            />

            {/* Zone info */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-0.5">
                <span
                  className="text-xs font-bold px-1.5 py-0.5 rounded-md"
                  style={{ backgroundColor: zone.color + "33", color: zone.color }}
                >
                  Z{zone.zone}
                </span>
                <span className="text-sm font-semibold text-white truncate">{zone.name}</span>
              </div>
              <p className="text-[11px] text-zinc-500 leading-snug">{zone.description}</p>
            </div>

            {/* Pace range */}
            <div className="text-right flex-shrink-0">
              <div className="text-sm font-bold text-white">
                {zone.pace_min}–{zone.pace_max}
              </div>
              <div className="text-[10px] text-zinc-500">/km</div>
              <div className="text-[10px] text-zinc-600 mt-0.5">
                {zone.hr_min}–{zone.hr_max} bpm
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
