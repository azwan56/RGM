"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Navbar from "@/components/Navbar";
import { supabase } from "@/lib/supabase";
import apiClient from "@/lib/apiClient";
import { User, Target, Save, Heart, Shield, Award, Plus, Trash2, Zap, RefreshCw, Flame, Camera, CheckCircle2, Trophy, Clock, Image as ImageIcon, ExternalLink, X, Loader2, Eye, EyeOff, Lock, AlertTriangle, Check, BookOpen } from "lucide-react";

export interface RacePlan {
  id?: string;
  name: string;
  race_type: string;
  race_date: string;
  target_time: string;
  days_left?: number;
  is_past?: boolean;
  priority?: number | string;
  race_info?: Record<string, any>;
  status?: string; // "upcoming" | "completed"
  finish_time?: string;
  finish_notes?: string;
  photo_url?: string;
  photos?: string[];
  is_completed?: boolean;
  diff_seconds?: number;
  diff_str?: string;
  performance_badge?: string;
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
  const [savingNickname, setSavingNickname] = useState(false);
  const [nicknameSavedSuccess, setNicknameSavedSuccess] = useState(false);
  const [avatarUrl, setAvatarUrl] = useState("");
  const [uploadingAvatar, setUploadingAvatar] = useState(false);
  const [gender, setGender] = useState("male");
  const [heightCm, setHeightCm] = useState<number | "">(175);
  const [weightKg, setWeightKg] = useState<number | "">(65);
  const [yearsRunning, setYearsRunning] = useState<number | "">(3);
  const [maxHr, setMaxHr] = useState<number | "">(190);
  const [restHr, setRestHr] = useState<number | "">(56);
  const [dateOfBirth, setDateOfBirth] = useState("");
  const [vo2max, setVo2max] = useState<number | "">("");
  const [age, setAge] = useState<number | null>(null);
  const [syncingDeviceProfile, setSyncingDeviceProfile] = useState(false);

const ORG_PROGRAM_OPTIONS = ["中文EMBA", "台大班", "复旦-BI（挪威）", "奥林班", "港大班"];
const GOBI_EDITIONS = Array.from({ length: 21 }, (_, i) => `戈${21 - i}`);
const GOBI_GROUPS = ["A组", "B组", "C组"];
const CLOTHING_SIZES = ["XS", "S", "M", "L", "XL", "2XL", "3XL", "4XL"];

  // ── Privacy & Sensitive Identity Fields ──
  const [realName, setRealName] = useState("");
  const [idCard, setIdCard] = useState("");
  const [phone, setPhone] = useState("");

  // ── 商学院与戈友身份认证 ──
  const [program, setProgram] = useState("");
  const [classDetail, setClassDetail] = useState("");
  const [className, setClassName] = useState("");
  const [gobiType, setGobiType] = useState<"new" | "vet">("new");
  const [gobiEdition, setGobiEdition] = useState("戈21");
  const [gobiGroup, setGobiGroup] = useState("A组");

  // ── 赛事活动与装备保障 ──
  const [emergencyContact, setEmergencyContact] = useState("");
  const [clothingSize, setClothingSize] = useState("");
  const [shoeSize, setShoeSize] = useState("");
  const [healthDeclaration, setHealthDeclaration] = useState(true);

  const [showRealName, setShowRealName] = useState(false);
  const [showIdCard, setShowIdCard] = useState(false);
  const [showPhone, setShowPhone] = useState(false);
  const [showDob, setShowDob] = useState(false);

  const [showPurgeConfirmModal, setShowPurgeConfirmModal] = useState(false);
  const [purgingPrivacy, setPurgingPrivacy] = useState(false);
  const [userOrgs, setUserOrgs] = useState<any[]>([]);
  const [activeTab, setActiveTab] = useState<"profile" | "training">("profile");

  function scrollToRequiredFields() {
    setActiveTab("profile");
    setTimeout(() => {
      if (typeof document !== "undefined") {
        const el = document.getElementById("required-personal-fields");
        if (el) {
          el.scrollIntoView({ behavior: "smooth" });
        }
      }
    }, 100);
  }

  function computeAge(dobStr: string): number | null {
    if (!dobStr) return null;
    try {
      const parts = dobStr.slice(0, 10).split("-");
      if (parts.length < 3) return null;
      const y = parseInt(parts[0], 10);
      const m = parseInt(parts[1], 10) - 1;
      const d = parseInt(parts[2], 10);
      const dob = new Date(y, m, d);
      if (isNaN(dob.getTime())) return null;
      const today = new Date();
      let a = today.getFullYear() - dob.getFullYear();
      const monthDiff = today.getMonth() - dob.getMonth();
      if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < dob.getDate())) {
        a--;
      }
      return Math.max(0, a);
    } catch {
      return null;
    }
  }

  function getAgeGroup(ageVal: number | null): string {
    if (ageVal === null || ageVal === undefined) return "青年组";
    if (ageVal >= 50) return "大师组 (50+)";
    if (ageVal >= 40) return "壮年组 (40-49)";
    if (ageVal >= 30) return "中坚组 (30-39)";
    return "青年组 (<30)";
  }

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
        if (profile.real_name) setRealName(profile.real_name);
        if (profile.id_card) setIdCard(profile.id_card);
        if (profile.phone) setPhone(profile.phone);
        if (profile.program) setProgram(profile.program);
        if (profile.class_detail) setClassDetail(profile.class_detail);
        if (profile.class_name) setClassName(profile.class_name);
        if (profile.gobi_experience) {
          if (profile.gobi_experience === "新戈") {
            setGobiType("new");
          } else {
            setGobiType("vet");
            const parts = profile.gobi_experience.split(" ");
            if (parts[0]) setGobiEdition(parts[0]);
            if (parts[1]) setGobiGroup(parts[1]);
          }
        }
        if (profile.emergency_contact) setEmergencyContact(profile.emergency_contact);
        if (profile.clothing_size) setClothingSize(profile.clothing_size);
        if (profile.shoe_size) setShoeSize(profile.shoe_size);
        if (profile.health_declaration !== undefined && profile.health_declaration !== null) {
          setHealthDeclaration(Boolean(profile.health_declaration));
        }
        if (profile.height_cm) setHeightCm(profile.height_cm);
        if (profile.weight_kg) setWeightKg(profile.weight_kg);
        if (profile.date_of_birth) {
          setDateOfBirth(profile.date_of_birth);
          setAge(profile.age !== undefined && profile.age !== null ? profile.age : computeAge(profile.date_of_birth));
        }
        if (profile.vo2max !== undefined && profile.vo2max !== null) {
          setVo2max(profile.vo2max);
        }
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

      try {
        const orgRes = await apiClient.get(`/api/org/my-orgs/${uid}`);
        if (orgRes.data?.organizations) {
          setUserOrgs(orgRes.data.organizations);
        }
      } catch (orgErr) {
        console.error("Load user organizations error:", orgErr);
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
    if (!user?.id) {
      alert("无法获取当前用户ID，请刷新页面后重试");
      return;
    }
    if (!confirm("确定解除佳明账号绑定吗？解除后将停止自动同步运动数据。")) return;
    setUnbinding(true);
    try {
      const res = await apiClient.post("/api/auth/garmin/unbind", { uid: user.id });
      setGarminConnected(false);
      setGarminEmail("");
      alert(res.data?.message || "佳明账号已解除绑定");
      loadProfile(user.id);
    } catch (e: any) {
      alert("解除失败: " + (e?.response?.data?.detail || e?.message || e));
    } finally {
      setUnbinding(false);
    }
  }

  async function handleUnbindCoros() {
    if (!user?.id) {
      alert("无法获取当前用户ID，请刷新页面后重试");
      return;
    }
    if (!confirm("确定解除高驰账号绑定吗？解除后将停止自动同步运动数据。")) return;
    setUnbindingCoros(true);
    try {
      const res = await apiClient.post("/api/auth/coros/unbind", { uid: user.id });
      setCorosConnected(false);
      setCorosAccount("");
      alert(res.data?.message || "高驰账号已解除绑定");
      loadProfile(user.id);
    } catch (e: any) {
      alert("解除失败: " + (e?.response?.data?.detail || e?.message || e));
    } finally {
      setUnbindingCoros(false);
    }
  }

  const [expandedRaceInfo, setExpandedRaceInfo] = useState<Record<number, boolean>>({});

  function toggleRaceInfoExpand(index: number) {
    setExpandedRaceInfo((prev) => ({ ...prev, [index]: !prev[index] }));
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
      race_info: {},
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

  function updateRaceInfo(index: number, field: string, val: any) {
    const updated = [...races];
    const currentInfo = updated[index].race_info || {};
    if (val === "" || val === null || val === undefined) {
      const { [field]: _, ...rest } = currentInfo;
      updated[index] = { ...updated[index], race_info: rest };
    } else {
      updated[index] = { ...updated[index], race_info: { ...currentInfo, [field]: val } };
    }
    setRaces(updated);
  }

  const [searchingRaceInfo, setSearchingRaceInfo] = useState<Record<number, boolean>>({});

  async function handleAutoFetchRaceInfo(index: number) {
    const race = races[index];
    if (!race.name || !race.name.trim()) {
      alert("请先在上方输入比赛名称（例如：无锡马拉松、上海半马、崇礼168 或 武功山 50K）");
      return;
    }

    setSearchingRaceInfo((prev) => ({ ...prev, [index]: true }));
    try {
      const res = await apiClient.post("/api/profile/race-intel-lookup", {
        race_name: race.name.trim(),
        race_type: race.race_type,
      });

      if (res.data?.success && res.data?.race_info) {
        const info = res.data.race_info;
        const updated = [...races];
        updated[index] = {
          ...updated[index],
          race_info: {
            ...(updated[index].race_info || {}),
            ...info,
          },
        };
        // Auto-adapt race_type if detected as trail vs road
        if (res.data.race_category === "trail" && !updated[index].race_type?.includes("越野")) {
          const dist = info.race_distance_km ? `${info.race_distance_km}K` : "50K";
          updated[index].race_type = `越野跑 ${dist}`;
        }
        setRaces(updated);
        // Automatically expand panel so user sees and can review/edit
        setExpandedRaceInfo((prev) => ({ ...prev, [index]: true }));
        alert(`✅ ${res.data.message || "已成功获取赛事情报"}！\n已自动填充赛道特点、爬升、历史天气与参赛规模，您可以自由检查与修改。`);
      } else {
        alert(res.data?.message || "未能检索到该赛事信息，请直接在下方手动填写。");
      }
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || "检索失败";
      alert("自动检索提示: " + msg);
    } finally {
      setSearchingRaceInfo((prev) => ({ ...prev, [index]: false }));
    }
  }

  function removeRace(index: number) {
    setRaces(races.filter((_, idx) => idx !== index));
  }

  const [uploadingPhotoIdx, setUploadingPhotoIdx] = useState<number | null>(null);
  const [matchingActivityIdx, setMatchingActivityIdx] = useState<number | null>(null);
  const [previewPhotoUrl, setPreviewPhotoUrl] = useState<string | null>(null);

  async function handleMatchActivity(index: number) {
    const race = races[index];
    if (!user) return;
    if (!race.race_date) {
      alert("请先选择比赛日期");
      return;
    }
    setMatchingActivityIdx(index);
    try {
      const raceId = race.id || "temp";
      const res = await apiClient.get(`/api/profile/${user.id}/races/${raceId}/matched-activity?race_date=${race.race_date}`);
      if (res.data?.matched && res.data?.activity) {
        const act = res.data.activity;
        const updated = [...races];
        const formattedTime = act.formatted_time || "";
        let diffSec: number | undefined;
        let diffStr: string | undefined;
        let badge: string | undefined;

        try {
          const tSec = parseTimeToSec(updated[index].target_time);
          const fSec = parseTimeToSec(formattedTime);
          if (tSec && fSec) {
            diffSec = fSec - tSec;
            if (diffSec < 0) {
              diffStr = `-${formatSecToTime(Math.abs(diffSec))}`;
              badge = "超额达标 🎉";
            } else if (diffSec === 0) {
              diffStr = "精准达标";
              badge = "精准达标 🎯";
            } else {
              diffStr = `+${formatSecToTime(diffSec)}`;
              badge = "顺利完赛 🏅";
            }
          }
        } catch {}

        updated[index] = {
          ...updated[index],
          status: "completed",
          is_completed: true,
          finish_time: formattedTime,
          diff_seconds: diffSec,
          diff_str: diffStr,
          performance_badge: badge,
          finish_notes: updated[index].finish_notes || `匹配到手表记录【${act.name}】(${act.distance_km}km, 平均配速 ${act.avg_pace_str})`,
        };
        setRaces(updated);
        alert(`🎉 成功从手表记录匹配到成绩！\n记录名称: ${act.name}\n完赛用时: ${formattedTime} (${act.distance_km}km)\n已为您自动填报成绩并标记完赛。`);
      } else {
        alert(res.data?.message || "未在比赛日找到匹配的运动记录，您可以手动输入完赛用时。");
      }
    } catch (e: any) {
      alert("手表记录检索失败: " + (e?.message || e));
    } finally {
      setMatchingActivityIdx(null);
    }
  }

  async function handleUploadRacePhoto(index: number, e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !user) return;
    const race = races[index];
    setUploadingPhotoIdx(index);
    try {
      const raceId = race.id || `race_${Date.now()}`;
      if (!race.id) {
        const updated = [...races];
        updated[index].id = raceId;
        setRaces(updated);
      }
      const formData = new FormData();
      formData.append("file", file);
      const res = await apiClient.post(`/api/profile/${user.id}/races/${raceId}/photo`, formData, {
        headers: { "Content-Type": "multipart/form-data" }
      });
      if (res.data?.photo_url) {
        const updated = [...races];
        updated[index] = {
          ...updated[index],
          id: raceId,
          photo_url: res.data.photo_url,
          photos: res.data.photos || [res.data.photo_url],
        };
        setRaces(updated);
        alert("📸 完赛照片上传成功！");
      }
    } catch (err: any) {
      alert("上传照片失败: " + (err?.message || err));
    } finally {
      setUploadingPhotoIdx(null);
      e.target.value = "";
    }
  }

  async function handleDeleteRacePhoto(index: number, photoUrl: string) {
    if (!confirm("确定要删除这张照片吗？")) return;
    const race = races[index];
    if (!user || !race.id) {
      const updated = [...races];
      const photos = (updated[index].photos || []).filter(p => p !== photoUrl);
      updated[index].photos = photos;
      updated[index].photo_url = photos[0] || "";
      setRaces(updated);
      return;
    }
    try {
      const res = await apiClient.delete(`/api/profile/${user.id}/races/${race.id}/photo`, {
        data: { photo_url: photoUrl }
      });
      const updated = [...races];
      updated[index].photos = res.data?.photos || [];
      updated[index].photo_url = updated[index].photos?.[0] || "";
      setRaces(updated);
    } catch (e: any) {
      alert("删除照片失败: " + (e?.message || e));
    }
  }

  function parseTimeToSec(tStr: string): number | null {
    if (!tStr) return null;
    const parts = tStr.trim().split(":");
    try {
      if (parts.length === 3) return parseInt(parts[0])*3600 + parseInt(parts[1])*60 + parseInt(parts[2]);
      if (parts.length === 2) return parseInt(parts[0])*60 + parseInt(parts[1]);
    } catch {}
    return null;
  }

  function formatSecToTime(sec: number): string {
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = sec % 60;
    if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
    return `${m}:${String(s).padStart(2, "0")}`;
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

  async function handleSyncDeviceProfile() {
    if (!user) return;
    setSyncingDeviceProfile(true);
    try {
      const res = await apiClient.post(`/api/profile/${user.id}/sync-device-profile`);
      if (res.data?.success && res.data?.profile) {
        const p = res.data.profile;
        if (p.date_of_birth) {
          setDateOfBirth(p.date_of_birth);
          setAge(p.age !== undefined && p.age !== null ? p.age : computeAge(p.date_of_birth));
        }
        if (p.gender) setGender(p.gender);
        if (p.height_cm) setHeightCm(p.height_cm);
        if (p.weight_kg) setWeightKg(p.weight_kg);
        if (p.vo2max !== undefined && p.vo2max !== null) setVo2max(p.vo2max);
        if (p.max_heart_rate) setMaxHr(p.max_heart_rate);
        if (p.resting_heart_rate) setRestHr(p.resting_heart_rate);
        if (p.display_name && (!displayName || displayName === "跑者" || displayName === "微信跑者")) {
          setDisplayName(p.display_name);
        }
        if (p.avatar_url && !avatarUrl) {
          setAvatarUrl(p.avatar_url);
        }
        alert(res.data.message || "✅ 成功从手表同步身体指标！");
      } else {
        alert(res.data?.message || "未能获取到手表数据");
      }
    } catch (e: any) {
      const errMsg = e.response?.data?.detail || e.message || "同步失败，请检查手表账号连接";
      alert("手表同步提示: " + errMsg);
    } finally {
      setSyncingDeviceProfile(false);
    }
  }

  const [estimatingVo2, setEstimatingVo2] = useState(false);

  async function handleEstimateVo2max() {
    if (!user) return;
    setEstimatingVo2(true);
    try {
      const res = await apiClient.post(`/api/profile/${user.id}/estimate-vo2max`, {
        five_k_pb: fiveKPb,
        ten_k_pb: tenKPb,
        half_pb: halfPb,
        marathon_pb: marathonPb,
        max_heart_rate: maxHr ? Number(maxHr) : null,
        resting_heart_rate: restHr ? Number(restHr) : null,
        save: false,
      });
      if (res.data?.success && res.data?.estimated_vo2max) {
        setVo2max(res.data.estimated_vo2max);
        alert(`✅ ${res.data.message}\n\n已自动填入上方 VO2Max 框，点击页面底部“保存跑者档案”即可持久保存！`);
      } else {
        alert(res.data?.message || "未能推算出 VO2Max，请先填写任意距离 PB 成绩");
      }
    } catch (e: any) {
      const errMsg = e.response?.data?.detail || e.message || "推算失败";
      alert("VO2Max 推算提示: " + errMsg);
    } finally {
      setEstimatingVo2(false);
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

  async function handleSaveNicknameOnly() {
    if (!user?.id) return;
    const name = displayName.trim();
    if (!name) {
      alert("跑者昵称不能为空！");
      return;
    }
    setSavingNickname(true);
    try {
      await apiClient.put(`/api/profile/${encodeURIComponent(user.id)}`, {
        display_name: name,
      });

      // Update session in localStorage
      try {
        const raw = localStorage.getItem("rgm_auth_session");
        if (raw) {
          const sess = JSON.parse(raw);
          if (sess?.user) {
            sess.user.display_name = name;
            localStorage.setItem("rgm_auth_session", JSON.stringify(sess));
          }
        }
      } catch (e) {}

      // Update local user state
      setUser((prev: any) => (prev ? { ...prev, display_name: name } : prev));

      setNicknameSavedSuccess(true);
      setTimeout(() => setNicknameSavedSuccess(false), 3000);
      alert(`✅ 跑者昵称已成功更新并保存为「${name}」！`);
    } catch (err: any) {
      alert("保存昵称失败: " + (err?.response?.data?.detail || err?.message || err));
    } finally {
      setSavingNickname(false);
    }
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!user) return;

    setSaving(true);
    try {
      const cleanName = displayName.trim();
      const effGobiExp = gobiType === "new" ? "新戈" : `${gobiEdition} ${gobiGroup}`;
      const effClassName = program ? `${program} ${classDetail}`.trim() : (className.trim() || null);

      // 1. Update Profile
      await apiClient.put(`/api/profile/${user.id}`, {
        display_name: cleanName || undefined,
        avatar_url: avatarUrl || undefined,
        gender,
        real_name: realName.trim() || null,
        id_card: idCard.trim() || null,
        phone: phone.trim() || null,
        program: program || null,
        class_detail: classDetail.trim() || null,
        class_name: effClassName,
        gobi_experience: effGobiExp,
        emergency_contact: emergencyContact.trim() || null,
        clothing_size: clothingSize.trim() || null,
        shoe_size: shoeSize.trim() || null,
        health_declaration: healthDeclaration,
        date_of_birth: dateOfBirth || null,
        vo2max: vo2max !== "" ? Number(vo2max) : null,
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

      // Update session in localStorage
      if (cleanName) {
        try {
          const raw = localStorage.getItem("rgm_auth_session");
          if (raw) {
            const sess = JSON.parse(raw);
            if (sess?.user) {
              sess.user.display_name = cleanName;
              localStorage.setItem("rgm_auth_session", JSON.stringify(sess));
            }
          }
        } catch (e) {}
        setUser((prev: any) => (prev ? { ...prev, display_name: cleanName } : prev));
      }

      alert("🎉 个人资料、比赛计划与跑量目标保存成功！");
    } catch (e: any) {
      alert("保存失败: " + (e?.message || e));
    } finally {
      setSaving(false);
    }
  }

  async function handleExecutePurgePrivacy() {
    if (!user?.id) return;
    setPurgingPrivacy(true);
    try {
      const res = await apiClient.post(`/api/profile/${user.id}/purge-privacy`);
      alert(res.data?.message || "所有个人隐私数据（真实姓名、身份证、生日、手机号及第三方手表账号凭证）已彻底安全清除！");
      if (res.data?.anonymized_display_name) {
        setDisplayName(res.data.anonymized_display_name);
      }
      setRealName("");
      setIdCard("");
      setPhone("");
      setDateOfBirth("");
      setAge(null);
      setGarminConnected(false);
      setGarminEmail("");
      setCorosConnected(false);
      setCorosAccount("");
      setShowPurgeConfirmModal(false);
    } catch (e: any) {
      alert("清除失败: " + (e.response?.data?.detail || e.message || "网络异常"));
    } finally {
      setPurgingPrivacy(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#070708] text-white">
      <Navbar />

      <main className="max-w-4xl mx-auto px-4 sm:px-6 py-8">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
          <div>
            <h1 className="text-2xl sm:text-3xl font-black tracking-tight">跑者档案、比赛计划与目标</h1>
            <p className="text-xs sm:text-sm text-zinc-400 mt-1">
              完善生理指标、赛事周期倒计时与各距离 PB，驱动 Canova教练 精准配速生成
            </p>
          </div>
          <Link
            href="/dashboard/manual"
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold bg-white/5 hover:bg-white/10 text-zinc-300 hover:text-white border border-white/10 transition self-start sm:self-auto shrink-0 shadow-sm"
          >
            <BookOpen className="w-3.5 h-3.5 text-[#FC4C02]" />
            <span>📖 新用户手册与指引 ›</span>
          </Link>
        </div>

        {/* Tab Switcher */}
        <div className="flex border-b border-white/10 mb-8 space-x-2">
          <button
            type="button"
            onClick={() => setActiveTab("profile")}
            className={`flex items-center gap-2 px-5 py-3 text-sm sm:text-base font-bold transition-all relative border-b-2 -mb-px ${
              activeTab === "profile"
                ? "text-[#FC4C02] border-[#FC4C02] bg-white/[0.03]"
                : "text-zinc-400 border-transparent hover:text-zinc-200"
            }`}
          >
            <span>👤</span>
            <span>个人资料与账号</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("training")}
            className={`flex items-center gap-2 px-5 py-3 text-sm sm:text-base font-bold transition-all relative border-b-2 -mb-px ${
              activeTab === "training"
                ? "text-[#FC4C02] border-[#FC4C02] bg-white/[0.03]"
                : "text-zinc-400 border-transparent hover:text-zinc-200"
            }`}
          >
            <span>🏃</span>
            <span>训练档案与赛事</span>
          </button>
        </div>

        <form onSubmit={handleSave} className="space-y-8">
          {/* ══════════════════════════════════════════════════════════════════ */}
          {/* TAB 1: 个人资料与账号 (Profile & Account)                         */}
          {/* ══════════════════════════════════════════════════════════════════ */}
          {activeTab === "profile" && (
            <div className="space-y-8">
              {/* ── CARD: 大群体成员认证与审核状态 (Grand Org Membership Status Card) ── */}
          {userOrgs && userOrgs.length > 0 && (
            <div className="bg-[#121215] border border-amber-500/30 rounded-3xl p-6 sm:p-8 shadow-2xl space-y-5 relative overflow-hidden">
              <div className="absolute top-0 right-0 w-96 h-96 bg-amber-500/5 rounded-full blur-3xl pointer-events-none" />
              
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-white/5 pb-4">
                <div className="flex items-center gap-2.5">
                  <div className="p-2 rounded-2xl bg-amber-500/20 text-amber-400">
                    <Award className="w-5 h-5" />
                  </div>
                  <div>
                    <h2 className="text-lg font-bold text-white tracking-wide">
                      大群体成员认证与审核状态
                    </h2>
                    <p className="text-xs text-zinc-400 mt-0.5">
                      您已加入的商学院大组织准入考核与认证资格（关系到下属跑团的浏览与活动参与权限）
                    </p>
                  </div>
                </div>
              </div>

              <div className="space-y-4">
                {userOrgs.map((org: any) => {
                  const isConfirmed = org.status === "confirmed";
                  const isSuspended = org.status === "expired" || org.status === "suspended" || org.is_suspended;
                  const isPending = org.status === "pending";
                  const daysRemaining = org.days_remaining !== null && org.days_remaining !== undefined ? org.days_remaining : 14;

                  return (
                    <div
                      key={org.id}
                      className={`p-5 rounded-2xl border transition ${
                        isConfirmed
                          ? "bg-emerald-500/5 border-emerald-500/20"
                          : isSuspended
                          ? "bg-rose-500/10 border-rose-500/40"
                          : isPending
                          ? "bg-blue-500/5 border-blue-500/20"
                          : "bg-amber-500/5 border-amber-500/30"
                      }`}
                    >
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-3">
                        <div className="flex items-center gap-2.5">
                          <span className="text-base font-bold text-white">{org.name}</span>
                          {org.city && (
                            <span className="text-xs text-zinc-400 bg-white/5 px-2 py-0.5 rounded-full border border-white/5">
                              {org.city}
                            </span>
                          )}
                        </div>

                        <div className="self-start sm:self-auto">
                          {isConfirmed ? (
                            <span className="px-3 py-1 rounded-full text-xs font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 flex items-center gap-1.5">
                              <CheckCircle2 className="w-3.5 h-3.5" />
                              正式队员 · 已核验
                            </span>
                          ) : isSuspended ? (
                            <span className="px-3 py-1 rounded-full text-xs font-bold bg-rose-500/20 text-rose-300 border border-rose-500/40 flex items-center gap-1.5">
                              <AlertTriangle className="w-3.5 h-3.5" />
                              🚫 访问已暂停
                            </span>
                          ) : isPending ? (
                            <span className="px-3 py-1 rounded-full text-xs font-bold bg-blue-500/20 text-blue-300 border border-blue-500/30 flex items-center gap-1.5">
                              <Clock className="w-3.5 h-3.5" />
                              📋 待管理员核验 · 余{daysRemaining}天
                            </span>
                          ) : (
                            <span className="px-3 py-1 rounded-full text-xs font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30 flex items-center gap-1.5">
                              <Clock className="w-3.5 h-3.5" />
                              ⏳ 临时状态 · 余{daysRemaining}天
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Description / Instructions */}
                      {isConfirmed && (
                        <p className="text-xs text-emerald-200/90 leading-relaxed">
                          ✓ 您已完成所有必填字段并通过大团管理员审核确认，已成为正式队员，享有大团及所有从属跑团的永久完整访问与活动参与权限。
                        </p>
                      )}

                      {isSuspended && (
                        <div className="space-y-3">
                          <p className="text-xs text-rose-200/95 leading-relaxed font-medium">
                            ⚠️ 您的2周临时访问期已到期。由于超期未完成所有必填字段填写并获大团管理员确认，已暂停浏览使用该大团及其从属跑团的一切内容和活动！
                          </p>
                          <button
                            type="button"
                            onClick={scrollToRequiredFields}
                            className="px-4 py-2 rounded-xl text-xs font-bold bg-rose-600 hover:bg-rose-500 text-white shadow-md shadow-rose-600/30 transition flex items-center gap-1.5"
                          >
                            <span>📝 立即补齐必填字段</span>
                          </button>
                        </div>
                      )}

                      {isPending && (
                        <p className="text-xs text-blue-200/90 leading-relaxed">
                          📋 您已填齐必填资料，正在等待大团管理员审核确认。请在 2 周临时期内（剩余 {daysRemaining} 天）由管理员在后台核验批准成为正式队员。
                        </p>
                      )}

                      {!isConfirmed && !isSuspended && !isPending && (
                        <div className="space-y-3">
                          <p className="text-xs text-amber-200/90 leading-relaxed">
                            ⏳ 根据大群群规，必须在 2 周内（剩余 {daysRemaining} 天）完成所有必填字段填写并获得大团管理员确认。2周超期未完成将被暂停大团及从属跑团的一切内容和活动！
                          </p>
                          {org.missing_fields && org.missing_fields.length > 0 && (
                            <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-xs">
                              <span className="text-amber-300 font-bold mr-2">待补齐必填项：</span>
                              <span className="text-amber-200">
                                {org.missing_fields.map((f: any) => f.label).join("、")}
                              </span>
                            </div>
                          )}
                          <button
                            type="button"
                            onClick={scrollToRequiredFields}
                            className="px-4 py-2 rounded-xl text-xs font-bold bg-amber-500 hover:bg-amber-400 text-black shadow-md shadow-amber-500/20 transition flex items-center gap-1.5"
                          >
                            <span>📝 立即前往补齐必填字段</span>
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

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
                  referrerPolicy="no-referrer"
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
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      value={displayName}
                      onChange={(e) => setDisplayName(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          e.preventDefault();
                          handleSaveNicknameOnly();
                        }
                      }}
                      placeholder="例如: Alex Wan / 珍珍"
                      className="flex-1 bg-[#18181c] border border-white/10 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-[#FC4C02]"
                    />
                    <button
                      type="button"
                      disabled={savingNickname}
                      onClick={handleSaveNicknameOnly}
                      className="px-4 py-2.5 rounded-xl text-xs font-bold bg-[#FC4C02] text-white hover:bg-[#ff5d1a] transition active:scale-95 shadow-md shadow-[#FC4C02]/20 shrink-0 flex items-center gap-1.5 disabled:opacity-50"
                    >
                      {savingNickname ? (
                        <>
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          <span>保存中...</span>
                        </>
                      ) : nicknameSavedSuccess ? (
                        <>
                          <Check className="w-3.5 h-3.5 text-white" />
                          <span>已保存</span>
                        </>
                      ) : (
                        <>
                          <Save className="w-3.5 h-3.5" />
                          <span>保存昵称</span>
                        </>
                      )}
                    </button>
                  </div>
                  <p className="text-[11px] text-zinc-500 mt-1">
                    该昵称将展示在跑团花名册、大盘排行榜与 Renato Canova 科学训练档案中（支持直接回车保存）
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

              {/* ── CARD: 个人实名身份与敏感信息 (AES-256-GCM 密文存储) ── */}
          <div id="required-personal-fields" className="bg-[#121215] border border-white/[0.08] rounded-3xl p-6 sm:p-8 shadow-2xl space-y-6 scroll-mt-24">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-white/5 pb-4">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-2xl bg-emerald-500/20 text-emerald-400">
                  <Lock className="w-5 h-5" />
                </div>
                <div>
                  <h2 className="text-lg font-bold text-white tracking-wide">个人实名身份与敏感信息</h2>
                  <p className="text-xs text-zinc-400 mt-0.5">
                    真实姓名、生理性别、出生日期、联系电话及证件号采用 AES-256-GCM 密文存储保护
                  </p>
                </div>
              </div>
              <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 self-start sm:self-auto">
                🔒 AES-256 高强度加密 · 非必要不暴露
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {/* 性别 */}
              <div>
                <label className="text-xs text-zinc-400 flex items-center gap-1.5 mb-1.5">
                  <span>生理性别<span className="text-red-400 ml-0.5 font-bold">*</span></span>
                  <span className="text-[10px] text-amber-400/90 bg-amber-500/10 px-1.5 py-0.5 rounded border border-amber-500/20 font-bold">大组织必填项</span>
                </label>
                <select
                  value={gender}
                  onChange={(e) => setGender(e.target.value)}
                  className="w-full bg-[#18181c] border border-white/10 rounded-xl px-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-[#FC4C02]"
                >
                  <option value="male">男 (Male)</option>
                  <option value="female">女 (Female)</option>
                </select>
              </div>
              {/* 真实姓名 */}
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="text-xs text-zinc-400 flex items-center gap-1.5 flex-wrap">
                      <span>真实姓名 (实名认证)<span className="text-red-400 ml-0.5 font-bold">*</span></span>
                      <span className="text-[10px] text-amber-400/90 bg-amber-500/10 px-1.5 py-0.5 rounded border border-amber-500/20 font-bold">大组织必填项</span>
                      <span className="text-[10px] text-emerald-400/80 bg-emerald-500/10 px-1.5 py-0.2 rounded border border-emerald-500/20">加密存储</span>
                    </label>
                    <span className="text-[11px] text-zinc-500">{showRealName ? "明文展示" : "星号遮罩"}</span>
                  </div>
                  <div className="relative flex items-center">
                    <input
                      type={showRealName ? "text" : "password"}
                      value={realName}
                      onChange={(e) => setRealName(e.target.value)}
                      placeholder="戈友实名认证真实姓名"
                      className="w-full bg-[#18181c] border border-white/10 rounded-xl px-3.5 py-2.5 pr-10 text-sm text-white focus:outline-none focus:border-[#FC4C02]"
                    />
                    <button
                      type="button"
                      onClick={() => setShowRealName(!showRealName)}
                      className="absolute right-2.5 text-zinc-400 hover:text-white transition p-1"
                      title={showRealName ? "隐藏" : "显示"}
                    >
                      {showRealName ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                {/* 紧急联系手机 */}
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="text-xs text-zinc-400 flex items-center gap-1.5">
                      <span>联系手机 (Emergency Phone)</span>
                      <span className="text-[10px] text-emerald-400/80 bg-emerald-500/10 px-1.5 py-0.2 rounded border border-emerald-500/20">保密</span>
                    </label>
                    <span className="text-[11px] text-zinc-500">{showPhone ? "明文展示" : "星号遮罩"}</span>
                  </div>
                  <div className="relative flex items-center">
                    <input
                      type={showPhone ? "tel" : "password"}
                      maxLength={11}
                      value={phone}
                      onChange={(e) => setPhone(e.target.value)}
                      placeholder="便于紧急联络与赛事活动通知"
                      className="w-full bg-[#18181c] border border-white/10 rounded-xl px-3.5 py-2.5 pr-10 text-sm text-white focus:outline-none focus:border-[#FC4C02]"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPhone(!showPhone)}
                      className="absolute right-2.5 text-zinc-400 hover:text-white transition p-1"
                      title={showPhone ? "隐藏" : "显示"}
                    >
                      {showPhone ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                {/* 出生日期 & 年龄 */}
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="text-xs text-zinc-400 flex items-center gap-1.5 flex-wrap">
                      <span>出生日期 (Date of Birth)<span className="text-red-400 ml-0.5 font-bold">*</span></span>
                      <span className="text-[10px] text-amber-400/90 bg-amber-500/10 px-1.5 py-0.5 rounded border border-amber-500/20 font-bold">大组织必填项</span>
                      <span className="text-[10px] text-emerald-400/80 bg-emerald-500/10 px-1.5 py-0.2 rounded border border-emerald-500/20">密文分级</span>
                    </label>
                    {age !== null && (
                      <span className="text-[11px] font-bold px-2 py-0.5 rounded-full bg-[#FC4C02]/15 text-[#FC4C02] border border-[#FC4C02]/30">
                        {age} 岁 · {getAgeGroup(age)}
                      </span>
                    )}
                  </div>
                  <div className="relative flex items-center">
                    {showDob ? (
                      <input
                        type="date"
                        value={dateOfBirth}
                        onChange={(e) => {
                          setDateOfBirth(e.target.value);
                          setAge(computeAge(e.target.value));
                        }}
                        className="w-full bg-[#18181c] border border-white/10 rounded-xl px-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-[#FC4C02]"
                      />
                    ) : (
                      <input
                        type="password"
                        readOnly
                        value={dateOfBirth ? "1990-01-01" : ""}
                        placeholder="点击右侧眼睛显示并选择出生日期"
                        onClick={() => setShowDob(true)}
                        className="w-full bg-[#18181c] border border-white/10 rounded-xl px-3.5 py-2.5 pr-10 text-sm text-white focus:outline-none focus:border-[#FC4C02] cursor-pointer"
                      />
                    )}
                    <button
                      type="button"
                      onClick={() => setShowDob(!showDob)}
                      className="absolute right-2.5 text-zinc-400 hover:text-white transition p-1"
                      title={showDob ? "隐藏" : "显示"}
                    >
                      {showDob ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                  <p className="text-[11px] text-zinc-500 mt-1">
                    仅用于生理体能评估与大组织分组核实，对外公开名册仅显示组别脱敏保护
                  </p>
                </div>

                {/* 身份证号码 / 证件号 */}
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="text-xs text-zinc-400 flex items-center gap-1.5">
                      <span>身份证号码 / 证件号 (选填)</span>
                      <span className="text-[10px] text-emerald-400/80 bg-emerald-500/10 px-1.5 py-0.2 rounded border border-emerald-500/20">非必要不暴露</span>
                    </label>
                    <span className="text-[11px] text-zinc-500">{showIdCard ? "明文展示" : "星号遮罩"}</span>
                  </div>
                  <div className="relative flex items-center">
                    <input
                      type={showIdCard ? "text" : "password"}
                      maxLength={18}
                      value={idCard}
                      onChange={(e) => setIdCard(e.target.value)}
                      placeholder="用于赛事保险投保与参赛资格核验"
                      className="w-full bg-[#18181c] border border-white/10 rounded-xl px-3.5 py-2.5 pr-10 text-sm text-white focus:outline-none focus:border-[#FC4C02]"
                    />
                    <button
                      type="button"
                      onClick={() => setShowIdCard(!showIdCard)}
                      className="absolute right-2.5 text-zinc-400 hover:text-white transition p-1"
                      title={showIdCard ? "隐藏" : "显示"}
                    >
                      {showIdCard ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                  <p className="text-[11px] text-zinc-500 mt-1">
                    默认以 *** 隐藏，点击眼睛符号才完整显示。非必要绝不向任何第三方暴露
                  </p>
                </div>
            </div>
          </div>

              {/* ── CARD: 商学院项目与戈友认证 (Gobi & Business School Credentials) ── */}
          <div className="bg-[#121215] border border-white/[0.08] rounded-3xl p-6 sm:p-8 shadow-2xl space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Award className="w-5 h-5 text-amber-400" />
                <h2 className="text-lg font-bold text-white tracking-wide">商学院项目与戈友认证</h2>
              </div>
              <span className="px-3 py-1 rounded-full text-xs font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20 self-start sm:self-auto">
                🏫 大组织审核资格 · 实时双向自动同步
              </span>
            </div>
            <p className="text-xs text-zinc-400">
              在此填写的商学院项目、班级与戈壁经历，将自动同步至您已加入的所有商学院大群（如复旦戈友会）实名花名册。当群管理员设置必须字段时，在此补齐即可自动流转为正式/待审核状态，无需重复填报。
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-2">
              {/* 商学院项目与班级 */}
              <div className="p-5 rounded-2xl bg-white/[0.02] border border-white/5 space-y-4">
                <div className="flex items-center justify-between">
                  <label className="text-sm font-bold text-white flex items-center gap-1.5">
                    <span>商学院项目与班级<span className="text-red-400 ml-0.5">*</span></span>
                    <span className="text-[10px] text-amber-400/80 bg-amber-500/10 px-1.5 py-0.5 rounded border border-amber-500/20">大组织必填项</span>
                  </label>
                </div>
                
                <div>
                  <span className="text-xs text-zinc-400 block mb-2">选择所属项目：</span>
                  <div className="flex flex-wrap gap-2">
                    {ORG_PROGRAM_OPTIONS.map((prog) => (
                      <button
                        key={prog}
                        type="button"
                        onClick={() => setProgram(prog)}
                        className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition ${
                          program === prog
                            ? "bg-amber-500 text-black shadow-md shadow-amber-500/20 font-bold"
                            : "bg-white/5 text-zinc-400 hover:text-white hover:bg-white/10 border border-white/5"
                        }`}
                      >
                        {prog}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <div className="flex items-center gap-1.5 mb-1.5">
                    <span className="text-xs text-zinc-400">所在班级 / 届别 (自由输入)<span className="text-red-400 ml-0.5 font-bold">*</span>：</span>
                    <span className="text-[10px] text-amber-400/90 bg-amber-500/10 px-1.5 py-0.5 rounded border border-amber-500/20 font-bold">大组织必填项</span>
                  </div>
                  <input
                    type="text"
                    value={classDetail}
                    onChange={(e) => setClassDetail(e.target.value)}
                    placeholder="例如: 23春、21级、18班、2022秋"
                    className="w-full bg-[#18181c] border border-white/10 rounded-xl px-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-amber-500"
                  />
                  {program && classDetail && (
                    <div className="mt-2 text-xs text-amber-300 flex items-center gap-1.5 bg-amber-500/10 px-3 py-1.5 rounded-xl border border-amber-500/20">
                      <span>名册显示组合：</span>
                      <span className="font-bold">{program} {classDetail}</span>
                    </div>
                  )}
                </div>
              </div>

              {/* 戈壁经历 */}
              <div className="p-5 rounded-2xl bg-white/[0.02] border border-white/5 space-y-4">
                <div className="flex items-center justify-between">
                  <label className="text-sm font-bold text-white flex items-center gap-1.5">
                    <span>戈壁经历 (戈赛经验)</span>
                    <span className="text-[10px] text-amber-400/80 bg-amber-500/10 px-1.5 py-0.5 rounded border border-amber-500/20">分组与荣誉铭牌</span>
                  </label>
                  <span className="text-xs text-zinc-400">{gobiType === "new" ? "🌱 新戈跑者" : `🏅 ${gobiEdition} ${gobiGroup}`}</span>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={() => setGobiType("new")}
                    className={`p-3 rounded-xl border text-left transition flex items-center gap-2.5 ${
                      gobiType === "new"
                        ? "bg-emerald-500/15 border-emerald-500/40 text-emerald-300 shadow-md shadow-emerald-500/10"
                        : "bg-white/5 border-white/5 text-zinc-400 hover:bg-white/10"
                    }`}
                  >
                    <span className="text-xl">🌱</span>
                    <div>
                      <div className="font-bold text-xs text-white">新戈</div>
                      <div className="text-[10px] text-zinc-400">首次备赛/无往届</div>
                    </div>
                  </button>
                  <button
                    type="button"
                    onClick={() => setGobiType("vet")}
                    className={`p-3 rounded-xl border text-left transition flex items-center gap-2.5 ${
                      gobiType === "vet"
                        ? "bg-amber-500/15 border-amber-500/40 text-amber-300 shadow-md shadow-amber-500/10"
                        : "bg-white/5 border-white/5 text-zinc-400 hover:bg-white/10"
                    }`}
                  >
                    <span className="text-xl">🏅</span>
                    <div>
                      <div className="font-bold text-xs text-white">往届老戈友</div>
                      <div className="text-[10px] text-zinc-400">戈1至戈21</div>
                    </div>
                  </button>
                </div>

                {gobiType === "vet" && (
                  <div className="p-3.5 bg-black/40 border border-white/10 rounded-xl space-y-3">
                    <div>
                      <span className="text-xs text-zinc-400 block mb-1.5">参加届数 (戈1 ~ 戈21)：</span>
                      <select
                        value={gobiEdition}
                        onChange={(e) => setGobiEdition(e.target.value)}
                        className="w-full bg-[#18181c] border border-white/10 rounded-xl px-3 py-2 text-white text-sm focus:outline-none focus:border-amber-500"
                      >
                        {GOBI_EDITIONS.map((ed) => (
                          <option key={ed} value={ed}>{ed}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <span className="text-xs text-zinc-400 block mb-1.5">参赛组别：</span>
                      <div className="flex gap-2">
                        {GOBI_GROUPS.map((grp) => (
                          <button
                            key={grp}
                            type="button"
                            onClick={() => setGobiGroup(grp)}
                            className={`flex-1 py-1.5 rounded-xl text-xs font-bold transition ${
                              gobiGroup === grp
                                ? "bg-amber-500 text-black font-extrabold shadow-md shadow-amber-500/20"
                                : "bg-white/5 text-zinc-400 hover:text-white border border-white/5"
                            }`}
                          >
                            {grp}
                          </button>
                        ))}
                      </div>
                    </div>
                    <div className="text-[11px] text-amber-300 flex items-center gap-1.5 pt-1">
                      <span>认证经历展示：</span>
                      <span className="px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-400 font-bold border border-amber-500/30">
                        🏅 {gobiEdition} {gobiGroup}
                      </span>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

              {/* ── CARD: 赛事活动与装备保障 (Race Gear & Emergency) ── */}
          <div className="bg-[#121215] border border-white/[0.08] rounded-3xl p-6 sm:p-8 shadow-2xl space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Shield className="w-5 h-5 text-indigo-400" />
                <h2 className="text-lg font-bold text-white tracking-wide">赛事活动与装备保障</h2>
              </div>
              <span className="px-3 py-1 rounded-full text-xs font-bold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 self-start sm:self-auto">
                🎽 物资发放 · 安全保险
              </span>
            </div>
            <p className="text-xs text-zinc-400">
              用于商学院戈壁拉练、选拔赛与官方马拉松活动定制队服采购、装备物资统一分发及紧急安全联络。
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4 pt-2">
              {/* 紧急联系人及电话 */}
              <div>
                <label className="text-xs text-zinc-400 block mb-1.5">
                  紧急联系人及电话
                </label>
                <input
                  type="text"
                  value={emergencyContact}
                  onChange={(e) => setEmergencyContact(e.target.value)}
                  placeholder="例如: 张三 13900001111"
                  className="w-full bg-[#18181c] border border-white/10 rounded-xl px-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500"
                />
                <span className="text-[11px] text-zinc-500 mt-1 block">建议填写直系亲属或紧急联络人姓名与电话</span>
              </div>

              {/* 队服尺码 */}
              <div>
                <label className="text-xs text-zinc-400 block mb-1.5">
                  队服尺码 (Clothing Size)
                </label>
                <select
                  value={clothingSize}
                  onChange={(e) => setClothingSize(e.target.value)}
                  className="w-full bg-[#18181c] border border-white/10 rounded-xl px-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500"
                >
                  <option value="">请选择尺码</option>
                  {CLOTHING_SIZES.map((sz) => (
                    <option key={sz} value={sz}>{sz}</option>
                  ))}
                </select>
                <span className="text-[11px] text-zinc-500 mt-1 block">用于团队赛事战袍、训练T恤订制与发放</span>
              </div>

              {/* 跑鞋尺码 */}
              <div>
                <label className="text-xs text-zinc-400 block mb-1.5">
                  跑鞋尺码 (Shoe Size)
                </label>
                <input
                  type="text"
                  value={shoeSize}
                  onChange={(e) => setShoeSize(e.target.value)}
                  placeholder="例如: 42 或 42.5"
                  className="w-full bg-[#18181c] border border-white/10 rounded-xl px-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500"
                />
                <span className="text-[11px] text-zinc-500 mt-1 block">欧洲码 (EUR)，如 40、41、42、42.5、43</span>
              </div>
            </div>

            {/* 健康状况声明 */}
            <div className="p-4 rounded-2xl bg-white/[0.02] border border-white/5 flex items-start gap-3 mt-2">
              <input
                type="checkbox"
                id="health-decl-check"
                checked={healthDeclaration}
                onChange={(e) => setHealthDeclaration(e.target.checked)}
                className="mt-1 w-4 h-4 rounded border-white/20 text-[#FC4C02] focus:ring-[#FC4C02] bg-[#18181c] cursor-pointer"
              />
              <label htmlFor="health-decl-check" className="text-xs text-zinc-300 leading-relaxed cursor-pointer select-none">
                <span className="font-bold text-white block mb-0.5">健康状况与免责声明确认</span>
                本人身体健康，无高血压、心脑血管疾病、糖尿病或其他不适宜参加长距离剧烈耐力跑之疾病，具备参加跑步训练及马拉松、戈壁越野拉练的身体条件。自愿遵从教练团队安全指引与急救规范。
              </label>
            </div>
          </div>

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

              {/* ── CARD 5: 个人隐私与数据安全保障 & 一键彻底清除 ── */}
          <div className="bg-[#121215] border border-white/[0.08] rounded-3xl p-6 sm:p-8 shadow-2xl space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="flex items-center gap-2">
                <Shield className="w-5 h-5 text-emerald-400" />
                <h2 className="text-lg font-bold text-white tracking-wide">个人隐私与数据安全保障</h2>
              </div>
              <span className="px-3 py-1 rounded-full text-xs font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 self-start sm:self-auto">
                🔒 AES-256-GCM 高强度密文保护
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-4 rounded-2xl bg-white/[0.02] border border-white/5 space-y-2">
                <div className="flex items-center gap-2 text-white font-bold text-xs">
                  <span className="text-base">🔒</span>
                  <span>敏感隐私密文存储</span>
                </div>
                <p className="text-xs text-zinc-400 leading-relaxed">
                  真实姓名、身份证号、出生日期及手机号均在数据库底层采用 AES-256-GCM 密文存储，非必要不暴露，仅用于赛事保险投保与资格核验。
                </p>
              </div>

              <div className="p-4 rounded-2xl bg-white/[0.02] border border-white/5 space-y-2">
                <div className="flex items-center gap-2 text-white font-bold text-xs">
                  <span className="text-base">👁️</span>
                  <span>大群体名册自动脱敏</span>
                </div>
                <p className="text-xs text-zinc-400 leading-relaxed">
                  在公开团队名册中，非管理员跑友仅可见脱敏姓名（如：张*、李*华）与年龄组别（如：大师组、壮年组），身份证号与手机号对普通成员完全隐蔽。
                </p>
              </div>

              <div className="p-4 rounded-2xl bg-white/[0.02] border border-white/5 space-y-2">
                <div className="flex items-center gap-2 text-white font-bold text-xs">
                  <span className="text-base">🧹</span>
                  <span>随时一键彻底清除</span>
                </div>
                <p className="text-xs text-zinc-400 leading-relaxed">
                  您可以随时一键彻底擦除真实姓名、证件号、生日、手机号及第三方手表账号密码密文。历史运动里程将以匿名跑者形式保留。
                </p>
              </div>
            </div>

            <div className="pt-2 border-t border-white/5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <p className="text-xs text-zinc-500">
                若您不再需要参与赛事资格审核，可随时一键清除所有个人实名与认证记录。
              </p>
              <button
                type="button"
                onClick={() => setShowPurgeConfirmModal(true)}
                className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold text-rose-400 bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/20 transition active:scale-95 shrink-0"
              >
                <Trash2 className="w-4 h-4" />
                <span>🧹 一键清除所有个人隐私数据</span>
              </button>
            </div>
          </div>

                          <div className="flex justify-end pt-4">
              <button
                type="submit"
                disabled={saving}
                className="flex items-center gap-2 px-8 py-3.5 rounded-2xl text-base font-bold bg-gradient-to-r from-[#FC4C02] to-[#ff7a45] text-white hover:brightness-110 transition active:scale-95 shadow-xl shadow-[#FC4C02]/25"
              >
                <Save className="w-5 h-5" />
                {saving ? "正在保存..." : "💾 保存个人资料与账号设置"}
              </button>
            </div>
            </div>
          )}

          {/* ══════════════════════════════════════════════════════════════════ */}
          {/* TAB 2: 训练档案与赛事 (Training Metrics & Races)                  */}
          {/* ══════════════════════════════════════════════════════════════════ */}
          {activeTab === "training" && (
            <div className="space-y-8">
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

              {/* ── CARD 3: 运动体能与生理指标 ── */}
          <div className="bg-[#121215] border border-white/[0.08] rounded-3xl p-6 sm:p-8 shadow-2xl space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-2">
                  <Heart className="w-5 h-5 text-rose-500" />
                  <h2 className="text-lg font-bold text-white tracking-wide">运动体能与生理指标</h2>
                </div>
                <p className="text-xs text-zinc-400 mt-1">
                  Renato Canova 教练根据实际体能参数与 VO2Max 精准自适应训练配速与超量恢复窗口
                </p>
              </div>

              <button
                type="button"
                onClick={handleSyncDeviceProfile}
                disabled={syncingDeviceProfile || (!garminConnected && !corosConnected)}
                className="flex items-center justify-center gap-2 px-4 py-2 rounded-xl text-xs font-bold bg-white/5 hover:bg-white/10 border border-white/10 text-white transition active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed shadow-lg"
              >
                <RefreshCw className={`w-3.5 h-3.5 text-[#FC4C02] ${syncingDeviceProfile ? "animate-spin" : ""}`} />
                {syncingDeviceProfile ? "正在同步手表身体指标..." : "从手表同步指标"}
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4 pt-2">
              {/* 最大摄氧量 VO2Max */}
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="text-xs text-zinc-400">最大摄氧量 (VO2Max)</label>
                  <button
                    type="button"
                    onClick={handleEstimateVo2max}
                    disabled={estimatingVo2}
                    className="text-[11px] text-[#FC4C02] hover:text-[#ff5d1a] font-bold flex items-center gap-1 transition active:scale-95"
                    title="基于您在上方填写的 5K/10K/半马/全马 PB 成绩自动测算 VDOT"
                  >
                    <span>⚡ 依据 PB 测算</span>
                  </button>
                </div>
                <input
                  type="number"
                  step="0.1"
                  value={vo2max}
                  onChange={(e) => setVo2max(e.target.value ? Number(e.target.value) : "")}
                  placeholder="例如 54.0"
                  className="w-full bg-[#18181c] border border-white/10 rounded-xl px-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-[#FC4C02]"
                />
              </div>

              {/* 身高 */}
              <div>
                <label className="text-xs text-zinc-400 block mb-1.5">身高 (cm)</label>
                <input
                  type="number"
                  value={heightCm}
                  onChange={(e) => setHeightCm(e.target.value ? Number(e.target.value) : "")}
                  className="w-full bg-[#18181c] border border-white/10 rounded-xl px-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-[#FC4C02]"
                />
              </div>

              {/* 体重 */}
              <div>
                <label className="text-xs text-zinc-400 block mb-1.5">体重 (kg)</label>
                <input
                  type="number"
                  step="0.1"
                  value={weightKg}
                  onChange={(e) => setWeightKg(e.target.value ? Number(e.target.value) : "")}
                  className="w-full bg-[#18181c] border border-white/10 rounded-xl px-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-[#FC4C02]"
                />
              </div>

              {/* 最大心率 */}
              <div>
                <label className="text-xs text-zinc-400 block mb-1.5">最大心率 (Max HR bpm)</label>
                <input
                  type="number"
                  value={maxHr}
                  onChange={(e) => setMaxHr(e.target.value ? Number(e.target.value) : "")}
                  className="w-full bg-[#18181c] border border-white/10 rounded-xl px-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-[#FC4C02]"
                />
              </div>

              {/* 静息心率 */}
              <div>
                <label className="text-xs text-zinc-400 block mb-1.5">静息心率 (Resting HR bpm)</label>
                <input
                  type="number"
                  value={restHr}
                  onChange={(e) => setRestHr(e.target.value ? Number(e.target.value) : "")}
                  className="w-full bg-[#18181c] border border-white/10 rounded-xl px-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-[#FC4C02]"
                />
              </div>

              {/* 跑龄 */}
              <div>
                <label className="text-xs text-zinc-400 block mb-1.5">跑龄 (年)</label>
                <input
                  type="number"
                  value={yearsRunning}
                  onChange={(e) => setYearsRunning(e.target.value ? Number(e.target.value) : "")}
                  className="w-full bg-[#18181c] border border-white/10 rounded-xl px-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-[#FC4C02]"
                />
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
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-base">{idx === 0 ? "🔥" : "⛰️"}</span>
                      <span className="text-sm font-bold text-white">比赛 {idx + 1}</span>
                      {race.status === "completed" || race.is_completed ? (
                        <div className="flex items-center gap-1.5">
                          <span className="bg-emerald-500/20 text-emerald-400 text-xs px-2.5 py-0.5 rounded-full border border-emerald-500/30 font-bold flex items-center gap-1">
                            <Trophy className="w-3 h-3 text-emerald-400" />
                            已完赛
                          </span>
                          {race.finish_time && (
                            <span className="bg-zinc-800 text-cyan-300 text-xs px-2.5 py-0.5 rounded-full border border-white/10 font-mono font-bold">
                              {race.finish_time}
                            </span>
                          )}
                          {race.performance_badge && (
                            <span className={`text-xs px-2 py-0.5 rounded-full font-semibold border ${
                              (race.diff_seconds || 0) <= 0 
                                ? "bg-amber-500/15 text-amber-300 border-amber-500/30" 
                                : "bg-blue-500/15 text-blue-300 border-blue-500/30"
                            }`}>
                              {race.performance_badge} {race.diff_str}
                            </span>
                          )}
                        </div>
                      ) : (
                        <div className="flex items-center gap-1.5">
                          <span className="bg-[#24242c] text-zinc-300 text-xs px-2.5 py-0.5 rounded-full border border-white/5 font-semibold">
                            {race.days_left !== undefined ? `${race.days_left} 天` : "—"}
                            {race.days_left !== undefined && race.days_left < 30 ? " 冲刺" : ""}
                          </span>
                          {race.is_past && (
                            <span className="bg-amber-500/15 text-amber-400 text-[11px] px-2 py-0.5 rounded-full border border-amber-500/20 animate-pulse">
                              ⚠️ 比赛日已过，可标记完赛
                            </span>
                          )}
                        </div>
                      )}
                    </div>

                    <button
                      type="button"
                      onClick={() => removeRace(idx)}
                      className="text-zinc-500 hover:text-rose-400 transition p-1"
                      title="删除此赛事计划"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
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

                    <div>
                      <label className="text-xs text-zinc-400 block mb-1.5">完赛状态</label>
                      <select
                        value={race.status || (race.is_completed ? "completed" : "upcoming")}
                        onChange={(e) => {
                          const val = e.target.value;
                          updateRace(idx, "status", val);
                          updateRace(idx, "is_completed", val === "completed");
                        }}
                        className={`w-full border rounded-xl px-3.5 py-2.5 text-sm font-medium focus:outline-none transition ${
                          race.status === "completed" || race.is_completed
                            ? "bg-emerald-950/40 border-emerald-500/40 text-emerald-300"
                            : "bg-[#202026] border-white/10 text-white focus:border-[#FC4C02]"
                        }`}
                      >
                        <option value="upcoming">🟢 备战中 (Upcoming)</option>
                        <option value="completed">🏅 已完赛 (Completed)</option>
                      </select>
                    </div>
                  </div>

                  {/* ── Completed Race Details & Photo Section ── */}
                  {(race.status === "completed" || race.is_completed) && (
                    <div className="rounded-xl border border-emerald-500/20 bg-emerald-950/15 p-4 space-y-4">
                      <div className="flex items-center justify-between border-b border-emerald-500/10 pb-2.5">
                        <div className="flex items-center gap-2 text-xs font-bold text-emerald-400">
                          <Trophy className="w-4 h-4 text-amber-400" />
                          <span>已完赛成绩记录与荣誉证书</span>
                        </div>

                        <button
                          type="button"
                          onClick={() => handleMatchActivity(idx)}
                          disabled={matchingActivityIdx === idx}
                          className="flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-medium bg-[#FC4C02]/20 hover:bg-[#FC4C02]/30 text-[#FC4C02] border border-[#FC4C02]/30 transition active:scale-95 disabled:opacity-50"
                        >
                          {matchingActivityIdx === idx ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          ) : (
                            <Zap className="w-3.5 h-3.5" />
                          )}
                          <span>⚡ 从手表记录一键提取成绩</span>
                        </button>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div>
                          <label className="text-xs text-zinc-400 block mb-1.5 flex items-center justify-between">
                            <span>实际完成时间 (HH:MM:SS)</span>
                            {race.diff_str && (
                              <span className={`text-[11px] font-bold ${
                                (race.diff_seconds || 0) <= 0 ? "text-emerald-400" : "text-cyan-400"
                              }`}>
                                {race.performance_badge} ({race.diff_str})
                              </span>
                            )}
                          </label>
                          <div className="relative">
                            <input
                              type="text"
                              value={race.finish_time || ""}
                              onChange={(e) => {
                                const val = e.target.value;
                                updateRace(idx, "finish_time", val);
                                try {
                                  const tSec = parseTimeToSec(race.target_time);
                                  const fSec = parseTimeToSec(val);
                                  if (tSec && fSec) {
                                    const diff = fSec - tSec;
                                    updateRace(idx, "diff_seconds", diff);
                                    updateRace(idx, "diff_str", diff < 0 ? `-${formatSecToTime(Math.abs(diff))}` : (diff === 0 ? "精准达标" : `+${formatSecToTime(diff)}`));
                                    updateRace(idx, "performance_badge", diff < 0 ? "超额达标 🎉" : "顺利完赛 🏅");
                                  }
                                } catch {}
                              }}
                              placeholder="如: 3:24:15 或 08:12:00"
                              className="w-full bg-[#18181f] border border-emerald-500/30 rounded-xl px-3.5 py-2.5 text-sm text-emerald-300 font-mono font-bold focus:outline-none focus:border-emerald-400"
                            />
                            <Clock className="w-4 h-4 text-zinc-500 absolute right-3.5 top-3" />
                          </div>
                        </div>

                        <div>
                          <label className="text-xs text-zinc-400 block mb-1.5">完赛心得 / 感言</label>
                          <input
                            type="text"
                            value={race.finish_notes || ""}
                            onChange={(e) => updateRace(idx, "finish_notes", e.target.value)}
                            placeholder="如: 补给充分，下坡控速理想，超额达成目标！"
                            className="w-full bg-[#18181f] border border-white/10 rounded-xl px-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-emerald-400"
                          />
                        </div>
                      </div>

                      {/* Photo Upload & Gallery */}
                      <div>
                        <div className="flex items-center justify-between mb-2">
                          <label className="text-xs text-zinc-400 flex items-center gap-1.5">
                            <Camera className="w-3.5 h-3.5 text-cyan-400" />
                            <span>完赛照片 / 成绩证书 / 奖牌现场照</span>
                          </label>

                          <label className="cursor-pointer inline-flex items-center gap-1 px-3 py-1 bg-white/5 hover:bg-white/10 text-zinc-200 border border-white/10 rounded-lg text-xs font-medium transition active:scale-95">
                            {uploadingPhotoIdx === idx ? (
                              <Loader2 className="w-3 h-3 animate-spin text-[#FC4C02]" />
                            ) : (
                              <Plus className="w-3 h-3 text-[#FC4C02]" />
                            )}
                            <span>{uploadingPhotoIdx === idx ? "正在上传..." : "上传照片"}</span>
                            <input
                              type="file"
                              accept="image/*"
                              className="hidden"
                              disabled={uploadingPhotoIdx === idx}
                              onChange={(e) => handleUploadRacePhoto(idx, e)}
                            />
                          </label>
                        </div>

                        {/* Photo thumbnails */}
                        {race.photos && race.photos.length > 0 ? (
                          <div className="flex flex-wrap gap-3">
                            {race.photos.map((pUrl, pIdx) => (
                              <div
                                key={pIdx}
                                className="relative group w-20 h-20 sm:w-24 sm:h-24 rounded-xl overflow-hidden border border-white/10 bg-black cursor-pointer shadow-md"
                                onClick={() => setPreviewPhotoUrl(pUrl)}
                              >
                                <img
                                  src={pUrl}
                                  alt="完赛照片"
                                  className="w-full h-full object-cover transition duration-200 group-hover:scale-105"
                                />
                                <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition flex items-center justify-center gap-1">
                                  <ExternalLink className="w-4 h-4 text-white" />
                                </div>
                                <button
                                  type="button"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleDeleteRacePhoto(idx, pUrl);
                                  }}
                                  className="absolute top-1 right-1 w-5 h-5 bg-black/70 hover:bg-rose-600 text-white rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition"
                                  title="删除照片"
                                >
                                  <X className="w-3 h-3" />
                                </button>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div className="p-3 bg-white/[0.02] border border-dashed border-white/10 rounded-xl text-center text-xs text-zinc-500">
                            暂无照片，支持上传完赛成绩证书、奖牌合影或现场冲线照 📸
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* ── Race Intelligence Expandable Panel ── */}
                  <div className="pt-2 border-t border-white/5 space-y-2">
                    <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
                      <button
                        type="button"
                        onClick={() => toggleRaceInfoExpand(idx)}
                        className="flex-1 flex items-center justify-between px-3.5 py-2.5 bg-white/[0.03] hover:bg-white/[0.06] border border-white/5 rounded-xl text-xs text-zinc-300 font-semibold transition"
                      >
                        <span className="flex items-center gap-1.5">
                          📋 {Object.values(race.race_info || {}).some(v => v !== null && v !== undefined && v !== "") ? "赛事情报已填写 (点击展开/编辑)" : "赛事情报未填写 (难度/天气/海拔等)"}
                        </span>
                        <span className="text-zinc-500 text-[10px]">{expandedRaceInfo[idx] ? "▲ 收起" : "▼ 展开填写"}</span>
                      </button>

                      <button
                        type="button"
                        onClick={() => handleAutoFetchRaceInfo(idx)}
                        disabled={searchingRaceInfo[idx]}
                        className="flex items-center justify-center gap-1.5 px-3.5 py-2.5 rounded-xl text-xs font-bold bg-purple-600/20 hover:bg-purple-600/30 text-purple-300 border border-purple-500/30 transition active:scale-95 disabled:opacity-50 shrink-0"
                        title="输入比赛名称后，点击即可自动检索赛道爬升、难度、历史气温并自动填充下方表单"
                      >
                        <Zap className={`w-3.5 h-3.5 text-purple-400 ${searchingRaceInfo[idx] ? "animate-spin" : ""}`} />
                        {searchingRaceInfo[idx] ? "正在智能检索赛事情报..." : "⚡ AI 自动搜索填写"}
                      </button>
                    </div>

                    {expandedRaceInfo[idx] && (
                      <div className="p-4 bg-white/[0.02] border border-white/5 rounded-xl space-y-4 text-xs">
                        <div className="flex items-center justify-between pb-2 border-b border-white/5">
                          <span className="font-bold text-zinc-300 flex items-center gap-1.5">
                            {race.race_type?.includes("越野") ? "🏔️ 越野赛情报数据" : "🏅 公路赛事客观情报"}
                          </span>
                          <span className="text-[11px] text-zinc-400">
                            💡 支持手动编辑任意字段，保存后自动同步
                          </span>
                        </div>

                        {race.race_type?.includes("越野") ? (
                          <>
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                              <div>
                                <label className="text-zinc-400 block mb-1">报名赛程 (km)</label>
                                <input
                                  type="number"
                                  placeholder="如 50 / 100"
                                  value={race.race_info?.race_distance_km ?? ""}
                                  onChange={(e) => updateRaceInfo(idx, "race_distance_km", e.target.value ? Number(e.target.value) : null)}
                                  className="w-full bg-[#202026] border border-white/10 rounded-lg px-3 py-2 text-white"
                                />
                              </div>
                              <div>
                                <label className="text-zinc-400 block mb-1">累计爬升 D+ (m)</label>
                                <input
                                  type="number"
                                  placeholder="如 2800"
                                  value={race.race_info?.elevation_gain_m ?? ""}
                                  onChange={(e) => updateRaceInfo(idx, "elevation_gain_m", e.target.value ? Number(e.target.value) : null)}
                                  className="w-full bg-[#202026] border border-white/10 rounded-lg px-3 py-2 text-white"
                                />
                              </div>
                              <div>
                                <label className="text-zinc-400 block mb-1">累计下降 D- (m)</label>
                                <input
                                  type="number"
                                  placeholder="如 2600"
                                  value={race.race_info?.elevation_loss_m ?? ""}
                                  onChange={(e) => updateRaceInfo(idx, "elevation_loss_m", e.target.value ? Number(e.target.value) : null)}
                                  className="w-full bg-[#202026] border border-white/10 rounded-lg px-3 py-2 text-white"
                                />
                              </div>
                              <div>
                                <label className="text-zinc-400 block mb-1">最高点海拔 (m)</label>
                                <input
                                  type="number"
                                  placeholder="如 1918"
                                  value={race.race_info?.max_altitude_m ?? ""}
                                  onChange={(e) => updateRaceInfo(idx, "max_altitude_m", e.target.value ? Number(e.target.value) : null)}
                                  className="w-full bg-[#202026] border border-white/10 rounded-lg px-3 py-2 text-white"
                                />
                              </div>
                              <div>
                                <label className="text-zinc-400 block mb-1">难度等级</label>
                                <select
                                  value={race.race_info?.difficulty_level ?? ""}
                                  onChange={(e) => updateRaceInfo(idx, "difficulty_level", e.target.value || null)}
                                  className="w-full bg-[#202026] border border-white/10 rounded-lg px-3 py-2 text-white"
                                >
                                  <option value="">请选择难度</option>
                                  <option value="入门级">入门级</option>
                                  <option value="进阶级">进阶级</option>
                                  <option value="精英级">精英级</option>
                                  <option value="极限级">极限级</option>
                                </select>
                              </div>
                              <div>
                                <label className="text-zinc-400 block mb-1">地形类型</label>
                                <select
                                  value={race.race_info?.terrain_type ?? ""}
                                  onChange={(e) => updateRaceInfo(idx, "terrain_type", e.target.value || null)}
                                  className="w-full bg-[#202026] border border-white/10 rounded-lg px-3 py-2 text-white"
                                >
                                  <option value="">请选择地形</option>
                                  <option value="山地跑道">山地跑道</option>
                                  <option value="高原草甸">高原草甸</option>
                                  <option value="丛林密林">丛林密林</option>
                                  <option value="岩石峭壁">岩石峭壁</option>
                                  <option value="混合地形">混合地形</option>
                                </select>
                              </div>
                              <div>
                                <label className="text-zinc-400 block mb-1">气候带</label>
                                <select
                                  value={race.race_info?.climate_zone ?? ""}
                                  onChange={(e) => updateRaceInfo(idx, "climate_zone", e.target.value || null)}
                                  className="w-full bg-[#202026] border border-white/10 rounded-lg px-3 py-2 text-white"
                                >
                                  <option value="">请选择气候带</option>
                                  <option value="温带大陆性">温带大陆性</option>
                                  <option value="亚热带季风">亚热带季风</option>
                                  <option value="高寒高原">高寒高原</option>
                                  <option value="热带季风">热带季风</option>
                                </select>
                              </div>
                              <div>
                                <label className="text-zinc-400 block mb-1">强制装备要求</label>
                                <input
                                  type="text"
                                  placeholder="如: 头灯、1.5L水、急救毯"
                                  value={race.race_info?.mandatory_gear ?? ""}
                                  onChange={(e) => updateRaceInfo(idx, "mandatory_gear", e.target.value || null)}
                                  className="w-full bg-[#202026] border border-white/10 rounded-lg px-3 py-2 text-white"
                                />
                              </div>
                              <div className="sm:col-span-2">
                                <label className="text-zinc-400 block mb-1">关门时间说明</label>
                                <input
                                  type="text"
                                  placeholder="如: 总关门 20小时，中途补给站 4个"
                                  value={race.race_info?.cutoff_notes ?? ""}
                                  onChange={(e) => updateRaceInfo(idx, "cutoff_notes", e.target.value || null)}
                                  className="w-full bg-[#202026] border border-white/10 rounded-lg px-3 py-2 text-white"
                                />
                              </div>
                            </div>
                          </>
                        ) : (
                          <>
                            <div className="font-bold text-zinc-300 flex items-center gap-1.5 pb-1 border-b border-white/5">
                              🏅 公路赛事客观情报
                            </div>
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                              <div>
                                <label className="text-zinc-400 block mb-1">赛事等级</label>
                                <select
                                  value={race.race_info?.race_level ?? ""}
                                  onChange={(e) => updateRaceInfo(idx, "race_level", e.target.value || null)}
                                  className="w-full bg-[#202026] border border-white/10 rounded-lg px-3 py-2 text-white"
                                >
                                  <option value="">请选择等级</option>
                                  <option value="世界白金标">世界白金标</option>
                                  <option value="国际金标">国际金标</option>
                                  <option value="IAAF 银标">IAAF 银标</option>
                                  <option value="IAAF 铜标">IAAF 铜标</option>
                                  <option value="国内 A 类认证">国内 A 类认证</option>
                                  <option value="普通大众认证">普通大众认证</option>
                                  <option value="品牌邀请赛">品牌邀请赛</option>
                                </select>
                              </div>
                              <div>
                                <label className="text-zinc-400 block mb-1">赛道特点</label>
                                <select
                                  value={race.race_info?.course_profile ?? ""}
                                  onChange={(e) => updateRaceInfo(idx, "course_profile", e.target.value || null)}
                                  className="w-full bg-[#202026] border border-white/10 rounded-lg px-3 py-2 text-white"
                                >
                                  <option value="">请选择赛道特点</option>
                                  <option value="极速平坦 (破 PB 首选)">极速平坦 (破 PB 首选)</option>
                                  <option value="轻微起伏">轻微起伏</option>
                                  <option value="中等坡度">中等坡度</option>
                                  <option value="丘陵赛道">丘陵赛道</option>
                                  <option value="多爬升挑战赛道">多爬升挑战赛道</option>
                                </select>
                              </div>
                              <div>
                                <label className="text-zinc-400 block mb-1">路面材质</label>
                                <select
                                  value={race.race_info?.course_surface ?? ""}
                                  onChange={(e) => updateRaceInfo(idx, "course_surface", e.target.value || null)}
                                  className="w-full bg-[#202026] border border-white/10 rounded-lg px-3 py-2 text-white"
                                >
                                  <option value="">请选择路面材质</option>
                                  <option value="柏油路">柏油路</option>
                                  <option value="石板路">石板路</option>
                                  <option value="混合路面">混合路面</option>
                                  <option value="碎石路">碎石路</option>
                                </select>
                              </div>
                              <div>
                                <label className="text-zinc-400 block mb-1">赛道净爬升 (m)</label>
                                <input
                                  type="number"
                                  placeholder="如 120"
                                  value={race.race_info?.net_elevation_gain_m ?? ""}
                                  onChange={(e) => updateRaceInfo(idx, "net_elevation_gain_m", e.target.value ? Number(e.target.value) : null)}
                                  className="w-full bg-[#202026] border border-white/10 rounded-lg px-3 py-2 text-white"
                                />
                              </div>
                            </div>
                          </>
                        )}

                        <div className="font-bold text-zinc-300 pt-2 flex items-center gap-1.5 pb-1 border-b border-white/5">
                          🌤️ 历史天气 & 大致规模
                        </div>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                          <div>
                            <label className="text-zinc-400 block mb-1">历史平均气温 (℃)</label>
                            <input
                              type="number"
                              placeholder="如 12"
                              value={race.race_info?.avg_temp_c ?? ""}
                              onChange={(e) => updateRaceInfo(idx, "avg_temp_c", e.target.value ? Number(e.target.value) : null)}
                              className="w-full bg-[#202026] border border-white/10 rounded-lg px-3 py-2 text-white"
                            />
                          </div>
                          {!race.race_type?.includes("越野") && (
                            <div>
                              <label className="text-zinc-400 block mb-1">历史平均湿度 (%)</label>
                              <input
                                type="number"
                                placeholder="如 65"
                                value={race.race_info?.humidity_pct ?? ""}
                                onChange={(e) => updateRaceInfo(idx, "humidity_pct", e.target.value ? Number(e.target.value) : null)}
                                className="w-full bg-[#202026] border border-white/10 rounded-lg px-3 py-2 text-white"
                              />
                            </div>
                          )}
                          <div>
                            <label className="text-zinc-400 block mb-1">天气情况备注</label>
                            <input
                              type="text"
                              placeholder="如: 秋季举办，通常干燥清凉"
                              value={race.race_info?.weather_notes ?? ""}
                              onChange={(e) => updateRaceInfo(idx, "weather_notes", e.target.value || null)}
                              className="w-full bg-[#202026] border border-white/10 rounded-lg px-3 py-2 text-white"
                            />
                          </div>
                          <div>
                            <label className="text-zinc-400 block mb-1">大致参赛人数</label>
                            <input
                              type="number"
                              placeholder="如 10000"
                              value={race.race_info?.typical_participants ?? ""}
                              onChange={(e) => updateRaceInfo(idx, "typical_participants", e.target.value ? Number(e.target.value) : null)}
                              className="w-full bg-[#202026] border border-white/10 rounded-lg px-3 py-2 text-white"
                            />
                          </div>
                          <div className="sm:col-span-2">
                            <label className="text-zinc-400 block mb-1">其他补充备注</label>
                            <input
                              type="text"
                              placeholder="补充说明"
                              value={race.race_info?.custom_notes ?? ""}
                              onChange={(e) => updateRaceInfo(idx, "custom_notes", e.target.value || null)}
                              className="w-full bg-[#202026] border border-white/10 rounded-lg px-3 py-2 text-white"
                            />
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

                          <div className="flex justify-end pt-4">
              <button
                type="submit"
                disabled={saving}
                className="flex items-center gap-2 px-8 py-3.5 rounded-2xl text-base font-bold bg-gradient-to-r from-[#FC4C02] to-[#ff7a45] text-white hover:brightness-110 transition active:scale-95 shadow-xl shadow-[#FC4C02]/25"
              >
                <Save className="w-5 h-5" />
                {saving ? "正在保存..." : "🎯 保存训练目标与生理参数"}
              </button>
            </div>
            </div>
          )}
        </form>
      </main>

      {/* ── Anti-Accidental Deletion Purge Confirm Modal (一键彻底清除防误删弹窗) ── */}
      {showPurgeConfirmModal && (
        <div
          className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4"
          onClick={() => setShowPurgeConfirmModal(false)}
        >
          <div
            className="bg-[#151518] border border-rose-500/30 rounded-3xl max-w-lg w-full p-6 sm:p-8 shadow-2xl space-y-5"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between pb-3 border-b border-white/10">
              <div className="flex items-center gap-2.5">
                <span className="text-2xl">🚨</span>
                <h3 className="text-lg font-black text-rose-400">
                  高危操作：确认清除个人隐私数据
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setShowPurgeConfirmModal(false)}
                className="w-8 h-8 rounded-full bg-white/5 hover:bg-white/10 flex items-center justify-center text-zinc-400 hover:text-white transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="bg-rose-500/10 border border-rose-500/20 rounded-2xl p-4 flex items-start gap-3">
              <span className="text-rose-400 text-lg">⚠️</span>
              <div className="space-y-1">
                <p className="text-xs font-bold text-rose-300">请谨慎确认，清除后数据不可撤销！</p>
                <p className="text-[11px] text-rose-300/80 leading-relaxed">
                  系统将立即从服务器物理抹除您的敏感身份信息，防止任何潜在隐私泄露。
                </p>
              </div>
            </div>

            <div className="bg-[#1c1c20] border border-white/5 rounded-2xl p-4 space-y-3.5 text-xs">
              <div className="space-y-2">
                <p className="font-bold text-rose-400 flex items-center gap-1.5">
                  <span>将被彻底物理抹除的隐私（不可恢复）：</span>
                </p>
                <ul className="space-y-1.5 text-zinc-300 pl-1">
                  <li className="flex items-center gap-2">
                    <span className="text-rose-500 font-bold">✕</span>
                    <span>真实姓名、身份证号码、出生年月日</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <span className="text-rose-500 font-bold">✕</span>
                    <span>紧急联系手机号、个人邮箱、个人简介</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <span className="text-rose-500 font-bold">✕</span>
                    <span>已绑定的 Garmin / 高驰手表授权密码与令牌</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <span className="text-rose-500 font-bold">✕</span>
                    <span>各大跑团 / 大群体花名册中的实名认证登记</span>
                  </li>
                </ul>
              </div>

              <div className="h-px bg-white/10" />

              <div className="space-y-2">
                <p className="font-bold text-emerald-400 flex items-center gap-1.5">
                  <span>将被安全保留的信息（匿名化保护）：</span>
                </p>
                <ul className="space-y-1.5 text-zinc-300 pl-1">
                  <li className="flex items-center gap-2">
                    <span className="text-emerald-400 font-bold">✓</span>
                    <span>历史跑步里程、活动与打卡记录（自动显示为匿名跑者）</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <span className="text-emerald-400 font-bold">✓</span>
                    <span>所在跑团队伍历史总里程与数据统计不受影响</span>
                  </li>
                </ul>
              </div>
            </div>

            <div className="flex items-center gap-3 pt-2">
              <button
                type="button"
                onClick={() => setShowPurgeConfirmModal(false)}
                className="flex-1 py-3 bg-white/5 hover:bg-white/10 border border-white/10 text-white rounded-2xl text-xs font-bold transition"
              >
                取消返回
              </button>
              <button
                type="button"
                disabled={purgingPrivacy}
                onClick={handleExecutePurgePrivacy}
                className="flex-1 py-3 bg-gradient-to-r from-rose-600 to-red-600 hover:from-rose-500 hover:to-red-500 text-white rounded-2xl text-xs font-bold transition shadow-lg shadow-rose-600/30 flex items-center justify-center gap-2 disabled:opacity-50"
              >
                {purgingPrivacy ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>正在彻底清除...</span>
                  </>
                ) : (
                  <span>确认彻底清除</span>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Photo Lightbox Preview Modal ── */}
      {previewPhotoUrl && (
        <div
          className="fixed inset-0 z-50 bg-black/90 backdrop-blur-md flex items-center justify-center p-4"
          onClick={() => setPreviewPhotoUrl(null)}
        >
          <div className="relative max-w-4xl max-h-[90vh] flex flex-col items-center" onClick={(e) => e.stopPropagation()}>
            <button
              type="button"
              onClick={() => setPreviewPhotoUrl(null)}
              className="absolute -top-10 right-0 text-white/80 hover:text-white p-1.5 rounded-full bg-white/10 hover:bg-white/20 transition"
              title="关闭全屏"
            >
              <X className="w-5 h-5" />
            </button>
            <img
              src={previewPhotoUrl}
              alt="完赛照片大图"
              className="max-h-[80vh] max-w-full rounded-2xl shadow-2xl object-contain border border-white/10"
            />
            <div className="mt-3 flex items-center gap-3">
              <a
                href={previewPhotoUrl}
                target="_blank"
                rel="noreferrer"
                className="px-4 py-1.5 rounded-xl bg-white/10 hover:bg-white/20 text-white text-xs font-semibold flex items-center gap-1.5 transition"
              >
                <ExternalLink className="w-3.5 h-3.5" />
                <span>在新窗口查看原图</span>
              </a>
            </div>
          </div>
        </div>
      )}

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
