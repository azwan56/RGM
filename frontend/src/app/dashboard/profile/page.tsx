"use client";

import { useEffect, useState } from "react";
import Navbar from "@/components/Navbar";
import { supabase } from "@/lib/supabase";
import apiClient from "@/lib/apiClient";
import { User, Target, Save, Heart, Shield, Award, Plus, Trash2, Zap, RefreshCw, Flame } from "lucide-react";

export interface RacePlan {
  id?: string;
  name: string;
  race_type: string;
  race_date: string;
  target_time: string;
  days_left?: number;
  priority?: number | string;
}

import GarminConnectModal from "@/components/GarminConnectModal";

export default function ProfilePage() {
  const [user, setUser] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [importingGarmin, setImportingGarmin] = useState(false);
  const [garminModalOpen, setGarminModalOpen] = useState(false);
  const [modalBrand, setModalBrand] = useState<"garmin" | "coros">("garmin");
  const [garminConnected, setGarminConnected] = useState(false);
  const [garminEmail, setGarminEmail] = useState("");
  const [garminDomain, setGarminDomain] = useState("garmin.cn");
  const [unbinding, setUnbinding] = useState(false);

  const [corosConnected, setCorosConnected] = useState(false);
  const [corosAccount, setCorosAccount] = useState("");
  const [corosDomain, setCorosDomain] = useState("teamcnapi.coros.com");
  const [unbindingCoros, setUnbindingCoros] = useState(false);

  const [displayName, setDisplayName] = useState("");
  const [avatarUrl, setAvatarUrl] = useState("");
  const [uploadingAvatar, setUploadingAvatar] = useState(false);
  const [gender, setGender] = useState("male");
  const [heightCm, setHeightCm] = useState<number | "">(175);
  const [weightKg, setWeightKg] = useState<number | "">(65);
  const [yearsRunning, setYearsRunning] = useState<number | "">(3);
  const [maxHr, setMaxHr] = useState<number | "">(190);
  const [restHr, setRestHr] = useState<number | "">(56);

  // PB (HH:MM:SS or MM:SS)
  const [marathonPb, setMarathonPb] = useState("3:09:30");
  const [halfPb, setHalfPb] = useState("1:30:57");
  const [tenKPb, setTenKPb] = useState("40:26");
  const [fiveKPb, setFiveKPb] = useState("19:24");

  // Goals
  const [targetDistance, setTargetDistance] = useState<number>(200);
  const [weeklyTarget, setWeeklyTarget] = useState<number>(50);
  const [savingWeekly, setSavingWeekly] = useState(false);
  const [monthlyTargets, setMonthlyTargets] = useState<number[]>([
    200, 200, 200, 200, 200, 200, 200, 250, 300, 350, 400, 400,
  ]);
  const [goalMode, setGoalMode] = useState<"uniform" | "custom">("uniform");

  function handleGoalModeChange(mode: "uniform" | "custom") {
    setGoalMode(mode);
    if (mode === "uniform") {
      setMonthlyTargets(Array(12).fill(targetDistance));
    }
  }

  function handleSliderChange(val: number) {
    if (goalMode === "custom") return;
    setTargetDistance(val);
    setMonthlyTargets(Array(12).fill(val));
  }

  function handleSyncUniformToAll() {
    setMonthlyTargets(Array(12).fill(targetDistance));
  }

  // Race Plans
  const [races, setRaces] = useState<RacePlan[]>([
    {
      id: "race_1",
      name: "Chiang Dao 160",
      race_type: "越野跑 100英里",
      race_date: "2026-12-04",
      target_time: "40:00:00",
      days_left: 108,
    },
    {
      id: "race_2",
      name: "武功山",
      race_type: "越野跑 50K",
      race_date: "2026-09-12",
      target_time: "8:00:00",
      days_left: 25,
    },
  ]);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      const u = data?.session?.user;
      if (u) {
        setUser(u);
        loadProfile(u.id);
      }
    });
  }, []);

  async function loadProfile(uid: string) {
    try {
      const res = await apiClient.get(`/api/profile/${uid}`);
      const { profile, goal, races: userRaces } = res.data;
      if (profile) {
        setDisplayName(profile.display_name || "");
        setAvatarUrl(profile.avatar_url || "");
        setGender(profile.gender || "male");
        setGarminConnected(Boolean(profile.garmin_connected));
        setGarminEmail(profile.garmin_email || "");
        setGarminDomain(profile.garmin_domain || "garmin.cn");
        setCorosConnected(Boolean(profile.coros_connected));
        setCorosAccount(profile.coros_account || "");
        setCorosDomain(profile.coros_domain || "teamcnapi.coros.com");
        if (profile.height_cm) setHeightCm(profile.height_cm);
        if (profile.weight_kg) setWeightKg(profile.weight_kg);
        if (profile.years_running) setYearsRunning(profile.years_running);
        if (profile.max_heart_rate) setMaxHr(profile.max_heart_rate);
        if (profile.resting_heart_rate) setRestHr(profile.resting_heart_rate);
        if (profile.marathon_pb) setMarathonPb(secsToTime(profile.marathon_pb));
        if (profile.half_pb) setHalfPb(secsToTime(profile.half_pb));
        if (profile.ten_k_pb) setTenKPb(secsToTime(profile.ten_k_pb));
        if (profile.five_k_pb) setFiveKPb(secsToTime(profile.five_k_pb));
      }
      if (goal) {
        setTargetDistance(goal.target_distance || 200);
        if (goal.weekly_target) {
          setWeeklyTarget(Number(goal.weekly_target));
        } else {
          setWeeklyTarget(Math.max(10, Math.round((goal.target_distance || 200) / 4)));
        }
        if (goal.monthly_targets && Array.isArray(goal.monthly_targets)) {
          setMonthlyTargets(goal.monthly_targets);
          const first = goal.monthly_targets[0];
          const allEqual = goal.monthly_targets.every((v: number) => v === first);
          setGoalMode(allEqual ? "uniform" : "custom");
        } else {
          setMonthlyTargets(Array(12).fill(goal.target_distance || 200));
          setGoalMode("uniform");
        }
      }
      if (userRaces && Array.isArray(userRaces) && userRaces.length > 0) {
        setRaces(userRaces);
      }
    } catch (e) {
      console.error("Load profile failed:", e);
    } finally {
      setLoading(false);
    }
  }

  function compressImageToBlob(file: File, maxDim = 800, quality = 0.85): Promise<Blob> {
    return new Promise((resolve) => {
      if (file.type === "image/svg+xml" || file.type === "image/gif") {
        return resolve(file);
      }
      const reader = new FileReader();
      reader.onload = (readerEvent) => {
        const img = new Image();
        img.onload = () => {
          let { width, height } = img;
          if (width > maxDim || height > maxDim) {
            if (width > height) {
              height = Math.round((height * maxDim) / width);
              width = maxDim;
            } else {
              width = Math.round((width * maxDim) / height);
              height = maxDim;
            }
          }
          const canvas = document.createElement("canvas");
          canvas.width = width;
          canvas.height = height;
          const ctx = canvas.getContext("2d");
          if (!ctx) return resolve(file);
          ctx.drawImage(img, 0, 0, width, height);
          canvas.toBlob(
            (blob) => {
              if (blob && blob.size < file.size) {
                resolve(blob);
              } else {
                resolve(file);
              }
            },
            "image/jpeg",
            quality
          );
        };
        img.onerror = () => resolve(file);
        img.src = readerEvent.target?.result as string;
      };
      reader.onerror = () => resolve(file);
      reader.readAsDataURL(file);
    });
  }

  async function handleAvatarUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !user?.id) return;
    setUploadingAvatar(true);
    try {
      const uploadBlob = await compressImageToBlob(file);
      const formData = new FormData();
      formData.append("file", uploadBlob, "avatar.jpg");
      const res = await apiClient.post(`/api/profile/${encodeURIComponent(user.id)}/avatar`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      if (res.data?.avatar_url) {
        setAvatarUrl(res.data.avatar_url);
        alert("✅ 头像上传成功并已实时生效！");
      }
    } catch (err: any) {
      alert("头像上传失败: " + (err.response?.data?.detail || err.message));
    } finally {
      setUploadingAvatar(false);
      e.target.value = "";
    }
  }

  async function handleUnbindGarmin() {
    if (!confirm("确定解除佳明账号绑定吗？解除后将停止自动同步运动数据。")) return;
    setUnbinding(true);
    try {
      await apiClient.post("/api/auth/garmin/unbind", { uid: user?.id });
      alert("佳明账号已解除绑定");
      if (user?.id) loadProfile(user.id);
    } catch (e: any) {
      alert("解除失败: " + (e?.message || e));
    } finally {
      setUnbinding(false);
    }
  }

  async function handleUnbindCoros() {
    if (!confirm("确定解除高驰账号绑定吗？解除后将停止自动同步运动数据。")) return;
    setUnbindingCoros(true);
    try {
      await apiClient.post("/api/auth/coros/unbind", { uid: user?.id });
      alert("高驰账号已解除绑定");
      if (user?.id) loadProfile(user.id);
    } catch (e: any) {
      alert("解除失败: " + (e?.message || e));
    } finally {
      setUnbindingCoros(false);
    }
  }

  function addRace() {
    const newRace: RacePlan = {
      id: `race_${Date.now()}`,
      name: "",
      race_type: "全马 (42.195K)",
      race_date: new Date().toISOString().slice(0, 10),
      target_time: "3:30:00",
      days_left: 60,
      priority: 1,
    };
    setRaces([...races, newRace]);
  }

  function updateRace(index: number, field: keyof RacePlan, val: any) {
    const updated = [...races];
    updated[index] = { ...updated[index], [field]: val };
    if (field === "race_date") {
      try {
        const target = new Date(val);
        const today = new Date();
        const diff = Math.ceil((target.getTime() - today.getTime()) / (1000 * 3600 * 24));
        updated[index].days_left = Math.max(0, diff);
      } catch (e) {}
    }
    setRaces(updated);
  }

  function removeRace(index: number) {
    setRaces(races.filter((_, idx) => idx !== index));
  }

  async function handleImportGarminPb() {
    if (!user) return;
    setImportingGarmin(true);
    try {
      const res = await apiClient.post(`/api/profile/${user.id}/import-garmin-pb`);
      if (res.data?.formatted) {
        const f = res.data.formatted;
        if (f.marathon_pb) setMarathonPb(f.marathon_pb);
        if (f.half_pb) setHalfPb(f.half_pb);
        if (f.ten_k_pb) setTenKPb(f.ten_k_pb);
        if (f.five_k_pb) setFiveKPb(f.five_k_pb);
        alert("✅ 成功从 Garmin 官方同步个人最佳成绩 (PB)！");
      }
    } catch (e: any) {
      const errMsg = e.response?.data?.detail || e.message || "导入失败，请检查 Garmin 账号绑定";
      alert("Garmin 导入提示: " + errMsg);
    } finally {
      setImportingGarmin(false);
    }
  }

  async function handleSaveWeeklyOnly() {
    if (!user?.id) return;
    setSavingWeekly(true);
    try {
      await apiClient.put(`/api/profile/${encodeURIComponent(user.id)}/goal`, {
        weekly_target: weeklyTarget,
      });
      alert(`✅ 常规周跑量目标已单独保存为 ${weeklyTarget} km/周！`);
    } catch (e: any) {
      alert("保存失败: " + (e?.message || e));
    } finally {
      setSavingWeekly(false);
    }
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!user) return;

    setSaving(true);
    try {
      // 1. Update Profile
      await apiClient.put(`/api/profile/${user.id}`, {
        display_name: displayName.trim() || undefined,
        avatar_url: avatarUrl || undefined,
        gender,
        height_cm: heightCm || null,
        weight_kg: weightKg || null,
        years_running: yearsRunning || null,
        max_heart_rate: maxHr || null,
        resting_heart_rate: restHr || null,
        marathon_pb: timeToSecs(marathonPb),
        half_pb: timeToSecs(halfPb),
        ten_k_pb: timeToSecs(tenKPb),
        five_k_pb: timeToSecs(fiveKPb),
      });

      // 2. Update Goal
      await apiClient.put(`/api/profile/${user.id}/goal`, {
        target_distance: targetDistance,
        weekly_target: weeklyTarget,
        monthly_targets: monthlyTargets,
      });

      // 3. Save Races
      for (const r of races) {
        if (r.name.trim()) {
          await apiClient.post(`/api/profile/${user.id}/races`, r);
        }
      }

      alert("🎉 个人资料、比赛计划与跑量目标保存成功！");
    } catch (e: any) {
      alert("保存失败: " + (e?.message || e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#070708] text-white">
      <Navbar />

      <main className="max-w-4xl mx-auto px-4 sm:px-6 py-8">
        <div className="mb-8">
          <h1 className="text-2xl sm:text-3xl font-black tracking-tight">跑者档案、比赛计划与目标</h1>
          <p className="text-xs sm:text-sm text-zinc-400 mt-1">
            完善生理指标、赛事周期倒计时与各距离 PB，驱动 Renato Canova AI 精准配速生成
          </p>
        </div>

        <form onSubmit={handleSave} className="space-y-8">
          {/* ── CARD 0: 运动手表数据直连 (Garmin & COROS) ── */}
          <div className="bg-[#121215] border border-white/[0.08] rounded-3xl p-6 sm:p-8 shadow-2xl space-y-6">
            <h2 className="text-lg font-bold text-white tracking-wide">运动手表数据直连</h2>

            {/* Garmin Row */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 rounded-2xl bg-white/[0.02] border border-white/5">
              <div className="flex items-start sm:items-center gap-3">
                <div className="w-10 h-10 rounded-2xl bg-[#0A84FF]/10 border border-[#0A84FF]/30 flex items-center justify-center text-[#0A84FF] shrink-0 font-bold text-xs">
                  佳明
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-bold text-white">Garmin (佳明) 手表</h3>
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full font-semibold border ${
                        garminConnected
                          ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                          : "bg-zinc-800 text-zinc-400 border-white/5"
                      }`}
                    >
                      {garminConnected ? "已连接 ✓" : "未连接"}
                    </span>
                  </div>
                  <p className="text-xs text-zinc-400 mt-1">
                    {garminConnected
                      ? `已绑定：${garminEmail} (${garminDomain}) · 自动同步跑步记录与生理健康数据`
                      : "直连官方服务器，自动同步跑步记录、心率、夜间 HRV 与睡眠体能"}
                  </p>
                </div>
              </div>

              <div>
                {garminConnected ? (
                  <button
                    type="button"
                    onClick={handleUnbindGarmin}
                    disabled={unbinding}
                    className="px-4 py-2 rounded-xl text-xs font-semibold bg-white/5 border border-white/10 text-rose-400 hover:bg-rose-500/10 transition active:scale-95"
                  >
                    {unbinding ? "正在解绑..." : "解除佳明绑定"}
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => { setModalBrand("garmin"); setGarminModalOpen(true); }}
                    className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-bold bg-[#0A84FF] hover:bg-blue-600 text-white transition active:scale-95 shadow-lg shadow-blue-500/20"
                  >
                    <Zap className="w-4 h-4" />
                    绑定佳明账号
                  </button>
                )}
              </div>
            </div>

            {/* COROS Row */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 rounded-2xl bg-white/[0.02] border border-white/5">
              <div className="flex items-start sm:items-center gap-3">
                <div className="w-10 h-10 rounded-2xl bg-[#FC4C02]/10 border border-[#FC4C02]/30 flex items-center justify-center text-[#FC4C02] shrink-0 font-bold text-xs">
                  高驰
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-bold text-white">COROS (高驰) 手表</h3>
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full font-semibold border ${
                        corosConnected
                          ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                          : "bg-zinc-800 text-zinc-400 border-white/5"
                      }`}
                    >
                      {corosConnected ? "已连接 ✓" : "未连接"}
                    </span>
                  </div>
                  <p className="text-xs text-zinc-400 mt-1">
                    {corosConnected
                      ? `已绑定：${corosAccount} (${corosDomain}) · 自动同步跑步记录与训练负荷`
                      : "直连高驰 Training Hub，自动同步跑步记录、心率区间与训练负荷"}
                  </p>
                </div>
              </div>

              <div>
                {corosConnected ? (
                  <button
                    type="button"
                    onClick={handleUnbindCoros}
                    disabled={unbindingCoros}
                    className="px-4 py-2 rounded-xl text-xs font-semibold bg-white/5 border border-white/10 text-rose-400 hover:bg-rose-500/10 transition active:scale-95"
                  >
                    {unbindingCoros ? "正在解绑..." : "解除高驰绑定"}
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => { setModalBrand("coros"); setGarminModalOpen(true); }}
                    className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-bold bg-[#FC4C02] hover:bg-orange-600 text-white transition active:scale-95 shadow-lg shadow-[#FC4C02]/20"
                  >
                    <Zap className="w-4 h-4" />
                    绑定高驰账号
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* ── CARD 0.5: 跑者个人形象与昵称 ── */}
          <div className="bg-[#121215] border border-white/[0.08] rounded-3xl p-6 sm:p-8 shadow-2xl space-y-6">
            <div className="flex items-center gap-2">
              <User className="w-5 h-5 text-amber-500" />
              <h2 className="text-lg font-bold text-white tracking-wide">跑者基本资料与形象</h2>
            </div>

            <div className="flex flex-col sm:flex-row items-center gap-6">
              <div className="relative group shrink-0">
                <img
                  src={avatarUrl || "https://mmbiz.qpic.cn/mmbiz/icTdbqWNOwNRna42FI242Lcia07jQodd2FJGIYQfG0LAJGFxM4FbnQP6yfMxBgJ0F3YRqJCJ1aPAK2dQagdusBZg/0"}
                  alt="跑者头像"
                  className="w-24 h-24 rounded-full object-cover border-2 border-white/10 shadow-lg group-hover:border-[#FC4C02] transition"
                />
                <label className="absolute inset-0 bg-black/60 rounded-full flex flex-col items-center justify-center text-white opacity-0 group-hover:opacity-100 cursor-pointer transition">
                  <span className="text-[11px] font-bold">更换头像</span>
                  <input
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={handleAvatarUpload}
                  />
                </label>
              </div>

              <div className="flex-1 w-full space-y-3">
                <div>
                  <label className="text-xs text-zinc-400 block mb-1.5 font-semibold">跑者昵称 (Display Name)</label>
                  <input
                    type="text"
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    placeholder="例如: Alex Wan / 珍珍"
                    className="w-full bg-[#18181c] border border-white/10 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-[#FC4C02]"
                  />
                  <p className="text-[11px] text-zinc-500 mt-1">
                    该昵称将展示在跑团花名册、大盘排行榜与 Renato Canova 科学训练档案中
                  </p>
                </div>

                <div className="flex items-center gap-3">
                  <label className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-white/5 border border-white/10 text-zinc-300 hover:bg-white/10 cursor-pointer transition">
                    <span>📷 上传本地图片替换头像</span>
                    <input
                      type="file"
                      accept="image/*"
                      className="hidden"
                      onChange={handleAvatarUpload}
                    />
                  </label>
                  {uploadingAvatar && <span className="text-xs text-[#FC4C02] animate-pulse">正在上传头像...</span>}
                </div>
              </div>
            </div>
          </div>

          {/* ── CARD 1: 比赛计划 (Race Plans) ── */}
          <div className="bg-[#121215] border border-white/[0.08] rounded-3xl p-6 sm:p-8 shadow-2xl space-y-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-lg">🏁</span>
                <h2 className="text-lg font-bold text-white tracking-wide">比赛计划</h2>
              </div>
              <button
                type="button"
                onClick={addRace}
                className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-bold bg-[#FC4C02] text-white hover:bg-[#ff5d1a] transition active:scale-95 shadow-lg shadow-[#FC4C02]/20"
              >
                <Plus className="w-3.5 h-3.5" />
                添加比赛
              </button>
            </div>

            <div className="space-y-4">
              {races.map((race, idx) => (
                <div
                  key={race.id || idx}
                  className="bg-[#18181c] border border-white/5 rounded-2xl p-5 space-y-4 relative"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-base">{idx === 0 ? "🔥" : "⛰️"}</span>
                      <span className="text-sm font-bold text-white">比赛 {idx + 1}</span>
                      <span className="bg-[#24242c] text-zinc-300 text-xs px-2.5 py-0.5 rounded-full border border-white/5 font-semibold">
                        {race.days_left !== undefined ? `${race.days_left} 天` : "—"}
                        {race.days_left !== undefined && race.days_left < 30 ? " 冲刺" : ""}
                      </span>
                    </div>

                    <button
                      type="button"
                      onClick={() => removeRace(idx)}
                      className="text-zinc-500 hover:text-rose-400 transition p-1"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="text-xs text-zinc-400 block mb-1.5">比赛名称</label>
                      <input
                        type="text"
                        value={race.name}
                        onChange={(e) => updateRace(idx, "name", e.target.value)}
                        placeholder="例如: Chiang Dao 160 / 上马"
                        className="w-full bg-[#202026] border border-white/10 rounded-xl px-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-[#FC4C02]"
                      />
                    </div>

                    <div>
                      <label className="text-xs text-zinc-400 block mb-1.5">比赛类型</label>
                      <select
                        value={race.race_type}
                        onChange={(e) => updateRace(idx, "race_type", e.target.value)}
                        className="w-full bg-[#202026] border border-white/10 rounded-xl px-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-[#FC4C02]"
                      >
                        <option value="越野跑 100英里">越野跑 100英里</option>
                        <option value="越野跑 100K">越野跑 100K</option>
                        <option value="越野跑 50K">越野跑 50K</option>
                        <option value="全马 (42.195K)">全马 (42.195K)</option>
                        <option value="半马 (21.0975K)">半马 (21.0975K)</option>
                        <option value="10公里">10公里</option>
                        <option value="5公里">5公里</option>
                      </select>
                    </div>

                    <div>
                      <label className="text-xs text-zinc-400 block mb-1.5">比赛日期</label>
                      <input
                        type="date"
                        value={race.race_date}
                        onChange={(e) => updateRace(idx, "race_date", e.target.value)}
                        className="w-full bg-[#202026] border border-white/10 rounded-xl px-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-[#FC4C02]"
                      />
                    </div>

                    <div>
                      <label className="text-xs text-zinc-400 block mb-1.5">目标成绩 (HH:MM:SS)</label>
                      <input
                        type="text"
                        value={race.target_time}
                        onChange={(e) => updateRace(idx, "target_time", e.target.value)}
                        placeholder="例如 3:30:00 或 40:00:00"
                        className="w-full bg-[#202026] border border-white/10 rounded-xl px-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-[#FC4C02]"
                      />
                    </div>

                    <div>
                      <label className="text-xs text-zinc-400 block mb-1.5">赛事定位分级 (Canova A/B/C)</label>
                      <select
                        value={race.priority || 1}
                        onChange={(e) => updateRace(idx, "priority", Number(e.target.value))}
                        className="w-full bg-[#202026] border border-white/10 rounded-xl px-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-[#FC4C02]"
                      >
                        <option value={1}>A 标核心目标 (Goal Race / 全力突破)</option>
                        <option value={2}>B 标以赛代练 (Tune-up Test / 门槛验证)</option>
                        <option value={3}>C 标模拟拉练 (Training Run / 基础长跑)</option>
                      </select>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* ── CARD 2: 个人最佳成绩 (PB) - 从 Garmin 导入 ── */}
          <div className="bg-[#121215] border border-white/[0.08] rounded-3xl p-6 sm:p-8 shadow-2xl space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-2">
                  <Award className="w-5 h-5 text-[#FC4C02]" />
                  <h2 className="text-lg font-bold text-white tracking-wide">个人最佳成绩 (PB)</h2>
                </div>
                <p className="text-xs text-zinc-400 mt-1">
                  格式: H:MM:SS 或 MM:SS · 例如 3:45:30 或 45:10 · 可手动修改导入值
                </p>
              </div>

              {/* Import from Garmin Button (Replacing Strava) */}
              <button
                type="button"
                onClick={handleImportGarminPb}
                disabled={importingGarmin}
                className="flex items-center justify-center gap-2 px-4 py-2 rounded-xl text-xs font-bold bg-[#FC4C02] hover:bg-[#ff5d1a] transition active:scale-95 text-white shadow-lg shadow-[#FC4C02]/25"
              >
                <Zap className={`w-3.5 h-3.5 ${importingGarmin ? "animate-spin" : ""}`} />
                {importingGarmin ? "正在同步 Garmin PR..." : "从 Garmin 导入"}
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <label className="text-xs text-zinc-400 block mb-1.5">全马 PB (时:分:秒)</label>
                <input
                  type="text"
                  value={marathonPb}
                  onChange={(e) => setMarathonPb(e.target.value)}
                  placeholder="3:09:29"
                  className="w-full bg-[#18181c] border border-white/10 rounded-xl px-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-[#FC4C02]"
                />
              </div>

              <div>
                <label className="text-xs text-zinc-400 block mb-1.5">半马 PB (时:分:秒)</label>
                <input
                  type="text"
                  value={halfPb}
                  onChange={(e) => setHalfPb(e.target.value)}
                  placeholder="1:25:00"
                  className="w-full bg-[#18181c] border border-white/10 rounded-xl px-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-[#FC4C02]"
                />
              </div>

              <div>
                <label className="text-xs text-zinc-400 block mb-1.5">10公里 PB (分:秒)</label>
                <input
                  type="text"
                  value={tenKPb}
                  onChange={(e) => setTenKPb(e.target.value)}
                  placeholder="40:00"
                  className="w-full bg-[#18181c] border border-white/10 rounded-xl px-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-[#FC4C02]"
                />
              </div>

              <div>
                <label className="text-xs text-zinc-400 block mb-1.5">5公里 PB (分:秒)</label>
                <input
                  type="text"
                  value={fiveKPb}
                  onChange={(e) => setFiveKPb(e.target.value)}
                  placeholder="19:00"
                  className="w-full bg-[#18181c] border border-white/10 rounded-xl px-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-[#FC4C02]"
                />
              </div>
            </div>
          </div>

          {/* ── CARD 3: 生理参数与跑者身材 ── */}
          <div className="bg-[#121215] border border-white/[0.08] rounded-3xl p-6 sm:p-8 shadow-2xl space-y-6">
            <div className="flex items-center gap-2">
              <Heart className="w-5 h-5 text-rose-500" />
              <h2 className="text-lg font-bold text-white tracking-wide">生理参数与身体指标</h2>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
              <div>
                <label className="text-xs text-zinc-400 block mb-1.5">最大心率 (Max HR bpm)</label>
                <input
                  type="number"
                  value={maxHr}
                  onChange={(e) => setMaxHr(e.target.value ? Number(e.target.value) : "")}
                  className="w-full bg-[#18181c] border border-white/10 rounded-xl px-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-[#FC4C02]"
                />
              </div>

              <div>
                <label className="text-xs text-zinc-400 block mb-1.5">静息心率 (Resting HR bpm)</label>
                <input
                  type="number"
                  value={restHr}
                  onChange={(e) => setRestHr(e.target.value ? Number(e.target.value) : "")}
                  className="w-full bg-[#18181c] border border-white/10 rounded-xl px-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-[#FC4C02]"
                />
              </div>

              <div>
                <label className="text-xs text-zinc-400 block mb-1.5">跑龄 (年)</label>
                <input
                  type="number"
                  value={yearsRunning}
                  onChange={(e) => setYearsRunning(e.target.value ? Number(e.target.value) : "")}
                  className="w-full bg-[#18181c] border border-white/10 rounded-xl px-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-[#FC4C02]"
                />
              </div>

              <div>
                <label className="text-xs text-zinc-400 block mb-1.5">身高 (cm)</label>
                <input
                  type="number"
                  value={heightCm}
                  onChange={(e) => setHeightCm(e.target.value ? Number(e.target.value) : "")}
                  className="w-full bg-[#18181c] border border-white/10 rounded-xl px-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-[#FC4C02]"
                />
              </div>

              <div>
                <label className="text-xs text-zinc-400 block mb-1.5">体重 (kg)</label>
                <input
                  type="number"
                  value={weightKg}
                  onChange={(e) => setWeightKg(e.target.value ? Number(e.target.value) : "")}
                  className="w-full bg-[#18181c] border border-white/10 rounded-xl px-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-[#FC4C02]"
                />
              </div>

              <div>
                <label className="text-xs text-zinc-400 block mb-1.5">性别</label>
                <select
                  value={gender}
                  onChange={(e) => setGender(e.target.value)}
                  className="w-full bg-[#18181c] border border-white/10 rounded-xl px-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-[#FC4C02]"
                >
                  <option value="male">男 (Male)</option>
                  <option value="female">女 (Female)</option>
                </select>
              </div>
            </div>
          </div>

          {/* ── CARD 4: 训练目标与跑量设置 ── */}
          <div className="bg-[#121215] border border-white/[0.08] rounded-3xl p-6 sm:p-8 shadow-2xl space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Target className="w-5 h-5 text-cyan-400" />
                <h2 className="text-lg font-bold text-white tracking-wide">训练目标与跑量设置</h2>
              </div>
              <span
                className={`text-xs px-3 py-1 rounded-full font-bold self-start sm:self-auto border ${
                  goalMode === "custom"
                    ? "bg-cyan-500/10 text-cyan-400 border-cyan-500/20"
                    : "bg-[#FC4C02]/10 text-[#FC4C02] border-[#FC4C02]/20"
                }`}
              >
                {goalMode === "uniform" ? `${targetDistance} km / 月` : "12 个月独立设定"}
              </span>
            </div>

            {/* ── 常规周跑量计划 (可单独设置与单独保存) ── */}
            <div className="bg-[#18181c] border border-emerald-500/20 rounded-2xl p-5 space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="text-base">🏃</span>
                  <h3 className="text-sm font-bold text-white tracking-wide">常规周跑量计划 (每周目标)</h3>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs px-3 py-1 rounded-full font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                    {weeklyTarget} km / 周
                  </span>
                  <button
                    type="button"
                    onClick={handleSaveWeeklyOnly}
                    disabled={savingWeekly}
                    className="px-3 py-1 text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg transition active:scale-95 disabled:opacity-50 shadow-md shadow-emerald-600/20"
                  >
                    {savingWeekly ? "保存中..." : "单独保存周跑量"}
                  </button>
                </div>
              </div>

              <p className="text-xs text-zinc-400">
                周跑量目标无需按 52 周单独设定，设定常规周目标后自动应用于全年的每周训练进度与负荷追踪，可完全独立于月跑量设置。
              </p>

              {/* Quick Pills */}
              <div className="flex flex-wrap gap-2">
                {[30, 40, 50, 60, 70, 80, 100].map((km) => (
                  <button
                    key={km}
                    type="button"
                    onClick={() => setWeeklyTarget(km)}
                    className={`px-3 py-1 text-xs font-semibold rounded-lg border transition ${
                      weeklyTarget === km
                        ? "bg-emerald-500 text-white border-emerald-500 shadow-md shadow-emerald-500/20"
                        : "bg-[#202026] text-zinc-300 border-white/5 hover:border-white/20"
                    }`}
                  >
                    {km}k
                  </button>
                ))}
              </div>

              {/* Weekly Slider */}
              <div className="space-y-1.5 pt-1">
                <div className="flex justify-between text-xs text-zinc-400">
                  <span>微调滑块: <strong className="text-emerald-400">{weeklyTarget} km</strong></span>
                  <span>范围: 10 ~ 160 km</span>
                </div>
                <input
                  type="range"
                  min={10}
                  max={160}
                  step={5}
                  value={weeklyTarget}
                  onChange={(e) => setWeeklyTarget(Number(e.target.value))}
                  className="w-full accent-emerald-500 bg-zinc-800 h-2 rounded-lg cursor-pointer"
                />
                <p className="text-[11px] text-zinc-500">
                  相当于月均完成约 {Math.round(weeklyTarget * 4.3)} km 跑步负荷。
                </p>
              </div>
            </div>

            {/* ── 月跑量计划 ── */}
            <div className="pt-2 border-t border-white/5">
              <h3 className="text-xs font-bold text-zinc-400 mb-3">📅 月度跑量规划</h3>
            </div>

            {/* Mode Switcher */}
            <div className="flex bg-[#18181c] p-1 rounded-2xl border border-white/5 max-w-sm">
              <button
                type="button"
                onClick={() => handleGoalModeChange("uniform")}
                className={`flex-1 py-2 text-xs font-bold rounded-xl transition ${
                  goalMode === "uniform"
                    ? "bg-[#282830] text-white shadow"
                    : "text-zinc-400 hover:text-zinc-200"
                }`}
              >
                每月统一跑量
              </button>
              <button
                type="button"
                onClick={() => handleGoalModeChange("custom")}
                className={`flex-1 py-2 text-xs font-bold rounded-xl transition ${
                  goalMode === "custom"
                    ? "bg-[#282830] text-white shadow"
                    : "text-zinc-400 hover:text-zinc-200"
                }`}
              >
                12 个月独立设定
              </button>
            </div>

            {/* General Slider */}
            <div className={`space-y-2 transition-opacity ${goalMode === "custom" ? "opacity-40" : "opacity-100"}`}>
              <div className="flex justify-between text-xs text-zinc-400">
                <span>月度通用基准: <strong className="text-white text-sm">{targetDistance} km</strong></span>
                <span>范围: 50 ~ 600 km</span>
              </div>
              <input
                type="range"
                min={50}
                max={600}
                step={10}
                disabled={goalMode === "custom"}
                value={targetDistance}
                onChange={(e) => handleSliderChange(Number(e.target.value))}
                className="w-full accent-[#FC4C02] bg-zinc-800 h-2 rounded-lg cursor-pointer disabled:cursor-not-allowed"
              />
              {goalMode === "custom" ? (
                <p className="text-[11px] text-cyan-400">
                  🔒 当前已启用 12 个月独立设定，通用滑动条已锁定以防误触变更。可在下方单独修改每月跑量。
                </p>
              ) : (
                <p className="text-[11px] text-zinc-500">
                  ✨ 拖动滑块将同时应用到全年 12 个月份。
                </p>
              )}
            </div>

            {/* 12 Months Grid when custom */}
            {goalMode === "custom" && (
              <div className="pt-4 border-t border-white/5 space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-zinc-300">各月份独立跑量 (km)</span>
                  <button
                    type="button"
                    onClick={handleSyncUniformToAll}
                    className="text-xs text-[#FC4C02] hover:underline"
                  >
                    一键统一为 {targetDistance}km
                  </button>
                </div>

                <div className="grid grid-cols-3 sm:grid-cols-6 gap-3">
                  {monthlyTargets.map((target, index) => (
                    <div key={index} className="bg-[#18181c] border border-white/5 rounded-2xl p-3 text-center">
                      <span className="text-[11px] text-zinc-500 block mb-1">{index + 1} 月</span>
                      <input
                        type="number"
                        value={target}
                        onChange={(e) => {
                          const newTargets = [...monthlyTargets];
                          newTargets[index] = Number(e.target.value);
                          setMonthlyTargets(newTargets);
                        }}
                        className="w-full bg-[#202026] text-center border border-white/10 rounded-lg py-1.5 text-sm font-bold text-white focus:outline-none focus:border-[#FC4C02]"
                      />
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Submit Button */}
          <div className="flex justify-end pt-4">
            <button
              type="submit"
              disabled={saving}
              className="flex items-center gap-2 px-8 py-3.5 rounded-2xl text-base font-bold bg-gradient-to-r from-[#FC4C02] to-[#ff7a45] text-white hover:brightness-110 transition active:scale-95 shadow-xl shadow-[#FC4C02]/25"
            >
              <Save className="w-5 h-5" />
              {saving ? "正在保存..." : "保存设置"}
            </button>
          </div>
        </form>
      </main>

      <GarminConnectModal
        open={garminModalOpen}
        onClose={() => setGarminModalOpen(false)}
        uid={user?.id}
        initialBrand={modalBrand}
        onSuccess={() => {
          if (user?.id) loadProfile(user.id);
        }}
      />
    </div>
  );
}

function secsToTime(secs?: number): string {
  if (!secs || secs <= 0) return "";
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const s = secs % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function timeToSecs(timeStr: string): number | null {
  if (!timeStr) return null;
  const parts = timeStr.split(":").map(Number);
  if (parts.some(isNaN)) return null;
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
  if (parts.length === 2) return parts[0] * 60 + parts[1];
  return null;
}
