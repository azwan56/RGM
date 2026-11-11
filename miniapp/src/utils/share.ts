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

/** 统一对外落地页 (所有分享均统一落地至统一分享专页，不携带任何个人 ID 或私密参数) */
export const UNIFIED_SHARE_PATH = "/pages/share/share";

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
  const path = uid
    ? `${UNIFIED_SHARE_PATH}?inviter_uid=${encodeURIComponent(uid)}&from=create_club`
    : UNIFIED_SHARE_PATH;
  return {
    title: `🏃‍♂️ ${name} 邀你加入万跑跑团助手｜支持佳明/高驰/苹果/华为/颂拓同步，一键组建专属跑团！`,
    path,
    imageUrl: "/static/logo-square.png",
  };
}

/**
 * 获取跑团专属微信邀请卡片配置
 */
export function getClubShareAppMessage(club: any, inviterName?: string, inviterUid?: string): ShareMessageResult {
  if (!club) return getUnifiedShareAppMessage(inviterUid);
  const name = club.name || "跑团";
  const clubId = club.id || club.club_id || "";
  const inviteCode = club.invite_code || "";
  const uid = getCurrentInviterUid(inviterUid);
  const title = inviterName
    ? `🏃‍♂️【${name}】${inviterName} 邀请您加入跑团，点击立即入团！`
    : `🏃‍♂️ 诚邀您加入【${name}】跑团，点击立即入团！`;
  const uidParam = uid ? `&inviter_uid=${encodeURIComponent(uid)}` : "";
  const path = `/pages/team/team?club_id=${encodeURIComponent(clubId)}&invite_code=${encodeURIComponent(inviteCode)}&action=join_club${uidParam}`;
  return {
    title,
    path,
    imageUrl: club.logo_url || "/static/logo-square.png",
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
  return {
    title: `🏃‍♂️ 加入【${club.name || '跑团'}】，与跑友科学训练备战！`,
    query: `club_id=${encodeURIComponent(clubId)}&invite_code=${encodeURIComponent(inviteCode)}&action=join_club${uidParam}`,
    imageUrl: club.logo_url || "/static/logo-square.png",
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
