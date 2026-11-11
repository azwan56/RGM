"use client";

import { useEffect, useState } from "react";
import Navbar from "@/components/Navbar";
import axios from "axios";
import { formatBeijingTime } from "@/lib/apiClient";
import { showToast, askConfirm } from "@/components/ui/UiFeedbackProvider";
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
  School,
  ShieldCheck,
  Clock,
  FileText,
  Save,
  Pause,
  Play,
  Trash2,
  AlertTriangle,
  Activity,
  BarChart2,
  Eye,
  ArrowRight,
  Smartphone,
  TrendingUp
} from "lucide-react";

export default function AdminPage() {
  const [adminToken, setAdminToken] = useState<string | null>(null);
  const [adminInfo, setAdminInfo] = useState<any>(null);

  // Tab state: 'orgs' (大群体架构) | 'clubs' (分跑团) | 'unaffiliated' (未入团自由跑友) | 'support' (用户问题反馈工单) | 'analytics' (用户体验与行为分析)
  const [activeTab, setActiveTab] = useState<"orgs" | "clubs" | "unaffiliated" | "support" | "analytics">("orgs");

  // Unaffiliated users roster state
  const [unaffiliatedData, setUnaffiliatedData] = useState<any>(null);
  const [unaffiliatedFilter, setUnaffiliatedFilter] = useState<"all" | "recent" | "pending" | "ready">("all");
  const [unaffiliatedSearch, setUnaffiliatedSearch] = useState<string>("");
  const [remindingUnaffiliatedUid, setRemindingUnaffiliatedUid] = useState<string>("");

  // UX & Behavior Analytics states
  const [analyticsDays, setAnalyticsDays] = useState<number>(14);
  const [analyticsData, setAnalyticsData] = useState<any>(null);
  const [analyticsLoading, setAnalyticsLoading] = useState<boolean>(false);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [sessionDetail, setSessionDetail] = useState<any>(null);
  const [sessionDetailLoading, setSessionDetailLoading] = useState<boolean>(false);
  const [userJourneyData, setUserJourneyData] = useState<any>(null);
  const [userJourneyLoading, setUserJourneyLoading] = useState<boolean>(false);

  // Login form state
  const [email, setEmail] = useState("admin@rgm.com");
  const [password, setPassword] = useState("");
  const [loginLoading, setLoginLoading] = useState(false);
  const [loginError, setLoginError] = useState("");

  // Data states
  const [orgs, setOrgs] = useState<any[]>([]);
  const [clubs, setClubs] = useState<any[]>([]);
  const [users, setUsers] = useState<any[]>([]);
  const [supportTickets, setSupportTickets] = useState<any[]>([]);
  const [replyDrafts, setReplyDrafts] = useState<Record<string, string>>({});
  const [replyingTicketId, setReplyingTicketId] = useState<string | null>(null);
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
  const [editClubStatus, setEditClubStatus] = useState<"active" | "paused" | "locked">("active");

  const [selectedNewOwnerId, setSelectedNewOwnerId] = useState("");

  // Club Lifecycle & Filter states
  const [clubStatusFilter, setClubStatusFilter] = useState<"all" | "active" | "paused" | "locked">("all");
  const [showDeleteClubModal, setShowDeleteClubModal] = useState(false);
  const [clubToDelete, setClubToDelete] = useState<any>(null);
  const [deleteConfirmInput, setDeleteConfirmInput] = useState("");
  const [statusChangingId, setStatusChangingId] = useState<string | null>(null);


  // Org Modal states
  const [showCreateOrgModal, setShowCreateOrgModal] = useState(false);
  const [showEditOrgModal, setShowEditOrgModal] = useState(false);
  const [showOrgRosterModal, setShowOrgRosterModal] = useState(false);
  const [showOrgClubsModal, setShowOrgClubsModal] = useState(false);
  const [showOrgFieldRulesModal, setShowOrgFieldRulesModal] = useState(false);
  const [orgFieldRules, setOrgFieldRules] = useState<any[]>([]);
  const [loadingFieldRules, setLoadingFieldRules] = useState(false);
  const [savingFieldRules, setSavingFieldRules] = useState(false);
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
  const [updatingRoleUid, setUpdatingRoleUid] = useState<string | null>(null);

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
      showToast("请选择有效的图片文件（JPG, PNG, WebP 等）");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      showToast("图片文件大小不能超过 10MB");
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
      showToast(msg);
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
    setSupportTickets([]);
  }

  async function loadAdminData(token: string) {
    setLoadingData(true);
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const [clubsRes, usersRes, orgsRes, ticketsRes, unaffRes] = await Promise.all([
        axios.get("/api/admin/clubs", { headers }),
        axios.get("/api/admin/users", { headers }),
        axios.get("/api/org/admin/all-list", { headers }).catch(() => ({ data: { organizations: [] } })),
        axios.get("/api/admin/support-tickets", { headers }).catch(() => ({ data: { tickets: [] } })),
        axios.get("/api/admin/unaffiliated-users", { headers }).catch(() => ({ data: null }))
      ]);
      setClubs(clubsRes.data?.clubs || []);
      const userList = usersRes.data?.users || [];
      setUsers(userList);
      setOrgs(orgsRes.data?.organizations || []);
      if (unaffRes?.data) {
        setUnaffiliatedData(unaffRes.data);
      }
      const tList = ticketsRes.data?.tickets || [];
      setSupportTickets(tList);
      const drafts: Record<string, string> = {};
      tList.forEach((t: any) => {
        if (t.admin_reply) drafts[t.id] = t.admin_reply;
      });
      setReplyDrafts(drafts);
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

  async function handleRemindUnaffiliatedUser(targetUid: string, displayName: string) {
    if (!adminToken || !targetUid) return;
    setRemindingUnaffiliatedUid(targetUid);
    try {
      const res = await axios.post(
        `/api/admin/unaffiliated-users/${encodeURIComponent(targetUid)}/remind`,
        {},
        { headers: { Authorization: `Bearer ${adminToken}` } }
      );
      setActionSuccessMsg(res.data?.message || `已向【${displayName || targetUid}】发送完善绑表与目标设定提醒！`);
    } catch (err: any) {
      showToast(err.response?.data?.detail || "发送提醒失败");
    } finally {
      setRemindingUnaffiliatedUid("");
    }
  }

  async function handleReplySupportTicket(ticketId: string, status: string = "resolved") {
    if (!adminToken) return;
    const replyText = (replyDrafts[ticketId] || "").trim();
    if (!replyText) {
      showToast("请输入回复内容");
      return;
    }
    setReplyingTicketId(ticketId);
    try {
      await axios.post(
        `/api/admin/support-tickets/${ticketId}/reply`,
        { admin_reply: replyText, status },
        { headers: { Authorization: `Bearer ${adminToken}` } }
      );
      setActionSuccessMsg("已保存技术支持回复，用户端「我的 -> 帮助与技术支持」将实时可见！");
      loadAdminData(adminToken);
    } catch (err: any) {
      showToast(err.response?.data?.detail || "回复失败");
    } finally {
      setReplyingTicketId(null);
    }
  }

  async function loadSessionTimeline(sessionId: string, tokenOverride?: string) {
    const tk = tokenOverride || adminToken;
    if (!tk || !sessionId) return;
    setSelectedSessionId(sessionId);
    setSessionDetailLoading(true);
    try {
      const res = await axios.get(`/api/admin/analytics/sessions/${encodeURIComponent(sessionId)}`, {
        headers: { Authorization: `Bearer ${tk}` }
      });
      setSessionDetail(res.data || null);
    } catch (err: any) {
      console.error("Load session timeline error:", err);
      setSessionDetail(null);
    } finally {
      setSessionDetailLoading(false);
    }
  }

  async function loadAnalyticsOverview(daysOverride?: number, tokenOverride?: string) {
    const tk = tokenOverride || adminToken;
    if (!tk) return;
    const d = daysOverride ?? analyticsDays;
    setAnalyticsLoading(true);
    try {
      const res = await axios.get(`/api/admin/analytics/overview?days=${d}&include_wechat=true`, {
        headers: { Authorization: `Bearer ${tk}` }
      });
      const data = res.data || null;
      setAnalyticsData(data);
      const recent = data?.behavior?.recent_sessions || [];
      if (recent.length > 0) {
        const currentStillExists = selectedSessionId && recent.some((s: any) => s.session_id === selectedSessionId);
        const targetSid = currentStillExists ? selectedSessionId! : recent[0].session_id;
        loadSessionTimeline(targetSid, tk);
      } else {
        setSelectedSessionId(null);
        setSessionDetail(null);
      }
    } catch (err: any) {
      console.error("Load analytics overview error:", err);
      setActionErrorMsg(err.response?.data?.detail || "加载行为统计数据失败");
    } finally {
      setAnalyticsLoading(false);
    }
  }

  async function loadUserJourney(userId: string) {
    if (!adminToken || !userId) return;
    setUserJourneyLoading(true);
    try {
      const res = await axios.get(`/api/admin/analytics/users/${encodeURIComponent(userId)}/journey?limit=15`, {
        headers: { Authorization: `Bearer ${adminToken}` }
      });
      setUserJourneyData(res.data || null);
    } catch (err: any) {
      showToast(err.response?.data?.detail || "加载该跑者历史访问记录失败");
    } finally {
      setUserJourneyLoading(false);
    }
  }

  useEffect(() => {
    if (activeTab === "analytics" && adminToken && !analyticsData && !analyticsLoading) {
      loadAnalyticsOverview(analyticsDays, adminToken);
    }
  }, [activeTab, adminToken]);

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
    setEditClubStatus(club.status || "active");
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
      const res = await axios.get(`/api/org/${org.id}/members?operator_uid=super_admin`);
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

  async function openOrgFieldRulesModal(org: any) {
    setActiveOrg(org);
    setShowOrgFieldRulesModal(true);
    setLoadingFieldRules(true);
    try {
      const res = await axios.get(`/api/org/${org.id}/field-rules`);
      setOrgFieldRules(res.data?.field_rules || []);
    } catch (err: any) {
      setActionErrorMsg("加载准入字段规则失败");
    } finally {
      setLoadingFieldRules(false);
    }
  }

  async function handleSaveFieldRules() {
    if (!adminToken || !activeOrg) return;
    setSavingFieldRules(true);
    try {
      await axios.put(
        `/api/org/${activeOrg.id}/field-rules`,
        { field_rules: orgFieldRules },
        { headers: { Authorization: `Bearer ${adminToken}` } }
      );
      setActionSuccessMsg("准入必填字段规则更新成功！");
      setShowOrgFieldRulesModal(false);
      loadAdminData(adminToken);
    } catch (err: any) {
      showToast(err.response?.data?.detail || "保存准入规则失败");
    } finally {
      setSavingFieldRules(false);
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
          status: editClubStatus,
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

  async function handleSetClubStatus(clubId: string, status: "active" | "paused" | "locked") {
    if (!adminToken) return;
    setStatusChangingId(clubId);
    setActionErrorMsg("");
    try {
      const res = await axios.post(
        `/api/admin/clubs/${clubId}/status`,
        { status },
        { headers: { Authorization: `Bearer ${adminToken}` } }
      );
      setActionSuccessMsg(res.data.message || "跑团状态更新成功");
      loadAdminData(adminToken);
    } catch (err: any) {
      setActionErrorMsg(err.response?.data?.detail || "更新跑团状态失败");
    } finally {
      setStatusChangingId(null);
    }
  }

  function openDeleteClubModal(club: any) {
    setClubToDelete(club);
    setDeleteConfirmInput("");
    setActionErrorMsg("");
    setShowDeleteClubModal(true);
  }

  async function handleDeleteClub(e: React.FormEvent) {
    e.preventDefault();
    if (!adminToken || !clubToDelete) return;
    if (deleteConfirmInput.trim() !== clubToDelete.name.trim()) {
      setActionErrorMsg("输入的跑团名称与当前跑团不一致，请核实后重新输入！");
      return;
    }
    setSubmitting(true);
    setActionErrorMsg("");
    try {
      const res = await axios.delete(`/api/admin/clubs/${clubToDelete.id}`, {
        headers: { Authorization: `Bearer ${adminToken}` },
      });
      setActionSuccessMsg(res.data.message || "跑团已成功删除，队员个人历史数据已完整保留");
      setShowDeleteClubModal(false);
      setClubToDelete(null);
      setDeleteConfirmInput("");
      loadAdminData(adminToken);
    } catch (err: any) {
      setActionErrorMsg(err.response?.data?.detail || "删除跑团失败");
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

  async function handleGrantGracePeriod(targetUid: string) {
    if (!adminToken || !activeOrg) return;
    setConfirmingUid(targetUid);
    try {
      await axios.post(`/api/org/${activeOrg.id}/members/${targetUid}/grace-period`);
      setOrgMembers((prev) =>
        prev.map((m) => (m.user_id === targetUid ? { ...m, status: "temporary", days_remaining: 14 } : m))
      );
      setActionSuccessMsg("已成功为该队员重置 14 天临时宽限期！");
    } catch (err: any) {
      showToast(err.response?.data?.detail || "重置宽限期失败");
    } finally {
      setConfirmingUid(null);
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
      const errorMsg = err.response?.data?.detail || "确认成员失败";
      const targetMember = orgMembers.find((m) => m.user_id === targetUid);
      if (targetMember?.status === 'expired' && errorMsg.includes("必填资料尚未补齐")) {
        const grant = await askConfirm(`${errorMsg}\n\n是否为该队员重置 14 天临时访问宽限期，给予其充足时间在小程序补齐资料？`);
        if (grant) {
          await handleGrantGracePeriod(targetUid);
          return;
        }
      } else {
        showToast(errorMsg);
      }
    } finally {
      setConfirmingUid(null);
    }
  }

  async function handleUpdateOrgRole(targetUid: string, newRole: "admin" | "member") {
    if (!adminToken || !activeOrg) return;
    setUpdatingRoleUid(targetUid);
    try {
      await axios.post(`/api/org/${activeOrg.id}/members/${targetUid}/role`, {
        role: newRole,
        operator_uid: "super_admin"
      });
      setOrgMembers((prev) =>
        prev.map((m) => (m.user_id === targetUid ? { ...m, role: newRole } : m))
      );
      setActionSuccessMsg(newRole === "admin" ? "已成功委派为大群管理员！" : "已撤销管理员权限！");
    } catch (err: any) {
      showToast(err.response?.data?.detail || "调整角色失败");
    } finally {
      setUpdatingRoleUid(null);
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
      showToast(err.response?.data?.detail || "操作挂靠失败");
    } finally {
      setBindingClubLoading(null);
    }
  }

  function handleCopyInvite(code: string) {
    navigator.clipboard.writeText(code);
    setCopiedCode(code);
    setTimeout(() => setCopiedCode(""), 2000);
  }

  function getAgeGroup(dob?: string, fallbackGroup?: string): string {
    if (fallbackGroup) return fallbackGroup;
    if (!dob) return "青年组";
    try {
      const y = parseInt(dob.slice(0, 4), 10);
      const thisYear = new Date().getFullYear();
      const age = thisYear - y;
      if (age >= 50) return "大师组";
      if (age >= 40) return "壮年组";
      if (age >= 30) return "中坚组";
      return "青年组";
    } catch {
      return "青年组";
    }
  }

  const filteredMembers = orgMembers.filter((m) => {
    if (!rosterSearch.trim()) return true;
    const q = rosterSearch.toLowerCase();
    return (
      (m.real_name && m.real_name.toLowerCase().includes(q)) ||
      (m.class_name && m.class_name.toLowerCase().includes(q)) ||
      (m.program && m.program.toLowerCase().includes(q)) ||
      (m.gobi_experience && m.gobi_experience.toLowerCase().includes(q)) ||
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
            <div className="flex flex-wrap items-center gap-3 border-b border-white/10 pb-4">
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

              <button
                onClick={() => setActiveTab("unaffiliated")}
                className={`flex items-center gap-2.5 px-5 py-3 rounded-2xl font-bold text-sm transition-all ${
                  activeTab === "unaffiliated"
                    ? "bg-gradient-to-r from-orange-600 to-red-600 text-white shadow-lg shadow-orange-600/25 border border-orange-400/30"
                    : "bg-[#141416] text-zinc-400 hover:text-white hover:bg-white/5 border border-white/5"
                }`}
              >
                <UserCheck className="w-4 h-4" />
                <span>🌍 未入团自由跑友 ({unaffiliatedData?.summary?.total_members ?? 0})</span>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-black/40 text-cyan-300 font-normal">
                  ⌚已绑表 {unaffiliatedData?.summary?.watch_bound_count ?? 0} · 🎯已设目标 {unaffiliatedData?.summary?.goal_set_count ?? 0}
                </span>
              </button>

              <button
                onClick={() => setActiveTab("support")}
                className={`flex items-center gap-2.5 px-5 py-3 rounded-2xl font-bold text-sm transition-all ${
                  activeTab === "support"
                    ? "bg-gradient-to-r from-orange-600 to-red-600 text-white shadow-lg shadow-orange-600/25 border border-orange-400/30"
                    : "bg-[#141416] text-zinc-400 hover:text-white hover:bg-white/5 border border-white/5"
                }`}
              >
                <FileText className="w-4 h-4" />
                <span>💬 用户技术支持工单 ({supportTickets.length})</span>
                {supportTickets.filter((t) => t.status !== "resolved" && !t.admin_reply).length > 0 && (
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-red-500 text-white font-bold">
                    {supportTickets.filter((t) => t.status !== "resolved" && !t.admin_reply).length} 待处理
                  </span>
                )}
              </button>

              <button
                onClick={() => setActiveTab("analytics")}
                className={`flex items-center gap-2.5 px-5 py-3 rounded-2xl font-bold text-sm transition-all ${
                  activeTab === "analytics"
                    ? "bg-gradient-to-r from-orange-600 to-red-600 text-white shadow-lg shadow-orange-600/25 border border-orange-400/30"
                    : "bg-[#141416] text-zinc-400 hover:text-white hover:bg-white/5 border border-white/5"
                }`}
              >
                <BarChart2 className="w-4 h-4" />
                <span>📊 用户体验与行为分析</span>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-black/40 text-emerald-300 font-normal">
                  单人轨迹回放 · We分析
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
                            src={org.logo_url || "/logo.png"}
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
                          onClick={() => openOrgFieldRulesModal(org)}
                          className="w-full py-2 px-3 rounded-xl bg-purple-500/10 border border-purple-500/30 text-purple-300 hover:bg-purple-500/20 text-xs font-bold transition-all flex items-center justify-center gap-1.5"
                        >
                          <ShieldCheck className="w-3.5 h-3.5" />
                          准入必填字段配置
                        </button>
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
                <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 bg-[#141416] p-4 rounded-2xl border border-white/5">
                  <div className="flex flex-wrap items-center gap-3">
                    <div className="flex items-center gap-2">
                      <Building className="w-5 h-5 text-orange-400" />
                      <span className="text-sm font-bold text-white">
                        跑团总览 ({clubs.length})
                      </span>
                    </div>

                    {/* Filter Pills */}
                    <div className="flex items-center gap-1.5 overflow-x-auto pl-2 border-l border-white/10">
                      <button
                        onClick={() => setClubStatusFilter("all")}
                        className={`px-3 py-1.5 rounded-xl text-xs font-bold transition whitespace-nowrap ${
                          clubStatusFilter === "all"
                            ? "bg-white/15 text-white border border-white/20"
                            : "text-zinc-400 hover:text-white hover:bg-white/5"
                        }`}
                      >
                        全部 ({clubs.length})
                      </button>
                      <button
                        onClick={() => setClubStatusFilter("active")}
                        className={`px-3 py-1.5 rounded-xl text-xs font-bold transition flex items-center gap-1.5 whitespace-nowrap ${
                          clubStatusFilter === "active"
                            ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                            : "text-zinc-400 hover:text-emerald-400 hover:bg-emerald-500/5"
                        }`}
                      >
                        <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
                        正常运行 ({clubs.filter(c => (c.status || "active") === "active").length})
                      </button>
                      <button
                        onClick={() => setClubStatusFilter("paused")}
                        className={`px-3 py-1.5 rounded-xl text-xs font-bold transition flex items-center gap-1.5 whitespace-nowrap ${
                          clubStatusFilter === "paused"
                            ? "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                            : "text-zinc-400 hover:text-amber-400 hover:bg-amber-500/5"
                        }`}
                      >
                        <Pause className="w-2.5 h-2.5 text-amber-400" />
                        已暂停 ({clubs.filter(c => c.status === "paused").length})
                      </button>
                      <button
                        onClick={() => setClubStatusFilter("locked")}
                        className={`px-3 py-1.5 rounded-xl text-xs font-bold transition flex items-center gap-1.5 whitespace-nowrap ${
                          clubStatusFilter === "locked"
                            ? "bg-blue-500/20 text-blue-300 border border-blue-500/30"
                            : "text-zinc-400 hover:text-blue-400 hover:bg-blue-500/5"
                        }`}
                      >
                        <Lock className="w-2.5 h-2.5 text-blue-400" />
                        已锁定 ({clubs.filter(c => c.status === "locked").length})
                      </button>
                    </div>
                  </div>

                  <button
                    onClick={openCreateModal}
                    className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-orange-500 to-[#FC4C02] text-white text-xs font-bold hover:opacity-90 transition-all flex items-center justify-center gap-1.5 shadow-lg shadow-orange-500/20 shrink-0"
                  >
                    <Plus className="w-4 h-4" />
                    添加新跑团并指定团长
                  </button>
                </div>

                {/* Clubs Grid / Cards */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {clubs
                    .filter((club) => {
                      const st = club.status || "active";
                      if (clubStatusFilter === "all") return true;
                      return st === clubStatusFilter;
                    })
                    .map((club) => (
                    <div
                      key={club.id}
                      className="bg-[#141416] border border-white/10 rounded-3xl p-6 flex flex-col justify-between hover:border-white/20 transition-all shadow-xl group"
                    >
                      <div>
                        {/* Top Info */}
                        <div className="flex items-start gap-3.5 mb-3">
                          <img
                            src={club.logo_url || "/logo.png"}
                            alt={club.name}
                            className="w-14 h-14 rounded-2xl object-cover border border-white/10 shrink-0"
                          />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-1.5 flex-wrap">
                              <h3 className="text-base font-bold text-white truncate">{club.name}</h3>
                              {club.status === "paused" ? (
                                <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30 shrink-0 flex items-center gap-1">
                                  <Pause className="w-2.5 h-2.5" /> 已暂停
                                </span>
                              ) : club.status === "locked" ? (
                                <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-blue-500/20 text-blue-300 border border-blue-500/30 shrink-0 flex items-center gap-1">
                                  <Lock className="w-2.5 h-2.5" /> 已锁定
                                </span>
                              ) : (
                                <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 shrink-0 flex items-center gap-1">
                                  <Play className="w-2.5 h-2.5" /> 正常运行
                                </span>
                              )}
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

                        {/* Status Notice Banner if paused or locked */}
                        {club.status === "paused" && (
                          <div className="p-2.5 rounded-2xl bg-amber-500/10 border border-amber-500/20 text-xs text-amber-300/90 flex items-center gap-2 mb-3">
                            <AlertTriangle className="w-4 h-4 shrink-0 text-amber-400" />
                            <span>已暂停运行：暂停消息动态、队员增删与数据更新，对外不可见</span>
                          </div>
                        )}
                        {club.status === "locked" && (
                          <div className="p-2.5 rounded-2xl bg-blue-500/10 border border-blue-500/20 text-xs text-blue-300/90 flex items-center gap-2 mb-3">
                            <Lock className="w-4 h-4 shrink-0 text-blue-400" />
                            <span>已锁定归档：不允许队员增删，对外不可见</span>
                          </div>
                        )}

                        {/* Meta details */}
                        <div className="space-y-2.5 py-3 border-y border-white/5 my-3 text-xs">
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

                        {/* Quick Lifecycle Status Switcher */}
                        <div className="flex items-center justify-between p-2 rounded-2xl bg-white/[0.03] border border-white/5 mb-3 text-xs">
                          <span className="text-zinc-500 text-[11px]">快捷状态:</span>
                          <div className="flex items-center gap-1.5">
                            {(club.status || "active") !== "active" && (
                              <button
                                disabled={statusChangingId === club.id}
                                onClick={() => handleSetClubStatus(club.id, "active")}
                                className="px-2 py-1 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 text-[11px] font-bold border border-emerald-500/20 transition flex items-center gap-1"
                                title="恢复跑团正常运行"
                              >
                                <Play className="w-2.5 h-2.5" />
                                恢复正常
                              </button>
                            )}
                            {club.status !== "paused" && (
                              <button
                                disabled={statusChangingId === club.id}
                                onClick={() => handleSetClubStatus(club.id, "paused")}
                                className="px-2 py-1 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 text-[11px] font-bold border border-amber-500/20 transition flex items-center gap-1"
                                title="暂停跑团运行（暂停消息、队员增删、数据更新）"
                              >
                                <Pause className="w-2.5 h-2.5" />
                                暂停
                              </button>
                            )}
                            {club.status !== "locked" && (
                              <button
                                disabled={statusChangingId === club.id}
                                onClick={() => handleSetClubStatus(club.id, "locked")}
                                className="px-2 py-1 rounded-lg bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 text-[11px] font-bold border border-blue-500/20 transition flex items-center gap-1"
                                title="锁定跑团（禁止队员增删）"
                              >
                                <Lock className="w-2.5 h-2.5" />
                                锁定
                              </button>
                            )}
                          </div>
                        </div>
                      </div>

                      {/* Actions Buttons */}
                      <div className="grid grid-cols-3 gap-2 pt-2">
                        <button
                          onClick={() => openAssignModal(club)}
                          className="py-2.5 px-2 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 hover:bg-amber-500/20 text-xs font-bold transition-all flex items-center justify-center gap-1 shadow-sm"
                        >
                          <Crown className="w-3.5 h-3.5 shrink-0" />
                          换团长
                        </button>
                        <button
                          onClick={() => openEditModal(club)}
                          className="py-2.5 px-2 rounded-xl bg-white/5 border border-white/10 text-zinc-300 hover:text-white hover:bg-white/10 text-xs font-bold transition-all flex items-center justify-center gap-1"
                        >
                          <Edit2 className="w-3.5 h-3.5 shrink-0" />
                          编辑
                        </button>
                        <button
                          onClick={() => openDeleteClubModal(club)}
                          className="py-2.5 px-2 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 hover:bg-red-500/20 hover:text-red-300 text-xs font-bold transition-all flex items-center justify-center gap-1"
                          title="解散删除跑团（队员个人数据完整保留）"
                        >
                          <Trash2 className="w-3.5 h-3.5 shrink-0" />
                          删除
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* TAB 2.5: Unaffiliated Users View */}
            {activeTab === "unaffiliated" && (
              <div className="space-y-6">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-[#141416] p-5 rounded-2xl border border-white/10">
                  <div>
                    <div className="flex items-center gap-2">
                      <UserCheck className="w-5 h-5 text-orange-400" />
                      <h2 className="text-base font-bold text-white">
                        🌍 未入团自由跑友全局名册 ({unaffiliatedData?.summary?.total_members ?? 0} 人)
                      </h2>
                    </div>
                    <p className="text-xs text-zinc-400 mt-1">
                      展示尚未加入任何跑团的注册跑友及其注册时间、运动手表绑定状态、周/月目标设定状态与月跑量进度。支持一键发送系统提醒或查看个人档案。
                    </p>
                  </div>
                  <button
                    onClick={() => adminToken && loadAdminData(adminToken)}
                    className="px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-xs font-bold text-zinc-200 flex items-center gap-1.5"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${loadingData ? "animate-spin text-orange-400" : ""}`} />
                    刷新名册
                  </button>
                </div>

                {/* 4 KPI Summary Cards */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div
                    onClick={() => setUnaffiliatedFilter("recent")}
                    className="bg-[#141416] border border-white/10 rounded-2xl p-4 cursor-pointer hover:border-orange-500/40 transition"
                  >
                    <div className="text-2xl font-black text-orange-400">
                      {unaffiliatedData?.summary?.new_7d_count ?? 0} <span className="text-xs font-bold">人</span>
                    </div>
                    <div className="text-xs font-bold text-white mt-1">🌱 近7天新注册</div>
                    <div className="text-[11px] text-zinc-400 mt-0.5">
                      近30天新注册 {unaffiliatedData?.summary?.new_30d_count ?? 0} 人
                    </div>
                  </div>

                  <div
                    onClick={() => setUnaffiliatedFilter("pending")}
                    className="bg-[#141416] border border-white/10 rounded-2xl p-4 cursor-pointer hover:border-emerald-500/40 transition"
                  >
                    <div className="text-2xl font-black text-emerald-400">
                      {unaffiliatedData?.summary?.watch_bound_count ?? 0} / {unaffiliatedData?.summary?.total_members ?? 0}
                    </div>
                    <div className="text-xs font-bold text-white mt-1">⌚ 手表已绑定</div>
                    <div className="text-[11px] text-zinc-400 mt-0.5">
                      未绑表 {unaffiliatedData?.summary?.watch_unbound_count ?? 0} 人
                    </div>
                  </div>

                  <div
                    onClick={() => setUnaffiliatedFilter("pending")}
                    className="bg-[#141416] border border-white/10 rounded-2xl p-4 cursor-pointer hover:border-cyan-500/40 transition"
                  >
                    <div className="text-2xl font-black text-cyan-400">
                      {unaffiliatedData?.summary?.goal_set_count ?? 0} / {unaffiliatedData?.summary?.total_members ?? 0}
                    </div>
                    <div className="text-xs font-bold text-white mt-1">🎯 目标已设定</div>
                    <div className="text-[11px] text-zinc-400 mt-0.5">
                      未设目标 {unaffiliatedData?.summary?.goal_unset_count ?? 0} 人
                    </div>
                  </div>

                  <div
                    onClick={() => setUnaffiliatedFilter("pending")}
                    className="bg-[#141416] border border-white/10 rounded-2xl p-4 cursor-pointer hover:border-amber-500/40 transition"
                  >
                    <div className="text-2xl font-black text-amber-400">
                      {unaffiliatedData?.summary?.pending_setup_count ?? 0} <span className="text-xs font-bold">人</span>
                    </div>
                    <div className="text-xs font-bold text-white mt-1">⚠️ 待完善设置</div>
                    <div className="text-[11px] text-zinc-400 mt-0.5">支持一键发送提醒通知</div>
                  </div>
                </div>

                {/* Filter Pills & Search */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-[#141416] p-4 rounded-2xl border border-white/5">
                  <div className="flex flex-wrap items-center gap-2">
                    {[
                      { key: "all", label: `全部 (${unaffiliatedData?.summary?.total_members ?? 0})` },
                      { key: "recent", label: `🌱 近30天 (${unaffiliatedData?.summary?.new_30d_count ?? 0})` },
                      { key: "pending", label: `⚠️ 待完善 (${unaffiliatedData?.summary?.pending_setup_count ?? 0})` },
                      {
                        key: "ready",
                        label: `✅ 已配齐 (${Math.max(
                          0,
                          (unaffiliatedData?.summary?.total_members ?? 0) -
                            (unaffiliatedData?.summary?.pending_setup_count ?? 0)
                        )})`
                      }
                    ].map((pill) => (
                      <button
                        key={pill.key}
                        onClick={() => setUnaffiliatedFilter(pill.key as any)}
                        className={`px-3.5 py-1.5 rounded-full text-xs font-bold transition ${
                          unaffiliatedFilter === pill.key
                            ? "bg-orange-500/20 text-orange-400 border border-orange-500/40"
                            : "bg-white/5 text-zinc-400 hover:text-white border border-white/10"
                        }`}
                      >
                        {pill.label}
                      </button>
                    ))}
                  </div>
                  <div className="relative w-full sm:w-72">
                    <Search className="w-4 h-4 text-zinc-500 absolute left-3 top-2.5" />
                    <input
                      type="text"
                      value={unaffiliatedSearch}
                      onChange={(e) => setUnaffiliatedSearch(e.target.value)}
                      placeholder="搜索未入团跑友昵称或 UID..."
                      className="w-full pl-9 pr-3 py-2 bg-white/5 border border-white/10 rounded-xl text-xs text-white placeholder:text-zinc-500 focus:outline-none focus:border-orange-500"
                    />
                  </div>
                </div>

                {/* Unaffiliated Members Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {(unaffiliatedData?.members || [])
                    .filter((m: any) => {
                      if (unaffiliatedFilter === "recent" && !m.is_new_30d) return false;
                      if (unaffiliatedFilter === "pending" && m.watch_bound && m.goal_set) return false;
                      if (unaffiliatedFilter === "ready" && (!m.watch_bound || !m.goal_set)) return false;
                      if (unaffiliatedSearch.trim()) {
                        const q = unaffiliatedSearch.trim().toLowerCase();
                        return (
                          (m.display_name || "").toLowerCase().includes(q) ||
                          (m.user_id || "").toLowerCase().includes(q)
                        );
                      }
                      return true;
                    })
                    .map((m: any) => (
                      <div
                        key={m.user_id}
                        className={`bg-[#141416] border rounded-2xl p-4 flex flex-col justify-between gap-3 ${
                          !m.watch_bound || !m.goal_set ? "border-amber-500/30" : "border-white/10"
                        }`}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex items-center gap-3 min-w-0">
                            <img
                              src={
                                m.avatar_url ||
                                "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80"
                              }
                              alt={m.display_name || "跑友"}
                              className="w-11 h-11 rounded-full object-cover border border-white/20 shrink-0"
                            />
                            <div className="min-w-0">
                              <div className="flex items-center gap-1.5 flex-wrap">
                                <span className="text-sm font-bold text-white truncate">
                                  {m.display_name || "新跑友"}
                                </span>
                                <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/10 text-zinc-300 font-semibold">
                                  🌍 未入团
                                </span>
                                {m.is_new_7d && (
                                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-bold">
                                    🌱 新注册
                                  </span>
                                )}
                              </div>
                              <div className="text-[11px] text-zinc-400 mt-0.5">
                                ⏰ 注册时间：{m.joined_at_display || "早期注册"}
                              </div>
                            </div>
                          </div>
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/5 text-zinc-400 shrink-0">
                            {m.joined_relative_label || "未入团"}
                          </span>
                        </div>

                        <div className="grid grid-cols-2 gap-2.5 text-xs">
                          <div
                            className={`p-2.5 rounded-xl border ${
                              m.watch_bound
                                ? "bg-emerald-500/5 border-emerald-500/25"
                                : "bg-amber-500/5 border-amber-500/25"
                            }`}
                          >
                            <div className="flex items-center justify-between mb-1">
                              <span className="font-bold text-zinc-200">⌚ 手表绑定</span>
                              <span
                                className={`text-[10px] px-1.5 py-0.5 rounded-full font-bold ${
                                  m.watch_bound
                                    ? "bg-emerald-500/20 text-emerald-300"
                                    : "bg-amber-500/20 text-amber-300"
                                }`}
                              >
                                {m.watch_bound ? m.watch_status_label || "已绑表" : "未绑定"}
                              </span>
                            </div>
                            <div className="text-[11px] text-zinc-400">
                              {m.total_runs_count > 0
                                ? `累计 ${m.total_runs_count} 次 · 本月 ${m.month_km || 0}km`
                                : m.watch_bound
                                  ? `本月跑量 ${m.month_km || 0}km`
                                  : "尚未绑定佳明/高驰/苹果/华为"}
                            </div>
                          </div>

                          <div
                            className={`p-2.5 rounded-xl border ${
                              m.goal_set
                                ? "bg-emerald-500/5 border-emerald-500/25"
                                : "bg-amber-500/5 border-amber-500/25"
                            }`}
                          >
                            <div className="flex items-center justify-between mb-1">
                              <span className="font-bold text-zinc-200">🎯 目标设定</span>
                              <span
                                className={`text-[10px] px-1.5 py-0.5 rounded-full font-bold ${
                                  m.goal_set
                                    ? "bg-emerald-500/20 text-emerald-300"
                                    : "bg-amber-500/20 text-amber-300"
                                }`}
                              >
                                {m.goal_set ? "已设定" : "未设目标"}
                              </span>
                            </div>
                            <div className="text-[11px] text-zinc-400">
                              周 {m.weekly_target_km || 50}km · 月 {m.monthly_target_km || 200}km
                              {m.has_training_plan ? " · 📋已排课" : ""}
                            </div>
                          </div>
                        </div>

                        <div className="flex items-center gap-2 pt-1">
                          {(!m.watch_bound || !m.goal_set) && (
                            <button
                              onClick={() => handleRemindUnaffiliatedUser(m.user_id, m.display_name)}
                              disabled={remindingUnaffiliatedUid === m.user_id}
                              className="flex-1 py-2 px-3 rounded-xl bg-orange-500/15 hover:bg-orange-500/25 border border-orange-500/35 text-orange-300 text-xs font-bold transition disabled:opacity-50"
                            >
                              {remindingUnaffiliatedUid === m.user_id
                                ? "发送中..."
                                : "🔔 提醒完善绑表/目标"}
                            </button>
                          )}
                          <a
                            href={`/dashboard/analysis?target_uid=${encodeURIComponent(
                              m.user_id
                            )}&target_name=${encodeURIComponent(m.display_name || "跑友")}`}
                            className="flex-1 py-2 px-3 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-zinc-200 text-xs font-bold text-center transition"
                          >
                            📊 查看跑力档案
                          </a>
                        </div>
                      </div>
                    ))}
                </div>
              </div>
            )}

            {/* TAB 3: Support Tickets View */}
            {activeTab === "support" && (
              <div className="space-y-6">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-[#141416] p-4 rounded-2xl border border-white/5">
                  <div>
                    <div className="flex items-center gap-2">
                      <FileText className="w-5 h-5 text-orange-400" />
                      <h2 className="text-base font-bold text-white">
                        用户技术支持与问题反馈工单 ({supportTickets.length})
                      </h2>
                    </div>
                    <p className="text-xs text-zinc-400 mt-1">
                      自动附带跑者 UID、当前手表绑定状态、所属跑团与手机系统诊断信息。您在此回复后，跑者在小程序「我的 → 帮助与技术支持」中可实时查看。
                    </p>
                  </div>
                </div>

                {supportTickets.length === 0 ? (
                  <div className="bg-[#141416] border border-white/10 rounded-3xl p-12 text-center">
                    <CheckCircle2 className="w-10 h-10 text-emerald-400 mx-auto mb-3 opacity-80" />
                    <p className="text-sm font-bold text-white">当前暂无待处理的用户问题反馈工单</p>
                    <p className="text-xs text-zinc-500 mt-1">
                      当跑者在小程序提交问题留言时，将自动连同设备与跑团诊断信息汇总于此
                    </p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {supportTickets.map((tkt) => {
                      const catMap: Record<string, string> = {
                        device_sync: "⌚ 手表绑定/同步",
                        club_org: "🏕️ 跑团/大群认证",
                        training_data: "📊 训练数据/配速",
                        other: "💡 其他问题建议",
                      };
                      const isResolved = tkt.status === "resolved" || !!tkt.admin_reply;
                      const dev = tkt.device_info || {};
                      return (
                        <div
                          key={tkt.id}
                          className="bg-[#141416] border border-white/10 rounded-3xl p-6 space-y-4 shadow-xl"
                        >
                          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/5 pb-3">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="px-2.5 py-1 rounded-lg text-xs font-bold bg-orange-500/15 text-orange-400 border border-orange-500/30">
                                {catMap[tkt.category] || "💬 问题反馈"}
                              </span>
                              <span className="text-sm font-bold text-white">
                                {tkt.display_name || "微信跑者"}
                              </span>
                              <span className="text-xs font-mono text-zinc-400 bg-white/5 px-2 py-0.5 rounded">
                                {tkt.user_id}
                              </span>
                              {tkt.clubs && tkt.clubs.length > 0 && (
                                <span className="text-xs px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">
                                  🏃 跑团: {tkt.clubs.join("、")}
                                </span>
                              )}
                            </div>
                            <div className="flex items-center gap-2">
                              <span className="text-xs text-zinc-500">
                                {formatBeijingTime(tkt.created_at, true)}
                              </span>
                              <span
                                className={`px-2.5 py-0.5 rounded-full text-xs font-bold ${
                                  isResolved
                                    ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                                    : "bg-amber-500/15 text-amber-400 border border-amber-500/30"
                                }`}
                              >
                                {isResolved ? "✓ 已回复/已解决" : "⏳ 待处理"}
                              </span>
                            </div>
                          </div>

                          {/* Diagnostic Bar */}
                          <div className="flex flex-wrap items-center gap-3 text-xs text-zinc-400 bg-white/[0.02] p-3 rounded-xl border border-white/5">
                            <span>
                              ⌚ 手表状态:{" "}
                              <strong className="text-zinc-200">
                                {dev.watch_status ||
                                  [
                                    tkt.garmin_connected ? `佳明(${tkt.garmin_email || "已绑"})` : "",
                                    tkt.coros_connected ? `高驰(${tkt.coros_account || "已绑"})` : "",
                                    tkt.apple_watch_connected ? "Apple Watch" : "",
                                    tkt.huawei_connected ? "华为手表" : "",
                                  ]
                                    .filter(Boolean)
                                    .join("、") ||
                                  "未连接"}
                              </strong>
                            </span>
                            {(dev.brand || dev.model || dev.system) && (
                              <span>
                                📱 终端:{" "}
                                <strong className="text-zinc-200">
                                  {[dev.brand, dev.model, dev.system].filter(Boolean).join(" ")}
                                </strong>
                              </span>
                            )}
                            {tkt.contact_info && (
                              <span>
                                📞 预留联系方式:{" "}
                                <strong className="text-amber-300">{tkt.contact_info}</strong>
                              </span>
                            )}
                          </div>

                          {/* User Content */}
                          <div className="text-sm text-zinc-100 whitespace-pre-wrap leading-relaxed bg-black/30 p-4 rounded-2xl border border-white/5">
                            {tkt.content}
                          </div>

                          {/* Admin Reply Input */}
                          <div className="flex flex-col sm:flex-row gap-3 pt-1">
                            <input
                              type="text"
                              value={replyDrafts[tkt.id] ?? ""}
                              onChange={(e) =>
                                setReplyDrafts((prev) => ({ ...prev, [tkt.id]: e.target.value }))
                              }
                              placeholder="输入给该跑者的技术支持回复（保存后跑者可在小程序端内直接查看）..."
                              className="flex-1 px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-xs text-white placeholder:text-zinc-500 focus:outline-none focus:border-orange-500"
                            />
                            <button
                              disabled={replyingTicketId === tkt.id}
                              onClick={() => handleReplySupportTicket(tkt.id, "resolved")}
                              className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 text-white text-xs font-bold hover:opacity-90 transition-all shrink-0 disabled:opacity-50"
                            >
                              {replyingTicketId === tkt.id
                                ? "保存中..."
                                : tkt.admin_reply
                                ? "更新回复"
                                : "发送回复并标为已解决"}
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}

            {/* TAB 4: UX & Behavior Analytics View */}
            {activeTab === "analytics" && (
              <div className="space-y-6">
                {/* Action Bar & Period Selector */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-[#141416] p-4 rounded-2xl border border-white/5">
                  <div>
                    <div className="flex items-center gap-2">
                      <BarChart2 className="w-5 h-5 text-orange-400" />
                      <h2 className="text-base font-bold text-white">
                        小程序用户体验与全链路行为分析
                      </h2>
                    </div>
                    <p className="text-xs text-zinc-400 mt-1">
                      单用户「打开小程序 → 页面停留与滚动浏览深度 → 按钮/弹窗点击 → 退出」全链路回放 · 存量转化漏斗 · 微信官方 We分析
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {[7, 14, 30].map((d) => (
                      <button
                        key={d}
                        onClick={() => {
                          setAnalyticsDays(d);
                          loadAnalyticsOverview(d);
                        }}
                        className={`px-3.5 py-2 rounded-xl text-xs font-bold transition-all ${
                          analyticsDays === d
                            ? "bg-orange-600 text-white shadow shadow-orange-600/30"
                            : "bg-white/5 text-zinc-400 hover:text-white border border-white/10"
                        }`}
                      >
                        近 {d} 天
                      </button>
                    ))}
                    <button
                      onClick={() => loadAnalyticsOverview(analyticsDays)}
                      disabled={analyticsLoading}
                      className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-zinc-200 text-xs font-medium border border-white/10 transition-all disabled:opacity-50"
                    >
                      <RefreshCw className={`w-3.5 h-3.5 ${analyticsLoading ? "animate-spin" : ""}`} />
                      {analyticsLoading ? "统计中..." : "刷新"}
                    </button>
                  </div>
                </div>

                {analyticsLoading && !analyticsData ? (
                  <div className="bg-[#141416] p-12 rounded-2xl border border-white/5 text-center text-zinc-400 text-sm">
                    <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-3 text-orange-400" />
                    正在拉取单用户行为埋点、业务转化漏斗与微信官方 We分析 数据...
                  </div>
                ) : (
                  <>
                    {/* ── SECTION 1: Per-User Session Trajectory Replay & Real-Time Telemetry ── */}
                    <div className="bg-[#141416] p-5 rounded-3xl border border-white/5 space-y-5">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-white/5 pb-4">
                        <div className="flex items-center gap-2">
                          <Activity className="w-5 h-5 text-emerald-400" />
                          <h3 className="text-sm font-bold text-white">
                            一、单用户真实访问轨迹回放 & 细粒度交互埋点（近 {analyticsData?.days || analyticsDays} 天）
                          </h3>
                        </div>
                        <span className="text-[11px] text-zinc-400">
                          累计采集埋点事件 <strong className="text-white">{analyticsData?.behavior?.summary?.total_events ?? 0}</strong> 条
                        </span>
                      </div>

                      {/* 6 KPI Summary Cards */}
                      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
                        <div className="bg-black/30 p-3.5 rounded-2xl border border-white/5">
                          <div className="text-[11px] text-zinc-400">总打开会话</div>
                          <div className="text-xl font-black text-white mt-1">
                            {analyticsData?.behavior?.summary?.total_sessions ?? 0}
                            <span className="text-xs font-normal text-zinc-500 ml-1">次</span>
                          </div>
                        </div>
                        <div className="bg-black/30 p-3.5 rounded-2xl border border-white/5">
                          <div className="text-[11px] text-zinc-400">独立访问跑者</div>
                          <div className="text-xl font-black text-emerald-400 mt-1">
                            {analyticsData?.behavior?.summary?.unique_visitors ?? 0}
                            <span className="text-xs font-normal text-zinc-500 ml-1">人</span>
                          </div>
                        </div>
                        <div className="bg-black/30 p-3.5 rounded-2xl border border-white/5">
                          <div className="text-[11px] text-zinc-400">平均单次停留</div>
                          <div className="text-xl font-black text-amber-300 mt-1">
                            {analyticsData?.behavior?.summary?.avg_session_duration_sec ?? 0}
                            <span className="text-xs font-normal text-zinc-500 ml-1">秒</span>
                          </div>
                        </div>
                        <div className="bg-black/30 p-3.5 rounded-2xl border border-white/5">
                          <div className="text-[11px] text-zinc-400">平均访问页数</div>
                          <div className="text-xl font-black text-sky-300 mt-1">
                            {analyticsData?.behavior?.summary?.avg_pages_per_session ?? 0}
                            <span className="text-xs font-normal text-zinc-500 ml-1">页/次</span>
                          </div>
                        </div>
                        <div className="bg-black/30 p-3.5 rounded-2xl border border-white/5">
                          <div className="text-[11px] text-zinc-400">平均下滑浏览深度</div>
                          <div className="text-xl font-black text-purple-300 mt-1">
                            {analyticsData?.behavior?.summary?.avg_scroll_pct ?? 0}
                            <span className="text-xs font-normal text-zinc-500 ml-1">%</span>
                          </div>
                        </div>
                        <div className="bg-black/30 p-3.5 rounded-2xl border border-white/5">
                          <div className="text-[11px] text-zinc-400">秒退跳出率 (10s内无点击)</div>
                          <div className="text-xl font-black text-rose-400 mt-1">
                            {analyticsData?.behavior?.summary?.bounce_sessions_pct ?? 0}
                            <span className="text-xs font-normal text-zinc-500 ml-1">%</span>
                          </div>
                        </div>
                      </div>

                      {/* Split View: Recent Sessions List (Left) + Chronological Timeline Replay (Right) */}
                      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
                        {/* Left: Recent Sessions */}
                        <div className="lg:col-span-5 bg-black/30 rounded-2xl border border-white/5 p-4 flex flex-col max-h-[560px]">
                          <div className="flex items-center justify-between mb-3">
                            <span className="text-xs font-bold text-zinc-200">
                              最近访问会话列表（点击右侧逐秒回放）
                            </span>
                            <span className="text-[11px] text-zinc-500">
                              显示最新 {(analyticsData?.behavior?.recent_sessions || []).length} 次
                            </span>
                          </div>

                          {(analyticsData?.behavior?.recent_sessions || []).length === 0 ? (
                            <div className="flex-1 flex flex-col items-center justify-center text-center py-12 px-4 text-zinc-500 text-xs leading-relaxed">
                              <Smartphone className="w-8 h-8 text-zinc-600 mb-2" />
                              <p className="text-zinc-300 font-semibold mb-1">暂无新采集的单人访问轨迹</p>
                              <p>
                                全链路静默埋点已就绪。新版小程序发布后，每位跑者打开小程序、浏览滚动、点击按钮到退出的完整时间轴将实时呈现在此处。
                              </p>
                            </div>
                          ) : (
                            <div className="space-y-2 overflow-y-auto pr-1">
                              {(analyticsData?.behavior?.recent_sessions || []).map((sess: any) => {
                                const isSelected = selectedSessionId === sess.session_id;
                                return (
                                  <button
                                    key={sess.session_id}
                                    onClick={() => loadSessionTimeline(sess.session_id)}
                                    className={`w-full text-left p-3 rounded-xl border transition-all ${
                                      isSelected
                                        ? "bg-orange-600/15 border-orange-500/50 shadow"
                                        : "bg-white/[0.02] hover:bg-white/[0.05] border-white/5"
                                    }`}
                                  >
                                    <div className="flex items-center justify-between gap-2">
                                      <div className="flex items-center gap-2 min-w-0">
                                        <span className="text-xs font-bold text-white truncate">
                                          {sess.display_name}
                                        </span>
                                        {sess.watch_brand && (
                                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/20 shrink-0">
                                            ⌚ {sess.watch_brand}
                                          </span>
                                        )}
                                        {sess.had_error && (
                                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-500/20 text-red-300 shrink-0">
                                            异常
                                          </span>
                                        )}
                                      </div>
                                      <span className="text-[10px] text-zinc-500 shrink-0">
                                        {formatBeijingTime(sess.started_at)}
                                      </span>
                                    </div>

                                    <div className="text-[11px] text-zinc-400 mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1">
                                      <span className="text-amber-300/90">{sess.scene_label}</span>
                                      <span>·</span>
                                      <span className="truncate max-w-[200px]">
                                        {sess.entry_title} → {sess.exit_title}
                                      </span>
                                    </div>

                                    <div className="flex items-center gap-3 mt-2 text-[11px] text-zinc-300">
                                      <span>⏱️ {sess.duration_sec}s</span>
                                      <span>📄 {sess.page_count} 页</span>
                                      <span>👆 {sess.click_count} 次交互</span>
                                      <span>📜 深度 {sess.max_scroll_pct}%</span>
                                    </div>
                                  </button>
                                );
                              })}
                            </div>
                          )}
                        </div>

                        {/* Right: Chronological Session Timeline Replay */}
                        <div className="lg:col-span-7 bg-black/30 rounded-2xl border border-white/5 p-4 flex flex-col max-h-[560px]">
                          {sessionDetailLoading ? (
                            <div className="flex-1 flex items-center justify-center text-zinc-400 text-xs py-16">
                              <RefreshCw className="w-4 h-4 animate-spin mr-2 text-orange-400" />
                              正在加载单次会话逐秒轨迹...
                            </div>
                          ) : !sessionDetail?.session ? (
                            <div className="flex-1 flex items-center justify-center text-zinc-500 text-xs py-16 text-center px-6">
                              在左侧选择任意一次用户会话，即可在此查看从打开小程序、每个页面停留时长与下滑百分比、点击哪个按钮/弹窗，一直到退出的完整轨迹回放。
                            </div>
                          ) : (
                            <>
                              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 mb-3 border-b border-white/10">
                                <div>
                                  <div className="flex flex-wrap items-center gap-2">
                                    <Eye className="w-4 h-4 text-orange-400" />
                                    <span className="text-sm font-bold text-white">
                                      {sessionDetail.session.display_name} 的单次访问回放
                                    </span>
                                    <span className="text-[11px] px-2 py-0.5 rounded-full bg-white/5 text-zinc-300">
                                      {sessionDetail.session.scene_label}
                                    </span>
                                    {sessionDetail.session.device_model && (
                                      <span className="text-[11px] text-zinc-400">
                                        📱 {sessionDetail.session.device_model}
                                      </span>
                                    )}
                                  </div>
                                  <div className="text-[11px] text-zinc-400 mt-1">
                                    打开时间：{formatBeijingTime(sessionDetail.session.started_at)} · 总停留{" "}
                                    <strong className="text-amber-300">{sessionDetail.session.duration_sec} 秒</strong> · 浏览{" "}
                                    <strong className="text-sky-300">{sessionDetail.session.page_count} 页</strong> · 最大滚动深度{" "}
                                    <strong className="text-purple-300">{sessionDetail.session.max_scroll_pct}%</strong>
                                  </div>
                                </div>

                                {sessionDetail.session.user_id && (
                                  <button
                                    onClick={() => loadUserJourney(sessionDetail.session.user_id)}
                                    disabled={userJourneyLoading}
                                    className="px-3 py-1.5 rounded-xl bg-orange-500/15 hover:bg-orange-500/25 text-orange-300 border border-orange-500/30 text-xs font-bold shrink-0 transition-all"
                                  >
                                    {userJourneyLoading ? "加载中..." : "查看该跑者历次访问"}
                                  </button>
                                )}
                              </div>

                              <div className="space-y-2.5 overflow-y-auto pr-1">
                                {(sessionDetail.events || []).map((ev: any, idx: number) => {
                                  const typeMeta: Record<string, { badge: string; cls: string }> = {
                                    session_start: {
                                      badge: "🚀 打开小程序",
                                      cls: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30"
                                    },
                                    page_enter: {
                                      badge: "📄 进入页面",
                                      cls: "bg-sky-500/15 text-sky-300 border-sky-500/30"
                                    },
                                    subview_enter: {
                                      badge: "🔀 切换子视图",
                                      cls: "bg-indigo-500/15 text-indigo-300 border-indigo-500/30"
                                    },
                                    button_click: {
                                      badge: "👆 点击按钮",
                                      cls: "bg-orange-500/15 text-orange-300 border-orange-500/30"
                                    },
                                    modal_open: {
                                      badge: "🪟 打开弹窗",
                                      cls: "bg-purple-500/15 text-purple-300 border-purple-500/30"
                                    },
                                    modal_close: {
                                      badge: "✖️ 关闭弹窗",
                                      cls: "bg-zinc-500/15 text-zinc-300 border-zinc-500/30"
                                    },
                                    funnel_step: {
                                      badge: "🎯 转化动作",
                                      cls: "bg-amber-500/20 text-amber-200 border-amber-400/40"
                                    },
                                    module_view: {
                                      badge: "👁️ 模块曝光",
                                      cls: "bg-teal-500/15 text-teal-300 border-teal-500/30"
                                    },
                                    page_leave: {
                                      badge: "⏱️ 离开页面",
                                      cls: "bg-zinc-700/30 text-zinc-300 border-zinc-600/40"
                                    },
                                    app_background: {
                                      badge: "⏸️ 切后台/选图",
                                      cls: "bg-slate-500/20 text-slate-300 border-slate-500/30"
                                    },
                                    api_issue: {
                                      badge: "⚠️ 接口慢/异常",
                                      cls: "bg-red-500/20 text-red-300 border-red-500/40"
                                    },
                                    session_end: {
                                      badge: "👋 结束访问",
                                      cls: "bg-slate-600/25 text-slate-200 border-slate-500/30"
                                    }
                                  };
                                  const meta = typeMeta[ev.event_type] || {
                                    badge: ev.event_type,
                                    cls: "bg-white/10 text-zinc-300 border-white/10"
                                  };

                                  return (
                                    <div
                                      key={ev.id || idx}
                                      className="flex items-start gap-3 p-2.5 rounded-xl bg-white/[0.02] border border-white/5"
                                    >
                                      <div className="w-14 shrink-0 text-right font-mono text-[11px] text-zinc-400 pt-0.5">
                                        +{ev.offset_sec}s
                                      </div>
                                      <div className="flex-1 min-w-0">
                                        <div className="flex flex-wrap items-center gap-2">
                                          <span
                                            className={`text-[10px] px-2 py-0.5 rounded-md border font-bold ${meta.cls}`}
                                          >
                                            {meta.badge}
                                          </span>
                                          <span className="text-xs font-semibold text-white">
                                            {ev.event_label}
                                          </span>
                                          {ev.page_title && (
                                            <span className="text-[11px] text-zinc-400">
                                              @{ev.page_title}
                                            </span>
                                          )}
                                        </div>

                                        {(ev.stay_sec > 0 || ev.scroll_pct > 0) && (
                                          <div className="flex flex-wrap items-center gap-3 mt-1.5 text-[11px] text-zinc-300">
                                            {ev.stay_sec > 0 && (
                                              <span>
                                                页面停留 <strong className="text-amber-300">{ev.stay_sec}s</strong>
                                              </span>
                                            )}
                                            {ev.scroll_pct > 0 && (
                                              <span className="flex items-center gap-1.5">
                                                <span>滚动浏览深度</span>
                                                <span className="inline-block w-20 h-1.5 bg-white/10 rounded-full overflow-hidden">
                                                  <span
                                                    className="block h-full bg-purple-400 rounded-full"
                                                    style={{ width: `${Math.min(100, ev.scroll_pct)}%` }}
                                                  />
                                                </span>
                                                <strong className="text-purple-300">{ev.scroll_pct}%</strong>
                                              </span>
                                            )}
                                          </div>
                                        )}

                                        {ev.props && Object.keys(ev.props).length > 0 && (
                                          <div className="text-[10px] text-zinc-500 mt-1 truncate">
                                            {Object.entries(ev.props)
                                              .slice(0, 5)
                                              .map(([k, v]) => `${k}: ${typeof v === "object" ? JSON.stringify(v) : String(v)}`)
                                              .join(" · ")}
                                          </div>
                                        )}
                                      </div>
                                    </div>
                                  );
                                })}
                              </div>
                            </>
                          )}
                        </div>
                      </div>

                      {/* 3-Column Aggregate Breakdown: Pages Stay/Scroll + Top Buttons + Page Transitions */}
                      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 pt-1">
                        {/* Col 1: Per-Page Stay & Scroll Depth */}
                        <div className="bg-black/30 rounded-2xl border border-white/5 p-4">
                          <h4 className="text-xs font-bold text-white mb-3">
                            📄 各页面停留时长与下滑浏览深度
                          </h4>
                          {(analyticsData?.behavior?.pages || []).length === 0 ? (
                            <p className="text-xs text-zinc-500 py-6 text-center">等待新埋点数据上报</p>
                          ) : (
                            <div className="space-y-2.5 max-h-72 overflow-y-auto pr-1">
                              {(analyticsData?.behavior?.pages || []).map((pg: any) => (
                                <div
                                  key={pg.page_path}
                                  className="p-2.5 rounded-xl bg-white/[0.02] border border-white/5 space-y-1"
                                >
                                  <div className="flex items-center justify-between gap-2">
                                    <span className="text-xs font-semibold text-white truncate">
                                      {pg.page_title}
                                    </span>
                                    <span className="text-[11px] text-zinc-400 shrink-0">
                                      {pg.pv} PV / {pg.uv} UV
                                    </span>
                                  </div>
                                  <div className="flex items-center justify-between text-[11px] text-zinc-300">
                                    <span>平均停留 {pg.avg_stay_sec}s</span>
                                    <span>平均滚动 {pg.avg_scroll_pct}%</span>
                                    <span
                                      className={
                                        pg.exit_rate_pct >= 30 ? "text-rose-400 font-bold" : "text-zinc-400"
                                      }
                                    >
                                      退出率 {pg.exit_rate_pct}%
                                    </span>
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>

                        {/* Col 2: Top Clicked Buttons & Modals */}
                        <div className="bg-black/30 rounded-2xl border border-white/5 p-4">
                          <h4 className="text-xs font-bold text-white mb-3">
                            👆 高频按钮与弹窗点击排行
                          </h4>
                          {(analyticsData?.behavior?.top_buttons || []).length === 0 ? (
                            <p className="text-xs text-zinc-500 py-6 text-center">等待新埋点数据上报</p>
                          ) : (
                            <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
                              {(analyticsData?.behavior?.top_buttons || []).map((btn: any, idx: number) => (
                                <div
                                  key={`${btn.event_name}-${idx}`}
                                  className="flex items-center justify-between gap-2 p-2.5 rounded-xl bg-white/[0.02] border border-white/5"
                                >
                                  <div className="min-w-0">
                                    <div className="text-xs font-semibold text-white truncate">
                                      {btn.event_label}
                                    </div>
                                    <div className="text-[10px] text-zinc-500 truncate">
                                      {btn.page_title} · {btn.event_name}
                                    </div>
                                  </div>
                                  <div className="text-right shrink-0">
                                    <div className="text-xs font-bold text-orange-400">{btn.clicks} 次</div>
                                    <div className="text-[10px] text-zinc-500">{btn.unique_users} 人</div>
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>

                        {/* Col 3: Page-to-Page Transitions & Client API Issues */}
                        <div className="bg-black/30 rounded-2xl border border-white/5 p-4 space-y-4">
                          <div>
                            <h4 className="text-xs font-bold text-white mb-3">
                              🔀 页面跳转流向（从哪页去哪页）
                            </h4>
                            {(analyticsData?.behavior?.page_transitions || []).length === 0 ? (
                              <p className="text-xs text-zinc-500 py-4 text-center">等待新埋点数据上报</p>
                            ) : (
                              <div className="space-y-2 max-h-44 overflow-y-auto pr-1">
                                {(analyticsData?.behavior?.page_transitions || []).map((tr: any, idx: number) => (
                                  <div
                                    key={idx}
                                    className="flex items-center justify-between gap-2 p-2 rounded-xl bg-white/[0.02] border border-white/5 text-xs"
                                  >
                                    <div className="flex items-center gap-1.5 min-w-0 text-zinc-200 truncate">
                                      <span className="truncate">{tr.from_title}</span>
                                      <ArrowRight className="w-3 h-3 text-orange-400 shrink-0" />
                                      <span className="truncate">{tr.to_title}</span>
                                    </div>
                                    <span className="text-xs font-bold text-sky-300 shrink-0">{tr.count} 次</span>
                                  </div>
                                ))}
                              </div>
                            )}

                            {(analyticsData?.behavior?.module_exposures || []).length > 0 && (
                              <div className="border-t border-white/10 mt-4 pt-3">
                                <h4 className="text-xs font-bold text-teal-300 mb-2">
                                  👁️ 首页与核心卡片模块曝光率
                                </h4>
                                <div className="space-y-1.5 max-h-40 overflow-y-auto pr-1">
                                  {(analyticsData?.behavior?.module_exposures || []).map((mod: any) => (
                                    <div
                                      key={mod.event_name}
                                      className="flex items-center justify-between text-[11px] bg-white/[0.02] border border-white/5 px-2.5 py-1.5 rounded-lg"
                                    >
                                      <span className="text-zinc-200 truncate">{mod.event_label}</span>
                                      <span className="text-teal-300 font-bold shrink-0 ml-2">
                                        {mod.exposure_pct}% 同页曝光 ({mod.unique_users}人)
                                      </span>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>

                          {(analyticsData?.behavior?.api_issues || []).length > 0 && (
                            <div className="border-t border-white/10 pt-3">
                              <h4 className="text-xs font-bold text-rose-300 mb-2">
                                ⚠️ 客户端感知慢接口 / 报错
                              </h4>
                              <div className="space-y-1.5 max-h-28 overflow-y-auto pr-1">
                                {(analyticsData?.behavior?.api_issues || []).map((iss: any, idx: number) => (
                                  <div
                                    key={idx}
                                    className="flex items-center justify-between text-[11px] bg-red-500/10 border border-red-500/20 px-2.5 py-1.5 rounded-lg"
                                  >
                                    <span className="text-red-200 truncate">{iss.event_label}</span>
                                    <span className="text-red-300 font-bold shrink-0 ml-2">{iss.count} 次</span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* ── SECTION 2: Real-User Product Conversion Funnel ── */}
                    <div className="bg-[#141416] p-5 rounded-3xl border border-white/5 space-y-4">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-white/5 pb-4">
                        <div className="flex items-center gap-2">
                          <TrendingUp className="w-5 h-5 text-orange-400" />
                          <h3 className="text-sm font-bold text-white">
                            二、存量真实用户全生命周期转化漏斗（已自动过滤测试夹具账号）
                          </h3>
                        </div>
                        {analyticsData?.conversion_funnel?.watch_breakdown && (
                          <div className="flex flex-wrap items-center gap-2 text-[11px]">
                            <span className="px-2.5 py-1 rounded-full bg-emerald-500/15 text-emerald-300 border border-emerald-500/25">
                              ⌚ 已绑表合计 {analyticsData.conversion_funnel.watch_breakdown.any} 人
                            </span>
                            <span className="text-zinc-400">
                              高驰 {analyticsData.conversion_funnel.watch_breakdown.coros} · 佳明{" "}
                              {analyticsData.conversion_funnel.watch_breakdown.garmin} · Apple{" "}
                              {analyticsData.conversion_funnel.watch_breakdown.apple_watch} · 华为{" "}
                              {analyticsData.conversion_funnel.watch_breakdown.huawei} · 颂拓{" "}
                              {analyticsData.conversion_funnel.watch_breakdown.suunto}
                            </span>
                          </div>
                        )}
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {(analyticsData?.conversion_funnel?.steps || []).map((step: any) => (
                          <div
                            key={step.key}
                            className="p-3.5 rounded-2xl bg-black/30 border border-white/5 space-y-2"
                          >
                            <div className="flex items-center justify-between gap-2">
                              <span className="text-xs font-bold text-white">{step.label}</span>
                              <span className="text-xs font-black text-orange-300 shrink-0">
                                {step.count} 人 ({step.pct_of_total}%)
                              </span>
                            </div>
                            <div className="w-full h-2 bg-white/5 rounded-full overflow-hidden">
                              <div
                                className="h-full bg-gradient-to-r from-orange-500 to-amber-400 rounded-full transition-all"
                                style={{ width: `${Math.min(100, Math.max(2, step.pct_of_total || 0))}%` }}
                              />
                            </div>
                            <div className="text-[11px] text-zinc-400">{step.hint}</div>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* ── SECTION 3: Official WeChat Mini Program We分析 Historical Stats ── */}
                    <div className="bg-[#141416] p-5 rounded-3xl border border-white/5 space-y-5">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-white/5 pb-4">
                        <div className="flex items-center gap-2">
                          <Sparkles className="w-5 h-5 text-sky-400" />
                          <h3 className="text-sm font-bold text-white">
                            三、微信官方「We分析」历史真实访问统计（近 {analyticsData?.wechat_datacube?.days || analyticsDays} 天 T-1 官方聚合）
                          </h3>
                        </div>
                        {analyticsData?.wechat_datacube?.available && (
                          <span className="text-xs text-sky-300 font-semibold">
                            历史累计访问总人数：{analyticsData.wechat_datacube.cumulative_visitors} 人
                          </span>
                        )}
                      </div>

                      {!analyticsData?.wechat_datacube?.available ? (
                        <div className="text-xs text-zinc-400 bg-black/30 p-6 rounded-2xl border border-white/5 text-center">
                          暂未获取到微信官方 We分析 数据：{analyticsData?.wechat_datacube?.reason || "未配置小程序密钥或网络受限"}
                        </div>
                      ) : (
                        <>
                          {/* WeChat Official Summary Cards */}
                          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                            <div className="bg-black/30 p-3.5 rounded-2xl border border-white/5">
                              <div className="text-[11px] text-zinc-400">累计独立访客</div>
                              <div className="text-xl font-black text-white mt-1">
                                {analyticsData.wechat_datacube.cumulative_visitors}
                                <span className="text-xs font-normal text-zinc-500 ml-1">人</span>
                              </div>
                            </div>
                            <div className="bg-black/30 p-3.5 rounded-2xl border border-white/5">
                              <div className="text-[11px] text-zinc-400">周期打开次数</div>
                              <div className="text-xl font-black text-sky-300 mt-1">
                                {analyticsData.wechat_datacube.total_sessions}
                                <span className="text-xs font-normal text-zinc-500 ml-1">次</span>
                              </div>
                            </div>
                            <div className="bg-black/30 p-3.5 rounded-2xl border border-white/5">
                              <div className="text-[11px] text-zinc-400">总浏览量 (PV)</div>
                              <div className="text-xl font-black text-emerald-300 mt-1">
                                {analyticsData.wechat_datacube.total_pv}
                                <span className="text-xs font-normal text-zinc-500 ml-1">次</span>
                              </div>
                            </div>
                            <div className="bg-black/30 p-3.5 rounded-2xl border border-white/5">
                              <div className="text-[11px] text-zinc-400">新增访问人数</div>
                              <div className="text-xl font-black text-amber-300 mt-1">
                                {analyticsData.wechat_datacube.total_new_uv}
                                <span className="text-xs font-normal text-zinc-500 ml-1">人</span>
                              </div>
                            </div>
                            <div className="bg-black/30 p-3.5 rounded-2xl border border-white/5 col-span-2 sm:col-span-1">
                              <div className="text-[11px] text-zinc-400">单次停留 / 深度</div>
                              <div className="text-base font-black text-purple-300 mt-1.5">
                                {analyticsData.wechat_datacube.avg_session_stay_sec}s ·{" "}
                                {analyticsData.wechat_datacube.avg_visit_depth}页
                              </div>
                            </div>
                          </div>

                          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
                            {/* Official Per-Page Stay & Exit Rate Table */}
                            <div className="lg:col-span-7 bg-black/30 rounded-2xl border border-white/5 p-4 overflow-x-auto">
                              <h4 className="text-xs font-bold text-white mb-3">
                                微信官方各页面访问量、停留时长与退出率
                              </h4>
                              <table className="w-full text-left text-xs">
                                <thead>
                                  <tr className="text-zinc-400 border-b border-white/10">
                                    <th className="pb-2 font-medium">页面</th>
                                    <th className="pb-2 font-medium text-right">PV (占比)</th>
                                    <th className="pb-2 font-medium text-right">平均停留</th>
                                    <th className="pb-2 font-medium text-right">入口页</th>
                                    <th className="pb-2 font-medium text-right">退出率</th>
                                    <th className="pb-2 font-medium text-right">转发</th>
                                  </tr>
                                </thead>
                                <tbody className="divide-y divide-white/5">
                                  {(analyticsData.wechat_datacube.pages || []).map((pg: any) => (
                                    <tr key={pg.page_path} className="hover:bg-white/[0.02]">
                                      <td className="py-2 pr-2">
                                        <div className="font-semibold text-white">{pg.page_title}</div>
                                        <div className="text-[10px] text-zinc-500 font-mono">{pg.page_path}</div>
                                      </td>
                                      <td className="py-2 text-right text-zinc-200 whitespace-nowrap">
                                        {pg.pv}{" "}
                                        <span className="text-[10px] text-zinc-500">({pg.pv_share_pct}%)</span>
                                      </td>
                                      <td className="py-2 text-right text-amber-300 whitespace-nowrap">
                                        {pg.avg_stay_sec}s
                                      </td>
                                      <td className="py-2 text-right text-zinc-300 whitespace-nowrap">
                                        {pg.entry_pv}
                                      </td>
                                      <td
                                        className={`py-2 text-right whitespace-nowrap font-semibold ${
                                          pg.exit_rate_pct >= 28
                                            ? "text-rose-400"
                                            : pg.exit_rate_pct <= 14
                                            ? "text-emerald-400"
                                            : "text-zinc-300"
                                        }`}
                                      >
                                        {pg.exit_rate_pct}% ({pg.exit_pv})
                                      </td>
                                      <td className="py-2 text-right text-zinc-400 whitespace-nowrap">
                                        {pg.share_pv}
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>

                            {/* Official Access Source Scenes & Daily Trend */}
                            <div className="lg:col-span-5 space-y-4">
                              <div className="bg-black/30 rounded-2xl border border-white/5 p-4">
                                <h4 className="text-xs font-bold text-white mb-3">
                                  用户从哪里打开小程序（微信入口场景分布）
                                </h4>
                                <div className="space-y-2.5">
                                  {(analyticsData.wechat_datacube.scenes || []).map((sc: any) => (
                                    <div key={sc.scene_key} className="space-y-1">
                                      <div className="flex items-center justify-between text-xs">
                                        <span className="text-zinc-200">{sc.scene_label}</span>
                                        <span className="text-sky-300 font-bold">
                                          {sc.count} 次 ({sc.pct}%)
                                        </span>
                                      </div>
                                      <div className="w-full h-1.5 bg-white/5 rounded-full overflow-hidden">
                                        <div
                                          className="h-full bg-sky-400 rounded-full"
                                          style={{ width: `${Math.min(100, Math.max(2, sc.pct || 0))}%` }}
                                        />
                                      </div>
                                    </div>
                                  ))}
                                </div>
                              </div>

                              <div className="bg-black/30 rounded-2xl border border-white/5 p-4 max-h-56 overflow-y-auto">
                                <h4 className="text-xs font-bold text-white mb-2.5">
                                  逐日访问趋势
                                </h4>
                                <div className="space-y-1.5 text-[11px]">
                                  {[...(analyticsData.wechat_datacube.daily_trend || [])]
                                    .reverse()
                                    .map((dy: any) => (
                                      <div
                                        key={dy.date}
                                        className="flex items-center justify-between py-1 border-b border-white/5 text-zinc-300"
                                      >
                                        <span className="font-mono text-zinc-400">{dy.date}</span>
                                        <span>
                                          打开 <strong className="text-white">{dy.session_cnt}</strong> · UV{" "}
                                          <strong className="text-emerald-300">{dy.visit_uv}</strong> (+{dy.visit_uv_new}) ·{" "}
                                          {dy.visit_pv} PV · 均留 {dy.stay_time_session_sec}s
                                        </span>
                                      </div>
                                    ))}
                                </div>
                              </div>
                            </div>
                          </div>
                        </>
                      )}
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        )}

        {/* ── Modal: Single Runner Historical Journey ── */}
        {userJourneyData && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
            <div className="relative w-full max-w-2xl bg-[#141416] border border-white/10 rounded-3xl p-6 shadow-2xl max-h-[85vh] overflow-y-auto">
              <button
                onClick={() => setUserJourneyData(null)}
                className="absolute top-5 right-5 p-2 rounded-full text-zinc-400 hover:text-white hover:bg-white/5"
              >
                <X className="w-5 h-5" />
              </button>
              <h3 className="text-base font-bold text-white">
                🏃 {userJourneyData.user?.display_name} 的历史访问轨迹（最近 {userJourneyData.total_sessions} 次打开）
              </h3>
              <p className="text-xs text-zinc-400 mt-1 mb-4">
                点击任一历史会话即可切换到该次访问的逐秒详细回放
              </p>
              <div className="space-y-2.5">
                {(userJourneyData.sessions || []).map((item: any) => {
                  const s = item.session;
                  if (!s) return null;
                  return (
                    <div
                      key={s.session_id}
                      className="p-3.5 rounded-2xl bg-black/40 border border-white/10 flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                    >
                      <div className="space-y-1">
                        <div className="text-xs font-bold text-white">
                          {formatBeijingTime(s.started_at)} · {s.scene_label}
                        </div>
                        <div className="text-[11px] text-zinc-400">
                          路径：{s.entry_title} → {s.exit_title} · 停留 {s.duration_sec}s · {s.page_count} 页 ·{" "}
                          {s.click_count} 次点击 · 最大滚动 {s.max_scroll_pct}%
                        </div>
                      </div>
                      <button
                        onClick={() => {
                          setSessionDetail(item);
                          setSelectedSessionId(s.session_id);
                          setUserJourneyData(null);
                        }}
                        className="px-3.5 py-2 rounded-xl bg-orange-600 hover:bg-orange-500 text-white text-xs font-bold shrink-0"
                      >
                        回放此次会话
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>
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
                  <label className="block text-xs font-medium text-zinc-400 mb-1.5">跑团运行状态</label>
                  <div className="grid grid-cols-3 gap-2">
                    <button
                      type="button"
                      onClick={() => setEditClubStatus("active")}
                      className={`py-2 px-2.5 rounded-xl text-xs font-bold transition flex items-center justify-center gap-1.5 ${
                        editClubStatus === "active"
                          ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                          : "bg-white/5 text-zinc-400 border border-white/10 hover:bg-white/10"
                      }`}
                    >
                      <Play className="w-3 h-3" />
                      正常运行
                    </button>
                    <button
                      type="button"
                      onClick={() => setEditClubStatus("paused")}
                      className={`py-2 px-2.5 rounded-xl text-xs font-bold transition flex items-center justify-center gap-1.5 ${
                        editClubStatus === "paused"
                          ? "bg-amber-500/20 text-amber-300 border border-amber-500/40"
                          : "bg-white/5 text-zinc-400 border border-white/10 hover:bg-white/10"
                      }`}
                    >
                      <Pause className="w-3 h-3" />
                      暂停跑团
                    </button>
                    <button
                      type="button"
                      onClick={() => setEditClubStatus("locked")}
                      className={`py-2 px-2.5 rounded-xl text-xs font-bold transition flex items-center justify-center gap-1.5 ${
                        editClubStatus === "locked"
                          ? "bg-blue-500/20 text-blue-300 border border-blue-500/40"
                          : "bg-white/5 text-zinc-400 border border-white/10 hover:bg-white/10"
                      }`}
                    >
                      <Lock className="w-3 h-3" />
                      锁定跑团
                    </button>
                  </div>
                  <p className="text-[11px] text-zinc-500 mt-1">
                    {editClubStatus === "active" && "🟢 正常运行：成员自由进出，打卡与群消息正常同步，公开可见。"}
                    {editClubStatus === "paused" && "⏸️ 暂停跑团：暂停动态消息与活动发布，禁止队员增删，暂停数据更新，对外不可见。"}
                    {editClubStatus === "locked" && "🔒 锁定跑团：禁止队员增删，对外不可见，保留历史记录。"}
                  </p>
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
                  placeholder="搜索戈友真实姓名、商学院项目、班级、戈壁经历(如戈20/新戈)、手机号或昵称..."
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
                        <th className="p-3.5">戈壁经历</th>
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
                                <div className="flex items-center gap-1.5 flex-wrap">
                                  <span className="font-bold text-white text-sm">{m.real_name || "未实名"}</span>
                                  {m.role === 'owner' ? (
                                    <span className="px-1.5 py-0.2 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">👑 主理人</span>
                                  ) : m.role === 'admin' ? (
                                    <span className="px-1.5 py-0.2 rounded text-[10px] font-bold bg-blue-500/20 text-blue-300 border border-blue-500/30">🛡️ 管理员</span>
                                  ) : null}
                                </div>
                                <span className="text-[11px] text-zinc-500 block">昵称: {m.display_name || "跑友"}</span>
                                {m.id_card && (
                                  <span className="text-[10px] text-zinc-500 block font-mono">证件: {m.id_card}</span>
                                )}
                              </div>
                            </div>
                          </td>
                          <td className="p-3.5">
                            {m.program ? (
                              <div className="space-y-1">
                                <span className="px-2 py-0.5 rounded-md bg-amber-500/15 text-amber-300 text-[11px] font-semibold inline-block border border-amber-500/20">
                                  {m.program}
                                </span>
                                <span className="text-zinc-300 text-xs font-medium block">
                                  {m.class_detail || (m.class_name ? m.class_name.replace(m.program, '').trim() : '') || "在读/毕业"}
                                </span>
                              </div>
                            ) : (
                              <span className="font-medium text-amber-300">
                                {m.class_name || "复旦商学院"}
                              </span>
                            )}
                          </td>
                          <td className="p-3.5">
                            {m.gobi_experience ? (
                              m.gobi_experience === "新戈" ? (
                                <span className="px-2.5 py-1 rounded-full text-[11px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 whitespace-nowrap">
                                  🌱 新戈
                                </span>
                              ) : (
                                <span className="px-2.5 py-1 rounded-full text-[11px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30 whitespace-nowrap">
                                  🏅 {m.gobi_experience}
                                </span>
                              )
                            ) : (
                              <span className="text-zinc-600 text-[11px]">未登记</span>
                            )}
                          </td>
                          <td className="p-3.5 text-zinc-300">
                            <div className="flex items-center gap-1.5 flex-wrap">
                              <span>{m.gender === "female" ? "🚺 女" : "🚹 男"}</span>
                              <span className="text-zinc-500">·</span>
                              <span>{m.date_of_birth ? `${m.date_of_birth.substring(0, 4)}年生` : "--"}</span>
                              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-purple-500/20 text-purple-300 border border-purple-500/30">
                                {m.age_group || getAgeGroup(m.date_of_birth)}
                              </span>
                            </div>
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
                            {m.status === 'confirmed' ? (
                              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                                ✓ 正式戈友 (已批准)
                              </span>
                            ) : m.status === 'pending' ? (
                              <div className="space-y-1">
                                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-blue-500/20 text-blue-400 border border-blue-500/30">
                                  ⏳ 待审核 (剩 {m.remaining_days ?? 14} 天)
                                </span>
                                <span className="block text-[10px] text-emerald-400">必填项已齐，待核验</span>
                              </div>
                            ) : m.status === 'temporary' ? (
                              <div className="space-y-1">
                                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/20 text-amber-400 border border-amber-500/30">
                                  ⚠️ 临时人员 (剩 {m.days_remaining ?? m.remaining_days ?? 14} 天)
                                </span>
                                {((m.missing_required_fields && m.missing_required_fields.length > 0) || (m.missing_fields && m.missing_fields.length > 0)) && (
                                  <span className="block text-[10px] text-rose-400">
                                    缺: {(m.missing_required_fields || m.missing_fields.map((f: any) => f.label || f.field)).join("、")}
                                  </span>
                                )}
                              </div>
                            ) : m.status === 'expired' ? (
                              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-500/20 text-rose-400 border border-rose-500/30">
                                🚫 已过期 (禁止进群)
                              </span>
                            ) : (
                              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-zinc-500/20 text-zinc-400 border border-zinc-500/30">
                                未知状态
                              </span>
                            )}
                          </td>
                          <td className="p-3.5 text-right">
                            {m.status !== 'confirmed' ? (
                              m.status === 'temporary' ? (
                                <button
                                  disabled
                                  className="px-2.5 py-1 rounded-lg bg-zinc-800 text-zinc-500 text-xs font-medium cursor-not-allowed border border-white/5"
                                  title="队员必填资料尚未齐备，暂无法核验转正"
                                >
                                  必填项未齐
                                </button>
                              ) : m.status === 'expired' ? (
                                <div className="flex items-center justify-end gap-1.5">
                                  <button
                                    onClick={() => handleConfirmMember(m.user_id)}
                                    disabled={confirmingUid === m.user_id}
                                    className="px-2.5 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs transition disabled:opacity-50"
                                    title="核验并通过实名资料转为正式成员"
                                  >
                                    {confirmingUid === m.user_id ? "核验中..." : "恢复并批准"}
                                  </button>
                                  <button
                                    onClick={() => handleGrantGracePeriod(m.user_id)}
                                    disabled={confirmingUid === m.user_id}
                                    className="px-2 py-1 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 border border-amber-500/30 text-[11px] font-medium transition disabled:opacity-50"
                                    title="重置14天临时宽限期，给予队员时间在小程序补齐资料"
                                  >
                                    宽限14天
                                  </button>
                                </div>
                              ) : (
                                <button
                                  onClick={() => handleConfirmMember(m.user_id)}
                                  disabled={confirmingUid === m.user_id}
                                  className="px-2.5 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs transition disabled:opacity-50"
                                >
                                  {confirmingUid === m.user_id ? "核验中..." : "核验并批准"}
                                </button>
                              )
                            ) : (
                              <div className="flex items-center justify-end gap-2">
                                <span className="text-zinc-500 text-xs flex items-center gap-1">
                                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                                  正式成员
                                </span>
                                {m.role === 'admin' ? (
                                  <button
                                    onClick={() => handleUpdateOrgRole(m.user_id, 'member')}
                                    disabled={updatingRoleUid === m.user_id}
                                    className="px-2 py-0.5 rounded text-[11px] font-medium text-zinc-400 hover:text-rose-400 hover:bg-rose-500/10 border border-white/10 transition"
                                    title="撤销该成员的大群管理员权限"
                                  >
                                    {updatingRoleUid === m.user_id ? "处理中..." : "撤销管理"}
                                  </button>
                                ) : m.role === 'member' ? (
                                  <button
                                    onClick={() => handleUpdateOrgRole(m.user_id, 'admin')}
                                    disabled={updatingRoleUid === m.user_id}
                                    className="px-2 py-0.5 rounded text-[11px] font-medium text-blue-400 hover:text-white hover:bg-blue-600/20 border border-blue-500/30 transition"
                                    title="委派该成员为大群管理员，具备花名册审核与管理权限"
                                  >
                                    {updatingRoleUid === m.user_id ? "处理中..." : "委派管理"}
                                  </button>
                                ) : null}
                              </div>
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
                              src={sc.logo_url || "/logo.png"}
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
                              src={c.logo_url || "/logo.png"}
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

        {/* ── Modal 8: Org Field Rules Config Modal (大群准入字段逐个自定义配置) ── */}
        {showOrgFieldRulesModal && activeOrg && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
            <div className="relative w-full max-w-2xl bg-[#141416] border border-purple-500/30 rounded-3xl p-6 sm:p-8 shadow-2xl max-h-[90vh] flex flex-col">
              <button
                onClick={() => setShowOrgFieldRulesModal(false)}
                className="absolute top-6 right-6 p-2 rounded-full text-zinc-400 hover:text-white hover:bg-white/5"
              >
                <X className="w-5 h-5" />
              </button>

              <div className="mb-4">
                <div className="flex items-center gap-2.5">
                  <div className="p-2 rounded-xl bg-purple-500/10 border border-purple-500/30 text-purple-400">
                    <ShieldCheck className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-white">
                      【{activeOrg.name}】大群准入必填字段配置
                    </h3>
                    <span className="text-xs text-purple-300 font-medium">逐个字段自定义准入门槛与加入规则</span>
                  </div>
                </div>
              </div>

              {/* Policy Explanatory Box */}
              <div className="p-3.5 rounded-2xl bg-purple-500/10 border border-purple-500/20 mb-4 space-y-1 text-xs">
                <div className="flex items-center gap-1.5 font-bold text-purple-300">
                  <Clock className="w-4 h-4 text-purple-400" />
                  <span>大群准入字段三态规则（必填 / 选填 / 不显示）与 14 天临时状态说明：</span>
                </div>
                <p className="text-zinc-300 text-[11px] leading-relaxed">
                  主理人或管理员可逐个字段设为<span className="text-purple-300 font-bold">【必填】</span>、<span className="text-emerald-300 font-bold">【选填】</span>或<span className="text-zinc-500 font-bold">【不显示】</span>。
                  设为【不显示】的字段将在入群及修改资料表单中彻底隐藏且不纳入考核；成员需在 14 天内完成全部【必填】字段并获审核通过。
                </p>
              </div>

              {/* Rules List */}
              <div className="flex-1 overflow-y-auto pr-1 space-y-2.5">
                {loadingFieldRules ? (
                  <div className="p-12 text-center text-zinc-500 text-sm flex items-center justify-center gap-2">
                    <RefreshCw className="w-4 h-4 animate-spin text-purple-400" />
                    <span>正在加载准入规则...</span>
                  </div>
                ) : (
                  orgFieldRules.map((rule, idx) => {
                    const ruleMode: "required" | "optional" | "hidden" =
                      rule.mode === "hidden" || rule.hidden
                        ? "hidden"
                        : rule.mode === "required" || rule.required
                        ? "required"
                        : "optional";
                    const setRuleMode = (nextMode: "required" | "optional" | "hidden") => {
                      const updated = orgFieldRules.map((r, i) =>
                        i === idx
                          ? {
                              ...r,
                              mode: nextMode,
                              required: nextMode === "required",
                              hidden: nextMode === "hidden",
                            }
                          : r
                      );
                      setOrgFieldRules(updated);
                    };
                    return (
                      <div
                        key={rule.field || rule.field_key || idx}
                        className={`flex items-center justify-between gap-3 p-3.5 rounded-2xl border transition ${
                          ruleMode === "required"
                            ? "bg-purple-500/[0.05] border-purple-500/30"
                            : ruleMode === "hidden"
                            ? "bg-black/40 border-white/5 opacity-60"
                            : "bg-white/[0.02] border-white/10"
                        }`}
                      >
                        <div className="flex items-start gap-3">
                          <div
                            className={`mt-0.5 w-6 h-6 rounded-lg flex items-center justify-center text-xs font-bold ${
                              ruleMode === "required"
                                ? "bg-purple-500/20 text-purple-300 border border-purple-500/40"
                                : ruleMode === "hidden"
                                ? "bg-zinc-900 text-zinc-600 border border-white/5"
                                : "bg-emerald-500/10 text-emerald-300 border border-emerald-500/20"
                            }`}
                          >
                            {idx + 1}
                          </div>
                          <div>
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className={`font-bold text-sm ${ruleMode === "hidden" ? "text-zinc-500 line-through" : "text-white"}`}>
                                {rule.label}
                              </span>
                              <span className="font-mono text-[10px] text-zinc-500">
                                {rule.field || rule.field_key}
                              </span>
                              {ruleMode === "required" ? (
                                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-purple-500/20 text-purple-300 border border-purple-500/30">
                                  必填项
                                </span>
                              ) : ruleMode === "hidden" ? (
                                <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-zinc-800 text-zinc-500 border border-white/5">
                                  不显示 (隐藏)
                                </span>
                              ) : (
                                <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
                                  选填项
                                </span>
                              )}
                            </div>
                            <p className="text-[11px] text-zinc-400 mt-0.5">
                              {rule.description || "成员加入及资料登记字段"}
                            </p>
                          </div>
                        </div>

                        {/* 3-State Segmented Selector: 必填 / 选填 / 不显示 */}
                        <div className="flex items-center bg-black/50 border border-white/10 rounded-xl p-1 shrink-0 gap-1">
                          <button
                            type="button"
                            onClick={() => setRuleMode("required")}
                            className={`px-2.5 py-1 rounded-lg text-xs font-bold transition ${
                              ruleMode === "required"
                                ? "bg-purple-600 text-white shadow"
                                : "text-zinc-400 hover:text-white"
                            }`}
                          >
                            必填
                          </button>
                          <button
                            type="button"
                            onClick={() => setRuleMode("optional")}
                            className={`px-2.5 py-1 rounded-lg text-xs font-bold transition ${
                              ruleMode === "optional"
                                ? "bg-emerald-600 text-white shadow"
                                : "text-zinc-400 hover:text-white"
                            }`}
                          >
                            选填
                          </button>
                          <button
                            type="button"
                            onClick={() => setRuleMode("hidden")}
                            className={`px-2.5 py-1 rounded-lg text-xs font-bold transition ${
                              ruleMode === "hidden"
                                ? "bg-zinc-700 text-zinc-200 shadow"
                                : "text-zinc-500 hover:text-zinc-300"
                            }`}
                          >
                            不显示
                          </button>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>

              {/* Bottom Actions */}
              <div className="pt-4 mt-4 border-t border-white/10 flex items-center justify-between flex-wrap gap-2">
                <div className="flex items-center gap-3 text-xs text-zinc-400">
                  <span>
                    必填:{" "}
                    <strong className="text-purple-400">
                      {orgFieldRules.filter((r) => !(r.mode === "hidden" || r.hidden) && (r.mode === "required" || r.required)).length}
                    </strong>
                  </span>
                  <span>
                    选填:{" "}
                    <strong className="text-emerald-400">
                      {orgFieldRules.filter((r) => !(r.mode === "hidden" || r.hidden) && !(r.mode === "required" || r.required)).length}
                    </strong>
                  </span>
                  <span>
                    不显示:{" "}
                    <strong className="text-zinc-500">
                      {orgFieldRules.filter((r) => r.mode === "hidden" || r.hidden).length}
                    </strong>
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setShowOrgFieldRulesModal(false)}
                    className="px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-zinc-300 text-xs font-bold transition"
                  >
                    取消
                  </button>
                  <button
                    type="button"
                    onClick={handleSaveFieldRules}
                    disabled={savingFieldRules || loadingFieldRules}
                    className="px-5 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-bold transition shadow-lg shadow-purple-600/25 flex items-center gap-1.5 disabled:opacity-50"
                  >
                    <Save className="w-3.5 h-3.5" />
                    <span>{savingFieldRules ? "保存中..." : "保存准入规则"}</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── Modal: Delete Club Confirmation ── */}
        {showDeleteClubModal && clubToDelete && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
            <div className="relative w-full max-w-md bg-[#141416] border border-red-500/30 rounded-3xl p-6 sm:p-8 shadow-2xl">
              <button
                onClick={() => {
                  setShowDeleteClubModal(false);
                  setClubToDelete(null);
                  setDeleteConfirmInput("");
                }}
                className="absolute top-6 right-6 p-2 rounded-full text-zinc-400 hover:text-white hover:bg-white/5"
              >
                <X className="w-5 h-5" />
              </button>

              <div className="flex items-center gap-3 mb-4">
                <div className="w-12 h-12 rounded-2xl bg-red-500/20 border border-red-500/30 flex items-center justify-center text-red-400 shrink-0">
                  <Trash2 className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-white">解散并删除跑团</h3>
                  <p className="text-xs text-zinc-400">请确认删除操作与数据安全保障</p>
                </div>
              </div>

              <div className="space-y-4 text-xs">
                <div className="p-3.5 bg-white/5 border border-white/10 rounded-2xl space-y-2">
                  <div className="flex justify-between">
                    <span className="text-zinc-400">待删除跑团:</span>
                    <span className="font-bold text-white">{clubToDelete.name}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-zinc-400">跑团成员数:</span>
                    <span className="text-zinc-300">{clubToDelete.member_count || 1} 人</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-zinc-400">现任团长:</span>
                    <span className="text-amber-300">{clubToDelete.owner_name || "未指定"}</span>
                  </div>
                </div>

                {/* Important Guarantee */}
                <div className="p-3.5 bg-emerald-500/10 border border-emerald-500/30 rounded-2xl space-y-1.5">
                  <div className="font-bold text-emerald-400 flex items-center gap-1.5 text-xs">
                    <ShieldCheck className="w-4 h-4 text-emerald-400" />
                    队员个人数据安全承诺
                  </div>
                  <p className="text-[11px] text-emerald-300/90 leading-relaxed">
                    本操作仅解散跑团群组织及成员从属关系。全体队员的<strong>个人账号、个人跑者档案、历史打卡记录、GPS轨迹与生理负荷数据将 100% 完整保留</strong>，绝不受任何影响！
                  </p>
                </div>

                <div className="p-3.5 bg-red-500/10 border border-red-500/20 rounded-2xl">
                  <p className="text-[11px] text-red-300/90 leading-relaxed">
                    ⚠️ 跑团解散后无法恢复，跑团专属活动及群打卡排行榜将被清理。
                  </p>
                </div>

                <form onSubmit={handleDeleteClub} className="space-y-4 pt-2">
                  <div>
                    <label className="block text-xs font-medium text-zinc-400 mb-1.5">
                      请输入跑团名称 <span className="text-red-400 font-bold">"{clubToDelete.name}"</span> 确认删除：
                    </label>
                    <input
                      type="text"
                      required
                      value={deleteConfirmInput}
                      onChange={(e) => setDeleteConfirmInput(e.target.value)}
                      placeholder={clubToDelete.name}
                      className="w-full px-3.5 py-2.5 bg-white/5 border border-white/10 rounded-xl text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-red-500"
                    />
                  </div>

                  {actionErrorMsg && (
                    <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-xs text-red-400 flex items-center gap-2">
                      <AlertCircle className="w-4 h-4 shrink-0" />
                      <span>{actionErrorMsg}</span>
                    </div>
                  )}

                  <div className="flex items-center gap-3 pt-2">
                    <button
                      type="button"
                      onClick={() => {
                        setShowDeleteClubModal(false);
                        setClubToDelete(null);
                        setDeleteConfirmInput("");
                      }}
                      className="flex-1 py-2.5 rounded-xl bg-white/5 hover:bg-white/10 text-zinc-300 text-xs font-bold transition"
                    >
                      取消
                    </button>
                    <button
                      type="submit"
                      disabled={submitting || deleteConfirmInput.trim() !== clubToDelete.name.trim()}
                      className="flex-1 py-2.5 rounded-xl bg-red-600 hover:bg-red-500 disabled:opacity-40 disabled:hover:bg-red-600 text-white text-xs font-bold transition shadow-lg shadow-red-600/30 flex items-center justify-center gap-1.5"
                    >
                      <Trash2 className="w-4 h-4" />
                      <span>{submitting ? "删除中..." : "确认删除跑团"}</span>
                    </button>
                  </div>
                </form>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );

}
