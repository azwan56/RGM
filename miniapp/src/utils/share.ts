/**
 * 微信小程序全量统一分享与转发通用配置
 * 统一分享文案与入口，严格剥离任何用户私密数据与个人页面参数，
 * 专为群发、多级转发、跑友圈推广设计。
 */

export interface ShareMessageResult {
  title: string;
  path: string;
  imageUrl?: string;
}

export interface ShareTimelineResult {
  title: string;
  query: string;
  imageUrl?: string;
}

/** 统一对外分享主标题 (适合跑步群群发与朋友圈) */
export const UNIFIED_SHARE_TITLE = "万跑跑团助手｜佳明·高驰·苹果·华为·颂拓同步 · 科学教练 · 自建跑团与约跑";

/** 统一对外落地页 (所有分享均统一落地至小程序主页，不携带任何个人 ID 或跑团信息) */
export const UNIFIED_SHARE_PATH = "/pages/index/index";

/** 朋友圈分享统一 query (空参数，保障纯净与隐私) */
export const UNIFIED_TIMELINE_QUERY = "";

function getCurrentInviterUid(explicitUid?: string): string {
  if (explicitUid) return explicitUid;
  try {
    const raw = uni.getStorageSync("rgm_user");
    if (!raw) return "";
    const parsed = typeof raw === "string" ? JSON.parse(raw) : raw;
    return parsed?.id || parsed?.uid || "";
  } catch {
    return "";
  }
}

/**
 * 获取统一的“发送给朋友 / 转发到微信群”配置（自动附带邀请人 UID 用于统计拉新解锁建团权益）
 */
export function getUnifiedShareAppMessage(inviterUid?: string): ShareMessageResult {
  const uid = getCurrentInviterUid(inviterUid);
  const path = uid ? `${UNIFIED_SHARE_PATH}?inviter_uid=${encodeURIComponent(uid)}` : UNIFIED_SHARE_PATH;
  return {
    title: UNIFIED_SHARE_TITLE,
    path,
    imageUrl: "/static/logo-square.png",
  };
}

/**
 * 获取邀请新用户解锁自建跑团权益的专属微信卡片配置
 */
export function getInviteNewRunnerShareMessage(user?: any): ShareMessageResult {
  const uid = getCurrentInviterUid(user?.id || user?.uid);
  const name = user?.real_name || user?.display_name || "跑友";
  const inviteLandingPath = "/pages/share/share";
  const path = uid
    ? `${inviteLandingPath}?inviter_uid=${encodeURIComponent(uid)}&from=create_club`
    : inviteLandingPath;
  return {
    title: `🏃‍♂️ ${name} 邀你加入万跑跑团助手｜支持佳明/高驰/苹果/华为/颂拓同步，一键组建专属跑团！`,
    path,
    imageUrl: "/static/logo-square.png",
  };
}

function resolveShareImageUrl(rawUrl?: string | null): string {
  const s = String(rawUrl || "").trim();
  if (!s) return "/static/logo-square.png";
  if (s.startsWith("/static/")) return s;
  if (s.startsWith("http://") || s.startsWith("https://")) return s;
  if (s.startsWith("/")) return `https://rgm.vanpower.net${s}`;
  return s;
}

/**
 * 获取跑团专属微信邀请卡片配置（综合跑团主要信息与封面/实拍大图，支持点击卡片直接进跑团）
 */
export function getClubShareAppMessage(club: any, inviterName?: string, inviterUid?: string): ShareMessageResult {
  if (!club) return getUnifiedShareAppMessage(inviterUid);
  const name = club.name || "跑团";
  const clubId = club.id || club.club_id || "";
  const inviteCode = club.invite_code || "";
  const uid = getCurrentInviterUid(inviterUid);

  const city = club.city || "";
  const landmarks: string[] = Array.isArray(club.home_landmarks) ? club.home_landmarks : [];
  const locPart = landmarks.length ? `${city ? city + "·" : ""}${landmarks[0]}` : city;
  const memberCnt = club.verified_stats?.member_count ?? club.member_count ?? 0;
  const sub330Cnt = club.verified_stats?.sub330_count ?? 0;
  const statPart = [
    locPart,
    memberCnt > 0 ? `${memberCnt}人同跑` : "",
    sub330Cnt > 0 ? `破330×${sub330Cnt}` : "",
  ]
    .filter(Boolean)
    .join(" · ");

  const inviterPrefix = inviterName ? `${inviterName}邀您入团` : "诚邀加入";
  const title = statPart
    ? `🏃‍♂️【${name}】${inviterPrefix}｜${statPart} · 点击直接进跑团`
    : `🏃‍♂️【${name}】${inviterPrefix}，点击卡片直接进跑团！`;

  const uidParam = uid ? `&inviter_uid=${encodeURIComponent(uid)}` : "";
  const path = `/pages/team/team?club_id=${encodeURIComponent(clubId)}&invite_code=${encodeURIComponent(inviteCode)}&action=join_club&auto_join=1${uidParam}`;
  const bestImg =
    club.share_card_image_url ||
    club.hero_cover_url ||
    (Array.isArray(club.photos) && club.photos[0]?.photo_url) ||
    club.logo_url ||
    "/static/logo-square.png";

  return {
    title,
    path,
    imageUrl: resolveShareImageUrl(bestImg),
  };
}

/**
 * 获取大群体专属微信邀请卡片配置 (如复旦戈友会)
 */
export function getOrgShareAppMessage(org: any, inviterName?: string, inviterUid?: string): ShareMessageResult {
  if (!org) return getUnifiedShareAppMessage(inviterUid);
  const name = org.name || "大群";
  const orgId = org.id || org.org_id || "";
  const inviteCode = org.invite_code || "";
  const uid = getCurrentInviterUid(inviterUid);
  const title = inviterName
    ? `🏛️【${name}】${inviterName} 邀请您加入大群，免输入邀请码直接认证！`
    : `🏛️ 诚邀您加入【${name}】大群，免输入邀请码直接实名认证！`;
  const uidParam = uid ? `&inviter_uid=${encodeURIComponent(uid)}` : "";
  const path = `/pages/team/team?org_id=${encodeURIComponent(orgId)}&invite_code=${encodeURIComponent(inviteCode)}&action=join_org${uidParam}`;
  return {
    title,
    path,
    imageUrl: org.logo_url || "/static/logo-square.png",
  };
}

/**
 * 获取统一的“分享到朋友圈”配置
 */
export function getUnifiedShareTimeline(inviterUid?: string): ShareTimelineResult {
  const uid = getCurrentInviterUid(inviterUid);
  return {
    title: UNIFIED_SHARE_TITLE,
    query: uid ? `inviter_uid=${encodeURIComponent(uid)}` : UNIFIED_TIMELINE_QUERY,
    imageUrl: "/static/logo-square.png",
  };
}

export function getClubShareTimeline(club: any, inviterUid?: string): ShareTimelineResult {
  if (!club) return getUnifiedShareTimeline(inviterUid);
  const clubId = club.id || club.club_id || "";
  const inviteCode = club.invite_code || "";
  const uid = getCurrentInviterUid(inviterUid);
  const uidParam = uid ? `&inviter_uid=${encodeURIComponent(uid)}` : "";
  const bestImg =
    club.share_card_image_url ||
    club.hero_cover_url ||
    (Array.isArray(club.photos) && club.photos[0]?.photo_url) ||
    club.logo_url ||
    "/static/logo-square.png";
  return {
    title: `🏃‍♂️ 加入【${club.name || '跑团'}】，点击直接进跑团与队友科学合练！`,
    query: `club_id=${encodeURIComponent(clubId)}&invite_code=${encodeURIComponent(inviteCode)}&action=join_club&auto_join=1${uidParam}`,
    imageUrl: resolveShareImageUrl(bestImg),
  };
}

export function getOrgShareTimeline(org: any, inviterUid?: string): ShareTimelineResult {
  if (!org) return getUnifiedShareTimeline(inviterUid);
  const orgId = org.id || org.org_id || "";
  const inviteCode = org.invite_code || "";
  const uid = getCurrentInviterUid(inviterUid);
  const uidParam = uid ? `&inviter_uid=${encodeURIComponent(uid)}` : "";
  return {
    title: `🏛️ 加入【${org.name || '大群'}】戈友会大群，实名认证免输邀请码！`,
    query: `org_id=${encodeURIComponent(orgId)}&invite_code=${encodeURIComponent(inviteCode)}&action=join_org${uidParam}`,
    imageUrl: org.logo_url || "/static/logo-square.png",
  };
}

/**
 * 显式初始化分享菜单
 * 开启 withShareTicket 确保微信群分享票据激活，全力支持群发与群内多级转发
 */
export function initShareMenu() {
  // #ifdef MP-WEIXIN
  if (typeof wx !== "undefined" && wx.showShareMenu) {
    wx.showShareMenu({
      withShareTicket: true,
      menus: ["shareAppMessage", "shareTimeline"],
    });
  }
  // #endif
}
