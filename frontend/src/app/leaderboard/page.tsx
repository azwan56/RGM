"use client";

import { useEffect, useState } from "react";
import { db } from "@/lib/firebase";
import { collection, getDocs, query, orderBy } from "firebase/firestore";

interface LeaderboardEntry {
  uid: string;
  email: string;
  total_distance_km: number;
  avg_pace: string;
  avg_heart_rate: number;
  goal_completion_percentage: number;
}

export default function Leaderboard() {
  const [entries, setEntries] = useState<LeaderboardEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [sortMethod, setSortMethod] = useState<"distance" | "completion">("completion");

  useEffect(() => {
    const fetchLeaderboard = async () => {
      try {
        const orderField = sortMethod === "distance" ? "total_distance_km" : "goal_completion_percentage";
        const q = query(collection(db, "leaderboard"), orderBy(orderField, "desc"));
        const snapshot = await getDocs(q);
        const data = snapshot.docs.map(doc => doc.data() as LeaderboardEntry);
        setEntries(data);
      } catch (error) {
        console.error("Failed to fetch leaderboard", error);
      }
      setLoading(false);
    };
    fetchLeaderboard();
  }, [sortMethod]);

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white pt-32 px-6 pb-20 relative">
      <div className="absolute top-[20%] left-[-10%] w-[40%] h-[40%] rounded-full bg-blue-600/10 blur-[150px] pointer-events-none" />

      <main className="max-w-5xl mx-auto relative z-10">
        <header className="flex flex-col md:flex-row justify-between items-end mb-10 gap-6">
          <div>
            <h1 className="text-4xl md:text-5xl font-black mb-2">Leaderboard</h1>
            <p className="text-zinc-400">See how your running community is pushing the limits.</p>
          </div>
          <div className="flex bg-black/50 p-1 rounded-xl border border-white/10">
             <button 
                onClick={() => setSortMethod("completion")}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${sortMethod === "completion" ? "bg-[#FC4C02] text-white" : "text-zinc-400 hover:text-white"}`}
             >
               % of Goal
             </button>
             <button 
                onClick={() => setSortMethod("distance")}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${sortMethod === "distance" ? "bg-[#FC4C02] text-white" : "text-zinc-400 hover:text-white"}`}
             >
               Distance (km)
             </button>
          </div>
        </header>

        <div className="bg-white/5 border border-white/10 backdrop-blur-md rounded-3xl overflow-hidden shadow-2xl">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-black/40 border-b border-white/10 text-sm font-semibold text-zinc-400">
                  <th className="p-6">Rank</th>
                  <th className="p-6">Athlete</th>
                  <th className="p-6 text-right">Distance</th>
                  <th className="p-6 text-right">Avg Pace</th>
                  <th className="p-6 text-right">Goal Progress</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr><td colSpan={5} className="p-12 text-center text-zinc-500">Loading rankings...</td></tr>
                ) : entries.length === 0 ? (
                  <tr><td colSpan={5} className="p-12 text-center text-zinc-500">No data found. Sync your Strava to appear here!</td></tr>
                ) : (
                  entries.map((entry, index) => (
                    <tr key={entry.uid} className="border-b border-white/5 hover:bg-white/5 transition-colors group">
                      <td className="p-6 font-bold text-xl text-zinc-500 group-hover:text-white transition-colors">
                        #{index + 1}
                      </td>
                      <td className="p-6 font-medium">
                        {entry.email.split('@')[0]}
                      </td>
                      <td className="p-6 text-right text-[#FC4C02] font-semibold">
                        {entry.total_distance_km} km
                      </td>
                      <td className="p-6 text-right text-zinc-300">
                        {entry.avg_pace} /km <span className="block text-xs text-zinc-500">Avg HR: {entry.avg_heart_rate}</span>
                      </td>
                      <td className="p-6 text-right">
                        <div className="flex items-center justify-end gap-3">
                          <span className="font-bold">{entry.goal_completion_percentage}%</span>
                          <div className="w-24 h-2 bg-black/50 rounded-full overflow-hidden">
                            <div 
                              className="h-full bg-gradient-to-r from-orange-500 to-yellow-400 rounded-full transition-all duration-1000"
                              style={{ width: `${Math.min(entry.goal_completion_percentage, 100)}%` }}
                            />
                          </div>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </main>
    </div>
  );
}
