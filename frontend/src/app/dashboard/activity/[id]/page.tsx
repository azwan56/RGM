"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { auth } from "@/lib/firebase";
import axios from "@/lib/apiClient";
import dynamic from "next/dynamic";
import VdotChart from "@/components/VdotChart";

const VdotTrend = dynamic(() => import("@/components/VdotTrend"), { ssr: false });

interface ActivityDetail {
  activity_id: number;
  name: string;
  start_date_local: string;
  distance_km: number;
  duration_str: string;
  elapsed_time: number;
  moving_time: number;
  avg_pace: string;
  avg_speed_kmh: number;
  max_speed_kmh: number;
  avg_heart_rate: number;
  max_heart_rate: number;
  has_heartrate: boolean;
  total_elevation_gain: number;
  avg_cadence: number;
  achievement_count: number;
  kudos_count: number;
  summary_polyline: string;
}

function StatItem({ label, value, unit }: { label: string; value: string | number; unit?: string }) {
  return (
    <div className="bg-white/5 border border-white/10 rounded-xl p-4">
      <p className="text-zinc-500 text-xs font-medium mb-1">{label}</p>
      <p className="text-white font-bold text-xl leading-tight">
        {value || "—"}
        {unit && value ? <span className="text-zinc-400 text-sm font-normal ml-1">{unit}</span> : null}
      </p>
    </div>
  );
}

function formatDate(iso: string) {
  if (!iso) return "—";
  const d = new Date(iso.replace("Z", ""));
  return d.toLocaleString("zh-CN", {
    year: "numeric", month: "long", day: "numeric",
    weekday: "long", hour: "2-digit", minute: "2-digit", hour12: false,
  });
}

export default function ActivityDetailPage() {
  const params = useParams();
  const activityId = params.id as string;
  const router = useRouter();
  const [activity, setActivity] = useState<ActivityDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [user, setUser] = useState<any>(null);
  const [vdotAnalysis, setVdotAnalysis] = useState<any | null>(null);
  const [vdotLoading, setVdotLoading] = useState(false);

  useEffect(() => {
    const unsub = auth.onAuthStateChanged(async (firebaseUser) => {
      if (!firebaseUser) { router.push("/"); return; }
      setUser(firebaseUser);
      const uid = firebaseUser.uid;
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

      try {
        // Load from backend API (not direct Firestore — faster in China)
        const res = await axios.get(`${backendUrl}/api/data/activity/${uid}/${activityId}`);
        if (!res.data?.activity) {
          setError("Activity not found. Please sync your data first.");
          setLoading(false);
          return;
        }
        const data = res.data.activity as ActivityDetail;
        setActivity(data);
        setLoading(false);

        // Lazy-load VDOT analysis (fire-and-forget)
        setVdotLoading(true);
        axios.get(`${backendUrl}/api/sync/activity/${activityId}/vdot?uid=${uid}`)
          .then(r => {
            if (r.data?.vdot_analysis) setVdotAnalysis(r.data.vdot_analysis);
          })
          .catch(() => {})
          .finally(() => setVdotLoading(false));

      } catch (e) {
        console.error(e);
        setError("Failed to load activity.");
        setLoading(false);
      }
    });
    return () => unsub();
  }, [activityId, router]);

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 border-4 border-[#FC4C02] border-t-transparent rounded-full animate-spin" />
          <p className="text-zinc-400 text-sm">Loading activity...</p>
        </div>
      </div>
    );
  }

  if (error || !activity) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center">
        <div className="text-center">
          <p className="text-zinc-400 mb-4">{error || "Activity not found."}</p>
          <button onClick={() => router.back()} className="text-[#FC4C02] hover:underline text-sm">← Back to Dashboard</button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white pt-24 px-6 pb-20 relative">
      <div className="absolute top-0 right-0 w-[35%] h-[35%] rounded-full bg-[#FC4C02]/10 blur-[140px] pointer-events-none" />

      <main className="max-w-4xl mx-auto space-y-8 relative z-10">

        {/* Back */}
        <button
          onClick={() => router.back()}
          className="flex items-center gap-2 text-zinc-400 hover:text-white transition-colors text-sm"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
          </svg>
          Back
        </button>

        {/* Header */}
        <div>
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-xl bg-[#FC4C02]/20 flex items-center justify-center">
              <svg className="w-5 h-5 text-[#FC4C02]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <div>
              <h1 className="text-3xl font-black">{activity.name}</h1>
              <p className="text-zinc-400 text-sm">{formatDate(activity.start_date_local)}</p>
            </div>
          </div>
        </div>

        {/* Primary stats */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <StatItem label="距离" value={`${activity.distance_km.toFixed(2)}`} unit="km" />
          <StatItem label="运动时长" value={activity.duration_str} />
          <StatItem label="平均配速" value={activity.avg_pace} unit="/km" />
          <StatItem label="爬升高度" value={activity.total_elevation_gain} unit="m" />
        </div>

        {/* Secondary stats */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {activity.has_heartrate && (
            <>
              <StatItem label="平均心率" value={activity.avg_heart_rate} unit="bpm" />
              <StatItem label="最大心率" value={activity.max_heart_rate} unit="bpm" />
            </>
          )}
          <StatItem label="平均速度" value={activity.avg_speed_kmh} unit="km/h" />
          <StatItem label="最大速度" value={activity.max_speed_kmh} unit="km/h" />
          {activity.avg_cadence > 0 && (
            <StatItem label="平均步频" value={activity.avg_cadence} unit="spm" />
          )}
          <StatItem label="成就数" value={activity.achievement_count || 0} />
          <StatItem label="点赞数" value={activity.kudos_count || 0} />
        </div>

        {/* VDOT Chart */}
        {(vdotLoading || vdotAnalysis) && (
          <div className="h-80">
            {vdotLoading && !vdotAnalysis ? (
              <div className="bg-white/5 border border-white/10 rounded-2xl p-6 h-full flex flex-col items-center justify-center gap-3">
                <div className="w-8 h-8 border-2 border-[#FC4C02] border-t-transparent rounded-full animate-spin" />
                <p className="text-zinc-500 text-sm">正在计算跑力指数 (VDOT)...</p>
              </div>
            ) : vdotAnalysis ? (
              <VdotChart data={vdotAnalysis} />
            ) : null}
          </div>
        )}

        {/* VDOT Trend */}
        {user && !vdotLoading && (
          <VdotTrend uid={user.uid} currentActivityId={activity.activity_id} />
        )}

        {/* Strava link */}
        <a
          href={`https://www.strava.com/activities/${activity.activity_id}`}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 px-5 py-2.5 bg-[#FC4C02] hover:bg-orange-500 text-white text-sm font-semibold rounded-xl transition-all"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
            <path d="M15.387 17.944l-2.089-4.116h-3.065L15.387 24l5.15-10.172h-3.066l-2.084 4.116z"/>
            <path d="M7.698 13.828l4.806-9.6 4.807 9.6h3.066L11.504 0 4.633 13.828h3.065z"/>
          </svg>
          在 Strava 查看
        </a>

      </main>
    </div>
  );
}
