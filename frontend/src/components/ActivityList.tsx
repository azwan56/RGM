"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { db, auth } from "@/lib/firebase";
import { collection, query, where, orderBy, onSnapshot } from "firebase/firestore";

interface Activity {
  activity_id: number;
  name: string;
  start_date_local: string;
  distance_km: number;
  duration_str: string;
  avg_pace: string;
  avg_heart_rate: number;
  has_heartrate: boolean;
  total_elevation_gain: number;
  period_start: string;
}

function formatActivityDate(iso: string): string {
  if (!iso) return "—";
  const d = new Date(iso.replace("Z", ""));  // treat as local time
  return d.toLocaleString("zh-CN", {
    month: "short",
    day: "numeric",
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function getPeriodStart(period: string): string {
  const today = new Date();
  let start: Date;
  if (period === "weekly") {
    // Monday = day 1; Sunday = day 0 → shift to Monday
    const day = today.getDay();
    const daysFromMonday = day === 0 ? 6 : day - 1;
    start = new Date(today);
    start.setDate(today.getDate() - daysFromMonday);
    start.setHours(0, 0, 0, 0);
  } else {
    start = new Date(today.getFullYear(), today.getMonth(), 1);
  }
  // Format as ISO local (YYYY-MM-DDTHH:MM:SS) to match Strava's start_date_local
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${start.getFullYear()}-${pad(start.getMonth() + 1)}-${pad(start.getDate())}T00:00:00`;
}

export default function ActivityList({ uid, period }: { uid: string; period: "weekly" | "monthly" }) {
  const [activities, setActivities] = useState<Activity[]>([]);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    if (!uid) return;
    const periodStart = getPeriodStart(period);

    const q = query(
      collection(db, "users", uid, "activities"),
      where("start_date_local", ">=", periodStart),
      orderBy("start_date_local", "desc")
    );

    const unsub = onSnapshot(q, (snap) => {
      const docs = snap.docs.map((d) => d.data() as Activity);
      setActivities(docs);
      setLoading(false);
    }, () => setLoading(false));

    return () => unsub();
  }, [uid, period]);

  if (loading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-20 bg-white/5 rounded-2xl animate-pulse" />
        ))}
      </div>
    );
  }

  if (activities.length === 0) {
    return (
      <div className="bg-white/5 border border-white/10 rounded-2xl p-8 text-center">
        <p className="text-zinc-400 text-sm">No runs recorded this {period === "weekly" ? "week" : "month"}.</p>
        <p className="text-zinc-600 text-xs mt-1">Sync your Strava data to see activities here.</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {activities.map((act) => (
        <button
          key={act.activity_id}
          onClick={() => router.push(`/dashboard/activity/${act.activity_id}`)}
          className="w-full bg-white/5 hover:bg-white/10 border border-white/10 hover:border-[#FC4C02]/30 rounded-2xl px-5 py-4 flex items-center gap-4 transition-all group text-left"
        >
          {/* Run icon */}
          <div className="w-10 h-10 flex-shrink-0 rounded-xl bg-[#FC4C02]/15 flex items-center justify-center group-hover:bg-[#FC4C02]/25 transition-colors">
            <svg className="w-5 h-5 text-[#FC4C02]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </div>

          {/* Main info */}
          <div className="flex-1 min-w-0">
            <p className="text-white font-semibold text-sm truncate">{act.name}</p>
            <p className="text-zinc-500 text-xs mt-0.5">{formatActivityDate(act.start_date_local)}</p>
          </div>

          {/* Stats */}
          <div className="flex items-center gap-5 flex-shrink-0">
            <div className="text-right">
              <p className="text-white font-bold text-sm">{act.distance_km.toFixed(2)}</p>
              <p className="text-zinc-500 text-xs">km</p>
            </div>
            <div className="text-right">
              <p className="text-white font-bold text-sm">{act.avg_pace}</p>
              <p className="text-zinc-500 text-xs">/km</p>
            </div>
            {act.has_heartrate && act.avg_heart_rate > 0 && (
              <div className="text-right">
                <p className="text-white font-bold text-sm">{act.avg_heart_rate}</p>
                <p className="text-zinc-500 text-xs">bpm</p>
              </div>
            )}
            <div className="hidden md:block text-right">
              <p className="text-white font-bold text-sm">{act.total_elevation_gain}m</p>
              <p className="text-zinc-500 text-xs">elev</p>
            </div>

            {/* Chevron */}
            <svg className="w-4 h-4 text-zinc-600 group-hover:text-[#FC4C02] transition-colors" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
            </svg>
          </div>
        </button>
      ))}
    </div>
  );
}
