"use client";

import { useEffect, useState } from "react";
import Navbar from "@/components/Navbar";
import axios from "axios";
import {
  Shield,
  Crown,
  Edit2,
  Users,
  Plus,
  Lock,
  Mail,
  LogOut,
  Check,
  RefreshCw,
  X,
  Building,
  AlertCircle,
  Copy,
  Upload,
  Image as ImageIcon
} from "lucide-react";

export default function AdminPage() {
  const [adminToken, setAdminToken] = useState<string | null>(null);
  const [adminInfo, setAdminInfo] = useState<any>(null);

  // Login form state
  const [email, setEmail] = useState("admin@rgm.com");
  const [password, setPassword] = useState("");
  const [loginLoading, setLoginLoading] = useState(false);
  const [loginError, setLoginError] = useState("");

  // Data states
  const [clubs, setClubs] = useState<any[]>([]);
  const [users, setUsers] = useState<any[]>([]);
  const [loadingData, setLoadingData] = useState(false);

  // Modal states
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showAssignModal, setShowAssignModal] = useState(false);
  const [activeClub, setActiveClub] = useState<any>(null);

  // Form states
  const [newClubName, setNewClubName] = useState("");
  const [newClubCity, setNewClubCity] = useState("上海");
  const [newClubDesc, setNewClubDesc] = useState("");
  const [newClubLogo, setNewClubLogo] = useState("");
  const [newClubOwnerId, setNewClubOwnerId] = useState("");

  const [editClubName, setEditClubName] = useState("");
  const [editClubCity, setEditClubCity] = useState("");
  const [editClubDesc, setEditClubDesc] = useState("");
  const [editClubLogo, setEditClubLogo] = useState("");
  const [editClubInviteCode, setEditClubInviteCode] = useState("");

  const [selectedNewOwnerId, setSelectedNewOwnerId] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [actionSuccessMsg, setActionSuccessMsg] = useState("");
  const [actionErrorMsg, setActionErrorMsg] = useState("");
  const [copiedCode, setCopiedCode] = useState("");
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const [uploadLogoError, setUploadLogoError] = useState("");

  async function handleFileUpload(file: File, isEdit: boolean) {
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      alert("请选择有效的图片文件（JPG, PNG, WebP 等）");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      alert("图片文件大小不能超过 10MB");
      return;
    }

    setUploadingLogo(true);
    setUploadLogoError("");

    try {
      const formData = new FormData();
      formData.append("file", file);

      const headers: Record<string, string> = {
        "Content-Type": "multipart/form-data",
      };
      if (adminToken) {
        headers["Authorization"] = `Bearer ${adminToken}`;
      }

      const res = await axios.post("/api/admin/upload-club-logo", formData, { headers });
      const uploadedUrl = res.data?.logo_url || res.data?.url;
      if (uploadedUrl) {
        if (isEdit) {
          setEditClubLogo(uploadedUrl);
        } else {
          setNewClubLogo(uploadedUrl);
        }
      }
    } catch (err: any) {
      console.error("Upload error:", err);
      const msg = err.response?.data?.detail || "上传图片失败，请稍后重试";
      setUploadLogoError(msg);
      alert(msg);
    } finally {
      setUploadingLogo(false);
    }
  }

  useEffect(() => {
    const savedToken = localStorage.getItem("rgm_admin_token");
    const savedInfo = localStorage.getItem("rgm_admin_info");
    if (savedToken) {
      setAdminToken(savedToken);
      if (savedInfo) {
        try {
          setAdminInfo(JSON.parse(savedInfo));
        } catch (e) {}
      }
      loadAdminData(savedToken);
    }
  }, []);

  async function handleAdminLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoginLoading(true);
    setLoginError("");

    try {
      const res = await axios.post("/api/admin/login", {
        email: email.trim(),
        password: password.trim()
      });

      const { token, admin } = res.data;
      setAdminToken(token);
      setAdminInfo(admin);
      localStorage.setItem("rgm_admin_token", token);
      localStorage.setItem("rgm_admin_info", JSON.stringify(admin));
      loadAdminData(token);
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || "登录失败，请检查密码";
      setLoginError(msg);
    } finally {
      setLoginLoading(false);
    }
  }

  function handleAdminLogout() {
    localStorage.removeItem("rgm_admin_token");
    localStorage.removeItem("rgm_admin_info");
    setAdminToken(null);
    setAdminInfo(null);
    setClubs([]);
    setUsers([]);
  }

  async function loadAdminData(token: string) {
    setLoadingData(true);
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const [clubsRes, usersRes] = await Promise.all([
        axios.get("/api/admin/clubs", { headers }),
        axios.get("/api/admin/users", { headers }),
      ]);
      setClubs(clubsRes.data?.clubs || []);
      const userList = usersRes.data?.users || [];
      setUsers(userList);
      if (userList.length > 0 && !newClubOwnerId) {
        setNewClubOwnerId(userList[0].id);
      }
    } catch (err: any) {
      if (err.response?.status === 401 || err.response?.status === 403) {
        handleAdminLogout();
        setLoginError("超级管理员认证已过期，请重新登录");
      }
    } finally {
      setLoadingData(false);
    }
  }

  function openCreateModal() {
    setNewClubName("");
    setNewClubCity("上海");
    setNewClubDesc("");
    setNewClubLogo("");
    if (users.length > 0) setNewClubOwnerId(users[0].id);
    setActionSuccessMsg("");
    setActionErrorMsg("");
    setShowCreateModal(true);
  }

  function openEditModal(club: any) {
    setActiveClub(club);
    setEditClubName(club.name || "");
    setEditClubCity(club.city || "上海");
    setEditClubDesc(club.description || "");
    setEditClubLogo(club.logo_url || "");
    setEditClubInviteCode(club.invite_code || "");
    setActionSuccessMsg("");
    setActionErrorMsg("");
    setShowEditModal(true);
  }

  function openAssignModal(club: any) {
    setActiveClub(club);
    setSelectedNewOwnerId(club.owner_id || (users[0]?.id || ""));
    setActionSuccessMsg("");
    setActionErrorMsg("");
    setShowAssignModal(true);
  }

  async function handleCreateClub(e: React.FormEvent) {
    e.preventDefault();
    if (!adminToken) return;
    setSubmitting(true);
    setActionErrorMsg("");

    try {
      const res = await axios.post(
        "/api/admin/clubs",
        {
          name: newClubName.trim(),
          city: newClubCity.trim(),
          description: newClubDesc.trim(),
          logo_url: newClubLogo.trim() || undefined,
          owner_id: newClubOwnerId
        },
        { headers: { Authorization: `Bearer ${adminToken}` } }
      );

      setActionSuccessMsg(res.data.message || "跑团创建成功！");
      setShowCreateModal(false);
      loadAdminData(adminToken);
    } catch (err: any) {
      setActionErrorMsg(err.response?.data?.detail || "创建跑团失败");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleEditClub(e: React.FormEvent) {
    e.preventDefault();
    if (!adminToken || !activeClub) return;
    setSubmitting(true);
    setActionErrorMsg("");

    try {
      const res = await axios.put(
        `/api/admin/clubs/${activeClub.id}`,
        {
          name: editClubName.trim(),
          city: editClubCity.trim(),
          description: editClubDesc.trim(),
          logo_url: editClubLogo.trim() || undefined,
          invite_code: editClubInviteCode.trim() || undefined
        },
        { headers: { Authorization: `Bearer ${adminToken}` } }
      );

      setActionSuccessMsg("跑团信息更新成功！");
      setShowEditModal(false);
      loadAdminData(adminToken);
    } catch (err: any) {
      setActionErrorMsg(err.response?.data?.detail || "更新跑团失败");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleAssignOwner(e: React.FormEvent) {
    e.preventDefault();
    if (!adminToken || !activeClub) return;
    setSubmitting(true);
    setActionErrorMsg("");

    try {
      const res = await axios.post(
        `/api/admin/clubs/${activeClub.id}/assign-owner`,
        { new_owner_id: selectedNewOwnerId },
        { headers: { Authorization: `Bearer ${adminToken}` } }
      );

      setActionSuccessMsg(res.data.message || "团长指定成功！");
      setShowAssignModal(false);
      loadAdminData(adminToken);
    } catch (err: any) {
      setActionErrorMsg(err.response?.data?.detail || "指定团长失败");
    } finally {
      setSubmitting(false);
    }
  }

  function handleCopyInvite(code: string) {
    navigator.clipboard.writeText(code);
    setCopiedCode(code);
    setTimeout(() => setCopiedCode(""), 2000);
  }

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-zinc-100 flex flex-col font-sans">
      <Navbar />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-8">
        {/* Header Banner */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8 bg-gradient-to-r from-red-950/40 via-zinc-900 to-zinc-900 border border-red-500/20 p-6 rounded-3xl backdrop-blur-md shadow-2xl">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-red-600 to-orange-500 flex items-center justify-center text-white shadow-lg shadow-red-600/30">
              <Shield className="w-8 h-8" />
            </div>
            <div>
              <div className="flex items-center gap-2.5">
                <h1 className="text-2xl font-black text-white tracking-tight">
                  平台超级管理员控制台
                </h1>
                <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-red-500/20 text-red-400 border border-red-500/30">
                  Web 专属权限
                </span>
              </div>
              <p className="text-xs text-zinc-400 mt-1">
                全平台跑团最高管辖中心 · 添加编辑跑团 · 指定与更换跑团团长
              </p>
            </div>
          </div>

          {adminToken && (
            <div className="flex items-center gap-3">
              <span className="text-xs text-zinc-400 hidden md:inline">
                管理员: <strong className="text-white">{adminInfo?.email || "admin@rgm.com"}</strong>
              </span>
              <button
                onClick={() => loadAdminData(adminToken)}
                disabled={loadingData}
                className="p-2.5 rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 text-zinc-300 transition-all text-xs font-bold flex items-center gap-1.5"
                title="刷新数据"
              >
                <RefreshCw className={`w-4 h-4 ${loadingData ? "animate-spin text-orange-400" : ""}`} />
                <span className="hidden sm:inline">刷新</span>
              </button>
              <button
                onClick={handleAdminLogout}
                className="px-4 py-2 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 hover:bg-red-500/20 text-xs font-bold transition-all flex items-center gap-1.5"
              >
                <LogOut className="w-3.5 h-3.5" />
                退出管理
              </button>
            </div>
          )}
        </div>

        {/* Global Notifications */}
        {actionSuccessMsg && (
          <div className="mb-6 p-4 bg-emerald-500/10 border border-emerald-500/30 rounded-2xl text-emerald-400 text-sm flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Check className="w-4 h-4" />
              <span>{actionSuccessMsg}</span>
            </div>
            <button onClick={() => setActionSuccessMsg("")} className="text-emerald-400/60 hover:text-emerald-400">
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {actionErrorMsg && (
          <div className="mb-6 p-4 bg-red-500/10 border border-red-500/30 rounded-2xl text-red-400 text-sm flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4" />
              <span>{actionErrorMsg}</span>
            </div>
            <button onClick={() => setActionErrorMsg("")} className="text-red-400/60 hover:text-red-400">
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Not Logged In as Admin -> Login Card */}
        {!adminToken ? (
          <div className="max-w-md mx-auto my-12 bg-[#141416] border border-white/10 rounded-3xl p-8 shadow-2xl">
            <div className="text-center mb-6">
              <div className="w-12 h-12 rounded-2xl bg-red-500/10 border border-red-500/20 flex items-center justify-center mx-auto mb-3 text-red-400">
                <Lock className="w-6 h-6" />
              </div>
              <h2 className="text-xl font-bold text-white">超级管理员安全验证</h2>
              <p className="text-xs text-zinc-400 mt-1.5">
                此控制台具备全平台跑团管理权限，请验证管理员密码进入
              </p>
            </div>

            {loginError && (
              <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-xs">
                {loginError}
              </div>
            )}

            <form onSubmit={handleAdminLogin} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1.5">管理员账号</label>
                <div className="relative">
                  <Mail className="absolute left-3.5 top-3 w-4 h-4 text-zinc-500" />
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="admin@rgm.com"
                    className="w-full pl-10 pr-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-red-500 transition-all"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1.5">超级管理员密码</label>
                <div className="relative">
                  <Lock className="absolute left-3.5 top-3 w-4 h-4 text-zinc-500" />
                  <input
                    type="password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="请输入超管密码"
                    className="w-full pl-10 pr-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-red-500 transition-all"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={loginLoading}
                className="w-full py-3 bg-gradient-to-r from-red-600 to-orange-600 text-white font-bold rounded-xl text-sm shadow-lg shadow-red-600/20 hover:opacity-90 transition-all disabled:opacity-50 mt-2"
              >
                {loginLoading ? "验证安全凭据..." : "解锁超级管理控制台"}
              </button>
            </form>
          </div>
        ) : (
          /* Logged In -> Admin Dashboard */
          <div className="space-y-6">
            {/* Action Bar */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-[#141416] p-4 rounded-2xl border border-white/5">
              <div className="flex items-center gap-3">
                <Building className="w-5 h-5 text-orange-400" />
                <span className="text-sm font-bold text-white">
                  跑团总览 ({clubs.length} 个跑团)
                </span>
              </div>
              <button
                onClick={openCreateModal}
                className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-orange-500 to-[#FC4C02] text-white text-xs font-bold hover:opacity-90 transition-all flex items-center justify-center gap-1.5 shadow-lg shadow-orange-500/20"
              >
                <Plus className="w-4 h-4" />
                添加新跑团并指定团长
              </button>
            </div>

            {/* Clubs Grid / Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {clubs.map((club) => (
                <div
                  key={club.id}
                  className="bg-[#141416] border border-white/10 rounded-3xl p-6 flex flex-col justify-between hover:border-white/20 transition-all shadow-xl group"
                >
                  <div>
                    {/* Top Info */}
                    <div className="flex items-start gap-3.5 mb-4">
                      <img
                        src={club.logo_url || "https://images.unsplash.com/photo-1552674605-db6ffd4facb5?w=300&auto=format&fit=crop&q=80"}
                        alt={club.name}
                        className="w-14 h-14 rounded-2xl object-cover border border-white/10 shrink-0"
                      />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <h3 className="text-base font-bold text-white truncate">{club.name}</h3>
                          {club.org_name && (
                            <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30 shrink-0">
                              🏛️ {club.org_name}
                            </span>
                          )}
                          <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-white/10 text-zinc-300 shrink-0">
                            {club.city || "全国"}
                          </span>
                        </div>
                        <p className="text-xs text-zinc-400 mt-1 line-clamp-2 leading-relaxed">
                          {club.description || "暂无跑团简介"}
                        </p>
                      </div>
                    </div>

                    {/* Meta details */}
                    <div className="space-y-2.5 py-3 border-y border-white/5 my-4 text-xs">
                      {/* Current Owner */}
                      <div className="flex items-center justify-between">
                        <span className="text-zinc-500 flex items-center gap-1.5">
                          <Crown className="w-3.5 h-3.5 text-amber-400" />
                          现任团长:
                        </span>
                        <div className="flex items-center gap-1.5 font-medium">
                          <span className="text-amber-300 font-bold">
                            {club.owner_name || "未指定团长"}
                          </span>
                          <span className="text-[10px] text-zinc-600">({club.owner_id})</span>
                        </div>
                      </div>

                      {/* Members Count */}
                      <div className="flex items-center justify-between">
                        <span className="text-zinc-500 flex items-center gap-1.5">
                          <Users className="w-3.5 h-3.5 text-cyan-400" />
                          跑团成员:
                        </span>
                        <span className="font-bold text-white">
                          {club.member_count || 1} 人
                        </span>
                      </div>

                      {/* Invite Code */}
                      <div className="flex items-center justify-between">
                        <span className="text-zinc-500">邀请码:</span>
                        <button
                          onClick={() => handleCopyInvite(club.invite_code)}
                          className="flex items-center gap-1 font-mono font-bold text-[#FC4C02] bg-[#FC4C02]/10 hover:bg-[#FC4C02]/20 px-2 py-0.5 rounded transition-colors"
                        >
                          <span>{club.invite_code}</span>
                          {copiedCode === club.invite_code ? (
                            <Check className="w-3 h-3 text-emerald-400" />
                          ) : (
                            <Copy className="w-3 h-3" />
                          )}
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Actions Buttons */}
                  <div className="grid grid-cols-2 gap-2.5 pt-2">
                    <button
                      onClick={() => openAssignModal(club)}
                      className="py-2.5 px-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 hover:bg-amber-500/20 text-xs font-bold transition-all flex items-center justify-center gap-1.5 shadow-sm"
                    >
                      <Crown className="w-3.5 h-3.5" />
                      指定/换团长
                    </button>
                    <button
                      onClick={() => openEditModal(club)}
                      className="py-2.5 px-3 rounded-xl bg-white/5 border border-white/10 text-zinc-300 hover:text-white hover:bg-white/10 text-xs font-bold transition-all flex items-center justify-center gap-1.5"
                    >
                      <Edit2 className="w-3.5 h-3.5" />
                      编辑跑团
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Modal 1: Create Club */}
        {showCreateModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
            <div className="relative w-full max-w-lg bg-[#141416] border border-white/10 rounded-3xl p-6 sm:p-8 shadow-2xl">
              <button
                onClick={() => setShowCreateModal(false)}
                className="absolute top-6 right-6 p-2 rounded-full text-zinc-400 hover:text-white hover:bg-white/5"
              >
                <X className="w-5 h-5" />
              </button>

              <div className="mb-6">
                <h3 className="text-xl font-bold text-white flex items-center gap-2">
                  <Plus className="w-5 h-5 text-[#FC4C02]" />
                  添加新跑团 (超级管理员)
                </h3>
                <p className="text-xs text-zinc-400 mt-1">创建跑团并指定平台跑者作为该跑团团长</p>
              </div>

              <form onSubmit={handleCreateClub} className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-zinc-400 mb-1">跑团名称 *</label>
                  <input
                    type="text"
                    required
                    value={newClubName}
                    onChange={(e) => setNewClubName(e.target.value)}
                    placeholder="例如: 世纪公园破风先锋战队"
                    className="w-full px-3.5 py-2.5 bg-white/5 border border-white/10 rounded-xl text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-[#FC4C02]"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-zinc-400 mb-1">所在城市</label>
                    <input
                      type="text"
                      value={newClubCity}
                      onChange={(e) => setNewClubCity(e.target.value)}
                      placeholder="上海"
                      className="w-full px-3.5 py-2.5 bg-white/5 border border-white/10 rounded-xl text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-[#FC4C02]"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-zinc-400 mb-1">初始指定团长 *</label>
                    <select
                      value={newClubOwnerId}
                      onChange={(e) => setNewClubOwnerId(e.target.value)}
                      className="w-full px-3.5 py-2.5 bg-[#1f1f23] border border-white/10 rounded-xl text-sm text-white focus:outline-none focus:border-[#FC4C02]"
                    >
                      {users.map((u) => (
                        <option key={u.id} value={u.id}>
                          {u.display_name || "微信跑者"} ({u.id})
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium text-zinc-400 mb-1">跑团口号与简介</label>
                  <textarea
                    rows={3}
                    value={newClubDesc}
                    onChange={(e) => setNewClubDesc(e.target.value)}
                    placeholder="基于科学耐力训练理念，追求 PB 突破..."
                    className="w-full px-3.5 py-2.5 bg-white/5 border border-white/10 rounded-xl text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-[#FC4C02]"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-zinc-400 mb-1.5">跑团 Logo 图片</label>
                  
                  <div className="flex items-center gap-3.5 p-3 bg-white/5 border border-white/10 rounded-xl">
                    <div className="w-14 h-14 rounded-xl overflow-hidden bg-black/40 border border-white/10 flex-shrink-0 flex items-center justify-center">
                      {newClubLogo ? (
                        <img
                          src={newClubLogo}
                          alt="Logo Preview"
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <span className="text-2xl">🏃</span>
                      )}
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <label className="cursor-pointer px-3 py-1.5 bg-[#FC4C02] hover:bg-[#e04302] text-white rounded-lg text-xs font-bold transition flex items-center gap-1.5">
                          {uploadingLogo ? (
                            <span>上传中...</span>
                          ) : (
                            <>
                              <Upload className="w-3.5 h-3.5" />
                              <span>本地上传图片</span>
                            </>
                          )}
                          <input
                            type="file"
                            accept="image/*"
                            className="hidden"
                            disabled={uploadingLogo}
                            onChange={(e) => {
                              const file = e.target.files?.[0];
                              if (file) handleFileUpload(file, false);
                            }}
                          />
                        </label>
                        {newClubLogo && (
                          <button
                            type="button"
                            onClick={() => setNewClubLogo("")}
                            className="px-2 py-1.5 text-xs text-zinc-400 hover:text-red-400 hover:bg-white/5 rounded-lg transition"
                          >
                            清除
                          </button>
                        )}
                      </div>
                      <p className="text-[11px] text-zinc-500 mt-1.5">
                        支持 JPG、PNG、WebP，本地一键上传
                      </p>
                    </div>
                  </div>

                  <div className="mt-2">
                    <input
                      type="url"
                      value={newClubLogo}
                      onChange={(e) => setNewClubLogo(e.target.value)}
                      placeholder="或直接粘贴图片 URL (选填)"
                      className="w-full px-3.5 py-2 bg-white/5 border border-white/10 rounded-xl text-xs text-zinc-300 placeholder:text-zinc-600 focus:outline-none focus:border-[#FC4C02]"
                    />
                  </div>
                </div>

                <div className="flex gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => setShowCreateModal(false)}
                    className="flex-1 py-2.5 rounded-xl bg-white/5 border border-white/10 text-xs font-bold text-zinc-400 hover:text-white"
                  >
                    取消
                  </button>
                  <button
                    type="submit"
                    disabled={submitting}
                    className="flex-1 py-2.5 rounded-xl bg-gradient-to-r from-orange-500 to-[#FC4C02] text-white text-xs font-bold hover:opacity-90 disabled:opacity-50"
                  >
                    {submitting ? "正在创建..." : "立即创建跑团"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Modal 2: Edit Club */}
        {showEditModal && activeClub && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
            <div className="relative w-full max-w-lg bg-[#141416] border border-white/10 rounded-3xl p-6 sm:p-8 shadow-2xl">
              <button
                onClick={() => setShowEditModal(false)}
                className="absolute top-6 right-6 p-2 rounded-full text-zinc-400 hover:text-white hover:bg-white/5"
              >
                <X className="w-5 h-5" />
              </button>

              <div className="mb-6">
                <h3 className="text-xl font-bold text-white flex items-center gap-2">
                  <Edit2 className="w-5 h-5 text-cyan-400" />
                  编辑跑团信息
                </h3>
                <p className="text-xs text-zinc-400 mt-1">更新【{activeClub.name}】的基础信息与邀请码</p>
              </div>

              <form onSubmit={handleEditClub} className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-zinc-400 mb-1">跑团名称</label>
                  <input
                    type="text"
                    required
                    value={editClubName}
                    onChange={(e) => setEditClubName(e.target.value)}
                    className="w-full px-3.5 py-2.5 bg-white/5 border border-white/10 rounded-xl text-sm text-white focus:outline-none focus:border-[#FC4C02]"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-zinc-400 mb-1">所在城市</label>
                    <input
                      type="text"
                      value={editClubCity}
                      onChange={(e) => setEditClubCity(e.target.value)}
                      className="w-full px-3.5 py-2.5 bg-white/5 border border-white/10 rounded-xl text-sm text-white focus:outline-none focus:border-[#FC4C02]"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-zinc-400 mb-1">专属邀请码</label>
                    <input
                      type="text"
                      value={editClubInviteCode}
                      onChange={(e) => setEditClubInviteCode(e.target.value.toUpperCase())}
                      className="w-full px-3.5 py-2.5 bg-white/5 border border-white/10 rounded-xl text-sm font-mono text-[#FC4C02] font-bold focus:outline-none focus:border-[#FC4C02]"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium text-zinc-400 mb-1">跑团简介与口号</label>
                  <textarea
                    rows={3}
                    value={editClubDesc}
                    onChange={(e) => setEditClubDesc(e.target.value)}
                    className="w-full px-3.5 py-2.5 bg-white/5 border border-white/10 rounded-xl text-sm text-white focus:outline-none focus:border-[#FC4C02]"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-zinc-400 mb-1.5">跑团 Logo 图片</label>
                  
                  <div className="flex items-center gap-3.5 p-3 bg-white/5 border border-white/10 rounded-xl">
                    <div className="w-14 h-14 rounded-xl overflow-hidden bg-black/40 border border-white/10 flex-shrink-0 flex items-center justify-center">
                      {editClubLogo ? (
                        <img
                          src={editClubLogo}
                          alt="Logo Preview"
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <span className="text-2xl">🏃</span>
                      )}
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <label className="cursor-pointer px-3 py-1.5 bg-[#FC4C02] hover:bg-[#e04302] text-white rounded-lg text-xs font-bold transition flex items-center gap-1.5">
                          {uploadingLogo ? (
                            <span>上传中...</span>
                          ) : (
                            <>
                              <Upload className="w-3.5 h-3.5" />
                              <span>本地上传图片</span>
                            </>
                          )}
                          <input
                            type="file"
                            accept="image/*"
                            className="hidden"
                            disabled={uploadingLogo}
                            onChange={(e) => {
                              const file = e.target.files?.[0];
                              if (file) handleFileUpload(file, true);
                            }}
                          />
                        </label>
                        {editClubLogo && (
                          <button
                            type="button"
                            onClick={() => setEditClubLogo("")}
                            className="px-2 py-1.5 text-xs text-zinc-400 hover:text-red-400 hover:bg-white/5 rounded-lg transition"
                          >
                            清除
                          </button>
                        )}
                      </div>
                      <p className="text-[11px] text-zinc-500 mt-1.5">
                        支持从本地选择图片文件直接上传
                      </p>
                    </div>
                  </div>

                  <div className="mt-2">
                    <input
                      type="url"
                      value={editClubLogo}
                      onChange={(e) => setEditClubLogo(e.target.value)}
                      placeholder="或直接粘贴图片 URL (选填)"
                      className="w-full px-3.5 py-2 bg-white/5 border border-white/10 rounded-xl text-xs text-zinc-300 placeholder:text-zinc-600 focus:outline-none focus:border-[#FC4C02]"
                    />
                  </div>
                </div>

                <div className="flex gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => setShowEditModal(false)}
                    className="flex-1 py-2.5 rounded-xl bg-white/5 border border-white/10 text-xs font-bold text-zinc-400 hover:text-white"
                  >
                    取消
                  </button>
                  <button
                    type="submit"
                    disabled={submitting}
                    className="flex-1 py-2.5 rounded-xl bg-[#FC4C02] text-white text-xs font-bold hover:opacity-90 disabled:opacity-50"
                  >
                    {submitting ? "正在保存..." : "保存更新"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Modal 3: Assign Owner */}
        {showAssignModal && activeClub && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
            <div className="relative w-full max-w-md bg-[#141416] border border-white/10 rounded-3xl p-6 sm:p-8 shadow-2xl">
              <button
                onClick={() => setShowAssignModal(false)}
                className="absolute top-6 right-6 p-2 rounded-full text-zinc-400 hover:text-white hover:bg-white/5"
              >
                <X className="w-5 h-5" />
              </button>

              <div className="mb-6">
                <div className="w-12 h-12 rounded-2xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center mb-3 text-amber-400">
                  <Crown className="w-6 h-6" />
                </div>
                <h3 className="text-xl font-bold text-white">指定跑团团长</h3>
                <p className="text-xs text-zinc-400 mt-1">
                  正在为跑团【<strong className="text-white">{activeClub.name}</strong>】指派主理人/团长
                </p>
              </div>

              <form onSubmit={handleAssignOwner} className="space-y-4">
                <div className="p-3 bg-white/5 border border-white/5 rounded-2xl text-xs space-y-1">
                  <span className="text-zinc-500 block">当前跑团团长:</span>
                  <span className="text-amber-400 font-bold block text-sm">
                    {activeClub.owner_name || "未指定"} ({activeClub.owner_id})
                  </span>
                </div>

                <div>
                  <label className="block text-xs font-medium text-zinc-400 mb-1.5">
                    从注册跑者中指定新团长:
                  </label>
                  <select
                    value={selectedNewOwnerId}
                    onChange={(e) => setSelectedNewOwnerId(e.target.value)}
                    className="w-full px-3.5 py-3 bg-[#1f1f23] border border-white/10 rounded-xl text-sm text-white focus:outline-none focus:border-amber-400"
                  >
                    {users.map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.display_name || "微信跑者"} · UID: {u.id} {u.garmin_connected ? "· [佳明]" : ""} {u.coros_connected ? "· [高驰]" : ""}
                      </option>
                    ))}
                  </select>
                  <p className="text-[11px] text-zinc-500 mt-2 leading-relaxed">
                    * 指定后，该跑者将立刻获得该跑团的【跑团主理人】最高管理权限，原团长将自动调整为教练身份。
                  </p>
                </div>

                <div className="flex gap-3 pt-3">
                  <button
                    type="button"
                    onClick={() => setShowAssignModal(false)}
                    className="flex-1 py-2.5 rounded-xl bg-white/5 border border-white/10 text-xs font-bold text-zinc-400 hover:text-white"
                  >
                    取消
                  </button>
                  <button
                    type="submit"
                    disabled={submitting}
                    className="flex-1 py-2.5 rounded-xl bg-gradient-to-r from-amber-500 to-orange-500 text-white text-xs font-bold hover:opacity-90 disabled:opacity-50"
                  >
                    {submitting ? "正在指定..." : "确认指定团长"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
