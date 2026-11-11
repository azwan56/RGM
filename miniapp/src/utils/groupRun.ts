/**
 * 约跑（跑团线下活动）通用工具：时间格式化、倒计时、日历提醒、导航，
 * 以及「我的下一场约跑」查询（首页卡片使用）。
 */
import { request, setActiveClubId } from "./api";

/** 只有日期、或时间是 00:00 的约跑，默认按 06:30 集合（与跑团页保持一致） */
export function sanitizeMeetTimeStr(meetTimeStr: string): string {
  if (!meetTimeStr) return "";
  let s = meetTimeStr.trim();
  if (!s.includes(":")) {
    s = `${s.split(" ")[0]} 06:30`;
  } else if (s.includes("00:00")) {
    s = s.replace("00:00", "06:30");
  }
  return s;
}

/** 集合时间的毫秒时间戳；解析失败返回 NaN */
export function meetTimestamp(evt: any): number {
  const raw = evt?.meet_time || evt?.start_date || "";
  if (!raw) return NaN;
  return new Date(sanitizeMeetTimeStr(raw).replace(/-/g, "/")).getTime();
}

export function formatMeetTime(meetTimeStr: string): string {
  if (!meetTimeStr) return "待定";
  const d = new Date(sanitizeMeetTimeStr(meetTimeStr).replace(/-/g, "/"));
  if (isNaN(d.getTime())) return meetTimeStr;
  const weekdays = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${d.getMonth() + 1}月${d.getDate()}日 (${weekdays[d.getDay()]}) ${hh}:${mm}`;
}

export function getCountdownText(meetTimeStr: string): string {
  if (!meetTimeStr) return "";
  const targetDate = new Date(sanitizeMeetTimeStr(meetTimeStr).replace(/-/g, "/"));
  const target = targetDate.getTime();
  if (isNaN(target)) return "";
  const nowDate = new Date();
  const diffMs = target - nowDate.getTime();
  if (diffMs < 0) return diffMs > -4 * 3600 * 1000 ? "🔥 正在进行中" : "已结束";
  const diffHours = Math.floor(diffMs / 3600000);

  // 按自然日判断今天 / 明天 / 后天，避免周六早 8 点看周日早 6:30（相隔 22 小时 < 24h）误判为“今天开跑”
  const todayMidnight = new Date(nowDate.getFullYear(), nowDate.getMonth(), nowDate.getDate()).getTime();
  const targetMidnight = new Date(targetDate.getFullYear(), targetDate.getMonth(), targetDate.getDate()).getTime();
  const calendarDays = Math.round((targetMidnight - todayMidnight) / 86400000);

  if (calendarDays <= 0) {
    if (diffHours === 0) return `⚡ 还有 ${Math.max(1, Math.floor(diffMs / 60000))} 分钟开跑`;
    return `⏰ 今天开跑（还有 ${diffHours} 小时）`;
  }
  if (calendarDays === 1) {
    return diffHours < 24 ? `⏰ 明天开跑（还有 ${diffHours} 小时）` : "⏰ 明天开跑";
  }
  if (calendarDays === 2) return "⏰ 后天开跑";
  return `⏰ 还有 ${calendarDays} 天开跑`;
}

/** 加入手机日历（提前 30 分钟提醒） */
export function addRunToCalendar(evt: any) {
  if (!evt) return;
  const ts = meetTimestamp(evt);
  const startTime = Math.floor((isNaN(ts) ? Date.now() + 3600000 : ts) / 1000);
  const locationStr = evt.location || "跑团指定地点";
  const descStr = `【跑团约跑】${evt.title}\n集合时间: ${evt.meet_time || evt.start_date || "请见跑团通知"}\n地点: ${locationStr}\n建议配速: ${evt.pace_requirement || "不限"}\n目标跑量: ${evt.target_km || 10}km\n${evt.rules || ""}`;
  // #ifdef MP-WEIXIN
  if (typeof wx !== "undefined" && (wx as any).addPhoneCalendar) {
    (wx as any).addPhoneCalendar({
      title: `【跑团约跑】${evt.title}`,
      startTime,
      endTime: startTime + 7200,
      allDay: false,
      location: locationStr,
      description: descStr,
      alarm: true,
      alarmOffset: 1800,
      success: () => uni.showToast({ title: "已加入手机日历提醒！", icon: "success" }),
      fail: (err: any) => {
        if (!String(err?.errMsg).includes("cancel")) {
          uni.showToast({ title: "添加日历失败，请稍后重试", icon: "none" });
        }
      },
    });
    return;
  }
  // #endif
  uni.showToast({ title: "当前环境不支持添加日历", icon: "none" });
}

/** 打开地图导航到集合点；没有坐标时复制地址 */
export function openRunLocation(evt: any) {
  if (!evt) return;
  // #ifdef MP-WEIXIN
  if (evt.latitude && evt.longitude && typeof wx !== "undefined" && wx.openLocation) {
    wx.openLocation({
      latitude: Number(evt.latitude),
      longitude: Number(evt.longitude),
      name: evt.location || "约跑集合点",
      address: evt.location_detail || evt.location || "",
      scale: 16,
    });
    return;
  }
  // #endif
  const copyText = (evt.location || "") + (evt.location_detail ? ` (${evt.location_detail})` : "");
  if (!copyText) {
    uni.showToast({ title: "暂无集合点信息", icon: "none" });
    return;
  }
  uni.setClipboardData({
    data: copyText,
    success: () => uni.showToast({ title: "集合地点已复制", icon: "none" }),
  });
}

export function isGroupRunArchived(evt: any): boolean {
  if (!evt) return false;
  if (evt.is_archived || evt.lifecycle_status === "archived") return true;
  if (evt.status === "archived" || evt.status === "completed" || evt.status === "ended") return true;
  const ts = meetTimestamp(evt);
  if (!isNaN(ts) && Date.now() >= ts + 4 * 3600 * 1000) return true;
  return false;
}

/**
 * 查询「我已报名、尚未结束」的最近一场约跑（汇总所有已加入的跑团）。
 * 开跑后 4 小时内仍视为进行中；已完成归档约跑自动排除；没有则返回 null。
 */
export async function fetchMyNextGroupRun(uid: string): Promise<any | null> {
  if (!uid || uid === "runner_001") return null;
  const myRes: any = await request(`/api/team/my-clubs/${uid}`).catch(() => null);
  const clubs: any[] = (myRes?.clubs || []).filter((c: any) => !c.is_access_suspended).slice(0, 8);
  if (!clubs.length) return null;
  const results = await Promise.all(
    clubs.map((c: any) =>
      request(`/api/team/${c.id}/events?user_id=${encodeURIComponent(uid)}`)
        .then((r: any) => (r?.events || []).map((e: any) => ({ ...e, club_id: c.id, club_name: c.name })))
        .catch(() => [])
    )
  );
  const cutoff = Date.now() - 4 * 3600 * 1000;
  const upcoming = ([] as any[])
    .concat(...results)
    .filter((e) => e.is_joined && !isGroupRunArchived(e) && (e.event_type === "group_run" || e.meet_time))
    .filter((e) => {
      const ts = meetTimestamp(e);
      return !isNaN(ts) && ts >= cutoff;
    })
    .sort((a, b) => meetTimestamp(a) - meetTimestamp(b));
  return upcoming[0] || null;
}

/** 跳到跑团 Tab 并打开「约跑与拉练活动」子页面 */
export function openTeamEvents(clubId?: string) {
  if (clubId) setActiveClubId(clubId);
  uni.setStorageSync("team_open_section", "events");
  uni.switchTab({ url: "/pages/team/team" });
}

/** 判断约跑是否已进入「约跑后（开跑中/已结束/已有完赛数据）」阶段 */
export function isGroupRunPostStage(evt: any): boolean {
  if (!evt) return false;
  if (Number(evt.completed_count || 0) > 0) return true;
  if (evt.status === "completed" || evt.status === "ended" || evt.status === "archived" || evt.is_archived) return true;
  const ts = meetTimestamp(evt);
  if (!isNaN(ts) && Date.now() >= ts) return true;
  return false;
}

/** 生成微信群转发约跑邀请卡片配置（点开直接进入约跑详情与一键报名页） */
export function buildGroupRunSharePayload(
  evt: any,
  clubName?: string,
  inviterUid?: string,
  stage: "pre" | "post" = "pre",
  posterImg?: string
) {
  const cId = evt?.club_id || "";
  const eId = evt?.id || evt?.event_id || "";
  const cName = clubName || evt?.club_name || "万跑跑团";
  const eTitle = evt?.title || "跑团约跑";
  const timeText = formatMeetTime(evt?.meet_time || evt?.start_date || "");
  const inviterParam = inviterUid ? `&inviter_uid=${encodeURIComponent(inviterUid)}` : "";
  const isPost = stage === "post";
  const title = isPost
    ? `🏆 完赛战报｜【${cName}】${eTitle}`
    : `🏃 约跑邀请｜${eTitle}（${timeText}）`;
  return {
    title,
    path: `/pages/group-run/group-run?club_id=${encodeURIComponent(cId)}&event_id=${encodeURIComponent(eId)}&stage=${stage}&invite=1${inviterParam}`,
    imageUrl: posterImg || evt?.cover_image || undefined,
  };
}

/** 打开约跑详情页，支持指定 stage='pre'（约跑前集结）或 stage='post'（约跑后完赛战报）以及自动弹出海报 */
export function openGroupRunDetail(clubId: string, eventId: string, stage?: "pre" | "post", openPoster?: boolean) {
  if (!clubId || !eventId) return;
  const stageParam = stage ? `&stage=${stage}` : "";
  const posterParam = openPoster ? "&poster=1" : "";
  uni.navigateTo({
    url: `/pages/group-run/group-run?club_id=${encodeURIComponent(clubId)}&event_id=${encodeURIComponent(eventId)}${stageParam}${posterParam}`,
  });
}

export interface GroupRunVenuePreset {
  name: string;
  address: string;
  latitude: number;
  longitude: number;
}

const LOCAL_LANDMARK_INDEX: GroupRunVenuePreset[] = [
  { name: "闵行文化公园", address: "上海市闵行区吴中路2019号闵行文化公园", latitude: 31.1634, longitude: 121.3609 },
  { name: "闵行文化公园1号门", address: "上海市闵行区吴中路2019号闵行文化公园1号门(北门)", latitude: 31.1682, longitude: 121.3586 },
  { name: "闵行文化公园2号门", address: "上海市闵行区漕宝路2001号闵行文化公园2号门(南门)", latitude: 31.1578, longitude: 121.3595 },
  { name: "闵行文化公园3号门", address: "上海市闵行区新镇路闵行文化公园3号门(西门)", latitude: 31.1625, longitude: 121.3538 },
  { name: "闵行体育公园", address: "上海市闵行区新镇路456号闵行体育公园", latitude: 31.1429, longitude: 121.3708 },
  { name: "世纪公园", address: "上海市浦东新区锦绣路1001号世纪公园", latitude: 31.2166, longitude: 121.5529 },
  { name: "世纪公园7号门", address: "上海市浦东新区锦绣路701号世纪公园7号门", latitude: 31.2165, longitude: 121.5518 },
  { name: "世纪公园1号门", address: "上海市浦东新区锦绣路1001号世纪公园1号门", latitude: 31.2241, longitude: 121.5403 },
  { name: "徐汇滨江", address: "上海市徐汇区龙腾大道瑞宁路市民跑步驿站", latitude: 31.1892, longitude: 121.4619 },
  { name: "卢湾体育场", address: "上海市黄浦区肇嘉浜路128号卢湾体育场", latitude: 31.2094, longitude: 121.4646 },
  { name: "源深体育中心", address: "上海市浦东新区源深路655号源深体育中心", latitude: 31.2335, longitude: 121.5396 },
  { name: "半马苏河公园苗江路", address: "上海市黄浦区苗江路望达路绿地驿站", latitude: 31.2016, longitude: 121.4932 },
  { name: "大宁公园", address: "上海市静安区广中西路288号大宁灵石公园", latitude: 31.2752, longitude: 121.4393 },
  { name: "共青森林公园", address: "上海市杨浦区军工路2000号共青森林公园", latitude: 31.3187, longitude: 121.5523 },
  { name: "顾村公园", address: "上海市宝山区沪太路4788号顾村公园", latitude: 31.3444, longitude: 121.3732 },
  { name: "佘山国家森林公园", address: "上海市松江区外青松公路9258号东佘山园", latitude: 31.0956, longitude: 121.1965 },
  { name: "滴水湖", address: "上海市浦东新区南汇新城镇环湖西一路滴水湖", latitude: 30.9069, longitude: 121.9299 },
  { name: "奥林匹克森林公园", address: "北京市朝阳区科荟路33号奥林匹克森林公园南门", latitude: 40.0156, longitude: 116.3924 },
  { name: "玄武湖公园", address: "江苏省南京市玄武区玄武巷1号玄武门", latitude: 32.0724, longitude: 118.7979 },
  { name: "西湖", address: "浙江省杭州市西湖区龙井路1号杭州西湖", latitude: 30.2437, longitude: 120.1479 },
  { name: "深圳湾公园", address: "广东省深圳市南山区滨海大道深圳湾公园", latitude: 22.5216, longitude: 113.9930 },
];

export interface GroupRunTemplateItem {
  id: string;
  name: string;
  is_custom?: boolean;
  title: string;
  event_type?: "group_run" | "distance_challenge";
  target_km: number;
  default_weekday?: number; // 0=周日, 1=周一 ... 6=周六
  meet_time_hm: string;
  location: string;
  location_detail: string;
  latitude: number | null;
  longitude: number | null;
  pace_requirement: string;
  rules: string;
}

export const DEFAULT_GROUP_RUN_TEMPLATES: GroupRunTemplateItem[] = [
  {
    id: "tpl_weekend_lsd",
    name: "🌅 周日22k LSD",
    title: "周日 22km 分组 LSD 有氧耐力合练",
    event_type: "group_run",
    target_km: 22,
    default_weekday: 0,
    meet_time_hm: "06:30",
    location: "",
    location_detail: "集合存包热身，按配速分组出发，跑完集中拉伸",
    latitude: null,
    longitude: null,
    pace_requirement: "A组4:15 / B组4:50 / C组5:30",
    rules: "240/A组配速4:15，B组配速4:50，C组配速5:30，D组配速6:00；每5km定点补水，跑完集合拉伸合影。",
  },
  {
    id: "tpl_tue_track",
    name: "🏟️ 周二间歇合练",
    title: "周二场地间歇跑 · 乳酸阈值强化",
    event_type: "group_run",
    target_km: 12,
    default_weekday: 2,
    meet_time_hm: "19:30",
    location: "",
    location_detail: "内圈1-2道间歇组，外道慢跑恢复",
    latitude: null,
    longitude: null,
    pace_requirement: "按组别间歇配速",
    rules: "热身慢跑2km + 动态激活；主课表：8×1000m间歇（组间慢跑400m恢复）；冷身2km，统一听哨发枪。",
  },
  {
    id: "tpl_mp_special",
    name: "⚡ 28k专项MP拉练",
    title: "周日 28km 马拉松专项配速拉练",
    event_type: "group_run",
    target_km: 28,
    default_weekday: 0,
    meet_time_hm: "06:00",
    location: "",
    location_detail: "赛前专项长距离，按目标配速分组巡航",
    latitude: null,
    longitude: null,
    pace_requirement: "目标全马配速 (MP)",
    rules: "前8km有氧热身配速，后20km严格按各组目标全马配速(MP)巡航，模拟比赛每5km进站饮水与能量胶补给。",
  },
  {
    id: "tpl_sat_aerobic",
    name: "🌳 周六15k例跑",
    title: "周六 15km 有氧耐力例跑",
    event_type: "group_run",
    target_km: 15,
    default_weekday: 6,
    meet_time_hm: "06:30",
    location: "",
    location_detail: "集合热身慢跑，跑完统一拉伸",
    latitude: null,
    longitude: null,
    pace_requirement: "5:00 - 6:15 /km",
    rules: "跑团周末固定有氧例跑，全程保持轻松交谈心率(Zone 2)，迎新破冰，跑完拉伸交流。",
  },
  {
    id: "tpl_trail_climb",
    name: "⛰️ 18k越野跑山",
    title: "周末 18km 山野台阶与有氧爬升拉练",
    event_type: "group_run",
    target_km: 18,
    default_weekday: 0,
    meet_time_hm: "07:00",
    location: "",
    location_detail: "入口集合热身，山野环线有氧爬升",
    latitude: null,
    longitude: null,
    pace_requirement: "有氧爬升·结伴同行",
    rules: "山野台阶与土路上下坡技术拉练；强制携带越野水袋包(≥1L水)、能量补给与防风皮肤衣。",
  },
  {
    id: "tpl_thu_night",
    name: "🌙 周四10k夜跑",
    title: "周四 10km 轻松排酸夜跑 + 核心训练",
    event_type: "group_run",
    target_km: 10,
    default_weekday: 4,
    meet_time_hm: "19:30",
    location: "",
    location_detail: "集合热身出发，跑后15分钟核心训练",
    latitude: null,
    longitude: null,
    pace_requirement: "5:30 - 6:30 /km",
    rules: "周中低心率轻松排酸慢跑10km，结束后集体完成15分钟核心平板与臀中肌抗阻训练。",
  },
];

/** 计算距离今天最近的指定星期几 (0=周日..6=周六) 的 YYYY-MM-DD */
export function resolveNextWeekdayIso(targetWeekday: number = 0): string {
  const now = new Date();
  const curDay = now.getDay();
  let diff = (targetWeekday - curDay + 7) % 7;
  if (diff === 0 && now.getHours() >= 10) {
    diff = 7;
  }
  const target = new Date(now.getFullYear(), now.getMonth(), now.getDate() + diff);
  const y = target.getFullYear();
  const m = String(target.getMonth() + 1).padStart(2, "0");
  const d = String(target.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

/**
 * 根据用户输入的地点关键词（如“闵行文化公园”）检索 GCJ-02 坐标候选列表
 */
export async function searchGroupRunGeocode(keyword: string): Promise<GroupRunVenuePreset[]> {
  const q = (keyword || "").trim();
  if (!q) return [];

  const localMatches = LOCAL_LANDMARK_INDEX.filter(
    (v) => v.name.includes(q) || q.includes(v.name)
  ).map((v) => ({
    ...v,
    name: q.length > v.name.length && q.includes(v.name) ? q : v.name,
  }));

  try {
    const res: any = await request(`/api/team/geocode?q=${encodeURIComponent(q)}`);
    const remoteList: GroupRunVenuePreset[] = Array.isArray(res?.results) ? res.results : [];
    if (remoteList.length > 0) {
      return remoteList;
    }
  } catch {
    // ignore network error and fall back to localMatches
  }
  return localMatches;
}

/**
 * 调用微信原生全屏地图选点（预先以当前或关键词解析出的坐标为中心）
 */
export async function pickGroupRunLocation(
  currentLat?: number | null,
  currentLng?: number | null,
  keyword?: string
): Promise<GroupRunVenuePreset | null> {
  let centerLat = currentLat ? Number(currentLat) : null;
  let centerLng = currentLng ? Number(currentLng) : null;

  if (keyword && keyword.trim() && (!centerLat || !centerLng)) {
    const matches = await searchGroupRunGeocode(keyword.trim());
    if (matches.length > 0) {
      centerLat = matches[0].latitude;
      centerLng = matches[0].longitude;
    }
  }

  return new Promise((resolve) => {
    if (typeof uni !== "undefined" && typeof uni.chooseLocation === "function") {
      const opts: any = {
        success: (res: any) => {
          if (res && (res.latitude || res.name || res.address)) {
            resolve({
              name: res.name || keyword || res.address || "选定集合点",
              address: res.address || res.name || "",
              latitude: Number(res.latitude) || centerLat || 31.2304,
              longitude: Number(res.longitude) || centerLng || 121.4737,
            });
          } else {
            resolve(null);
          }
        },
        fail: () => {
          resolve(null);
        },
      };
      if (centerLat && centerLng) {
        opts.latitude = Number(centerLat);
        opts.longitude = Number(centerLng);
      }
      uni.chooseLocation(opts);
    } else {
      resolve(null);
    }
  });
}
