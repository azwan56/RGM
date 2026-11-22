"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import apiClient from "@/lib/apiClient";
import { useUiFeedback } from "@/components/ui/UiFeedbackProvider";
import { Search, Zap, UserPlus, Check, ArrowLeftRight, Trophy, MapPin, ShieldCheck, X } from "lucide-react";

interface BuddyDiscoveryViewProps {
  uid: string;
}

const AGE_BRACKETS = ["", "青年组", "中坚组", "壮年组", "大师组"];

export default function BuddyDiscoveryView({ uid }: BuddyDiscoveryViewProps) {
  const { showToast } = useUiFeedback();
  const [scope, setScope] = useState<"org" | "club" | "public">("org");
  const [ageGroup, setAgeGroup] = useState("");
  const [gender, setGender] = useState("");
  const [matchMyVdot, setMatchMyVdot] = useState(true);
  const [monthlyKmMin, setMonthlyKmMin] = useState("");
  const [city, setCity] = useState("");
  const [landmark, setLandmark] = useState("");
  const [tag, setTag] = useState("");

  const [candidates, setCandidates] = useState<any[]>([]);
  const [viewerVdot, setViewerVdot] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [pkModalData, setPkModalData] = useState<any>(null);

  const loadCandidates = useCallback(async () => {
    if (!uid) return;
    setLoading(true);
    try {
      const q = new URLSearchParams({ viewer_uid: uid, scope, limit: "40" });
      if (ageGroup) q.set("age_group", ageGroup);
      if (gender) q.set("gender", gender);
      if (matchMyVdot) q.set("match_my_vdot", "1");
      if (monthlyKmMin) q.set("monthly_km_min", monthlyKmMin);
      if (city.trim()) q.set("city", city.trim());
      if (landmark.trim()) q.set("landmark", landmark.trim());
      if (tag) q.set("tag", tag);
      const res = await apiClient.get(`/api/community/discover?${q.toString()}`);
      setCandidates(res.data?.candidates || []);
      setViewerVdot(res.data?.viewer_vdot ?? null);
    } catch (e: any) {
      showToast("检索跑友失败：" + (e?.message || "网络异常"), "error");
    } finally {
      setLoading(false);
    }
  }, [uid, scope, ageGroup, gender, matchMyVdot, monthlyKmMin, city, landmark, tag, showToast]);

  useEffect(() => {
    loadCandidates();
  }, [loadCandidates]);

  async function toggleFollow(cand: any) {
    try {
      if (cand.is_following) {
        await apiClient.delete(
          `/api/community/follow/${encodeURIComponent(cand.user_id)}?follower_id=${encodeURIComponent(uid)}`
        );
        showToast("已取消关注");
      } else {
        const res = await apiClient.post("/api/community/follow", {
          follower_id: uid,
          target_uid: cand.user_id,
        });
        showToast(res.data?.is_mutual_buddy ? `⇄ 已与【${cand.display_name}】互关成为跑搭子！` : `🤝 已关注【${cand.display_name}】`);
      }
      loadCandidates();
    } catch (e: any) {
      showToast("关注操作失败：" + (e?.message || ""), "error");
    }
  }

  async function openPk(targetUid: string) {
    try {
      const res = await apiClient.get(
        `/api/community/buddies/${encodeURIComponent(targetUid)}/pk?viewer_uid=${encodeURIComponent(uid)}`
      );
      setPkModalData(res.data);
    } catch (e: any) {
      showToast(e?.message || "互关成为跑搭子后即可开启周跑量 PK", "info");
    }
  }

  return (
    <div className="space-y-5">
      {/* Header & Scope Tabs */}
      <div className="rgm-bento-card p-6 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-black text-[var(--rgm-text)]">
              🤝 六维同频寻搭子 & 隐私脱敏互关
            </h1>
            <p className="text-xs text-[var(--rgm-text-2)] mt-1">
              严格遵循年龄组别（青年组/中坚组/壮年组/大师组）与公共常跑地标脱敏规范，跑者在「档案与隐私设定」中可随时自主开关检索权限
            </p>
          </div>
          <Link
            href="/dashboard/profile?tab=profile"
            className="px-3.5 py-2 rounded-xl bg-[var(--rgm-green-tint)] border border-emerald-500/30 text-xs font-bold text-emerald-500 flex items-center gap-1.5 shrink-0"
          >
            <ShieldCheck className="w-4 h-4" />
            管理我的可搜索隐私开关 ›
          </Link>
        </div>

        {/* 3 Search Scopes */}
        <div className="inline-flex p-1 rounded-2xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] flex-wrap gap-1">
          {[
            { key: "org" as const, label: "🏛️ 同大群跨团校友" },
            { key: "club" as const, label: "🏃 本跑团队友" },
            { key: "public" as const, label: "🌏 同城公开寻搭子" },
          ].map((s) => (
            <button
              key={s.key}
              type="button"
              onClick={() => setScope(s.key)}
              className={`px-4 py-2 rounded-xl text-xs font-bold transition cursor-pointer ${
                scope === s.key ? "bg-[#FC4C02] text-white" : "text-[var(--rgm-text-2)] hover:text-[var(--rgm-text)]"
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>

        {/* 6D Filters */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 pt-1">
          <div>
            <label className="text-[11px] font-bold text-[var(--rgm-text-2)] block mb-1">1. 年龄组别</label>
            <select
              value={ageGroup}
              onChange={(e) => setAgeGroup(e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] text-xs text-[var(--rgm-text)]"
            >
              {AGE_BRACKETS.map((b) => (
                <option key={b || "all"} value={b}>
                  {b || "不限组别"}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-[11px] font-bold text-[var(--rgm-text-2)] block mb-1">2. 性别</label>
            <select
              value={gender}
              onChange={(e) => setGender(e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] text-xs text-[var(--rgm-text)]"
            >
              <option value="">全部性别</option>
              <option value="female">仅女性跑者</option>
              <option value="male">仅男性跑者</option>
            </select>
          </div>
          <div>
            <label className="text-[11px] font-bold text-[var(--rgm-text-2)] block mb-1">3. 跑力 VDOT</label>
            <button
              type="button"
              onClick={() => setMatchMyVdot(!matchMyVdot)}
              className={`w-full px-3 py-2 rounded-xl text-xs font-bold border flex items-center justify-center gap-1 cursor-pointer ${
                matchMyVdot
                  ? "bg-[var(--rgm-brand-tint)] border-[#FC4C02] text-[#FC4C02]"
                  : "bg-[var(--rgm-card-2)] border-[var(--rgm-border)] text-[var(--rgm-text-2)]"
              }`}
            >
              <Zap className="w-3.5 h-3.5" />
              {matchMyVdot ? `与我 ±2 同频${viewerVdot ? ` (${viewerVdot})` : ""}` : "不限 VDOT 差异"}
            </button>
          </div>
          <div>
            <label className="text-[11px] font-bold text-[var(--rgm-text-2)] block mb-1">4. 近30日跑量 ≥</label>
            <select
              value={monthlyKmMin}
              onChange={(e) => setMonthlyKmMin(e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] text-xs text-[var(--rgm-text)]"
            >
              <option value="">不限月跑量</option>
              <option value="50">≥ 50 km/月</option>
              <option value="100">≥ 100 km/月</option>
              <option value="180">≥ 180 km/月</option>
              <option value="250">≥ 250 km/月</option>
            </select>
          </div>
          <div>
            <label className="text-[11px] font-bold text-[var(--rgm-text-2)] block mb-1">5. 城市 / 常跑公园地标</label>
            <input
              type="text"
              value={landmark}
              onChange={(e) => setLandmark(e.target.value)}
              placeholder="如 世纪公园 / 徐汇滨江"
              className="w-full px-3 py-2 rounded-xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] text-xs text-[var(--rgm-text)]"
            />
          </div>
          <div>
            <label className="text-[11px] font-bold text-[var(--rgm-text-2)] block mb-1">6. 跑友状态</label>
            <select
              value={tag}
              onChange={(e) => setTag(e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] text-xs text-[var(--rgm-text)]"
            >
              <option value="">全部状态</option>
              <option value="newcomer_14d">🆕 近14天新人</option>
              <option value="same_race">🎯 备战同场赛事</option>
              <option value="official_pacer">🐰 认证官兔</option>
              <option value="mentor_ready">🥋 教练/可带徒</option>
            </select>
          </div>
        </div>
      </div>

      {/* Results Grid */}
      {loading ? (
        <div className="rgm-bento-card p-10 text-center text-xs text-[var(--rgm-text-muted)]">正在按六维同频检索中...</div>
      ) : candidates.length === 0 ? (
        <div className="rgm-bento-card p-10 text-center space-y-2">
          <Search className="w-8 h-8 text-[var(--rgm-text-muted)] mx-auto" />
          <div className="text-sm font-bold text-[var(--rgm-text)]">当前条件下暂无匹配的公开跑友</div>
          <div className="text-xs text-[var(--rgm-text-2)]">可尝试放宽「与我 ±2 同频」或切换至「同大群跨团校友 / 同城公开」域</div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {candidates.map((cand) => (
            <div key={cand.user_id} className="rgm-bento-card p-5 flex flex-col justify-between gap-4">
              <div className="space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-12 h-12 rounded-2xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] overflow-hidden shrink-0 flex items-center justify-center font-black text-[var(--rgm-text)]">
                      {cand.avatar_url ? (
                        <img src={cand.avatar_url} alt={cand.display_name} className="w-full h-full object-cover" />
                      ) : (
                        String(cand.display_name || "跑").slice(0, 1)
                      )}
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className="text-sm font-black text-[var(--rgm-text)] truncate">{cand.display_name}</span>
                        {cand.is_mutual_buddy && (
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-black bg-[var(--rgm-green-tint)] text-emerald-500">
                            ⇄ 跑搭子
                          </span>
                        )}
                      </div>
                      <div className="text-[11px] text-[var(--rgm-text-2)] mt-0.5">
                        {cand.age_group} · {cand.gender === "female" ? "女" : cand.gender === "male" ? "男" : "跑者"} · {cand.city || "同城"}
                      </div>
                    </div>
                  </div>
                  <div className="px-2.5 py-1 rounded-xl bg-[var(--rgm-brand-tint)] text-[#FC4C02] text-xs font-black shrink-0 tabular-nums">
                    {cand.match_score}% 同频
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="p-2.5 rounded-xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)]">
                    <div className="text-[10px] text-[var(--rgm-text-muted)]">跑力区间</div>
                    <div className="font-bold text-[var(--rgm-text)] mt-0.5 truncate">{cand.vdot_band}</div>
                  </div>
                  <div className="p-2.5 rounded-xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)]">
                    <div className="text-[10px] text-[var(--rgm-text-muted)]">近30日手表实跑</div>
                    <div className="font-bold text-[var(--rgm-text)] mt-0.5 tabular-nums">
                      {cand.monthly_km_30d} km ({cand.monthly_runs_30d}次)
                    </div>
                  </div>
                </div>

                {(cand.running_landmarks || []).length > 0 && (
                  <div className="flex items-center gap-1.5 flex-wrap text-[11px] text-[var(--rgm-text-2)]">
                    <MapPin className="w-3.5 h-3.5 text-[#FC4C02] shrink-0" />
                    {cand.running_landmarks.map((lm: string) => (
                      <span key={lm} className="px-2 py-0.5 rounded-lg bg-[var(--rgm-card-2)] border border-[var(--rgm-border)]">
                        {lm}
                      </span>
                    ))}
                  </div>
                )}

                {(cand.club_names || []).length > 0 && (
                  <div className="text-[11px] text-[var(--rgm-text-muted)] truncate">
                    跑团：{(cand.club_names || []).join(" · ")}
                  </div>
                )}
              </div>

              <div className="flex items-center gap-2 pt-2 border-t border-[var(--rgm-divider)]">
                <button
                  type="button"
                  onClick={() => toggleFollow(cand)}
                  className={`flex-1 py-2 rounded-xl text-xs font-black flex items-center justify-center gap-1.5 cursor-pointer transition ${
                    cand.is_mutual_buddy
                      ? "bg-[var(--rgm-green-tint)] text-emerald-500 border border-emerald-500/30"
                      : cand.is_following
                      ? "bg-[var(--rgm-card-2)] text-[var(--rgm-text-2)] border border-[var(--rgm-border)]"
                      : "bg-[#FC4C02] text-white"
                  }`}
                >
                  {cand.is_mutual_buddy ? (
                    <>
                      <ArrowLeftRight className="w-3.5 h-3.5" /> 互关跑搭子
                    </>
                  ) : cand.is_following ? (
                    <>
                      <Check className="w-3.5 h-3.5" /> 已关注
                    </>
                  ) : (
                    <>
                      <UserPlus className="w-3.5 h-3.5" /> {cand.is_followed_by ? "回关成为搭子" : "关注结伴"}
                    </>
                  )}
                </button>
                {(cand.is_mutual_buddy || cand.shared_club) && (
                  <button
                    type="button"
                    onClick={() => openPk(cand.user_id)}
                    className="px-3 py-2 rounded-xl border border-[var(--rgm-border)] bg-[var(--rgm-card-2)] text-xs font-bold text-[var(--rgm-text)] hover:border-amber-500/50 cursor-pointer flex items-center gap-1"
                  >
                    <Trophy className="w-3.5 h-3.5 text-amber-500" />
                    周PK
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {pkModalData && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
          <div className="rgm-bento-card max-w-md w-full p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-black text-[var(--rgm-text)] flex items-center gap-2">
                <Trophy className="w-4 h-4 text-amber-500" /> 周跑量友好 PK
              </h3>
              <button type="button" onClick={() => setPkModalData(null)} className="cursor-pointer text-[var(--rgm-text-muted)]">
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="p-3 rounded-2xl bg-[var(--rgm-brand-tint)] text-center">
                <div className="text-xs font-bold text-[var(--rgm-text)]">{pkModalData.viewer?.display_name}</div>
                <div className="text-2xl font-black text-[#FC4C02] mt-1 tabular-nums">{pkModalData.viewer?.week_km} km</div>
              </div>
              <div className="p-3 rounded-2xl bg-[var(--rgm-card-2)] text-center">
                <div className="text-xs font-bold text-[var(--rgm-text)]">{pkModalData.buddy?.display_name}</div>
                <div className="text-2xl font-black text-[var(--rgm-text)] mt-1 tabular-nums">{pkModalData.buddy?.week_km} km</div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
