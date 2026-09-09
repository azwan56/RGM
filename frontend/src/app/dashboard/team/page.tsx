"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Navbar from "@/components/Navbar";
import { supabase } from "@/lib/supabase";
import apiClient from "@/lib/apiClient";
import {
  Users,
  Trophy,
  Plus,
  UserPlus,
  Shield,
  Sparkles,
  ChevronDown,
  Copy,
  Check,
  Flame,
  Activity,
  Heart,
  Moon,
  AlertTriangle,
  Calendar,
  Award,
  Crown,
  Edit2,
  Trash2,
  MessageCircle,
  Send,
  Bot,
  FileText,
  X,
  Target,
  TrendingUp,
  UserMinus,
  ArrowRightLeft
} from "lucide-react";

export default function TeamPage() {
  const [user, setUser] = useState<any>(null);
  const [clubs, setClubs] = useState<any[]>([]);
  const [currentClub, setCurrentClub] = useState<any>(null);
  const [currentRole, setCurrentRole] = useState<string>("member");

  // Tab: 'leaderboard', 'president', 'coach', 'events'
  const [activeTab, setActiveTab] = useState<"leaderboard" | "president" | "coach" | "events">("leaderboard");

  // Data states
  const [loading, setLoading] = useState(true);
  const [dashboardMetrics, setDashboardMetrics] = useState<any>(null);
  const [leaderboard, setLeaderboard] = useState<any[]>([]);
  const [members, setMembers] = useState<any[]>([]);
  const [coachCockpit, setCoachCockpit] = useState<any>(null);
  const [events, setEvents] = useState<any[]>([]);
  const [feed, setFeed] = useState<any[]>([]);

  // Social interaction state
  const [commentInputs, setCommentInputs] = useState<Record<string, string>>({});
  const [submittingComment, setSubmittingComment] = useState<Record<string, boolean>>({});

  // Modals & form states
  const [showJoinModal, setShowJoinModal] = useState(false);
  const [showAllClubsModal, setShowAllClubsModal] = useState(false);
  const [showCreateEventModal, setShowCreateEventModal] = useState(false);
  const [editingEvent, setEditingEvent] = useState<any>(null);
  const [selectedStudentForReport, setSelectedStudentForReport] = useState<any | null>(null);

  const [allClubs, setAllClubs] = useState<any[]>([]);
  const [loadingAllClubs, setLoadingAllClubs] = useState(false);
  const [joiningClubId, setJoiningClubId] = useState<string | null>(null);

  const [inviteCodeInput, setInviteCodeInput] = useState("");

  const [eventTitle, setEventTitle] = useState("");
  const [eventTargetKm, setEventTargetKm] = useState(200);
  const [eventRules, setEventRules] = useState("");

  const router = useRouter();

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      const u = data?.session?.user;
      if (u) {
        setUser(u);
        loadUserClubs(u.id);
        loadAllClubs(u.id);
      } else {
        router.push("/login");
      }
    });
  }, [router]);

  async function loadAllClubs(uid?: string) {
    const effUid = uid || user?.id;
    setLoadingAllClubs(true);
    try {
      const res = await apiClient.get(`/api/team/all-clubs${effUid ? `?user_id=${effUid}` : ""}`);
      setAllClubs(res.data?.clubs || []);
    } catch (e) {
      console.error("Fetch all clubs error:", e);
    } finally {
      setLoadingAllClubs(false);
    }
  }

  async function handleJoinClubDirect(clubId: string) {
    if (!user?.id) return;
    setJoiningClubId(clubId);
    try {
      const res = await apiClient.post("/api/team/join-club", {
        user_id: user.id,
        club_id: clubId,
        privacy_consent: true,
      });
      alert(res.data?.message || "成功加入跑团！");
      if (typeof window !== "undefined") {
        localStorage.setItem("rgm_active_club_id", clubId);
      }
      setShowAllClubsModal(false);
      setShowJoinModal(false);
      await loadUserClubs(user.id);
      await loadAllClubs(user.id);
    } catch (err: any) {
      alert(err.response?.data?.detail || "加入跑团失败，请重试！");
    } finally {
      setJoiningClubId(null);
    }
  }

  async function loadUserClubs(uid: string) {
    setLoading(true);
    try {
      const res = await apiClient.get(`/api/team/my-clubs/${uid}`);
      const clubList = res.data?.clubs || [];
      setClubs(clubList);

      if (clubList.length > 0) {
        let primary = clubList[0];
        const savedClubId = typeof window !== "undefined" ? localStorage.getItem("rgm_active_club_id") : null;
        if (savedClubId) {
          const matched = clubList.find((c: any) => c.id === savedClubId);
          if (matched) primary = matched;
        }
        setCurrentClub(primary);
        setCurrentRole(primary.role || "member");
        if (typeof window !== "undefined") {
          localStorage.setItem("rgm_active_club_id", primary.id);
        }
        loadClubDetails(primary.id, uid);
      } else {
        if (typeof window !== "undefined") {
          localStorage.removeItem("rgm_active_club_id");
        }
        setCurrentClub(null);
        setCurrentRole("member");
        setDashboardMetrics(null);
        setLeaderboard([]);
        setMembers([]);
        setCoachCockpit(null);
        setEvents([]);
        setFeed([]);
      }
    } catch (e) {
      console.error("Fetch user clubs error:", e);
    } finally {
      setLoading(false);
    }
  }

  async function loadClubDetails(clubId: string, uid?: string) {
    const effUid = uid || user?.id;
    if (!effUid) return;
    try {
      const [dashRes, lbRes, memRes, coachRes, evtRes, feedRes] = await Promise.all([
        apiClient.get(`/api/team/${clubId}/dashboard`),
        apiClient.get(`/api/team/${clubId}/leaderboard`),
        apiClient.get(`/api/team/${clubId}/members`),
        apiClient.get(`/api/team/${clubId}/coach-cockpit?coach_uid=${effUid}`),
        apiClient.get(`/api/team/${clubId}/events`),
        apiClient.get(`/api/team/${clubId}/feed?uid=${effUid}`),
      ]);

      setDashboardMetrics(dashRes.data?.metrics || null);
      setLeaderboard(lbRes.data?.leaderboard || []);
      setMembers(memRes.data?.members || []);
      setCoachCockpit(coachRes.data || null);
      setEvents(evtRes.data?.events || []);
      setFeed(feedRes.data?.feed || []);
    } catch (e) {
      console.error("Load club details error:", e);
    }
  }

  function handleSwitchClub(club: any) {
    setCurrentClub(club);
    setCurrentRole(club.role || "member");
    if (typeof window !== "undefined") {
      localStorage.setItem("rgm_active_club_id", club.id);
    }
    loadClubDetails(club.id);
  }

  async function handleToggleLike(activityId: string) {
    if (!user?.id) return;
    try {
      const res = await apiClient.post(`/api/team/activities/${activityId}/like`, {
        user_id: user.id,
      });
      setFeed((prev) =>
        prev.map((item) => {
          if (item.id === activityId) {
            return {
              ...item,
              has_liked: res.data.liked,
              likes_count: res.data.likes_count,
            };
          }
          return item;
        })
      );
    } catch (e) {
      console.error("Like error:", e);
    }
  }

  async function handlePostComment(activityId: string) {
    const content = (commentInputs[activityId] || "").trim();
    if (!content || !user?.id) return;
    setSubmittingComment((prev) => ({ ...prev, [activityId]: true }));
    try {
      const res = await apiClient.post(`/api/team/activities/${activityId}/comments`, {
        user_id: user.id,
        content: content,
        author_name: user?.user_metadata?.display_name || user?.email?.split("@")[0] || "跑友",
        author_avatar: user?.user_metadata?.avatar_url || "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80",
      });

      const newCmt = res.data.comment;
      setFeed((prev) =>
        prev.map((item) => {
          if (item.id === activityId) {
            return {
              ...item,
              comments: [...(item.comments || []), newCmt],
            };
          }
          return item;
        })
      );
      setCommentInputs((prev) => ({ ...prev, [activityId]: "" }));
    } catch (e) {
      alert("评论发布失败");
    } finally {
      setSubmittingComment((prev) => ({ ...prev, [activityId]: false }));
    }
  }

  async function handleDeleteComment(activityId: string, commentId: string) {
    if (!user?.id) return;
    try {
      await apiClient.delete(`/api/team/activities/${activityId}/comments/${commentId}?user_id=${user.id}`);
      setFeed((prev) =>
        prev.map((item) => {
          if (item.id === activityId) {
            return {
              ...item,
              comments: (item.comments || []).filter((c: any) => c.id !== commentId),
            };
          }
          return item;
        })
      );
    } catch (e) {
      alert("删除失败");
    }
  }

  async function handleJoinClub(e: React.FormEvent) {
    e.preventDefault();
    if (!inviteCodeInput.trim() || !user?.id) return;
    try {
      const res = await apiClient.post("/api/team/join", {
        user_id: user.id,
        invite_code: inviteCodeInput.trim().toUpperCase(),
        privacy_consent: true,
      });
      alert(res.data.message || "加入跑团成功！");
      setShowJoinModal(false);
      setInviteCodeInput("");
      await loadUserClubs(user.id);
      await loadAllClubs(user.id);
    } catch (err: any) {
      alert(err.response?.data?.detail || "加入失败，请核对邀请码！");
    }
  }

  async function handleUpdateMemberRole(targetUid: string, role: string) {
    if (!currentClub || !user?.id) return;
    try {
      await apiClient.post(`/api/team/${currentClub.id}/role`, {
        operator_uid: user.id,
        target_uid: targetUid,
        role: role,
      });
      alert(`已成功将该成员设为【${role === "coach" ? "认证教练" : role === "owner" ? "团长" : "普通跑者"}】`);
      loadClubDetails(currentClub.id);
    } catch (e: any) {
      alert("操作失败");
    }
  }

  async function handleRemoveMember(targetUid: string, displayName: string) {
    if (!currentClub) return;
    if (!confirm(`确定要将跑者【${displayName}】从当前跑团中移除吗？此操作不可撤销。`)) return;
    try {
      await apiClient.delete(`/api/team/${currentClub.id}/members/${targetUid}`);
      alert(`已成功将【${displayName}】移出跑团`);
      loadClubDetails(currentClub.id);
    } catch (e: any) {
      alert(e.response?.data?.detail || "移除成员失败");
    }
  }

  async function handleTransferOwner(targetUid: string, displayName: string) {
    if (!currentClub || !user?.id) return;
    if (!confirm(`确定要将跑团【${currentClub.name}】的团长身份移交给【${displayName}】吗？移交后您将转为认证教练身份。`)) return;
    try {
      await apiClient.post(`/api/team/${currentClub.id}/role`, {
        operator_uid: user.id,
        target_uid: targetUid,
        role: "owner",
      });
      alert(`已成功将团长身份移交给【${displayName}】！`);
      loadUserClubs(user.id);
    } catch (e: any) {
      alert(e.response?.data?.detail || "移交团长失败");
    }
  }

  function formatPb(seconds: any) {
    if (!seconds) return "—";
    const num = Number(seconds);
    if (isNaN(num) || num <= 0) return String(seconds);
    const h = Math.floor(num / 3600);
    const m = Math.floor((num % 3600) / 60);
    const s = num % 60;
    return `${h}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  }

  function handleOpenEditEvent(evt: any) {
    setEditingEvent(evt);
    setEventTitle(evt.title || "");
    setEventTargetKm(evt.target_km || 200);
    setEventRules(evt.rules || "");
    setShowCreateEventModal(true);
  }

  async function handleDeleteEvent(eventId: string) {
    if (!currentClub) return;
    if (!confirm("确定要删除该跑团挑战赛活动吗？")) return;
    try {
      await apiClient.delete(`/api/team/${currentClub.id}/events/${eventId}`);
      alert("活动已成功删除");
      loadClubDetails(currentClub.id);
    } catch (e: any) {
      alert("删除失败");
    }
  }

  async function handleCreateOrEditEvent(e: React.FormEvent) {
    e.preventDefault();
    if (!currentClub || !eventTitle.trim() || !user?.id) return;
    try {
      if (editingEvent) {
        await apiClient.put(`/api/team/${currentClub.id}/events/${editingEvent.id}`, {
          operator_uid: user.id,
          title: eventTitle.trim(),
          target_km: Number(eventTargetKm),
          rules: eventRules.trim(),
        });
        alert("挑战赛修改成功！");
      } else {
        await apiClient.post(`/api/team/${currentClub.id}/events`, {
          operator_uid: user.id,
          title: eventTitle.trim(),
          target_km: Number(eventTargetKm),
          rules: eventRules.trim(),
        });
        alert("活动挑战发布成功！");
      }
      setShowCreateEventModal(false);
      setEditingEvent(null);
      setEventTitle("");
      setEventRules("");
      setActiveTab("events");
      loadClubDetails(currentClub.id);
    } catch (e: any) {
      alert("发布或修改失败");
    }
  }

  return (
    <div className="min-h-screen bg-[#070708] text-white">
      <Navbar />

      {loading ? (
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-24 text-center text-zinc-500">
          <p>跑团数据加载中...</p>
        </div>
      ) : !currentClub ? (
        <main className="max-w-5xl mx-auto px-4 sm:px-6 py-10 space-y-10">
          <div className="bg-gradient-to-b from-[#18181c] to-[#121215] border border-white/10 rounded-3xl p-8 sm:p-10 text-center shadow-2xl">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-[#FC4C02]/10 border border-[#FC4C02]/30 text-3xl mb-4">
              🏃‍♂️
            </div>
            <h1 className="text-2xl sm:text-3xl font-black text-white mb-2">
              欢迎来到跑团中心
            </h1>
            <p className="text-sm text-zinc-400 max-w-xl mx-auto leading-relaxed mb-6">
              请在下方浏览平台所有已创建跑团并选择加入，与队友共同参加月度跑量挑战、查看英雄榜与教练负荷监控！
            </p>
            <div className="flex items-center justify-center">
              <button
                onClick={() => setShowJoinModal(true)}
                className="inline-flex items-center gap-2 px-5 py-2 bg-white/5 hover:bg-white/10 border border-white/10 text-xs font-semibold text-zinc-300 hover:text-white rounded-xl transition"
              >
                <UserPlus className="w-3.5 h-3.5 text-[#FC4C02]" />
                已有邀请码？点此输入邀请码加入
              </button>
            </div>
          </div>

          {/* All Created Clubs Section */}
          <div className="space-y-5">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <div className="flex items-center gap-2.5">
                <span className="text-lg font-black text-white">🏆 平台所有跑团</span>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-[#FC4C02]/20 text-[#FC4C02] border border-[#FC4C02]/30">
                  {allClubs.length} 个跑团
                </span>
              </div>
              <span className="text-xs text-zinc-400">选择您感兴趣的跑团，点击即可一键加入开启训练</span>
            </div>

            {loadingAllClubs ? (
              <div className="py-12 text-center text-xs text-zinc-500">正在加载跑团列表...</div>
            ) : allClubs.length === 0 ? (
              <div className="bg-[#141416] border border-white/5 rounded-3xl p-12 text-center text-zinc-400">
                平台暂无已创建跑团，请联系平台超级管理员创建！
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                {allClubs.map((club) => (
                  <div
                    key={club.id}
                    className="bg-[#141416] hover:bg-[#18181c] border border-white/10 hover:border-[#FC4C02]/40 rounded-3xl p-6 transition flex flex-col justify-between shadow-xl"
                  >
                    <div>
                      <div className="flex items-start gap-4 mb-4">
                        <img
                          src={club.logo_url || "https://images.unsplash.com/photo-1552674605-db6ffd4facb5?w=300&auto=format&fit=crop&q=80"}
                          alt={club.name}
                          className="w-16 h-16 rounded-2xl object-cover border-2 border-[#FC4C02]/30 shrink-0 shadow-md"
                        />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <h3 className="text-lg font-black text-white truncate">{club.name}</h3>
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-white/10 text-zinc-300">
                              📍 {club.city || "上海"}
                            </span>
                          </div>
                          <p className="text-xs text-zinc-400 mt-1.5 line-clamp-2 leading-relaxed">
                            {club.description || "科学耐力训练 · PB 突破与健康长久奔跑。"}
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center gap-4 py-3 px-3.5 bg-black/30 rounded-2xl border border-white/5 text-xs text-zinc-400 mb-5">
                        <div>
                          <span className="text-zinc-500">团长: </span>
                          <span className="text-white font-semibold">{club.owner_name || "平台指定"}</span>
                        </div>
                        <div className="w-px h-3 bg-white/10" />
                        <div>
                          <span className="text-zinc-500">成员: </span>
                          <span className="text-[#FC4C02] font-bold">{club.member_count || 1} 人</span>
                        </div>
                      </div>
                    </div>

                    <div className="pt-2">
                      <button
                        onClick={() => handleJoinClubDirect(club.id)}
                        disabled={joiningClubId === club.id}
                        className="w-full py-3 bg-[#FC4C02] hover:bg-[#ff6426] text-white rounded-2xl text-xs font-bold transition shadow-lg shadow-[#FC4C02]/20 flex items-center justify-center gap-2"
                      >
                        <UserPlus className="w-4 h-4" />
                        {joiningClubId === club.id ? "正在加入..." : "选择参加此跑团"}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Feature Highlights Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="bg-[#141416] border border-white/5 rounded-2xl p-6 flex items-start gap-4">
              <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-xl shrink-0">
                🥇
              </div>
              <div>
                <h3 className="text-sm font-bold text-white mb-1">跑团月度英雄榜</h3>
                <p className="text-xs text-zinc-400 leading-relaxed">
                  自动汇聚全体团员月跑量与配速排名，良性竞逐突破个人 PB。
                </p>
              </div>
            </div>

            <div className="bg-[#141416] border border-white/5 rounded-2xl p-6 flex items-start gap-4">
              <div className="w-10 h-10 rounded-xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-xl shrink-0">
                🏆
              </div>
              <div>
                <h3 className="text-sm font-bold text-white mb-1">专属跑量挑战赛</h3>
                <p className="text-xs text-zinc-400 leading-relaxed">
                  团长与教练可随时发起公里数打卡挑战，团员达标点亮荣誉勋章。
                </p>
              </div>
            </div>

            <div className="bg-[#141416] border border-white/5 rounded-2xl p-6 flex items-start gap-4">
              <div className="w-10 h-10 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-xl shrink-0">
                💬
              </div>
              <div>
                <h3 className="text-sm font-bold text-white mb-1">跑友圈动态与 AI 点评</h3>
                <p className="text-xs text-zinc-400 leading-relaxed">
                  同步手表跑步记录后自动生成 AI 战报，支持队友点赞与留言互动。
                </p>
              </div>
            </div>

            <div className="bg-[#141416] border border-white/5 rounded-2xl p-6 flex items-start gap-4">
              <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-xl shrink-0">
                🧢
              </div>
              <div>
                <h3 className="text-sm font-bold text-white mb-1">教练学员体能罗盘</h3>
                <p className="text-xs text-zinc-400 leading-relaxed">
                  科学监控全员 CTL/ATL/TSB 负荷与心率变异性，预防过度训练与伤病。
                </p>
              </div>
            </div>
          </div>
        </main>
      ) : (
        <main className="max-w-6xl mx-auto px-4 sm:px-6 py-8 space-y-8">
          {/* Header with Multi-Club Selector and Actions */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 bg-gradient-to-r from-[#18181c] via-[#121215] to-[#18181c] border border-white/10 rounded-3xl p-6 shadow-2xl">
            <div className="flex items-center gap-4">
              <img
                src={currentClub.logo_url || "https://images.unsplash.com/photo-1552674605-db6ffd4facb5?w=300&auto=format&fit=crop&q=80"}
                alt="Club Logo"
                className="w-16 h-16 rounded-2xl object-cover border-2 border-[#FC4C02]/40 shadow-lg"
              />
              <div>
                <div className="flex items-center gap-2.5">
                  <h1 className="text-xl sm:text-2xl font-black text-white">
                    {currentClub.name}
                  </h1>
                  <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-[#FC4C02]/20 text-[#FC4C02] border border-[#FC4C02]/30">
                    {currentRole === "owner" ? "👑 跑团主理人" : currentRole === "coach" ? "🧢 认证教练" : "🏃 核心团员"}
                  </span>
                </div>
                <p className="text-xs text-zinc-400 mt-1 line-clamp-1 max-w-xl">
                  {currentClub.description || "精英跑者联盟，追求 PB 突破与健康长久奔跑。"}
                </p>
                <div className="flex items-center gap-3 mt-2">
                  <span className="text-[11px] text-zinc-500">📍 {currentClub.city || "上海"}</span>
                </div>
                {clubs.length > 1 && (
                  <div className="flex items-center gap-2 mt-3 flex-wrap">
                    <span className="text-[11px] text-zinc-400 font-medium">切换跑团:</span>
                    {clubs.map((c: any) => (
                      <button
                        key={c.id}
                        onClick={() => handleSwitchClub(c)}
                        className={`px-3 py-1 rounded-xl text-xs font-semibold transition ${
                          currentClub.id === c.id
                            ? "bg-[#FC4C02] text-white shadow-md shadow-[#FC4C02]/20 font-bold"
                            : "bg-white/5 hover:bg-white/10 text-zinc-400 hover:text-white border border-white/5"
                        }`}
                      >
                        {c.name} {currentClub.id === c.id && "✓"}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Quick Action Buttons */}
            <div className="flex items-center gap-3 flex-wrap">
              <button
                onClick={() => setShowAllClubsModal(true)}
                className="flex items-center gap-1.5 px-4 py-2.5 bg-[#FC4C02] hover:bg-[#ff6426] text-white rounded-2xl text-xs font-bold transition shadow-lg shadow-[#FC4C02]/20"
              >
                <Users className="w-4 h-4" />
                浏览全部跑团 ({allClubs.length})
              </button>
              <button
                onClick={() => setShowJoinModal(true)}
                className="flex items-center gap-1.5 px-4 py-2.5 bg-white/5 border border-white/10 hover:bg-white/10 text-white rounded-2xl text-xs font-bold transition shadow-sm"
              >
                <UserPlus className="w-4 h-4 text-[#FC4C02]" />
                输入邀请码
              </button>
            </div>
          </div>

        {/* 4-Tab Navigation */}
        <div className="flex items-center gap-2 border-b border-white/10 pb-3 overflow-x-auto">
          <button
            onClick={() => setActiveTab("leaderboard")}
            className={`flex items-center gap-2 px-5 py-2.5 rounded-2xl text-xs font-bold transition ${
              activeTab === "leaderboard"
                ? "bg-[#FC4C02] text-white shadow-lg shadow-[#FC4C02]/25"
                : "bg-white/5 text-zinc-400 hover:text-white"
            }`}
          >
            <Trophy className="w-4 h-4" />
            跑团总览与排行榜
          </button>

          {(currentRole === "owner" || currentRole === "coach") && (
            <button
              onClick={() => setActiveTab("coach")}
              className={`flex items-center gap-2 px-5 py-2.5 rounded-2xl text-xs font-bold transition ${
                activeTab === "coach"
                  ? "bg-purple-600 text-white shadow-lg shadow-purple-600/25"
                  : "bg-white/5 text-zinc-400 hover:text-white"
              }`}
            >
              <Activity className="w-4 h-4" />
              🧢 教练学员体能罗盘
            </button>
          )}

          {(currentRole === "owner" || currentRole === "coach" || user?.is_admin) && (
            <button
              onClick={() => setActiveTab("president")}
              className={`flex items-center gap-2 px-5 py-2.5 rounded-2xl text-xs font-bold transition ${
                activeTab === "president"
                  ? "bg-amber-600 text-white shadow-lg shadow-amber-600/25"
                  : "bg-white/5 text-zinc-400 hover:text-white"
              }`}
            >
              <Users className="w-4 h-4" />
              👥 跑团成员与管理
            </button>
          )}

          <button
            onClick={() => setActiveTab("events")}
            className={`flex items-center gap-2 px-5 py-2.5 rounded-2xl text-xs font-bold transition ${
              activeTab === "events"
                ? "bg-blue-600 text-white shadow-lg shadow-blue-600/25"
                : "bg-white/5 text-zinc-400 hover:text-white"
            }`}
          >
            <Award className="w-4 h-4" />
            🏆 跑团挑战赛与活动 ({events.length})
          </button>
        </div>

        {/* ── TAB 1: 跑团总览与排行榜 ── */}
        {activeTab === "leaderboard" && (
          <div className="space-y-8">
            {/* Top Stat Metrics */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div className="bg-[#121215] border border-white/5 rounded-3xl p-5">
                <span className="text-xs text-zinc-400 font-medium">🏃 本月跑团总里程</span>
                <div className="text-2xl font-black text-white mt-1">
                  {dashboardMetrics?.total_month_km || "16.0"} <span className="text-xs text-[#FC4C02]">km</span>
                </div>
              </div>
              <div className="bg-[#121215] border border-white/5 rounded-3xl p-5">
                <span className="text-xs text-zinc-400 font-medium">👥 注册跑者人数</span>
                <div className="text-2xl font-black text-white mt-1">
                  {dashboardMetrics?.members_count || members.length || 1} <span className="text-xs text-zinc-500">人</span>
                </div>
              </div>
              <div className="bg-[#121215] border border-white/5 rounded-3xl p-5">
                <span className="text-xs text-zinc-400 font-medium">🧢 认证专业教练</span>
                <div className="text-2xl font-black text-purple-400 mt-1">
                  {dashboardMetrics?.coaches_count || 1} <span className="text-xs text-zinc-500">位</span>
                </div>
              </div>
              <div className="bg-[#121215] border border-white/5 rounded-3xl p-5">
                <span className="text-xs text-zinc-400 font-medium">🎯 进行中挑战赛</span>
                <div className="text-2xl font-black text-emerald-400 mt-1">
                  {dashboardMetrics?.active_events_count || events.length || 1} <span className="text-xs text-zinc-500">项</span>
                </div>
              </div>
            </div>

            {/* Leaderboard Table */}
            <div className="bg-[#121215] border border-white/5 rounded-3xl p-6 sm:p-8 shadow-xl">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h2 className="text-lg font-black text-white flex items-center gap-2">
                    <Trophy className="w-5 h-5 text-amber-400" />
                    本月跑团月度英雄榜
                  </h2>
                  <p className="text-xs text-zinc-400 mt-0.5">按当月累计跑量实时竞逐排名</p>
                </div>
                <span className="px-3 py-1 rounded-full text-xs font-bold bg-white/5 text-zinc-300">
                  实时更新
                </span>
              </div>

              <div className="space-y-3">
                {leaderboard.map((runner) => (
                  <div
                    key={runner.user_id}
                    className={`flex items-center justify-between p-4 rounded-2xl border transition ${
                      runner.rank === 1
                        ? "bg-amber-500/10 border-amber-500/30"
                        : runner.rank === 2
                        ? "bg-zinc-400/10 border-zinc-400/20"
                        : runner.rank === 3
                        ? "bg-orange-500/10 border-orange-500/20"
                        : "bg-[#18181c] border-white/5"
                    }`}
                  >
                    <div className="flex items-center gap-4">
                      <div className="w-8 flex items-center justify-center font-black text-base">
                        {runner.rank === 1 ? "🥇" : runner.rank === 2 ? "🥈" : runner.rank === 3 ? "🥉" : `#${runner.rank}`}
                      </div>
                      <img
                        src={runner.avatar_url || "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80"}
                        alt={runner.display_name}
                        className="w-11 h-11 rounded-full object-cover border border-white/10"
                      />
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-bold text-white">{runner.display_name}</span>
                          {runner.role === "owner" && (
                            <span className="text-[10px] px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300 font-bold">团长</span>
                          )}
                          {runner.role === "coach" && (
                            <span className="text-[10px] px-1.5 py-0.2 rounded bg-purple-500/20 text-purple-300 font-bold">教练</span>
                          )}
                        </div>
                        <span className="text-xs text-zinc-400">
                          目标: {runner.target_km} km · 完成度 {runner.progress_pct}%
                        </span>
                      </div>
                    </div>

                    <div className="text-right">
                      <div className="text-lg font-black text-white">
                        {runner.distance_km} <span className="text-xs text-[#FC4C02]">km</span>
                      </div>
                      <div className="w-24 h-1.5 bg-zinc-800 rounded-full overflow-hidden mt-1 ml-auto">
                        <div
                          className="h-full bg-gradient-to-r from-[#FC4C02] to-amber-400 rounded-full"
                          style={{ width: `${Math.min(100, runner.progress_pct)}%` }}
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Recent Group Activities Feed with AI Coach Comments & Social Interaction */}
            <div className="bg-[#121215] border border-white/5 rounded-3xl p-6 sm:p-8 space-y-6">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-black text-white flex items-center gap-2">
                  <Flame className="w-5 h-5 text-[#FC4C02]" />
                  跑团打卡动态墙 · Canova教练点评与跑友互动
                </h2>
                <span className="text-xs text-zinc-400">点击 ❤️ 点赞 / 💬 发表跑友评论</span>
              </div>

              {feed.length > 0 ? (
                <div className="space-y-6">
                  {feed.map((act) => (
                    <div
                      key={act.id}
                      className="p-6 bg-[#18181c] border border-white/10 rounded-3xl space-y-4 hover:border-white/20 transition shadow-xl"
                    >
                      {/* Top: Runner & Activity Info */}
                      <div className="flex items-center justify-between gap-4">
                        <div className="flex items-center gap-3">
                          <img
                            src={act.avatar_url || "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80"}
                            alt={act.display_name}
                            className="w-12 h-12 rounded-full object-cover border border-white/10"
                          />
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-bold text-white">{act.display_name}</span>
                              <span className="text-xs text-zinc-400">· {act.name}</span>
                            </div>
                            <div className="text-xs text-zinc-400 mt-0.5 flex items-center gap-2 flex-wrap">
                              <span>⏱️ 配速 <strong className="text-white">{act.avg_pace_str}</strong></span>
                              <span>·</span>
                              <span>❤️ 心率 <strong className="text-rose-400">{act.average_heartrate || "—"} bpm</strong></span>
                              <span>·</span>
                              <span>⚡ 负荷 TRIMP <strong className="text-amber-400">{act.trimp || 50}</strong></span>
                              <span>·</span>
                              <span className="text-[11px] text-zinc-500">{act.start_time?.slice(0, 16)?.replace("T", " ")}</span>
                            </div>
                          </div>
                        </div>

                        <div className="text-right flex-shrink-0">
                          <div className="text-2xl font-black text-[#FC4C02]">
                            {roundKm(act.distance_meters)} <span className="text-xs text-zinc-400">km</span>
                          </div>
                        </div>
                      </div>

                      {/* AI Coach Critique Bubble */}
                      <div className="bg-gradient-to-r from-purple-950/30 via-[#1e1b2e] to-indigo-950/30 border border-purple-500/25 rounded-2xl p-4 text-xs leading-relaxed text-zinc-200">
                        <div className="flex items-center gap-2 font-bold text-purple-300 mb-1.5">
                          <Bot className="w-4 h-4 text-purple-400" />
                          <span>Canova教练专属点评</span>
                          <span className="text-[10px] px-2 py-0.2 rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/30">
                            智能生成
                          </span>
                        </div>
                        <p className="text-xs text-zinc-300 leading-relaxed font-sans">
                          {act.ai_journal || "正在基于 Canova 耐力生理模型生成点评..."}
                        </p>
                      </div>

                      {/* Social Actions: Like & Comment Counter */}
                      <div className="flex items-center justify-between pt-2 border-t border-white/5">
                        <div className="flex items-center gap-3">
                          <button
                            onClick={() => handleToggleLike(act.id)}
                            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold transition border ${
                              act.has_liked
                                ? "bg-rose-500/15 border-rose-500/40 text-rose-400 shadow-sm"
                                : "bg-white/5 border-white/10 text-zinc-400 hover:text-white hover:bg-white/10"
                            }`}
                          >
                            <Heart className={`w-3.5 h-3.5 ${act.has_liked ? "fill-rose-500 text-rose-500" : ""}`} />
                            <span>{act.has_liked ? "已点赞" : "点赞"} ({act.likes_count || 0})</span>
                          </button>

                          <div className="flex items-center gap-1 text-xs text-zinc-400 font-medium">
                            <MessageCircle className="w-3.5 h-3.5 text-zinc-500" />
                            <span>{act.comments?.length || 0} 条跑友留言</span>
                          </div>
                        </div>
                      </div>

                      {/* Comments Thread */}
                      {act.comments && act.comments.length > 0 && (
                        <div className="space-y-2 bg-[#121214] border border-white/5 rounded-2xl p-4">
                          {act.comments.map((cmt: any) => (
                            <div key={cmt.id} className="flex items-start justify-between gap-3 text-xs">
                              <div className="flex items-start gap-2.5">
                                <img
                                  src={cmt.author_avatar || "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80"}
                                  alt={cmt.author_name}
                                  className="w-6 h-6 rounded-full object-cover mt-0.5"
                                />
                                <div>
                                  <div className="flex items-center gap-2">
                                    <span className="font-bold text-white text-[11px]">{cmt.author_name}</span>
                                    <span className="text-[10px] text-zinc-500">{cmt.created_at?.slice(5, 16)?.replace("T", " ")}</span>
                                  </div>
                                  <p className="text-zinc-300 mt-0.5 text-xs">{cmt.content}</p>
                                </div>
                              </div>

                              {(cmt.user_id === user?.id || currentRole === "owner") && (
                                <button
                                  onClick={() => handleDeleteComment(act.id, cmt.id)}
                                  className="text-[10px] text-zinc-500 hover:text-rose-400 transition"
                                >
                                  删除
                                </button>
                              )}
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Post Comment Input Form */}
                      <div className="flex items-center gap-2 pt-1">
                        <input
                          type="text"
                          value={commentInputs[act.id] || ""}
                          onChange={(e) =>
                            setCommentInputs((prev) => ({ ...prev, [act.id]: e.target.value }))
                          }
                          onKeyDown={(e) => {
                            if (e.key === "Enter") handlePostComment(act.id);
                          }}
                          placeholder="在 Canova教练评语后给队友鼓励或写句评语..."
                          className="flex-1 bg-[#121214] border border-white/10 rounded-xl px-3.5 py-2 text-xs text-white placeholder:text-zinc-600 focus:outline-none focus:border-[#FC4C02]"
                        />
                        <button
                          onClick={() => handlePostComment(act.id)}
                          disabled={submittingComment[act.id] || !(commentInputs[act.id] || "").trim()}
                          className="flex items-center gap-1 px-4 py-2 bg-[#FC4C02] hover:bg-[#ff6426] disabled:opacity-40 text-white rounded-xl text-xs font-bold transition shadow-md shadow-[#FC4C02]/20"
                        >
                          <Send className="w-3.5 h-3.5" />
                          发送
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-zinc-500 text-center py-8">暂无队员近期打卡，快去完成今日跑步吧！</p>
              )}
            </div>
          </div>
        )}

        {/* ── TAB 2: 👥 跑团成员与管理 ── */}
        {activeTab === "president" && (currentRole === "owner" || currentRole === "coach" || user?.is_admin) && (
          <div className="space-y-6">
            <div className="bg-[#121215] border border-white/5 rounded-3xl p-6 sm:p-8">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
                <div>
                  <h2 className="text-lg font-black text-white flex items-center gap-2">
                    <Users className="w-5 h-5 text-amber-400" />
                    跑团成员与权限管理
                  </h2>
                  <p className="text-xs text-zinc-400 mt-0.5">管理跑团跑者成员、指定/撤销认证教练、移交团长或移除成员</p>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-zinc-400">共 <strong className="text-white">{members.length}</strong> 位团员</span>
                  {(currentRole === "owner" || user?.is_admin) && (
                    <button
                      onClick={() => {
                        setEditingEvent(null);
                        setEventTitle("");
                        setEventTargetKm(200);
                        setEventRules("");
                        setShowCreateEventModal(true);
                      }}
                      className="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white rounded-2xl text-xs font-bold transition shadow-lg shadow-amber-600/20"
                    >
                      + 发起跑团挑战赛
                    </button>
                  )}
                </div>
              </div>

              {/* Members Table */}
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-white/10 text-[11px] font-bold text-zinc-400 uppercase">
                      <th className="py-3 px-4">跑者</th>
                      <th className="py-3 px-4">当前角色</th>
                      <th className="py-3 px-4">月跑量计划与完成度</th>
                      <th className="py-3 px-4">全马 PB</th>
                      <th className="py-3 px-4">加入时间</th>
                      <th className="py-3 px-4 text-right">管理操作</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5 text-xs font-medium text-zinc-300">
                    {members.map((m) => (
                      <tr key={m.user_id} className="hover:bg-white/[0.02]">
                        <td className="py-3.5 px-4 flex items-center gap-3">
                          <img
                            src={m.avatar_url || "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80"}
                            alt={m.display_name}
                            className="w-8 h-8 rounded-full object-cover"
                          />
                          <div>
                            <span className="font-bold text-white block">{m.display_name}</span>
                            <span className="text-[10px] text-zinc-500">{m.user_id}</span>
                          </div>
                        </td>
                        <td className="py-3.5 px-4">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            m.role === "owner" ? "bg-amber-500/20 text-amber-300" : m.role === "coach" ? "bg-purple-500/20 text-purple-300" : "bg-zinc-800 text-zinc-400"
                          }`}>
                            {m.role === "owner" ? "👑 团长" : m.role === "coach" ? "🧢 教练" : "普通跑者"}
                          </span>
                        </td>
                        <td className="py-3.5 px-4">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-white text-xs">{m.month_km || 0} / {m.target_km || 200} km</span>
                            <span className={`text-[10px] px-1.5 py-0.2 rounded font-bold ${
                              (m.completion_rate || 0) >= 100 ? "bg-emerald-500/20 text-emerald-400" : "bg-white/5 text-zinc-400"
                            }`}>
                              {m.completion_rate || 0}%
                            </span>
                          </div>
                          <div className="w-32 bg-white/10 h-1.5 rounded-full overflow-hidden mt-1.5">
                            <div
                              className={`h-full rounded-full transition-all ${
                                (m.completion_rate || 0) >= 100 ? "bg-emerald-400" : "bg-[#FC4C02]"
                              }`}
                              style={{ width: `${Math.min(100, Math.max(2, m.completion_rate || 0))}%` }}
                            />
                          </div>
                        </td>
                        <td className="py-3.5 px-4 font-mono text-zinc-300">{formatPb(m.marathon_pb)}</td>
                        <td className="py-3.5 px-4 text-zinc-400">{m.joined_at?.slice(0, 10)}</td>
                        <td className="py-3.5 px-4 text-right space-x-2">
                          {(currentRole === "owner" || user?.is_admin) ? (
                            <>
                              {m.role !== "owner" ? (
                                <>
                                  {m.role !== "coach" ? (
                                    <button
                                      onClick={() => handleUpdateMemberRole(m.user_id, "coach")}
                                      className="px-2.5 py-1 bg-purple-600/30 hover:bg-purple-600 text-purple-200 hover:text-white rounded-lg text-[11px] font-bold transition"
                                      title="指定为认证教练"
                                    >
                                      设为教练
                                    </button>
                                  ) : (
                                    <button
                                      onClick={() => handleUpdateMemberRole(m.user_id, "member")}
                                      className="px-2.5 py-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-lg text-[11px] font-bold transition"
                                      title="取消教练权限"
                                    >
                                      取消教练
                                    </button>
                                  )}

                                  <button
                                    onClick={() => handleTransferOwner(m.user_id, m.display_name)}
                                    className="px-2.5 py-1 bg-amber-500/10 hover:bg-amber-500/25 text-amber-300 rounded-lg text-[11px] font-bold transition"
                                    title="移交团长身份"
                                  >
                                    移交团长
                                  </button>

                                  <button
                                    onClick={() => handleRemoveMember(m.user_id, m.display_name)}
                                    className="px-2.5 py-1 bg-rose-500/10 hover:bg-rose-500/25 text-rose-400 hover:text-rose-300 rounded-lg text-[11px] font-bold transition inline-flex items-center gap-1"
                                    title="将该跑者移出跑团"
                                  >
                                    <UserMinus className="w-3 h-3" />
                                    移除
                                  </button>
                                </>
                              ) : (
                                <span className="text-[11px] text-amber-400 font-bold">最高管理者</span>
                              )}
                            </>
                          ) : (
                            <span className="text-[11px] text-zinc-500">仅团长可管理</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* ── TAB 3: 🧢 教练学员体能监控与计划罗盘 ── */}
        {activeTab === "coach" && (currentRole === "owner" || currentRole === "coach" || user?.is_admin) && (
          <div className="space-y-6">
            {/* Status Summary Cards */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div className="bg-[#121215] border border-emerald-500/30 rounded-3xl p-5">
                <span className="text-xs text-emerald-400 font-bold">🟢 巅峰状态 (TSB &gt; 5)</span>
                <div className="text-2xl font-black text-white mt-1">
                  {coachCockpit?.summary?.peak_count || 0} <span className="text-xs text-zinc-500">人</span>
                </div>
                <p className="text-[10px] text-zinc-400 mt-1">适宜安排比赛测速或高强度课</p>
              </div>

              <div className="bg-[#121215] border border-blue-500/30 rounded-3xl p-5">
                <span className="text-xs text-blue-400 font-bold">🔵 专项适应 (TSB -30~5)</span>
                <div className="text-2xl font-black text-white mt-1">
                  {coachCockpit?.summary?.optimal_count || 0} <span className="text-xs text-zinc-500">人</span>
                </div>
                <p className="text-[10px] text-zinc-400 mt-1">身体良好吸收负荷，按计划推进</p>
              </div>

              <div className="bg-[#121215] border border-amber-500/30 rounded-3xl p-5">
                <span className="text-xs text-amber-400 font-bold">🟡 疲劳积累 (TSB -50~-30)</span>
                <div className="text-2xl font-black text-white mt-1">
                  {coachCockpit?.summary?.tired_count || 0} <span className="text-xs text-zinc-500">人</span>
                </div>
                <p className="text-[10px] text-zinc-400 mt-1">建议穿插低心率排酸轻松跑</p>
              </div>

              <div className="bg-[#121215] border border-rose-500/30 rounded-3xl p-5">
                <span className="text-xs text-rose-400 font-bold">🔴 伤病预警 (TSB &lt; -50)</span>
                <div className="text-2xl font-black text-white mt-1">
                  {coachCockpit?.summary?.danger_count || 0} <span className="text-xs text-zinc-500">人</span>
                </div>
                <p className="text-[10px] text-zinc-400 mt-1">过度训练风险，需强制休整</p>
              </div>
            </div>

            {/* Students Matrix Table */}
            <div className="bg-[#121215] border border-white/5 rounded-3xl p-6 sm:p-8">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
                <div>
                  <h2 className="text-lg font-black text-white flex items-center gap-2">
                    <Shield className="w-5 h-5 text-purple-400" />
                    全队学员跑量计划、进度与生理负荷监控大盘
                  </h2>
                  <p className="text-xs text-zinc-400 mt-0.5">
                    * 整合每位学员的个人跑量计划进度、Garmin 生理负荷(CTL/ATL/TSB) 与 Canova 科学训练诊断报告
                  </p>
                </div>
              </div>

              <div className="space-y-5">
                {(coachCockpit?.students || []).map((student: any) => (
                  <div
                    key={student.user_id}
                    className="p-6 bg-[#18181c] border border-white/5 hover:border-white/10 rounded-2xl flex flex-col gap-4 transition shadow-lg"
                  >
                    {/* Top Row: Info + Badges */}
                    <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                      <div className="flex items-center gap-4">
                        <img
                          src={student.avatar_url || "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80"}
                          alt={student.display_name}
                          className="w-12 h-12 rounded-full object-cover border border-white/10"
                        />
                        <div>
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-base font-bold text-white">{student.display_name}</span>
                            <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              student.status_level === "peak"
                                ? "bg-emerald-500/20 text-emerald-300"
                                : student.status_level === "optimal"
                                ? "bg-blue-500/20 text-blue-300"
                                : student.status_level === "tired"
                                ? "bg-amber-500/20 text-amber-300"
                                : student.status_level === "danger"
                                ? "bg-rose-500/20 text-rose-300"
                                : "bg-zinc-800 text-zinc-400"
                            }`}>
                              {student.status_text}
                            </span>
                            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-purple-500/20 text-purple-300">
                              {student.canova_phase || "基础准备期"}
                            </span>
                          </div>
                          <div className="flex items-center gap-3 text-xs text-zinc-400 mt-1.5 flex-wrap">
                            <span>全马 PB: <strong className="text-white font-mono">{formatPb(student.marathon_pb)}</strong></span>
                            <span>·</span>
                            <span>静息心率: <strong className={student.resting_heart_rate ? "text-rose-400" : "text-zinc-500"}>{student.resting_heart_rate ? `${student.resting_heart_rate} bpm` : "—"}</strong></span>
                            <span>·</span>
                            <span>夜间 HRV: <strong className={student.hrv_ms ? "text-cyan-400" : "text-zinc-500"}>{student.hrv_ms ? `${student.hrv_ms} ms` : "—"}</strong></span>
                            <span>·</span>
                            <span>睡眠得分: <strong className={student.sleep_score ? "text-emerald-400" : "text-zinc-500"}>{student.sleep_score ? `${student.sleep_score} 分` : "—"}</strong></span>
                          </div>
                        </div>
                      </div>

                      {/* Right: CTL/ATL/TSB Badges + Report Trigger */}
                      <div className="flex items-center gap-3 self-start md:self-auto flex-wrap">
                        <div className="flex items-center gap-3 bg-[#121215] px-4 py-2.5 rounded-xl border border-white/5">
                          <div className="text-center">
                            <span className="text-[10px] text-zinc-500 block">CTL 体能</span>
                            <span className="text-xs font-black text-blue-400">
                              {student.ctl > 0 ? student.ctl : "—"}
                            </span>
                          </div>
                          <div className="text-center">
                            <span className="text-[10px] text-zinc-500 block">ATL 疲劳</span>
                            <span className="text-xs font-black text-purple-400">
                              {student.atl > 0 ? student.atl : "—"}
                            </span>
                          </div>
                          <div className="text-center">
                            <span className="text-[10px] text-zinc-500 block">TSB 状况</span>
                            <span className={`text-xs font-black ${
                              student.ctl > 0 || student.atl > 0
                                ? (student.tsb >= 0 ? "text-emerald-400" : "text-amber-400")
                                : "text-zinc-500"
                            }`}>
                              {student.ctl > 0 || student.atl > 0 ? (student.tsb > 0 ? `+${student.tsb}` : student.tsb) : "—"}
                            </span>
                          </div>
                        </div>

                        <button
                          onClick={() => setSelectedStudentForReport(student)}
                          className="px-3.5 py-2.5 bg-purple-600/20 hover:bg-purple-600 text-purple-200 hover:text-white rounded-xl text-xs font-bold transition flex items-center gap-1.5 border border-purple-500/30 shadow-sm"
                        >
                          <FileText className="w-3.5 h-3.5" />
                          学员诊断报告
                        </button>
                      </div>
                    </div>

                    {/* Middle Row: Monthly Running Plan Progress Bar */}
                    <div className="bg-[#121215] border border-white/5 rounded-xl p-4">
                      <div className="flex items-center justify-between text-xs mb-2">
                        <div className="flex items-center gap-2">
                          <Target className="w-4 h-4 text-[#FC4C02]" />
                          <span className="text-zinc-300 font-bold">月跑量目标计划:</span>
                          <span className="text-white font-mono font-bold text-sm">
                            {student.month_km} <span className="text-zinc-500 font-normal">/ {student.target_km || 200} km</span>
                          </span>
                          <span className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                            student.completion_rate >= 100
                              ? "bg-emerald-500/20 text-emerald-400"
                              : student.pacing_status === "ahead"
                              ? "bg-blue-500/20 text-blue-400"
                              : student.pacing_status === "lagging"
                              ? "bg-amber-500/20 text-amber-400"
                              : "bg-white/5 text-zinc-300"
                          }`}>
                            {student.completion_rate || 0}% ({student.pacing_text || "按计划推进"})
                          </span>
                        </div>
                        <div className="text-zinc-400 text-xs hidden sm:block">
                          剩余: <strong className="text-white font-mono">{student.remaining_km || 0} km</strong> · 建议日均: <strong className="text-[#FC4C02] font-mono">{student.suggested_daily_km || 0} km/天</strong>
                        </div>
                      </div>

                      {/* Progress Track */}
                      <div className="w-full bg-white/5 h-2.5 rounded-full overflow-hidden relative">
                        <div
                          className={`h-full rounded-full transition-all ${
                            student.completion_rate >= 100
                              ? "bg-emerald-400"
                              : student.pacing_status === "ahead"
                              ? "bg-blue-400"
                              : student.pacing_status === "lagging"
                              ? "bg-amber-400"
                              : "bg-[#FC4C02]"
                          }`}
                          style={{ width: `${Math.min(100, Math.max(2, student.completion_rate || 0))}%` }}
                        />
                      </div>

                      <div className="flex items-center justify-between text-[11px] text-zinc-500 mt-2">
                        <span>近7天完成: <strong className="text-zinc-300">{student.km_7d || 0} km</strong> ({student.runs_7d_count || 0}次训练)</span>
                        <span className="sm:hidden text-zinc-400">
                          剩余 {student.remaining_km || 0}km (日均 {student.suggested_daily_km || 0}km)
                        </span>
                      </div>
                    </div>

                    {/* Bottom Row: Coach Diagnosis Recommendation */}
                    <div className="text-xs text-zinc-300 bg-purple-950/20 border border-purple-500/20 rounded-xl px-4 py-3 flex items-start gap-2.5">
                      <span className="text-purple-400 font-bold shrink-0">💡 教练科学指导:</span>
                      <span className="text-zinc-300 leading-relaxed">{student.coach_diagnosis || "暂无具体诊断建议"}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ── Coach Student Deep Report Modal ── */}
        {selectedStudentForReport && (
          <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
            <div className="bg-[#151518] border border-white/10 rounded-3xl p-6 sm:p-8 max-w-3xl w-full max-h-[90vh] overflow-y-auto space-y-6 shadow-2xl relative">
              {/* Header */}
              <div className="flex items-center justify-between border-b border-white/10 pb-4">
                <div className="flex items-center gap-4">
                  <img
                    src={selectedStudentForReport.avatar_url || "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80"}
                    alt={selectedStudentForReport.display_name}
                    className="w-14 h-14 rounded-full object-cover border-2 border-purple-500/50"
                  />
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-xl font-black text-white">{selectedStudentForReport.display_name}</h3>
                      <span className="text-xs px-2 py-0.5 rounded font-bold bg-purple-500/20 text-purple-300">
                        {selectedStudentForReport.canova_phase || "基础准备期"}
                      </span>
                    </div>
                    <p className="text-xs text-zinc-400 mt-1">
                      全马 PB: <strong className="text-white font-mono">{formatPb(selectedStudentForReport.marathon_pb)}</strong>
                      {" · "}
                      半马 PB: <strong className="text-white font-mono">{formatPb(selectedStudentForReport.half_pb)}</strong>
                      {selectedStudentForReport.height && selectedStudentForReport.weight && (
                        <>
                          {" · "}
                          身高体重: <strong className="text-zinc-300">{selectedStudentForReport.height}cm / {selectedStudentForReport.weight}kg</strong>
                        </>
                      )}
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setSelectedStudentForReport(null)}
                  className="p-2 text-zinc-400 hover:text-white bg-white/5 hover:bg-white/10 rounded-full transition"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* 1. 2026 全年 12 个月跑量规划梯队图 */}
              <div className="bg-[#101013] border border-white/5 rounded-2xl p-5">
                <div className="flex items-center justify-between mb-4">
                  <h4 className="text-sm font-bold text-white flex items-center gap-2">
                    <Calendar className="w-4 h-4 text-purple-400" />
                    2026 全年跑量计划目标规划 (1~12月)
                  </h4>
                  <span className="text-xs text-zinc-400">
                    当前月份: <strong className="text-[#FC4C02]">{new Date().getMonth() + 1} 月</strong>
                  </span>
                </div>

                <div className="grid grid-cols-4 sm:grid-cols-6 md:grid-cols-12 gap-2 text-center">
                  {(selectedStudentForReport.monthly_targets || Array(12).fill(200)).map((t: number, idx: number) => {
                    const isCurrent = idx === new Date().getMonth();
                    return (
                      <div
                        key={idx}
                        className={`p-2.5 rounded-xl border transition ${
                          isCurrent
                            ? "bg-[#FC4C02]/15 border-[#FC4C02] text-white shadow-md shadow-[#FC4C02]/10"
                            : "bg-white/[0.02] border-white/5 text-zinc-400"
                        }`}
                      >
                        <span className={`text-[11px] block font-bold ${isCurrent ? "text-[#FC4C02]" : "text-zinc-500"}`}>
                          {idx + 1}月
                        </span>
                        <span className="text-xs font-mono font-black mt-1 block">
                          {t}
                          <span className="text-[9px] font-normal text-zinc-500 block">km</span>
                        </span>
                        {isCurrent && (
                          <span className="text-[9px] text-emerald-400 font-bold block mt-1">
                            进行中
                          </span>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* 2. 当月进度指标 */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div className="bg-[#101013] border border-white/5 rounded-2xl p-4 text-center">
                  <span className="text-[11px] text-zinc-500 block">本月目标</span>
                  <span className="text-lg font-black text-white font-mono mt-0.5 block">{selectedStudentForReport.target_km || 200} km</span>
                </div>
                <div className="bg-[#101013] border border-white/5 rounded-2xl p-4 text-center">
                  <span className="text-[11px] text-zinc-500 block">已完成跑量</span>
                  <span className="text-lg font-black text-emerald-400 font-mono mt-0.5 block">{selectedStudentForReport.month_km || 0} km</span>
                </div>
                <div className="bg-[#101013] border border-white/5 rounded-2xl p-4 text-center">
                  <span className="text-[11px] text-zinc-500 block">计划完成度</span>
                  <span className="text-lg font-black text-[#FC4C02] font-mono mt-0.5 block">{selectedStudentForReport.completion_rate || 0}%</span>
                </div>
                <div className="bg-[#101013] border border-white/5 rounded-2xl p-4 text-center">
                  <span className="text-[11px] text-zinc-500 block">建议日均跑量</span>
                  <span className="text-lg font-black text-blue-400 font-mono mt-0.5 block">{selectedStudentForReport.suggested_daily_km || 0} km</span>
                </div>
              </div>

              {/* 3. 生理状态与疲劳状况 */}
              <div className="bg-[#101013] border border-white/5 rounded-2xl p-5">
                <h4 className="text-sm font-bold text-white flex items-center gap-2 mb-4">
                  <Activity className="w-4 h-4 text-cyan-400" />
                  生理机能状态与训练负荷监控
                </h4>
                <div className="grid grid-cols-3 sm:grid-cols-6 gap-3 text-center">
                  <div className="bg-white/[0.02] border border-white/5 rounded-xl p-3">
                    <span className="text-[10px] text-zinc-500 block">CTL 体能储备</span>
                    <span className="text-sm font-black text-blue-400 font-mono mt-1 block">
                      {selectedStudentForReport.ctl > 0 ? selectedStudentForReport.ctl : "—"}
                    </span>
                  </div>
                  <div className="bg-white/[0.02] border border-white/5 rounded-xl p-3">
                    <span className="text-[10px] text-zinc-500 block">ATL 近期疲劳</span>
                    <span className="text-sm font-black text-purple-400 font-mono mt-1 block">
                      {selectedStudentForReport.atl > 0 ? selectedStudentForReport.atl : "—"}
                    </span>
                  </div>
                  <div className="bg-white/[0.02] border border-white/5 rounded-xl p-3">
                    <span className="text-[10px] text-zinc-500 block">TSB 竞技状况</span>
                    <span className={`text-sm font-black font-mono mt-1 block ${
                      selectedStudentForReport.ctl > 0 || selectedStudentForReport.atl > 0
                        ? (selectedStudentForReport.tsb >= 0 ? "text-emerald-400" : "text-amber-400")
                        : "text-zinc-500"
                    }`}>
                      {selectedStudentForReport.ctl > 0 || selectedStudentForReport.atl > 0 ? selectedStudentForReport.tsb : "—"}
                    </span>
                  </div>
                  <div className="bg-white/[0.02] border border-white/5 rounded-xl p-3">
                    <span className="text-[10px] text-zinc-500 block">静息心率</span>
                    <span className="text-sm font-black text-rose-400 font-mono mt-1 block">
                      {selectedStudentForReport.resting_heart_rate ? `${selectedStudentForReport.resting_heart_rate} bpm` : "—"}
                    </span>
                  </div>
                  <div className="bg-white/[0.02] border border-white/5 rounded-xl p-3">
                    <span className="text-[10px] text-zinc-500 block">夜间 HRV</span>
                    <span className="text-sm font-black text-cyan-400 font-mono mt-1 block">
                      {selectedStudentForReport.hrv_ms ? `${selectedStudentForReport.hrv_ms} ms` : "—"}
                    </span>
                  </div>
                  <div className="bg-white/[0.02] border border-white/5 rounded-xl p-3">
                    <span className="text-[10px] text-zinc-500 block">睡眠质量</span>
                    <span className="text-sm font-black text-emerald-400 font-mono mt-1 block">
                      {selectedStudentForReport.sleep_score ? `${selectedStudentForReport.sleep_score} 分` : "—"}
                    </span>
                  </div>
                </div>
              </div>

              {/* 4. 教练科学指导与 Canova 建议 */}
              <div className="bg-purple-950/20 border border-purple-500/30 rounded-2xl p-5">
                <div className="flex items-center gap-2 mb-2">
                  <Shield className="w-4 h-4 text-purple-400" />
                  <h4 className="text-sm font-bold text-purple-300">Canova 科学训练期与教练专属指导</h4>
                </div>
                <p className="text-xs text-zinc-300 leading-relaxed">
                  {selectedStudentForReport.coach_diagnosis}
                </p>
              </div>

              {/* 5. 近期跑步记录明细 */}
              {selectedStudentForReport.recent_activities?.length > 0 && (
                <div className="bg-[#101013] border border-white/5 rounded-2xl p-5">
                  <h4 className="text-sm font-bold text-white flex items-center gap-2 mb-3">
                    <Flame className="w-4 h-4 text-amber-400" />
                    近期跑步与训练记录 (前 5 条)
                  </h4>
                  <div className="divide-y divide-white/5 text-xs">
                    {selectedStudentForReport.recent_activities.map((act: any, idx: number) => (
                      <div key={idx} className="py-2.5 flex items-center justify-between">
                        <div>
                          <span className="text-white font-bold block">{act.name}</span>
                          <span className="text-[10px] text-zinc-500">{act.start_time?.slice(0, 16).replace("T", " ")}</span>
                        </div>
                        <div className="text-right">
                          <span className="text-emerald-400 font-mono font-bold">{act.distance_km} km</span>
                          <span className="text-[10px] text-zinc-400 ml-2">({act.duration_mins} 分钟)</span>
                          {act.avg_hr && (
                            <span className="text-[10px] text-rose-400 ml-2">均心: {act.avg_hr}</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── TAB 4: 🏆 跑团挑战赛与活动 ── */}
        {activeTab === "events" && (
          <div className="space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <h2 className="text-lg font-black text-white flex items-center gap-2">
                  <Award className="w-5 h-5 text-blue-400" />
                  跑团活动与月度挑战赛
                </h2>
                <p className="text-xs text-zinc-400 mt-0.5">全团共同参与，用公里数兑换专属荣誉与完赛勋章</p>
              </div>

              {(currentRole === "owner" || currentRole === "coach") && (
                <button
                  onClick={() => {
                    setEditingEvent(null);
                    setEventTitle("");
                    setEventTargetKm(200);
                    setEventRules("");
                    setShowCreateEventModal(true);
                  }}
                  className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-2xl text-xs font-bold transition shadow-lg shadow-blue-600/20 self-start sm:self-auto"
                >
                  <Plus className="w-4 h-4" />
                  发起新挑战 / 活动
                </button>
              )}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {events.map((evt) => (
                <div key={evt.id} className="bg-[#121215] border border-white/10 rounded-3xl p-6 sm:p-8 shadow-xl flex flex-col justify-between">
                  <div>
                    <div className="flex items-center justify-between mb-3">
                      <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-blue-500/20 text-blue-300">
                        <Award className="w-3.5 h-3.5" />
                        月度里程挑战赛
                      </div>

                      {/* Edit / Delete actions for Owner/Coach */}
                      {(currentRole === "owner" || currentRole === "coach") && (
                        <div className="flex items-center gap-1.5">
                          <button
                            onClick={() => handleOpenEditEvent(evt)}
                            className="px-2.5 py-1 bg-white/5 hover:bg-white/10 text-zinc-300 hover:text-white rounded-lg text-[11px] font-bold transition flex items-center gap-1"
                          >
                            <Edit2 className="w-3 h-3" /> 编辑
                          </button>
                          <button
                            onClick={() => handleDeleteEvent(evt.id)}
                            className="px-2.5 py-1 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 hover:text-rose-300 rounded-lg text-[11px] font-bold transition flex items-center gap-1"
                          >
                            <Trash2 className="w-3 h-3" /> 删除
                          </button>
                        </div>
                      )}
                    </div>

                    <h3 className="text-xl font-black text-white mb-2">{evt.title}</h3>
                    <p className="text-xs text-zinc-300 leading-relaxed mb-4">{evt.rules}</p>
                  </div>

                  <div className="pt-4 border-t border-white/5 flex items-center justify-between">
                    <span className="text-xs text-zinc-400">
                      目标里程: <strong className="text-white text-sm">{evt.target_km} km</strong>
                    </span>
                    <span className="text-xs text-emerald-400 font-bold">
                      进行中 · 9月打卡
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>
      )}

      {/* Join Club Modal */}
      {showJoinModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="bg-[#151518] border border-white/10 rounded-3xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <h3 className="text-lg font-black text-white">加入跑团</h3>
            <p className="text-xs text-zinc-400">请输入团长分享的 6 位专属邀请码：</p>
            <form onSubmit={handleJoinClub} className="space-y-4">
              <input
                type="text"
                maxLength={6}
                value={inviteCodeInput}
                onChange={(e) => setInviteCodeInput(e.target.value.toUpperCase())}
                placeholder="例如: RGM888"
                className="w-full bg-[#1c1c20] border border-white/10 rounded-2xl px-4 py-3 text-center text-xl font-mono font-bold tracking-widest text-white uppercase focus:outline-none focus:border-[#FC4C02]"
              />
              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={() => setShowJoinModal(false)}
                  className="flex-1 py-3 bg-zinc-800 hover:bg-zinc-700 text-white rounded-2xl text-xs font-bold transition"
                >
                  取消
                </button>
                <button
                  type="submit"
                  className="flex-1 py-3 bg-[#FC4C02] hover:bg-[#ff6426] text-white rounded-2xl text-xs font-bold transition"
                >
                  立即加入
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* All Clubs Modal (Browse and Select/Join) */}
      {showAllClubsModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="bg-[#151518] border border-white/10 rounded-3xl max-w-2xl w-full p-6 shadow-2xl space-y-4 max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between pb-3 border-b border-white/10">
              <div>
                <h3 className="text-lg font-black text-white flex items-center gap-2">
                  🏆 平台所有跑团 ({allClubs.length})
                </h3>
                <p className="text-xs text-zinc-400 mt-0.5">浏览平台已创建跑团，点击即可切换查看或加入新跑团</p>
              </div>
              <button
                onClick={() => setShowAllClubsModal(false)}
                className="w-8 h-8 rounded-full bg-white/5 hover:bg-white/10 flex items-center justify-center text-zinc-400 hover:text-white transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="overflow-y-auto space-y-3.5 pr-1 flex-1">
              {allClubs.map((club) => {
                const isCurrent = currentClub?.id === club.id;
                const isMember = clubs.some((c) => c.id === club.id) || club.is_member;

                return (
                  <div
                    key={club.id}
                    className={`border rounded-2xl p-4 flex items-center justify-between gap-4 transition ${
                      isCurrent
                        ? "bg-[#FC4C02]/10 border-[#FC4C02]/40"
                        : "bg-[#1c1c20] border-white/5 hover:border-white/20"
                    }`}
                  >
                    <div className="flex items-center gap-3.5 min-w-0">
                      <img
                        src={club.logo_url || "https://images.unsplash.com/photo-1552674605-db6ffd4facb5?w=300&auto=format&fit=crop&q=80"}
                        alt={club.name}
                        className="w-12 h-12 rounded-xl object-cover border border-white/10 shrink-0"
                      />
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <h4 className="text-sm font-bold text-white truncate">{club.name}</h4>
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-white/10 text-zinc-300">
                            {club.city || "上海"}
                          </span>
                          {isCurrent && (
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-[#FC4C02] text-white">
                              当前查看
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-zinc-400 truncate mt-0.5 max-w-md">
                          {club.description || "精英跑者联盟，追求 PB 突破与健康长久奔跑。"}
                        </p>
                        <div className="flex items-center gap-3 text-[11px] text-zinc-500 mt-1">
                          <span>团长: {club.owner_name || "平台指定"}</span>
                          <span>·</span>
                          <span className="text-zinc-400">{club.member_count || 1} 位跑者</span>
                        </div>
                      </div>
                    </div>

                    <div className="shrink-0">
                      {isCurrent ? (
                        <span className="text-xs text-[#FC4C02] font-bold px-3 py-1.5 bg-[#FC4C02]/10 rounded-xl">
                          正在查看
                        </span>
                      ) : isMember ? (
                        <button
                          onClick={() => {
                            const target = clubs.find((c) => c.id === club.id) || club;
                            handleSwitchClub(target);
                            setShowAllClubsModal(false);
                          }}
                          className="px-4 py-2 bg-white/10 hover:bg-white/20 text-white rounded-xl text-xs font-bold transition"
                        >
                          切换查看
                        </button>
                      ) : (
                        <button
                          onClick={() => handleJoinClubDirect(club.id)}
                          disabled={joiningClubId === club.id}
                          className="px-4 py-2 bg-[#FC4C02] hover:bg-[#ff6426] text-white rounded-xl text-xs font-bold transition shadow-md shadow-[#FC4C02]/20"
                        >
                          {joiningClubId === club.id ? "加入中..." : "+ 参加此跑团"}
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Create / Edit Event Modal */}
      {showCreateEventModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="bg-[#151518] border border-white/10 rounded-3xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <h3 className="text-lg font-black text-white">
              {editingEvent ? "编辑跑团挑战赛" : "发起跑团月度挑战赛"}
            </h3>
            <form onSubmit={handleCreateOrEditEvent} className="space-y-3">
              <div>
                <label className="text-xs text-zinc-400 block mb-1">挑战赛标题</label>
                <input
                  type="text"
                  required
                  value={eventTitle}
                  onChange={(e) => setEventTitle(e.target.value)}
                  placeholder="例如: 9月 200km 破风进阶挑战"
                  className="w-full bg-[#1c1c20] border border-white/10 rounded-2xl px-4 py-2.5 text-xs text-white focus:outline-none focus:border-blue-500"
                />
              </div>
              <div>
                <label className="text-xs text-zinc-400 block mb-1">目标跑量 (km)</label>
                <input
                  type="number"
                  required
                  value={eventTargetKm}
                  onChange={(e) => setEventTargetKm(Number(e.target.value))}
                  className="w-full bg-[#1c1c20] border border-white/10 rounded-2xl px-4 py-2.5 text-xs text-white focus:outline-none focus:border-blue-500"
                />
              </div>
              <div>
                <label className="text-xs text-zinc-400 block mb-1">挑战规则说明</label>
                <textarea
                  rows={3}
                  value={eventRules}
                  onChange={(e) => setEventRules(e.target.value)}
                  placeholder="完赛即可获得专属完赛电子勋章与跑团定制奖章..."
                  className="w-full bg-[#1c1c20] border border-white/10 rounded-2xl px-4 py-2 text-xs text-white focus:outline-none focus:border-blue-500"
                />
              </div>
              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setShowCreateEventModal(false);
                    setEditingEvent(null);
                  }}
                  className="flex-1 py-3 bg-zinc-800 hover:bg-zinc-700 text-white rounded-2xl text-xs font-bold transition"
                >
                  取消
                </button>
                <button
                  type="submit"
                  className="flex-1 py-3 bg-blue-600 hover:bg-blue-500 text-white rounded-2xl text-xs font-bold transition shadow-lg shadow-blue-600/20"
                >
                  {editingEvent ? "保存修改" : "立即发布"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

function roundKm(meters?: number): string {
  if (!meters) return "0.0";
  return (meters / 1000.0).toFixed(1);
}
