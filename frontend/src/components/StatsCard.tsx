"use client";

interface StatsCardProps {
  title: string;
  value: string | number;
  unit: string;
  icon: React.ReactNode;
  color?: string;
  subtext?: string;
}

export default function StatsCard({ title, value, unit, icon, color = "orange", subtext }: StatsCardProps) {
  const colorMap: Record<string, string> = {
    orange: "from-[#FC4C02]/20 to-orange-500/5 border-[#FC4C02]/20 text-[#FC4C02]",
    blue:   "from-blue-500/20 to-blue-600/5 border-blue-500/20 text-blue-400",
    green:  "from-green-500/20 to-green-600/5 border-green-500/20 text-green-400",
    purple: "from-purple-500/20 to-purple-600/5 border-purple-500/20 text-purple-400",
  };
  const styles = colorMap[color] || colorMap.orange;

  return (
    <div className={`bg-gradient-to-br ${styles} border backdrop-blur-sm p-5 rounded-2xl flex flex-col gap-3 relative overflow-hidden`}>
      <div className="flex items-center justify-between">
        <span className="text-zinc-400 text-sm font-medium">{title}</span>
        <div className={`w-9 h-9 rounded-xl bg-black/20 flex items-center justify-center ${styles.split(" ").pop()}`}>
          {icon}
        </div>
      </div>
      <div className="flex items-end gap-1.5">
        <span className="text-3xl font-black text-white leading-none">
          {value === 0 || value === "" ? "—" : value}
        </span>
        {value !== 0 && value !== "" && (
          <span className="text-zinc-400 text-sm mb-0.5">{unit}</span>
        )}
      </div>
      {subtext && (
        <p className="text-zinc-500 text-xs">{subtext}</p>
      )}
    </div>
  );
}
