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
  Image as ImageIcon,
  Link2,
  Unlink,
  UserCheck,
  Search,
  CheckCircle2,
  Sparkles,
  School
} from "lucide-react";

export default function AdminPage() {
  const [adminToken, setAdminToken] = useState<string | null>(null);
  const [adminInfo, setAdminInfo] = useState<any>(null);

  // Tab state: 'orgs' (大群体架构) | 'clubs' (分跑团)
  const [activeTab, setActiveTab] = useState<"orgs" | "clubs">("orgs");

  // Login form state
  const [email, setEmail] = useState("admin@rgm.com");
  const [password, setPassword] = useState("");
  const [loginLoading, setLoginLoading] = useState(false);
  const [loginError, setLoginError] = useState("");

  // Data states
  const [orgs, setOrgs] = useState<any[]>([]);
  const [clubs, setClubs] = useState<any[]>([]);
  const [users, setUsers] = useState<any[]>([]);
  const [loadingData, setLoadingData] = useState(false);

  // Club Modal states
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showAssignModal, setShowAssignModal] = useState(false);
  const [activeClub, setActiveClub] = useState<any>(null);

  // Club Form states
  const [newClubName, setNewClubName] = useState("");
  const [newClubCity, setNewClubCity] = useState("上海");
  const [newClubDesc, setNewClubDesc] = useState("");
  const [newClubLogo, setNewClubLogo] = useState("");
  const [newClubOwnerId, setNewClubOwnerId] = useState("");
  const [newClubOrgId, setNewClubOrgId] = useState("");

  const [editClubName, setEditClubName] = useState("");
  const [editClubCity, setEditClubCity] = useState("");
  const [editClubDesc, setEditClubDesc] = useState("");
  const [editClubLogo, setEditClubLogo] = useState("");
  const [editClubInviteCode, setEditClubInviteCode] = useState("");
  const [editClubJoinMode, setEditClubJoinMode] = useState<"free" | "invite">("free");
  const [editClubOrgId, setEditClubOrgId] = useState("");

  const [selectedNewOwnerId, setSelectedNewOwnerId] = useState("");

  // Org Modal states
  const [showCreateOrgModal, setShowCreateOrgModal] = useState(false);
  const [showEditOrgModal, setShowEditOrgModal] = useState(false);
  const [showOrgRosterModal, setShowOrgRosterModal] = useState(false);
  const [showOrgClubsModal, setShowOrgClubsModal] = useState(false);
  const [activeOrg, setActiveOrg] = useState<any>(null);

  // Org Form states
  const [newOrgName, setNewOrgName] = useState("");
  const [newOrgInviteCode, setNewOrgInviteCode] = useState("");
  const [newOrgCity, setNewOrgCity] = useState("上海");
  const [newOrgDesc, setNewOrgDesc] = useState("");
  const [newOrgLogo, setNewOrgLogo] = useState("");
  const [newOrgOwnerId, setNewOrgOwnerId] = useState("");

  const [editOrgName, setEditOrgName] = useState("");
  const [editOrgInviteCode, setEditOrgInviteCode] = useState("");
  const [editOrgCity, setEditOrgCity] = useState("");
  const [editOrgDesc, setEditOrgDesc] = useState("");
  const [editOrgLogo, setEditOrgLogo] = useState("");
  const [editOrgOwnerId, setEditOrgOwnerId] = useState("");

  // Org Roster states
  const [orgMembers, setOrgMembers] = useState<any[]>([]);
  const [rosterSearch, setRosterSearch] = useState("");
  const [rosterLoading, setRosterLoading] = useState(false);
  const [confirmingUid, setConfirmingUid] = useState<string | null>(null);

  // Org Sub-Clubs binding states
  const [orgSubClubs, setOrgSubClubs] = useState<any[]>([]);
  const [bindingClubLoading, setBindingClubLoading] = useState<string | null>(null);

  const [submitting, setSubmitting] = useState(false);
  const [actionSuccessMsg, setActionSuccessMsg] = useState("");
  const [actionErrorMsg, setActionErrorMsg] = useState("");
  const [copiedCode, setCopiedCode] = useState("");
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const [uploadLogoError, setUploadLogoError] = useState("");

  async function handleFileUpload(file: File, target: "newClub" | "editClub" | "newOrg" | "editOrg") {
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
        if (target === "newClub") setNewClubLogo(uploadedUrl);
        else if (target === "editClub") setEditClubLogo(uploadedUrl);
        else if (target === "newOrg") setNewOrgLogo(uploadedUrl);
        else if (target === "editOrg") setEditOrgLogo(uploadedUrl);
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
    setOrgs([]);
  }

  async function loadAdminData(token: string) {
    setLoadingData(true);
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const [clubsRes, usersRes, orgsRes] = await Promise.all([
        axios.get("/api/admin/clubs", { headers }),
        axios.get("/api/admin/users", { headers }),
        axios.get("/api/org/admin/all-list", { headers }).catch(() => ({ data: { organizations: [] } }))
      ]);
      setClubs(clubsRes.data?.clubs || []);
      const userList = usersRes.data?.users || [];
      setUsers(userList);
      setOrgs(orgsRes.data?.organizations || []);
      if (userList.length > 0 && !newClubOwnerId) {
        setNewClubOwnerId(userList[0].id);
      }
      if (userList.length > 0 && !newOrgOwnerId) {
        setNewOrgOwnerId(userList[0].id);
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

  // Club Modals Opener
  function openCreateModal() {
    setNewClubName("");
    setNewClubCity("上海");
    setNewClubDesc("");
    setNewClubLogo("");
    setNewClubOrgId("");
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
    setEditClubJoinMode(club.join_mode === "invite" ? "invite" : "free");
    setEditClubOrgId(club.org_id || "");
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

  // Org Modals Opener
  function openCreateOrgModal() {
    setNewOrgName("");
    setNewOrgInviteCode("");
    setNewOrgCity("上海");
    setNewOrgDesc("");
    setNewOrgLogo("");
    if (users.length > 0) setNewOrgOwnerId(users[0].id);
    setActionSuccessMsg("");
    setActionErrorMsg("");
    setShowCreateOrgModal(true);
  }

  function openEditOrgModal(org: any) {
    setActiveOrg(org);
    setEditOrgName(org.name || "");
    setEditOrgInviteCode(org.invite_code || "");
    setEditOrgCity(org.city || "上海");
    setEditOrgDesc(org.description || "");
    setEditOrgLogo(org.logo_url || "");
    setEditOrgOwnerId(org.owner_id || (users[0]?.id || ""));
    setActionSuccessMsg("");
    setActionErrorMsg("");
    setShowEditOrgModal(true);
  }

  async function openOrgRosterModal(org: any) {
    setActiveOrg(org);
    setRosterSearch("");
    setShowOrgRosterModal(true);
    setRosterLoading(true);
    try {
      const res = await axios.get(`/api/org/${org.id}/members`);
      setOrgMembers(res.data?.members || []);
    } catch (err: any) {
      setActionErrorMsg("加载花名册失败");
    } finally {
      setRosterLoading(false);
    }
  }

  async function openOrgClubsModal(org: any) {
    setActiveOrg(org);
    setShowOrgClubsModal(true);
    try {
      const res = await axios.get(`/api/org/${org.id}/sub-clubs`);
      setOrgSubClubs(res.data?.sub_clubs || []);
    } catch (err: any) {
      setActionErrorMsg("加载下属分跑团失败");
    }
  }

  // Actions: Club
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
          owner_id: newClubOwnerId,
          org_id: newClubOrgId || undefined,
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
      await axios.put(
        `/api/admin/clubs/${activeClub.id}`,
        {
          name: editClubName.trim(),
          city: editClubCity.trim(),
          description: editClubDesc.trim(),
          logo_url: editClubLogo.trim() || undefined,
          invite_code: editClubInviteCode.trim() || undefined,
          join_mode: editClubJoinMode,
          org_id: editClubOrgId || "",
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

  // Actions: Organization
  async function handleCreateOrg(e: React.FormEvent) {
    e.preventDefault();
    if (!adminToken) return;
    setSubmitting(true);
    setActionErrorMsg("");

    try {
      const res = await axios.post(
        "/api/org/create",
        {
          name: newOrgName.trim(),
          invite_code: newOrgInviteCode.trim().toUpperCase(),
          city: newOrgCity.trim(),
          description: newOrgDesc.trim(),
          logo_url: newOrgLogo.trim() || undefined,
          owner_id: newOrgOwnerId || undefined,
        },
        { headers: { Authorization: `Bearer ${adminToken}` } }
      );

      setActionSuccessMsg(res.data.message || "大组织创建成功！");
      setShowCreateOrgModal(false);
      loadAdminData(adminToken);
    } catch (err: any) {
      setActionErrorMsg(err.response?.data?.detail || "创建大组织失败");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleEditOrg(e: React.FormEvent) {
    e.preventDefault();
    if (!adminToken || !activeOrg) return;
    setSubmitting(true);
    setActionErrorMsg("");

    try {
      await axios.put(
        `/api/org/${activeOrg.id}`,
        {
          name: editOrgName.trim(),
          invite_code: editOrgInviteCode.trim().toUpperCase(),
          city: editOrgCity.trim(),
          description: editOrgDesc.trim(),
          logo_url: editOrgLogo.trim() || undefined,
          owner_id: editOrgOwnerId || undefined,
        },
        { headers: { Authorization: `Bearer ${adminToken}` } }
      );

      setActionSuccessMsg("大组织信息保存成功！");
      setShowEditOrgModal(false);
      loadAdminData(adminToken);
    } catch (err: any) {
      setActionErrorMsg(err.response?.data?.detail || "更新大组织失败");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleConfirmMember(targetUid: string) {
    if (!adminToken || !activeOrg) return;
    setConfirmingUid(targetUid);
    try {
      await axios.post(`/api/org/${activeOrg.id}/members/${targetUid}/confirm`, {
        operator_uid: "super_admin"
      });
      // Update local state
      setOrgMembers((prev) =>
        prev.map((m) => (m.user_id === targetUid ? { ...m, status: "confirmed" } : m))
      );
      setActionSuccessMsg("戈友实名认证已核对通过！");
    } catch (err: any) {
      alert(err.response?.data?.detail || "确认成员失败");
    } finally {
      setConfirmingUid(null);
    }
  }

  async function handleBindClub(clubId: string, action: "bind" | "unbind") {
    if (!adminToken || !activeOrg) return;
    setBindingClubLoading(clubId);
    try {
      const res = await axios.post(`/api/org/${activeOrg.id}/bind-club`, {
        club_id: clubId,
        action: action
      });
      setActionSuccessMsg(res.data.message || "跑团挂靠状态更新成功！");
      // Refresh sub clubs modal
      const subRes = await axios.get(`/api/org/${activeOrg.id}/sub-clubs`);
      setOrgSubClubs(subRes.data?.sub_clubs || []);
      // Refresh global clubs list
      loadAdminData(adminToken);
    } catch (err: any) {
      alert(err.response?.data?.detail || "操作挂靠失败");
    } finally {
      setBindingClubLoading(null);
    }
  }

  function handleCopyInvite(code: string) {
    navigator.clipboard.writeText(code);
    setCopiedCode(code);
    setTimeout(() => setCopiedCode(""), 2000);
  }

  const filteredMembers = orgMembers.filter((m) => {
    if (!rosterSearch.trim()) return true;
    const q = rosterSearch.toLowerCase();
    return (
      (m.real_name && m.real_name.toLowerCase().includes(q)) ||
      (m.class_name && m.class_name.toLowerCase().includes(q)) ||
      (m.display_name && m.display_name.toLowerCase().includes(q)) ||
      (m.phone && m.phone.includes(q))
    );
  });

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-zinc-100 flex flex-col font-sans">
      <Navbar />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-8">
        {/* Header Banner */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6 bg-gradient-to-r from-red-950/40 via-zinc-900 to-zinc-900 border border-red-500/20 p-6 rounded-3xl backdrop-blur-md shadow-2xl">
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
                全平台大群体架构 · 高校戈友会管理 · 分跑团主理人任命与挂靠
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
                此控制台具备全平台大组织架构与跑团管辖权限，请验证管理员密码进入
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
            {/* Top Navigation Tabs */}
            <div className="flex items-center gap-3 border-b border-white/10 pb-4">
              <button
                onClick={() => setActiveTab("orgs")}
                className={`flex items-center gap-2.5 px-5 py-3 rounded-2xl font-bold text-sm transition-all ${
                  activeTab === "orgs"
                    ? "bg-gradient-to-r from-orange-600 to-red-600 text-white shadow-lg shadow-orange-600/25 border border-orange-400/30"
                    : "bg-[#141416] text-zinc-400 hover:text-white hover:bg-white/5 border border-white/5"
                }`}
              >
                <School className="w-4 h-4" />
                <span>🏛️ 大群体架构管理 ({orgs.length})</span>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-black/40 text-amber-200 font-normal">
                  复旦戈及商学院总会
                </span>
              </button>

              <button
                onClick={() => setActiveTab("clubs")}
                className={`flex items-center gap-2.5 px-5 py-3 rounded-2xl font-bold text-sm transition-all ${
                  activeTab === "clubs"
                    ? "bg-gradient-to-r from-orange-600 to-red-600 text-white shadow-lg shadow-orange-600/25 border border-orange-400/30"
                    : "bg-[#141416] text-zinc-400 hover:text-white hover:bg-white/5 border border-white/5"
                }`}
              >
                <Users className="w-4 h-4" />
                <span>🏃 分跑团与俱乐部 ({clubs.length})</span>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-black/40 text-zinc-300 font-normal">
                  下属与独立分队
                </span>
              </button>
            </div>

            {/* TAB 1: Organizations View */}
            {activeTab === "orgs" && (
              <div className="space-y-6">
                {/* Action Bar */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-[#141416] p-4 rounded-2xl border border-white/5">
                  <div>
                    <div className="flex items-center gap-2">
                      <School className="w-5 h-5 text-orange-400" />
                      <h2 className="text-base font-bold text-white">大群体架构总览 ({orgs.length} 个组织)</h2>
                    </div>
                    <p className="text-xs text-zinc-400 mt-1">
                      支持复旦戈、交大戈及各大商学院大群体，审核戈友认证花名册，指派主理人与挂靠分跑团
                    </p>
                  </div>
                  <button
                    onClick={openCreateOrgModal}
                    className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-orange-500 to-[#FC4C02] text-white text-xs font-bold hover:opacity-90 transition-all flex items-center justify-center gap-1.5 shadow-lg shadow-orange-500/20"
                  >
                    <Plus className="w-4 h-4" />
                    创建新大群体架构
                  </button>
                </div>

                {/* Organizations Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {orgs.map((org) => (
                    <div
                      key={org.id}
                      className="bg-[#141416] border border-white/10 rounded-3xl p-6 flex flex-col justify-between hover:border-orange-500/30 transition-all shadow-xl group relative overflow-hidden"
                    >
                      <div className="absolute top-0 right-0 w-32 h-32 bg-orange-500/5 rounded-bl-full pointer-events-none" />

                      <div>
                        {/* Top Info */}
                        <div className="flex items-start gap-3.5 mb-4">
                          <img
                            src={org.logo_url || "https://images.unsplash.com/photo-1461896836934-ffe607ba8211?w=300&auto=format&fit=crop&q=80"}
                            alt={org.name}
                            className="w-14 h-14 rounded-2xl object-cover border border-white/10 shrink-0 bg-white/5"
                          />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <h3 className="text-base font-bold text-white truncate">{org.name}</h3>
                              <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-white/10 text-zinc-300 shrink-0">
                                📍 {org.city || "上海"}
                              </span>
                            </div>
                            <p className="text-xs text-zinc-400 mt-1 line-clamp-2 leading-relaxed">
                              {org.description || "暂无组织描述"}
                            </p>
                          </div>
                        </div>

                        {/* Meta details */}
                        <div className="space-y-2.5 py-3 border-y border-white/5 my-4 text-xs">
                          {/* Invite Code */}
                          <div className="flex items-center justify-between">
                            <span className="text-zinc-500">专属邀请码:</span>
                            <button
                              onClick={() => handleCopyInvite(org.invite_code)}
                              className="flex items-center gap-1 font-mono font-bold text-orange-400 bg-orange-500/10 hover:bg-orange-500/20 px-2.5 py-1 rounded-lg transition-colors"
                              title="点击复制邀请码"
                            >
                              <span>{org.invite_code}</span>
                              {copiedCode === org.invite_code ? (
                                <Check className="w-3 h-3 text-emerald-400" />
                              ) : (
                                <Copy className="w-3 h-3" />
                              )}
                            </button>
                          </div>

                          {/* Owner */}
                          <div className="flex items-center justify-between">
                            <span className="text-zinc-500 flex items-center gap-1.5">
                              <Crown className="w-3.5 h-3.5 text-amber-400" />
                              组织主理人:
                            </span>
                            <span className="text-amber-300 font-medium">
                              {org.owner_name || "平台超管总代管"}
                            </span>
                          </div>

                          {/* Member stats */}
                          <div className="flex items-center justify-between">
                            <span className="text-zinc-500 flex items-center gap-1.5">
                              <UserCheck className="w-3.5 h-3.5 text-emerald-400" />
                              认证戈友/成员:
                            </span>
                            <span className="font-bold text-emerald-400">
                              {org.member_count || 0} 人
                            </span>
                          </div>

                          {/* Sub-clubs stats */}
                          <div className="flex items-center justify-between">
                            <span className="text-zinc-500 flex items-center gap-1.5">
                              <Building className="w-3.5 h-3.5 text-cyan-400" />
                              下属分跑团:
                            </span>
                            <span className="font-bold text-white">
                              {org.sub_clubs_count || 0} 个分队
                            </span>
                          </div>
                        </div>
                      </div>

                      {/* Action buttons */}
                      <div className="space-y-2 pt-2">
                        <div className="grid grid-cols-2 gap-2">
                          <button
                            onClick={() => openOrgRosterModal(org)}
                            className="py-2 px-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/20 text-xs font-bold transition-all flex items-center justify-center gap-1.5"
                          >
                            <UserCheck className="w-3.5 h-3.5" />
                            审核花名册
                          </button>
                          <button
                            onClick={() => openOrgClubsModal(org)}
                            className="py-2 px-3 rounded-xl bg-blue-500/10 border border-blue-500/30 text-blue-300 hover:bg-blue-500/20 text-xs font-bold transition-all flex items-center justify-center gap-1.5"
                          >
                            <Link2 className="w-3.5 h-3.5" />
                            挂靠跑团 ({org.sub_clubs_count || 0})
                          </button>
                        </div>
                        <button
                          onClick={() => openEditOrgModal(org)}
                          className="w-full py-2 px-3 rounded-xl bg-white/5 border border-white/10 text-zinc-300 hover:text-white hover:bg-white/10 text-xs font-bold transition-all flex items-center justify-center gap-1.5"
                        >
                          <Edit2 className="w-3.5 h-3.5" />
                          编辑大组织资料与邀请码
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* TAB 2: Clubs View */}
            {activeTab === "clubs" && (
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
                              {club.org_name ? (
                                <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30 shrink-0">
                                  🏛️ 挂靠: {club.org_name}
                                </span>
                              ) : (
                                <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-zinc-500/20 text-zinc-300 border border-zinc-500/30 shrink-0">
                                  🍃 独立自由跑团
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

                          {/* Join Mode */}
                          <div className="flex items-center justify-between">
                            <span className="text-zinc-500">入团规则:</span>
                            <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              club.join_mode === 'invite'
                                ? 'bg-amber-500/15 text-amber-400 border border-amber-500/30'
                                : 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                            }`}>
                              {club.join_mode === 'invite' ? '🔒 凭邀请码入团' : '🟢 自由入团'}
                            </span>
                          </div>

                          {/* Invite Code */}
                          <div className="flex items-center justify-between">
                            <span className="text-zinc-500">跑团邀请码:</span>
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
          </div>
        )}

        {/* ── Modal 1: Create Club ── */}
        {showCreateModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
            <div className="relative w-full max-w-lg bg-[#141416] border border-white/10 rounded-3xl p-6 sm:p-8 shadow-2xl max-h-[90vh] overflow-y-auto">
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
                <p className="text-xs text-zinc-400 mt-1">创建跑团、选择所属大群体并指定跑团团长</p>
              </div>

              <form onSubmit={handleCreateClub} className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-zinc-400 mb-1">跑团名称 *</label>
                  <input
                    type="text"
                    required
                    value={newClubName}
                    onChange={(e) => setNewClubName(e.target.value)}
                    placeholder="例如: 复旦戈闵文跑团"
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
                    <label className="block text-xs font-medium text-zinc-400 mb-1">挂靠大群体架构 (选填)</label>
                    <select
                      value={newClubOrgId}
                      onChange={(e) => setNewClubOrgId(e.target.value)}
                      className="w-full px-3.5 py-2.5 bg-[#1f1f23] border border-white/10 rounded-xl text-sm text-white focus:outline-none focus:border-[#FC4C02]"
                    >
                      <option value="">无（独立自由跑团）</option>
                      {orgs.map((o) => (
                        <option key={o.id} value={o.id}>
                          🏛️ {o.name}
                        </option>
                      ))}
                    </select>
                  </div>
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
                        <img src={newClubLogo} alt="Logo Preview" className="w-full h-full object-cover" />
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
                              if (file) handleFileUpload(file, "newClub");
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
                      <p className="text-[11px] text-zinc-500 mt-1.5">支持 JPG、PNG、WebP，本地一键上传</p>
                    </div>
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

        {/* ── Modal 2: Edit Club ── */}
        {showEditModal && activeClub && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
            <div className="relative w-full max-w-lg bg-[#141416] border border-white/10 rounded-3xl p-6 sm:p-8 shadow-2xl max-h-[90vh] overflow-y-auto">
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
                <p className="text-xs text-zinc-400 mt-1">更新【{activeClub.name}】的基础信息、所属组织与邀请码</p>
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
                    <label className="block text-xs font-medium text-zinc-400 mb-1">跑团专属邀请码</label>
                    <input
                      type="text"
                      value={editClubInviteCode}
                      onChange={(e) => setEditClubInviteCode(e.target.value.toUpperCase())}
                      className="w-full px-3.5 py-2.5 bg-white/5 border border-white/10 rounded-xl text-sm font-mono text-[#FC4C02] font-bold focus:outline-none focus:border-[#FC4C02]"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium text-zinc-400 mb-1">所属大群体架构</label>
                  <select
                    value={editClubOrgId}
                    onChange={(e) => setEditClubOrgId(e.target.value)}
                    className="w-full px-3.5 py-2.5 bg-[#1f1f23] border border-white/10 rounded-xl text-sm text-white focus:outline-none focus:border-[#FC4C02]"
                  >
                    <option value="">无（独立自由跑团）</option>
                    {orgs.map((o) => (
                      <option key={o.id} value={o.id}>
                        🏛️ {o.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-zinc-400 mb-1.5">入团门槛与规则</label>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      onClick={() => setEditClubJoinMode("free")}
                      className={`py-2 px-3 rounded-xl text-xs font-bold transition flex items-center justify-center gap-1 ${
                        editClubJoinMode === "free"
                          ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                          : "bg-white/5 text-zinc-400 border border-white/10 hover:bg-white/10"
                      }`}
                    >
                      🟢 自由入团（免邀请码）
                    </button>
                    <button
                      type="button"
                      onClick={() => setEditClubJoinMode("invite")}
                      className={`py-2 px-3 rounded-xl text-xs font-bold transition flex items-center justify-center gap-1 ${
                        editClubJoinMode === "invite"
                          ? "bg-amber-500/20 text-amber-300 border border-amber-500/40"
                          : "bg-white/5 text-zinc-400 border border-white/10 hover:bg-white/10"
                      }`}
                    >
                      🔒 凭专属邀请码入团
                    </button>
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
                        <img src={editClubLogo} alt="Logo Preview" className="w-full h-full object-cover" />
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
                              if (file) handleFileUpload(file, "editClub");
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
                      <p className="text-[11px] text-zinc-500 mt-1.5">支持本地图片上传</p>
                    </div>
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

        {/* ── Modal 3: Assign Owner ── */}
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

        {/* ── Modal 4: Create Organization (新建大群体架构) ── */}
        {showCreateOrgModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
            <div className="relative w-full max-w-lg bg-[#141416] border border-white/10 rounded-3xl p-6 sm:p-8 shadow-2xl max-h-[90vh] overflow-y-auto">
              <button
                onClick={() => setShowCreateOrgModal(false)}
                className="absolute top-6 right-6 p-2 rounded-full text-zinc-400 hover:text-white hover:bg-white/5"
              >
                <X className="w-5 h-5" />
              </button>

              <div className="mb-6">
                <h3 className="text-xl font-bold text-white flex items-center gap-2">
                  <School className="w-5 h-5 text-orange-400" />
                  创建新大群体架构 (高校戈友会/联盟)
                </h3>
                <p className="text-xs text-zinc-400 mt-1">
                  设立如复旦戈、交大戈、中欧戈等上千人大群体架构，并生成专属邀请码
                </p>
              </div>

              <form onSubmit={handleCreateOrg} className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-zinc-400 mb-1">大组织名称 *</label>
                  <input
                    type="text"
                    required
                    value={newOrgName}
                    onChange={(e) => setNewOrgName(e.target.value)}
                    placeholder="例如: 交大安泰戈友会 / 中欧戈"
                    className="w-full px-3.5 py-2.5 bg-white/5 border border-white/10 rounded-xl text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-orange-500"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-zinc-400 mb-1">专属邀请码 * (大写英数)</label>
                    <input
                      type="text"
                      required
                      value={newOrgInviteCode}
                      onChange={(e) => setNewOrgInviteCode(e.target.value.toUpperCase())}
                      placeholder="例如: SJTUGOBI"
                      className="w-full px-3.5 py-2.5 bg-white/5 border border-white/10 rounded-xl text-sm font-mono text-orange-400 font-bold placeholder:text-zinc-600 focus:outline-none focus:border-orange-500"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-zinc-400 mb-1">所在城市</label>
                    <input
                      type="text"
                      value={newOrgCity}
                      onChange={(e) => setNewOrgCity(e.target.value)}
                      placeholder="上海"
                      className="w-full px-3.5 py-2.5 bg-white/5 border border-white/10 rounded-xl text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-orange-500"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium text-zinc-400 mb-1">指定大组织总负责人 / 主理人</label>
                  <select
                    value={newOrgOwnerId}
                    onChange={(e) => setNewOrgOwnerId(e.target.value)}
                    className="w-full px-3.5 py-2.5 bg-[#1f1f23] border border-white/10 rounded-xl text-sm text-white focus:outline-none focus:border-orange-500"
                  >
                    {users.map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.display_name || "微信跑者"} ({u.id})
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-zinc-400 mb-1">大组织口号与使命</label>
                  <textarea
                    rows={3}
                    value={newOrgDesc}
                    onChange={(e) => setNewOrgDesc(e.target.value)}
                    placeholder="汇聚商学院EMBA/MBA及泛戈友，统筹下属各个分跑团备战与打卡..."
                    className="w-full px-3.5 py-2.5 bg-white/5 border border-white/10 rounded-xl text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-orange-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-zinc-400 mb-1.5">大组织 Logo / 徽标</label>
                  <div className="flex items-center gap-3.5 p-3 bg-white/5 border border-white/10 rounded-xl">
                    <div className="w-14 h-14 rounded-xl overflow-hidden bg-black/40 border border-white/10 flex-shrink-0 flex items-center justify-center">
                      {newOrgLogo ? (
                        <img src={newOrgLogo} alt="Org Logo Preview" className="w-full h-full object-cover" />
                      ) : (
                        <span className="text-2xl">🏛️</span>
                      )}
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <label className="cursor-pointer px-3 py-1.5 bg-orange-600 hover:bg-orange-500 text-white rounded-lg text-xs font-bold transition flex items-center gap-1.5">
                          {uploadingLogo ? (
                            <span>上传中...</span>
                          ) : (
                            <>
                              <Upload className="w-3.5 h-3.5" />
                              <span>本地上传Logo</span>
                            </>
                          )}
                          <input
                            type="file"
                            accept="image/*"
                            className="hidden"
                            disabled={uploadingLogo}
                            onChange={(e) => {
                              const file = e.target.files?.[0];
                              if (file) handleFileUpload(file, "newOrg");
                            }}
                          />
                        </label>
                        {newOrgLogo && (
                          <button
                            type="button"
                            onClick={() => setNewOrgLogo("")}
                            className="px-2 py-1.5 text-xs text-zinc-400 hover:text-red-400 hover:bg-white/5 rounded-lg transition"
                          >
                            清除
                          </button>
                        )}
                      </div>
                      <p className="text-[11px] text-zinc-500 mt-1.5">支持本地图片上传</p>
                    </div>
                  </div>
                </div>

                <div className="flex gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => setShowCreateOrgModal(false)}
                    className="flex-1 py-2.5 rounded-xl bg-white/5 border border-white/10 text-xs font-bold text-zinc-400 hover:text-white"
                  >
                    取消
                  </button>
                  <button
                    type="submit"
                    disabled={submitting}
                    className="flex-1 py-2.5 rounded-xl bg-gradient-to-r from-orange-600 to-red-600 text-white text-xs font-bold hover:opacity-90 disabled:opacity-50"
                  >
                    {submitting ? "正在创建..." : "立即创建大组织"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* ── Modal 5: Edit Organization (编辑大群体) ── */}
        {showEditOrgModal && activeOrg && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
            <div className="relative w-full max-w-lg bg-[#141416] border border-white/10 rounded-3xl p-6 sm:p-8 shadow-2xl max-h-[90vh] overflow-y-auto">
              <button
                onClick={() => setShowEditOrgModal(false)}
                className="absolute top-6 right-6 p-2 rounded-full text-zinc-400 hover:text-white hover:bg-white/5"
              >
                <X className="w-5 h-5" />
              </button>

              <div className="mb-6">
                <h3 className="text-xl font-bold text-white flex items-center gap-2">
                  <Edit2 className="w-5 h-5 text-orange-400" />
                  编辑大组织资料与邀请码
                </h3>
                <p className="text-xs text-zinc-400 mt-1">更新【{activeOrg.name}】的档案、专属邀请码与主理人</p>
              </div>

              <form onSubmit={handleEditOrg} className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-zinc-400 mb-1">大组织名称</label>
                  <input
                    type="text"
                    required
                    value={editOrgName}
                    onChange={(e) => setEditOrgName(e.target.value)}
                    className="w-full px-3.5 py-2.5 bg-white/5 border border-white/10 rounded-xl text-sm text-white focus:outline-none focus:border-orange-500"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-zinc-400 mb-1">大群体专属邀请码</label>
                    <input
                      type="text"
                      required
                      value={editOrgInviteCode}
                      onChange={(e) => setEditOrgInviteCode(e.target.value.toUpperCase())}
                      className="w-full px-3.5 py-2.5 bg-white/5 border border-white/10 rounded-xl text-sm font-mono text-orange-400 font-bold focus:outline-none focus:border-orange-500"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-zinc-400 mb-1">所在城市</label>
                    <input
                      type="text"
                      value={editOrgCity}
                      onChange={(e) => setEditOrgCity(e.target.value)}
                      className="w-full px-3.5 py-2.5 bg-white/5 border border-white/10 rounded-xl text-sm text-white focus:outline-none focus:border-orange-500"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium text-zinc-400 mb-1">大组织主理人</label>
                  <select
                    value={editOrgOwnerId}
                    onChange={(e) => setEditOrgOwnerId(e.target.value)}
                    className="w-full px-3.5 py-2.5 bg-[#1f1f23] border border-white/10 rounded-xl text-sm text-white focus:outline-none focus:border-orange-500"
                  >
                    {users.map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.display_name || "微信跑者"} ({u.id})
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-zinc-400 mb-1">组织口号与使命</label>
                  <textarea
                    rows={3}
                    value={editOrgDesc}
                    onChange={(e) => setEditOrgDesc(e.target.value)}
                    className="w-full px-3.5 py-2.5 bg-white/5 border border-white/10 rounded-xl text-sm text-white focus:outline-none focus:border-orange-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-zinc-400 mb-1.5">组织 Logo</label>
                  <div className="flex items-center gap-3.5 p-3 bg-white/5 border border-white/10 rounded-xl">
                    <div className="w-14 h-14 rounded-xl overflow-hidden bg-black/40 border border-white/10 flex-shrink-0 flex items-center justify-center">
                      {editOrgLogo ? (
                        <img src={editOrgLogo} alt="Org Logo Preview" className="w-full h-full object-cover" />
                      ) : (
                        <span className="text-2xl">🏛️</span>
                      )}
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <label className="cursor-pointer px-3 py-1.5 bg-orange-600 hover:bg-orange-500 text-white rounded-lg text-xs font-bold transition flex items-center gap-1.5">
                          {uploadingLogo ? (
                            <span>上传中...</span>
                          ) : (
                            <>
                              <Upload className="w-3.5 h-3.5" />
                              <span>本地上传Logo</span>
                            </>
                          )}
                          <input
                            type="file"
                            accept="image/*"
                            className="hidden"
                            disabled={uploadingLogo}
                            onChange={(e) => {
                              const file = e.target.files?.[0];
                              if (file) handleFileUpload(file, "editOrg");
                            }}
                          />
                        </label>
                        {editOrgLogo && (
                          <button
                            type="button"
                            onClick={() => setNewOrgLogo("")}
                            className="px-2 py-1.5 text-xs text-zinc-400 hover:text-red-400 hover:bg-white/5 rounded-lg transition"
                          >
                            清除
                          </button>
                        )}
                      </div>
                      <p className="text-[11px] text-zinc-500 mt-1.5">支持本地图片上传</p>
                    </div>
                  </div>
                </div>

                <div className="flex gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => setShowEditOrgModal(false)}
                    className="flex-1 py-2.5 rounded-xl bg-white/5 border border-white/10 text-xs font-bold text-zinc-400 hover:text-white"
                  >
                    取消
                  </button>
                  <button
                    type="submit"
                    disabled={submitting}
                    className="flex-1 py-2.5 rounded-xl bg-orange-600 text-white text-xs font-bold hover:opacity-90 disabled:opacity-50"
                  >
                    {submitting ? "正在保存..." : "保存更新"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* ── Modal 6: Org Roster Modal (戈友实名认证花名册审核) ── */}
        {showOrgRosterModal && activeOrg && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
            <div className="relative w-full max-w-4xl bg-[#141416] border border-white/10 rounded-3xl p-6 sm:p-8 shadow-2xl max-h-[90vh] flex flex-col">
              <button
                onClick={() => setShowOrgRosterModal(false)}
                className="absolute top-6 right-6 p-2 rounded-full text-zinc-400 hover:text-white hover:bg-white/5"
              >
                <X className="w-5 h-5" />
              </button>

              <div className="mb-5">
                <div className="flex items-center gap-2.5">
                  <h3 className="text-xl font-bold text-white">
                    【{activeOrg.name}】戈友实名认证花名册
                  </h3>
                  <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-orange-500/20 text-orange-400 border border-orange-500/30">
                    {orgMembers.length} 位认证成员
                  </span>
                </div>
                <p className="text-xs text-zinc-400 mt-1">
                  管理员可核对戈友真实姓名、性别、出生日期、商学院班级与挂靠分队，并完成实名审核
                </p>
              </div>

              {/* Search Bar */}
              <div className="relative mb-4">
                <Search className="absolute left-3.5 top-3 w-4 h-4 text-zinc-500" />
                <input
                  type="text"
                  value={rosterSearch}
                  onChange={(e) => setRosterSearch(e.target.value)}
                  placeholder="搜索戈友真实姓名、班级届别、手机号或昵称..."
                  className="w-full pl-10 pr-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-orange-500"
                />
              </div>

              {/* Roster Table */}
              <div className="flex-1 overflow-y-auto border border-white/10 rounded-2xl bg-black/20">
                {rosterLoading ? (
                  <div className="p-12 text-center text-zinc-500 text-sm flex items-center justify-center gap-2">
                    <RefreshCw className="w-4 h-4 animate-spin text-orange-400" />
                    <span>正在加载戈友认证花名册...</span>
                  </div>
                ) : filteredMembers.length === 0 ? (
                  <div className="p-12 text-center text-zinc-500 text-sm">
                    暂无符合条件的成员记录
                  </div>
                ) : (
                  <table className="w-full text-left border-collapse text-xs">
                    <thead>
                      <tr className="border-b border-white/10 bg-white/[0.02] text-zinc-400 font-semibold">
                        <th className="p-3.5">实名 / 跑者</th>
                        <th className="p-3.5">商学院班级</th>
                        <th className="p-3.5">生理资料 (脱敏)</th>
                        <th className="p-3.5">联系手机</th>
                        <th className="p-3.5">加入分跑团</th>
                        <th className="p-3.5">认证状态</th>
                        <th className="p-3.5 text-right">审核操作</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5">
                      {filteredMembers.map((m) => (
                        <tr key={m.id} className="hover:bg-white/[0.02] transition">
                          <td className="p-3.5">
                            <div className="flex items-center gap-2.5">
                              <img
                                src={m.avatar_url || "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80"}
                                alt="Avatar"
                                className="w-8 h-8 rounded-full object-cover border border-white/10 shrink-0"
                              />
                              <div>
                                <span className="font-bold text-white block text-sm">{m.real_name || "未实名"}</span>
                                <span className="text-[11px] text-zinc-500 block">昵称: {m.display_name || "跑友"}</span>
                              </div>
                            </div>
                          </td>
                          <td className="p-3.5 font-medium text-amber-300">
                            {m.class_name || "复旦商学院"}
                          </td>
                          <td className="p-3.5 text-zinc-300">
                            <span>{m.gender === "female" ? "🚺 女" : "🚹 男"}</span>
                            <span className="text-zinc-500 mx-1">·</span>
                            <span>{m.date_of_birth ? `${m.date_of_birth.substring(0, 4)}年生` : "--"}</span>
                          </td>
                          <td className="p-3.5 text-zinc-400 font-mono">
                            {m.phone || "未填写"}
                          </td>
                          <td className="p-3.5">
                            {m.sub_clubs && m.sub_clubs.length > 0 ? (
                              <div className="flex flex-wrap gap-1">
                                {m.sub_clubs.map((sc: any) => (
                                  <span key={sc.id} className="px-2 py-0.5 rounded bg-white/10 text-[11px] text-zinc-200">
                                    {sc.name}
                                  </span>
                                ))}
                              </div>
                            ) : (
                              <span className="text-zinc-600 text-[11px]">未加入分跑团</span>
                            )}
                          </td>
                          <td className="p-3.5">
                            <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                              m.status === 'confirmed'
                                ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                                : 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                            }`}>
                              {m.status === 'confirmed' ? '✓ 已核验确认' : '⏳ 待核对'}
                            </span>
                          </td>
                          <td className="p-3.5 text-right">
                            {m.status !== 'confirmed' ? (
                              <button
                                onClick={() => handleConfirmMember(m.user_id)}
                                disabled={confirmingUid === m.user_id}
                                className="px-2.5 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs transition disabled:opacity-50"
                              >
                                {confirmingUid === m.user_id ? "确认中..." : "核验通过"}
                              </button>
                            ) : (
                              <span className="text-zinc-600 text-xs flex items-center justify-end gap-1">
                                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                                已通过
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ── Modal 7: Org Clubs Management (挂靠分跑团管理) ── */}
        {showOrgClubsModal && activeOrg && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
            <div className="relative w-full max-w-2xl bg-[#141416] border border-white/10 rounded-3xl p-6 sm:p-8 shadow-2xl max-h-[90vh] flex flex-col">
              <button
                onClick={() => setShowOrgClubsModal(false)}
                className="absolute top-6 right-6 p-2 rounded-full text-zinc-400 hover:text-white hover:bg-white/5"
              >
                <X className="w-5 h-5" />
              </button>

              <div className="mb-5">
                <h3 className="text-xl font-bold text-white flex items-center gap-2">
                  <Link2 className="w-5 h-5 text-blue-400" />
                  【{activeOrg.name}】挂靠分跑团管理
                </h3>
                <p className="text-xs text-zinc-400 mt-1">
                  管理挂靠在此大群体下的下属分跑团。加入大群体的戈友可在小程序内直接选择或受邀加入各分队。
                </p>
              </div>

              <div className="flex-1 overflow-y-auto space-y-5 pr-1">
                {/* Currently Bound Sub-Clubs */}
                <div>
                  <div className="flex items-center justify-between mb-2.5">
                    <h4 className="text-xs font-bold text-zinc-300 flex items-center gap-1.5">
                      <span>已挂靠的下属跑团</span>
                      <span className="px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-400 text-[10px]">
                        {orgSubClubs.length} 个
                      </span>
                    </h4>
                  </div>

                  {orgSubClubs.length === 0 ? (
                    <div className="p-6 rounded-2xl bg-white/[0.02] border border-dashed border-white/10 text-center text-xs text-zinc-500">
                      该大组织下暂未挂靠任何跑团，请从下方独立跑团中选择挂靠！
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {orgSubClubs.map((sc) => (
                        <div
                          key={sc.id}
                          className="flex items-center justify-between p-3.5 bg-white/5 border border-white/10 rounded-2xl"
                        >
                          <div className="flex items-center gap-3">
                            <img
                              src={sc.logo_url || "https://images.unsplash.com/photo-1552674605-db6ffd4facb5?w=300&auto=format&fit=crop&q=80"}
                              alt={sc.name}
                              className="w-10 h-10 rounded-xl object-cover border border-white/10 shrink-0"
                            />
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="font-bold text-white text-sm">{sc.name}</span>
                                <span className="text-[10px] px-2 py-0.5 rounded bg-blue-500/20 text-blue-300">
                                  {sc.city || "上海"}
                                </span>
                              </div>
                              <span className="text-xs text-zinc-400 mt-0.5 block">
                                团长: {sc.owner_name || "未指定"} · {sc.member_count || 1} 位队员
                              </span>
                            </div>
                          </div>

                          <button
                            onClick={() => handleBindClub(sc.id, "unbind")}
                            disabled={bindingClubLoading === sc.id}
                            className="px-3 py-1.5 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 hover:bg-red-500/20 text-xs font-bold transition flex items-center gap-1"
                          >
                            <Unlink className="w-3 h-3" />
                            <span>{bindingClubLoading === sc.id ? "解绑中..." : "解除挂靠"}</span>
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Available Other Clubs to Bind */}
                <div className="pt-4 border-t border-white/10">
                  <div className="flex items-center justify-between mb-2.5">
                    <h4 className="text-xs font-bold text-zinc-300 flex items-center gap-1.5">
                      <span>平台未挂靠或其它跑团</span>
                    </h4>
                  </div>

                  <div className="space-y-2">
                    {clubs
                      .filter((c) => c.org_id !== activeOrg.id)
                      .map((c) => (
                        <div
                          key={c.id}
                          className="flex items-center justify-between p-3.5 bg-white/[0.02] border border-white/5 rounded-2xl hover:bg-white/[0.04] transition"
                        >
                          <div className="flex items-center gap-3">
                            <img
                              src={c.logo_url || "https://images.unsplash.com/photo-1552674605-db6ffd4facb5?w=300&auto=format&fit=crop&q=80"}
                              alt={c.name}
                              className="w-10 h-10 rounded-xl object-cover border border-white/10 shrink-0"
                            />
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="font-bold text-white text-sm">{c.name}</span>
                                {c.org_name ? (
                                  <span className="text-[10px] px-2 py-0.5 rounded bg-zinc-700 text-zinc-300">
                                    现属于: {c.org_name}
                                  </span>
                                ) : (
                                  <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400">
                                    独立自由跑团
                                  </span>
                                )}
                              </div>
                              <span className="text-xs text-zinc-400 mt-0.5 block">
                                团长: {c.owner_name || "未指定"}
                              </span>
                            </div>
                          </div>

                          <button
                            onClick={() => handleBindClub(c.id, "bind")}
                            disabled={bindingClubLoading === c.id}
                            className="px-3 py-1.5 rounded-xl bg-orange-600 hover:bg-orange-500 text-white text-xs font-bold transition flex items-center gap-1"
                          >
                            <Link2 className="w-3 h-3" />
                            <span>{bindingClubLoading === c.id ? "挂靠中..." : "挂靠至该组织"}</span>
                          </button>
                        </div>
                      ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
