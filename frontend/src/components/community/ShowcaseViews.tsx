"use client";

import { useState, useEffect, useCallback } from "react";
import apiClient from "@/lib/apiClient";
import { useUiFeedback } from "@/components/ui/UiFeedbackProvider";
import ShowcaseStudioModal from "./ShowcaseStudioModal";
import {
  MapPin,
  Users,
  Award,
  Watch,
  Camera,
  ChevronLeft,
  Sparkles,
  CheckCircle2,
  Paintbrush,
  X,
} from "lucide-react";

const CATEGORY_MAP: Record<string, string> = {
  all: "全部照片",
  group_run: "合练实拍",
  race_highlight: "赛场高光",
  certificate: "证书奖项",
  team_event: "补给团建",
};

export function ClubShowcaseDetail({
  clubId,
  viewerUid,
  inviteToken,
  onBack,
  onSelectCoach,
  onJoinedClub,
}: {
  clubId: string;
  viewerUid?: string;
  inviteToken?: string;
  onBack?: () => void;
  onSelectCoach?: (coachUid: string) => void;
  onJoinedClub?: () => void;
}) {
  const { showToast } = useUiFeedback();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [photoCat, setPhotoCat] = useState("all");
  const [lightboxUrl, setLightboxUrl] = useState("");
  const [studioOpen, setStudioOpen] = useState(false);

  const loadDetail = useCallback(async () => {
    setLoading(true);
    try {
      const q = new URLSearchParams();
      if (viewerUid) q.set("viewer_uid", viewerUid);
      if (inviteToken) q.set("invite_token", inviteToken);
      const res = await apiClient.get(`/api/community/showcase/clubs/${encodeURIComponent(clubId)}?${q.toString()}`);
      setData(res.data);
    } catch (e: any) {
      showToast("加载跑团宣传页失败：" + (e?.message || ""), "error");
    } finally {
      setLoading(false);
    }
  }, [clubId, viewerUid, inviteToken, showToast]);

  useEffect(() => {
    loadDetail();
  }, [loadDetail]);

  async function handleJoinClub() {
    if (!viewerUid) {
      showToast("请先登录后一键兼入跑团", "info");
      return;
    }
    try {
      await apiClient.post("/api/team/join-club", {
        user_id: viewerUid,
        club_id: clubId,
        privacy_consent: true,
        via_invite: Boolean(inviteToken),
      });
      showToast(`🎉 已兼入【${data?.club?.name || "跑团"}】，手表里程多团共享！`);
      loadDetail();
      onJoinedClub?.();
    } catch (e: any) {
      showToast("加入提示：" + (e?.message || "需凭邀请码加入"), "error");
    }
  }

  if (loading) {
    return <div className="rgm-bento-card p-10 text-center text-xs text-[var(--rgm-text-muted)]">加载跑团品牌宣传页中...</div>;
  }
  if (!data?.club) return null;

  const { club, showcase, verified_stats: st, coaching_team: coaches, photos, can_edit, viewer_membership } = data;
  const filteredPhotos = (photos || []).filter((p: any) => photoCat === "all" || p.category === photoCat);

  return (
    <div className="space-y-5">
      {onBack && (
        <button
          type="button"
          onClick={onBack}
          className="inline-flex items-center gap-1 text-xs font-bold text-[var(--rgm-text-2)] hover:text-[#FC4C02] cursor-pointer"
        >
          <ChevronLeft className="w-4 h-4" /> 返回选团与名帅展厅
        </button>
      )}

      {/* Hero Showcase Card */}
      <div className="rgm-bento-card overflow-hidden">
        {showcase?.hero_cover_url && (
          <div className="h-44 sm:h-56 w-full relative overflow-hidden bg-[var(--rgm-card-2)]">
            <img src={showcase.hero_cover_url} alt={club.name} className="w-full h-full object-cover" />
            <div className="absolute inset-0 bg-gradient-to-t from-black/75 via-black/25 to-transparent" />
          </div>
        )}
        <div className="p-6 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2 flex-wrap">
                <h2 className="text-xl font-black text-[var(--rgm-text)]">{club.name}</h2>
                {club.org_name && (
                  <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-[var(--rgm-amber-tint)] text-amber-500">
                    🏛️ {club.org_name}
                  </span>
                )}
              </div>
              <p className="text-sm font-bold text-[#FC4C02]">{showcase?.slogan || club.description}</p>
              <div className="flex items-center gap-2 flex-wrap pt-1 text-[11px] text-[var(--rgm-text-2)]">
                <span>📍 {club.city}</span>
                {(showcase?.home_landmarks || []).map((lm: string) => (
                  <span key={lm} className="px-2 py-0.5 rounded-lg bg-[var(--rgm-card-2)] border border-[var(--rgm-border)]">
                    {lm}
                  </span>
                ))}
                {(showcase?.style_tags || []).map((tg: string) => (
                  <span key={tg} className="px-2 py-0.5 rounded-lg bg-[var(--rgm-brand-tint)] text-[#FC4C02] font-bold">
                    #{tg}
                  </span>
                ))}
              </div>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              {can_edit && (
                <button
                  type="button"
                  onClick={() => setStudioOpen(true)}
                  className="px-3.5 py-2 rounded-xl border border-[var(--rgm-border)] bg-[var(--rgm-card-2)] text-xs font-bold text-[var(--rgm-text)] flex items-center gap-1.5 cursor-pointer"
                >
                  <Paintbrush className="w-3.5 h-3.5 text-[#FC4C02]" /> 装修主页 & 传图
                </button>
              )}
              {viewer_membership?.status === "active" ? (
                <span className="px-4 py-2 rounded-xl bg-[var(--rgm-green-tint)] text-emerald-500 text-xs font-black flex items-center gap-1">
                  <CheckCircle2 className="w-4 h-4" /> 已加入本团
                </span>
              ) : (
                club.join_mode === "free" && (
                  <button
                    type="button"
                    onClick={handleJoinClub}
                    className="px-4 py-2 rounded-xl bg-[#FC4C02] text-white text-xs font-black cursor-pointer hover:opacity-90"
                  >
                    + 无排他一键兼团
                  </button>
                )
              )}
            </div>
          </div>

          {/* 4 Verified Telemetry Tiles */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2">
            {[
              { label: "活跃队员", val: `${st?.member_count ?? 0} 人` },
              { label: "本月全团实跑", val: `${st?.month_total_km ?? 0} km` },
              { label: "⌚ 手表核验破330", val: `${st?.sub330_count ?? 0} 人 (破3 ${st?.sub300_count ?? 0} 人)` },
              { label: "🐰 平台认证官兔履历", val: `${st?.official_pacer_races_count ?? 0} 场次` },
            ].map((stat) => (
              <div key={stat.label} className="p-3 rounded-2xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)]">
                <div className="text-[11px] text-[var(--rgm-text-muted)]">{stat.label}</div>
                <div className="text-sm font-black text-[var(--rgm-text)] mt-0.5 tabular-nums">{stat.val}</div>
              </div>
            ))}
          </div>

          {(showcase?.schedule_summary || showcase?.highlights_md) && (
            <div className="p-4 rounded-2xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] space-y-1.5 text-xs">
              {showcase.schedule_summary && (
                <div className="font-bold text-[var(--rgm-text)]">🗓️ 合练排期：{showcase.schedule_summary}</div>
              )}
              {showcase.highlights_md && (
                <p className="text-[var(--rgm-text-2)] leading-relaxed">{showcase.highlights_md}</p>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Coaching Roster */}
      {(coaches || []).length > 0 && (
        <div className="rgm-bento-card p-6 space-y-3">
          <h3 className="text-sm font-black text-[var(--rgm-text)]">🎖️ 核心团长与教练天团（点击查看防伪核验资历）</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {coaches.map((ch: any) => (
              <button
                key={ch.user_id}
                type="button"
                onClick={() => onSelectCoach?.(ch.user_id)}
                className="p-3.5 rounded-2xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] hover:border-[#FC4C02]/50 text-left transition flex items-center gap-3 cursor-pointer"
              >
                <div className="w-11 h-11 rounded-full bg-[var(--rgm-card)] overflow-hidden shrink-0 flex items-center justify-center font-black">
                  {ch.avatar_url ? (
                    <img src={ch.avatar_url} alt={ch.display_name} className="w-full h-full object-cover" />
                  ) : (
                    String(ch.display_name || "教").slice(0, 1)
                  )}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs font-black text-[var(--rgm-text)] truncate">{ch.display_name}</span>
                    {ch.watch_verified && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--rgm-green-tint)] text-emerald-500 font-bold">
                        ⌚ 核验
                      </span>
                    )}
                  </div>
                  <div className="text-[11px] text-[var(--rgm-text-2)] truncate mt-0.5">{ch.headline}</div>
                  {ch.verified_marathon_pb && (
                    <div className="text-[10px] text-[#FC4C02] font-bold mt-0.5 tabular-nums">
                      全马 PB {ch.verified_marathon_pb}
                    </div>
                  )}
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Photo Wall */}
      <div className="rgm-bento-card p-6 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-black text-[var(--rgm-text)] flex items-center gap-1.5">
            <Camera className="w-4 h-4 text-[#FC4C02]" />
            合练与赛场风采照片墙 ({(photos || []).length})
          </h3>
          <div className="flex items-center gap-1.5 flex-wrap">
            {Object.entries(CATEGORY_MAP).map(([k, lbl]) => (
              <button
                key={k}
                type="button"
                onClick={() => setPhotoCat(k)}
                className={`px-3 py-1 rounded-full text-[11px] font-bold cursor-pointer ${
                  photoCat === k
                    ? "bg-[#FC4C02] text-white"
                    : "bg-[var(--rgm-card-2)] text-[var(--rgm-text-2)]"
                }`}
              >
                {lbl}
              </button>
            ))}
          </div>
        </div>

        {filteredPhotos.length === 0 ? (
          <div className="py-8 text-center text-xs text-[var(--rgm-text-muted)]">
            该分类下暂未上传实拍照片
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
            {filteredPhotos.map((p: any) => (
              <button
                key={p.id}
                type="button"
                onClick={() => setLightboxUrl(p.photo_url)}
                className="group relative aspect-[4/3] rounded-2xl overflow-hidden bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] cursor-pointer"
              >
                <img src={p.photo_url} alt={p.caption || "跑团实拍"} className="w-full h-full object-cover group-hover:scale-105 transition" />
                <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 to-transparent p-2 text-left">
                  <span className="text-[10px] text-orange-300 font-bold">{CATEGORY_MAP[p.category] || "合练"}</span>
                  {p.caption && <div className="text-[11px] text-white truncate">{p.caption}</div>}
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {lightboxUrl && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 p-4"
          onClick={() => setLightboxUrl("")}
        >
          <button
            type="button"
            onClick={() => setLightboxUrl("")}
            className="absolute top-5 right-5 p-2 rounded-full bg-white/10 text-white cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
          <img src={lightboxUrl} alt="preview" className="max-h-[88vh] max-w-[92vw] rounded-2xl object-contain" />
        </div>
      )}

      <ShowcaseStudioModal
        open={studioOpen}
        onClose={() => setStudioOpen(false)}
        mode="club"
        ownerId={clubId}
        operatorUid={viewerUid || ""}
        onSaved={loadDetail}
      />
    </div>
  );
}

export function CoachShowcaseDetail({
  coachUid,
  viewerUid,
  onBack,
  onSelectClub,
}: {
  coachUid: string;
  viewerUid?: string;
  onBack?: () => void;
  onSelectClub?: (clubId: string) => void;
}) {
  const { showToast } = useUiFeedback();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [studioOpen, setStudioOpen] = useState(false);

  const loadCoach = useCallback(async () => {
    setLoading(true);
    try {
      const q = viewerUid ? `?viewer_uid=${encodeURIComponent(viewerUid)}` : "";
      const res = await apiClient.get(`/api/community/showcase/coaches/${encodeURIComponent(coachUid)}${q}`);
      setData(res.data);
    } catch (e: any) {
      showToast("加载教练档案失败：" + (e?.message || ""), "error");
    } finally {
      setLoading(false);
    }
  }, [coachUid, viewerUid, showToast]);

  useEffect(() => {
    loadCoach();
  }, [loadCoach]);

  if (loading) {
    return <div className="rgm-bento-card p-10 text-center text-xs text-[var(--rgm-text-muted)]">加载团长/教练风采中...</div>;
  }
  if (!data?.coach_profile) return null;

  const { coach_profile: cp, resume, verified_achievements: va, coaching_impact: ci, photos, can_edit } = data;

  return (
    <div className="space-y-5">
      {onBack && (
        <button
          type="button"
          onClick={onBack}
          className="inline-flex items-center gap-1 text-xs font-bold text-[var(--rgm-text-2)] hover:text-[#FC4C02] cursor-pointer"
        >
          <ChevronLeft className="w-4 h-4" /> 返回展厅列表
        </button>
      )}

      <div className="rgm-bento-card p-6 space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="w-16 h-16 rounded-2xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] overflow-hidden flex items-center justify-center text-lg font-black">
              {cp.avatar_url ? (
                <img src={cp.avatar_url} alt={cp.display_name} className="w-full h-full object-cover" />
              ) : (
                String(cp.display_name || "教").slice(0, 1)
              )}
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <h2 className="text-xl font-black text-[var(--rgm-text)]">{cp.display_name}</h2>
                {va?.watch_verified && (
                  <span className="px-2.5 py-0.5 rounded-full text-[11px] font-black bg-[var(--rgm-green-tint)] text-emerald-500 flex items-center gap-1">
                    <Watch className="w-3 h-3" /> {(va.watch_brands || []).join("/")} 手表核验
                  </span>
                )}
                {(va?.official_pacer_count || 0) > 0 && (
                  <span className="px-2.5 py-0.5 rounded-full text-[11px] font-black bg-[var(--rgm-amber-tint)] text-amber-500">
                    🐰 平台官兔核验 ×{va.official_pacer_count}
                  </span>
                )}
              </div>
              <p className="text-sm font-bold text-[#FC4C02] mt-1">{resume?.headline}</p>
              <div className="text-xs text-[var(--rgm-text-2)] mt-1 flex items-center gap-2 flex-wrap">
                <span>{cp.age_group}</span>
                {cp.city && <span>· 📍 {cp.city}</span>}
                {cp.first_aid_cert_type && <span className="text-emerald-500 font-bold">· 🏥 {cp.first_aid_cert_type}</span>}
              </div>
            </div>
          </div>

          {can_edit && (
            <button
              type="button"
              onClick={() => setStudioOpen(true)}
              className="px-4 py-2 rounded-xl bg-[#FC4C02] text-white text-xs font-black flex items-center gap-1.5 cursor-pointer shrink-0"
            >
              <Paintbrush className="w-3.5 h-3.5" /> 编辑我的风采与相册
            </button>
          )}
        </div>

        {/* Verified PBs & Impact Metrics */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="p-3 rounded-2xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)]">
            <div className="text-[11px] text-[var(--rgm-text-muted)]">⌚ 核验全马 PB</div>
            <div className="text-base font-black text-[#FC4C02] mt-0.5 tabular-nums">
              {va?.verified_pbs?.marathon_pb || "持续刷新中"}
            </div>
          </div>
          <div className="p-3 rounded-2xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)]">
            <div className="text-[11px] text-[var(--rgm-text-muted)]">⚡ 核验半马 / VDOT</div>
            <div className="text-base font-black text-[var(--rgm-text)] mt-0.5 tabular-nums">
              {va?.verified_pbs?.half_pb || "--"} {va?.verified_pbs?.peak_vdot ? `· VDOT ${va.verified_pbs.peak_vdot}` : ""}
            </div>
          </div>
          <div className="p-3 rounded-2xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)]">
            <div className="text-[11px] text-[var(--rgm-text-muted)]">覆盖跑团学员</div>
            <div className="text-base font-black text-[var(--rgm-text)] mt-0.5 tabular-nums">
              {ci?.total_coached_runners ?? 0} 人 ({ci?.active_mentees_count ?? 0} 位徒弟)
            </div>
          </div>
          <div className="p-3 rounded-2xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)]">
            <div className="text-[11px] text-[var(--rgm-text-muted)]">本月带队累计跑量</div>
            <div className="text-base font-black text-emerald-500 mt-0.5 tabular-nums">{ci?.month_team_km ?? 0} km</div>
          </div>
        </div>

        {resume?.bio_story && (
          <div className="p-4 rounded-2xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] text-xs text-[var(--rgm-text-2)] leading-relaxed">
            {resume.bio_story}
          </div>
        )}

        {(resume?.certifications || []).length > 0 && (
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-bold text-[var(--rgm-text)]">📜 专业资历与认证：</span>
            {resume.certifications.map((ct: any, idx: number) => (
              <span
                key={idx}
                className="px-2.5 py-1 rounded-xl bg-[var(--rgm-blue-tint)] border border-sky-500/30 text-xs font-bold text-sky-400"
              >
                {ct.title || ct}
              </span>
            ))}
          </div>
        )}

        {(ci?.coached_clubs || []).length > 0 && (
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-bold text-[var(--rgm-text)]">🏛️ 执教跑团：</span>
            {ci.coached_clubs.map((cl: any) => (
              <button
                key={cl.id}
                type="button"
                onClick={() => onSelectClub?.(cl.id)}
                className="px-3 py-1.5 rounded-xl bg-[var(--rgm-brand-tint)] border border-[#FC4C02]/30 text-xs font-bold text-[#FC4C02] cursor-pointer hover:opacity-90"
              >
                {cl.name} ({cl.member_cnt}人) ›
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Coach Photo Wall */}
      <div className="rgm-bento-card p-6 space-y-3">
        <h3 className="text-sm font-black text-[var(--rgm-text)] flex items-center gap-1.5">
          <Camera className="w-4 h-4 text-[#FC4C02]" />
          执教风采、赛道冲线与资质证书照片墙 ({(photos || []).length})
        </h3>
        {(photos || []).length === 0 ? (
          <div className="py-6 text-center text-xs text-[var(--rgm-text-muted)]">暂未上传个人风采照</div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {photos.map((p: any) => (
              <div key={p.id} className="relative aspect-[4/3] rounded-2xl overflow-hidden border border-[var(--rgm-border)]">
                <img src={p.photo_url} alt={p.caption || "风采照"} className="w-full h-full object-cover" />
              </div>
            ))}
          </div>
        )}
      </div>

      <ShowcaseStudioModal
        open={studioOpen}
        onClose={() => setStudioOpen(false)}
        mode="coach"
        ownerId={coachUid}
        operatorUid={viewerUid || ""}
        onSaved={loadCoach}
      />
    </div>
  );
}

export function ShowcasePlazaView({
  viewerUid,
  initialTab = "clubs",
  initialClubId = "",
  initialCoachUid = "",
}: {
  viewerUid?: string;
  initialTab?: "clubs" | "coaches";
  initialClubId?: string;
  initialCoachUid?: string;
}) {
  const { showToast } = useUiFeedback();
  const [tab, setTab] = useState<"clubs" | "coaches">(initialTab);
  const [selectedClubId, setSelectedClubId] = useState(initialClubId);
  const [selectedCoachUid, setSelectedCoachUid] = useState(initialCoachUid);
  const [city, setCity] = useState("");
  const [search, setSearch] = useState("");
  const [clubs, setClubs] = useState<any[]>([]);
  const [coaches, setCoaches] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const loadPlaza = useCallback(async () => {
    setLoading(true);
    try {
      const q = new URLSearchParams({ tab });
      if (viewerUid) q.set("viewer_uid", viewerUid);
      if (city.trim()) q.set("city", city.trim());
      if (search.trim()) q.set("search", search.trim());
      const res = await apiClient.get(`/api/community/showcase/plaza?${q.toString()}`);
      setClubs(res.data?.clubs || []);
      setCoaches(res.data?.coaches || []);
    } catch (e: any) {
      showToast("加载展厅失败：" + (e?.message || ""), "error");
    } finally {
      setLoading(false);
    }
  }, [viewerUid, tab, city, search, showToast]);

  useEffect(() => {
    loadPlaza();
  }, [loadPlaza]);

  if (selectedClubId) {
    return (
      <ClubShowcaseDetail
        clubId={selectedClubId}
        viewerUid={viewerUid}
        onBack={() => setSelectedClubId("")}
        onSelectCoach={(uidC) => {
          setSelectedClubId("");
          setSelectedCoachUid(uidC);
        }}
        onJoinedClub={loadPlaza}
      />
    );
  }

  if (selectedCoachUid) {
    return (
      <CoachShowcaseDetail
        coachUid={selectedCoachUid}
        viewerUid={viewerUid}
        onBack={() => setSelectedCoachUid("")}
        onSelectClub={(cid) => {
          setSelectedCoachUid("");
          setSelectedClubId(cid);
        }}
      />
    );
  }

  return (
    <div className="space-y-5">
      <div className="rgm-bento-card p-6 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-black text-[var(--rgm-text)]">
              🏛️ 选团与名帅风采展厅（防伪战绩 & 实拍相册）
            </h1>
            <p className="text-xs text-[var(--rgm-text-2)] mt-1">
              跑团无排他限制，可通过合练实拍、手表核验全团战绩与主教练资历自由比较挑选适合自己的跑团
            </p>
          </div>
          <div className="inline-flex p-1 rounded-2xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)]">
            <button
              type="button"
              onClick={() => setTab("clubs")}
              className={`px-4 py-2 rounded-xl text-xs font-bold cursor-pointer ${
                tab === "clubs" ? "bg-[#FC4C02] text-white" : "text-[var(--rgm-text-2)]"
              }`}
            >
              🏛️ 跑团品牌展厅 ({clubs.length})
            </button>
            <button
              type="button"
              onClick={() => setTab("coaches")}
              className={`px-4 py-2 rounded-xl text-xs font-bold cursor-pointer ${
                tab === "coaches" ? "bg-[#FC4C02] text-white" : "text-[var(--rgm-text-2)]"
              }`}
            >
              🎖️ 认证团长/教练 ({coaches.length})
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="搜索跑团名称 / 公园据点 / 教练姓名..."
            className="sm:col-span-2 px-3.5 py-2 rounded-xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] text-xs text-[var(--rgm-text)]"
          />
          <input
            type="text"
            value={city}
            onChange={(e) => setCity(e.target.value)}
            placeholder="过滤城市（如 上海 / 北京）"
            className="px-3.5 py-2 rounded-xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] text-xs text-[var(--rgm-text)]"
          />
        </div>
      </div>

      {loading ? (
        <div className="rgm-bento-card p-10 text-center text-xs text-[var(--rgm-text-muted)]">加载展厅数据中...</div>
      ) : tab === "clubs" ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {clubs.map((c) => (
            <div
              key={c.club_id}
              onClick={() => setSelectedClubId(c.club_id)}
              className="rgm-bento-card overflow-hidden cursor-pointer hover:border-[#FC4C02]/50 transition flex flex-col"
            >
              <div className="h-36 bg-[var(--rgm-card-2)] relative overflow-hidden">
                {c.hero_cover_url ? (
                  <img src={c.hero_cover_url} alt={c.name} className="w-full h-full object-cover" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-xs text-[var(--rgm-text-muted)]">
                    <Sparkles className="w-5 h-5 mr-1 text-[#FC4C02]" /> 跑团品牌展厅
                  </div>
                )}
                {c.photo_count > 0 && (
                  <span className="absolute bottom-2 right-2 px-2 py-0.5 rounded-full bg-black/70 text-white text-[10px] font-bold">
                    📸 {c.photo_count} 张实拍
                  </span>
                )}
              </div>
              <div className="p-5 flex-1 flex flex-col justify-between gap-3">
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <h3 className="text-sm font-black text-[var(--rgm-text)] truncate">{c.name}</h3>
                    {c.is_member && (
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-[var(--rgm-green-tint)] text-emerald-500 font-bold shrink-0">
                        已加入
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-[var(--rgm-text-2)] mt-1 line-clamp-2">{c.slogan}</p>
                </div>
                <div className="flex items-center justify-between text-[11px] text-[var(--rgm-text-muted)] pt-2 border-t border-[var(--rgm-divider)]">
                  <span>
                    <Users className="w-3.5 h-3.5 inline mr-1" />
                    {c.verified_stats?.member_count ?? 0}人 · 破330 {c.verified_stats?.sub330_count ?? 0}人
                  </span>
                  <span className="text-[#FC4C02] font-bold">看相册与教练 ›</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {coaches.map((ch) => (
            <div
              key={ch.user_id}
              onClick={() => setSelectedCoachUid(ch.user_id)}
              className="rgm-bento-card p-5 cursor-pointer hover:border-[#FC4C02]/50 transition space-y-3"
            >
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-2xl bg-[var(--rgm-card-2)] overflow-hidden shrink-0 flex items-center justify-center font-black">
                  {ch.avatar_url ? (
                    <img src={ch.avatar_url} alt={ch.display_name} className="w-full h-full object-cover" />
                  ) : (
                    String(ch.display_name || "教").slice(0, 1)
                  )}
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="text-sm font-black text-[var(--rgm-text)]">{ch.display_name}</span>
                    {ch.watch_verified && (
                      <span className="px-1.5 py-0.5 rounded bg-[var(--rgm-green-tint)] text-emerald-500 text-[10px] font-bold">
                        ⌚ 手表核验
                      </span>
                    )}
                    {ch.official_pacer_count > 0 && (
                      <span className="px-1.5 py-0.5 rounded bg-[var(--rgm-amber-tint)] text-amber-500 text-[10px] font-bold">
                        🐰 官兔×{ch.official_pacer_count}
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-[#FC4C02] font-bold truncate mt-0.5">{ch.headline}</div>
                </div>
              </div>
              <div className="text-xs text-[var(--rgm-text-2)] flex items-center justify-between pt-2 border-t border-[var(--rgm-divider)]">
                <span>全马PB：{ch.verified_marathon_pb || "教练认证"}</span>
                <span className="text-[#FC4C02] font-bold flex items-center gap-1">
                  <Award className="w-3.5 h-3.5" /> 资历与相册 ({ch.photo_count}) ›
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
