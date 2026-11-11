/**
 * Modular Club Poster Canvas Renderers & Coach Student Filter/Sort Helpers
 * Extracted from TeamView.tsx to keep presentation components concise and testable.
 */

export function drawRoundedRectWeb(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  width: number,
  height: number,
  radius: number,
  fillStyle?: string,
  strokeStyle?: string
) {
  ctx.save();
  ctx.beginPath();
  ctx.moveTo(x + radius, y);
  ctx.lineTo(x + width - radius, y);
  ctx.arcTo(x + width, y, x + width, y + radius, radius);
  ctx.lineTo(x + width, y + height - radius);
  ctx.arcTo(x + width, y + height, x + width - radius, y + height, radius);
  ctx.lineTo(x + radius, y + height);
  ctx.arcTo(x, y + height, x, y + height - radius, radius);
  ctx.lineTo(x, y + radius);
  ctx.arcTo(x, y, x + radius, y, radius);
  ctx.closePath();
  if (fillStyle) {
    ctx.fillStyle = fillStyle;
    ctx.fill();
  }
  if (strokeStyle) {
    ctx.strokeStyle = strokeStyle;
    ctx.stroke();
  }
  ctx.restore();
}

export function drawWrappedTextWeb(
  ctx: CanvasRenderingContext2D,
  text: string,
  x: number,
  y: number,
  maxWidth: number,
  lineHeight: number,
  maxLines: number = 5
) {
  let line = "";
  let lineCount = 0;
  for (let i = 0; i < text.length; i++) {
    const testLine = line + text[i];
    if (ctx.measureText(testLine).width > maxWidth && i > 0) {
      ctx.fillText(line, x, y);
      line = text[i];
      y += lineHeight;
      lineCount++;
      if (lineCount >= maxLines - 1) {
        const remaining = text.substring(i);
        let lastLine = "";
        const suffix = text.startsWith("“") ? "…”" : "...";
        for (let j = 0; j < remaining.length; j++) {
          if (ctx.measureText(lastLine + remaining[j] + suffix).width > maxWidth) {
            break;
          }
          lastLine += remaining[j];
        }
        ctx.fillText(lastLine + suffix, x, y);
        return y + lineHeight;
      }
    } else {
      line = testLine;
    }
  }
  ctx.fillText(line, x, y);
  return y + lineHeight;
}

export function downloadCanvasAsPng(canvas: HTMLCanvasElement, filename: string) {
  const dataUrl = canvas.toDataURL("image/png");
  const a = document.createElement("a");
  a.href = dataUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

export async function renderClubInvitePosterCanvas(d: any): Promise<HTMLCanvasElement | null> {
  if (!d) return null;
  const canvas = document.createElement("canvas");
  const W = 750;
  const H = 980;
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;

  const bgGrad = ctx.createLinearGradient(0, 0, W, H);
  bgGrad.addColorStop(0, "#141118");
  bgGrad.addColorStop(0.5, "#0d0f17");
  bgGrad.addColorStop(1, "#121824");
  ctx.fillStyle = bgGrad;
  ctx.fillRect(0, 0, W, H);

  const topBarGrad = ctx.createLinearGradient(0, 0, W, 0);
  topBarGrad.addColorStop(0, "#FC4C02");
  topBarGrad.addColorStop(0.5, "#f59e0b");
  topBarGrad.addColorStop(1, "#10b981");
  ctx.fillStyle = topBarGrad;
  ctx.fillRect(0, 0, W, 10);

  drawRoundedRectWeb(ctx, 44, 42, 340, 44, 22, "rgba(252, 76, 2, 0.16)", "rgba(252, 76, 2, 0.45)");
  ctx.font = "bold 18px sans-serif";
  ctx.fillStyle = "#ff7a45";
  ctx.fillText("💌 万跑跑团助手 · 官方入团邀请函", 64, 70);

  ctx.font = "900 30px sans-serif";
  ctx.fillStyle = "#ffffff";
  const inviterLabel = d.inviter_name ? `👋 跑友【${d.inviter_name}】诚邀您入团` : "👋 诚邀您加入我们的跑团";
  ctx.fillText(inviterLabel, 44, 138);

  ctx.font = "18px sans-serif";
  ctx.fillStyle = "#9ca3af";
  ctx.fillText("科学耐力训练 · 佳明/高驰数据直连 · 队友同频共进", 44, 172);

  drawRoundedRectWeb(ctx, 40, 204, W - 80, 500, 28, "#171923", "rgba(255, 255, 255, 0.12)");

  ctx.font = "900 40px sans-serif";
  ctx.fillStyle = "#ffffff";
  ctx.fillText((d.name || "万跑跑团助手").slice(0, 15), 76, 278);

  let badgeX = 76;
  const badgeY = 302;
  if (d.org_name) {
    const orgTxt = `🏛️ ${d.org_name}`;
    ctx.font = "bold 17px sans-serif";
    const orgW = Math.min(ctx.measureText(orgTxt).width + 32, 320);
    drawRoundedRectWeb(ctx, badgeX, badgeY, orgW, 38, 12, "rgba(245, 158, 11, 0.18)", "rgba(245, 158, 11, 0.45)");
    ctx.fillStyle = "#fcd34d";
    ctx.fillText(orgTxt, badgeX + 16, badgeY + 25);
    badgeX += orgW + 14;
  }

  const metaTxt = `📍 ${d.city || "上海"} · ${d.member_count || 1} 位跑友同行`;
  ctx.font = "bold 17px sans-serif";
  const metaW = ctx.measureText(metaTxt).width + 32;
  drawRoundedRectWeb(ctx, badgeX, badgeY, metaW, 38, 12, "rgba(16, 185, 129, 0.16)", "rgba(16, 185, 129, 0.4)");
  ctx.fillStyle = "#6ee7b7";
  ctx.fillText(metaTxt, badgeX + 16, badgeY + 25);

  ctx.font = "20px sans-serif";
  ctx.fillStyle = "#d1d5db";
  drawWrappedTextWeb(
    ctx,
    d.description || "精英跑者联盟，追求 PB 突破与健康长久奔跑。欢迎每一位热爱奔跑的伙伴加入！",
    76,
    384,
    W - 152,
    30,
    3
  );

  drawRoundedRectWeb(
    ctx,
    72,
    490,
    W - 144,
    176,
    22,
    "rgba(252, 76, 2, 0.10)",
    "rgba(252, 76, 2, 0.40)"
  );
  ctx.font = "bold 18px sans-serif";
  ctx.fillStyle = "#fdba74";
  ctx.fillText(
    d.invite_code ? "🔑 跑团专属入团邀请码（小程序/网页通用）" : "🟢 本跑团已开启免码自由入团",
    102,
    534
  );

  ctx.font = "900 48px monospace";
  ctx.fillStyle = "#ffffff";
  ctx.fillText(d.invite_code || "免码直入", 102, 598);

  ctx.font = "17px sans-serif";
  ctx.fillStyle = "#9ca3af";
  ctx.fillText(
    d.invite_code
      ? "微信扫码直接免输码入团，或在小程序「跑团 → 输入邀请码」填入"
      : "微信长按或扫描下方小程序码，即可一键加入跑团",
    102,
    638
  );

  const fY = 740;
  drawRoundedRectWeb(ctx, 40, fY, W - 80, 190, 26, "#121520", "rgba(255, 255, 255, 0.12)");

  ctx.font = "bold 20px sans-serif";
  ctx.fillStyle = "#FC4C02";
  ctx.fillText("📱 微信扫码或长按识别 · 一键入团", 72, fY + 54);

  ctx.font = "900 28px sans-serif";
  ctx.fillStyle = "#ffffff";
  ctx.fillText("打开「万跑跑团助手」小程序", 72, fY + 98);

  ctx.font = "17px sans-serif";
  ctx.fillStyle = "#9ca3af";
  ctx.fillText("直达跑团受邀页面 · 同步跑表解锁 AI 教练与团队排行榜", 72, fY + 140);

  const qrSrc = d.qrcode_base64
    ? d.qrcode_base64.startsWith("data:")
      ? d.qrcode_base64
      : `data:image/jpeg;base64,${d.qrcode_base64}`
    : d.qrcode_url || "";

  if (qrSrc) {
    await new Promise<void>((resolve) => {
      const qrImg = new Image();
      qrImg.crossOrigin = "anonymous";
      qrImg.onload = () => {
        const qrBoxX = W - 40 - 166;
        const qrBoxY = fY + 20;
        drawRoundedRectWeb(ctx, qrBoxX, qrBoxY, 150, 150, 18, "#ffffff");
        ctx.drawImage(qrImg, qrBoxX + 8, qrBoxY + 8, 134, 134);
        resolve();
      };
      qrImg.onerror = () => resolve();
      qrImg.src = qrSrc;
    });
  }

  return canvas;
}

export async function renderClubReportPosterCanvas(rep: any, isLight: boolean): Promise<HTMLCanvasElement | null> {
  if (!rep) return null;
  const canvas = document.createElement("canvas");
  const W = 750;
  const H = 1380;
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;

  const bgGrad = ctx.createLinearGradient(0, 0, 0, H);
  if (isLight) {
    bgGrad.addColorStop(0, "#F8FAFC");
    bgGrad.addColorStop(0.5, "#FFFFFF");
    bgGrad.addColorStop(1, "#F1F5F9");
  } else {
    bgGrad.addColorStop(0, "#0e1017");
    bgGrad.addColorStop(0.5, "#131620");
    bgGrad.addColorStop(1, "#0a0b10");
  }
  ctx.fillStyle = bgGrad;
  ctx.fillRect(0, 0, W, H);

  drawRoundedRectWeb(
    ctx,
    16,
    16,
    W - 32,
    H - 32,
    24,
    undefined,
    isLight ? "rgba(217, 119, 6, 0.3)" : "rgba(255, 215, 0, 0.25)"
  );

  drawRoundedRectWeb(
    ctx,
    40,
    42,
    190,
    42,
    21,
    isLight ? "rgba(245, 158, 11, 0.14)" : "rgba(255, 215, 0, 0.15)",
    isLight ? "rgba(217, 119, 6, 0.4)" : "rgba(255, 215, 0, 0.4)"
  );
  ctx.font = "bold 20px sans-serif";
  ctx.fillStyle = isLight ? "#b45309" : "#ffd700";
  ctx.fillText("👑 跑团专属战报", 52, 71);

  ctx.font = "900 36px sans-serif";
  ctx.fillStyle = isLight ? "#0f172a" : "#ffffff";
  ctx.fillText(rep.club_name || "跑团战报", 40, 130);

  ctx.font = "bold 22px sans-serif";
  ctx.fillStyle = isLight ? "#b45309" : "#ffd700";
  const trailTagCanvas =
    rep.trail_mode === "exclude_pace"
      ? " · 仅去除越野配速"
      : rep.trail_mode === "exclude_all"
      ? " · 去除越野跑量与配速"
      : "";
  ctx.fillText(`${rep.period_label} · ${rep.date_range_str}${trailTagCanvas}`, 40, 172);

  ctx.beginPath();
  ctx.moveTo(40, 195);
  ctx.lineTo(W - 40, 195);
  ctx.strokeStyle = isLight ? "rgba(15, 23, 42, 0.1)" : "rgba(255, 255, 255, 0.12)";
  ctx.stroke();

  drawRoundedRectWeb(
    ctx,
    40,
    215,
    W - 80,
    155,
    20,
    isLight ? "#FFF7ED" : "#181b26",
    isLight ? "rgba(252, 76, 2, 0.3)" : "rgba(252, 76, 2, 0.35)"
  );
  ctx.font = "bold 22px sans-serif";
  ctx.fillStyle = isLight ? "#475569" : "#9ca3af";
  ctx.fillText("全团累计奔跑总里程", 64, 252);

  ctx.font = "900 72px monospace";
  ctx.fillStyle = "#fc4c02";
  ctx.fillText(`${rep.total_distance_km}`, 64, 326);

  const kmWidth = ctx.measureText(`${rep.total_distance_km}`).width;
  ctx.font = "900 30px sans-serif";
  ctx.fillStyle = isLight ? "#b45309" : "#f59e0b";
  ctx.fillText("KM", 64 + kmWidth + 12, 324);

  ctx.font = "20px sans-serif";
  ctx.fillStyle = isLight ? "#64748b" : "#71717a";
  ctx.fillText("汇聚全员热血汗水 · 每一步都在突破极限", 64, 355);

  const gW = (W - 80 - 18) / 2;
  const gH = 92;
  const metricBg = isLight ? "#FFFFFF" : "#151722";
  const metricStroke = isLight ? "rgba(15, 23, 42, 0.1)" : "rgba(255, 255, 255, 0.08)";
  const metricLabel = isLight ? "#64748b" : "#9ca3af";
  const metricVal = isLight ? "#0f172a" : "#ffffff";

  drawRoundedRectWeb(ctx, 40, 390, gW, gH, 16, metricBg, metricStroke);
  ctx.font = "20px sans-serif";
  ctx.fillStyle = metricLabel;
  ctx.fillText("队员出勤率", 56, 422);
  ctx.font = "bold 30px sans-serif";
  ctx.fillStyle = metricVal;
  ctx.fillText(`${rep.attendance_rate_pct}%`, 56, 462);
  ctx.font = "18px sans-serif";
  ctx.fillStyle = isLight ? "#64748b" : "#6b7280";
  ctx.fillText(`(${rep.active_members_count}/${rep.total_members_count}人)`, 160, 460);

  drawRoundedRectWeb(ctx, 40 + gW + 18, 390, gW, gH, 16, metricBg, metricStroke);
  ctx.font = "20px sans-serif";
  ctx.fillStyle = metricLabel;
  ctx.fillText("全团平均配速", 56 + gW + 18, 422);
  ctx.font = "bold 30px monospace";
  ctx.fillStyle = metricVal;
  ctx.fillText(`${rep.avg_pace_str}`, 56 + gW + 18, 462);

  drawRoundedRectWeb(ctx, 40, 498, gW, gH, 16, metricBg, metricStroke);
  ctx.font = "20px sans-serif";
  ctx.fillStyle = metricLabel;
  ctx.fillText("累计爬升克服", 56, 530);
  ctx.font = "bold 30px sans-serif";
  ctx.fillStyle = metricVal;
  ctx.fillText(`+${rep.total_elevation_gain_m}m`, 56, 570);

  drawRoundedRectWeb(ctx, 40 + gW + 18, 498, gW, gH, 16, metricBg, metricStroke);
  ctx.font = "20px sans-serif";
  ctx.fillStyle = metricLabel;
  ctx.fillText("累计打卡总人次", 56 + gW + 18, 530);
  ctx.font = "bold 30px sans-serif";
  ctx.fillStyle = metricVal;
  ctx.fillText(`${rep.total_activities_count} 次`, 56 + gW + 18, 570);

  drawRoundedRectWeb(
    ctx,
    40,
    606,
    W - 80,
    235,
    20,
    isLight ? "#FFFBEB" : "#151722",
    isLight ? "rgba(217, 119, 6, 0.3)" : "rgba(255, 215, 0, 0.3)"
  );
  ctx.font = "bold 24px sans-serif";
  ctx.fillStyle = isLight ? "#b45309" : "#ffd700";
  ctx.fillText("🏆 荣誉榜单 Top 3", 60, 642);

  const podium = rep.podium || [];
  const medals = ["🥇 冠军", "🥈 亚军", "🥉 季军"];
  const medalBgs = isLight
    ? ["#FFFFFF", "#FFFFFF", "#FFFFFF"]
    : ["rgba(255, 215, 0, 0.12)", "rgba(192, 192, 192, 0.10)", "rgba(205, 127, 50, 0.10)"];
  const medalStrokes = isLight
    ? ["rgba(217, 119, 6, 0.35)", "rgba(100, 116, 139, 0.25)", "rgba(180, 83, 9, 0.28)"]
    : ["rgba(255, 215, 0, 0.35)", "rgba(192, 192, 192, 0.3)", "rgba(205, 127, 50, 0.3)"];

  for (let i = 0; i < 3; i++) {
    const pY = 660 + i * 55;
    if (podium[i]) {
      drawRoundedRectWeb(ctx, 60, pY, W - 120, 48, 12, medalBgs[i], medalStrokes[i]);
      ctx.font = "bold 22px sans-serif";
      ctx.fillStyle = isLight ? "#b45309" : "#ffd700";
      ctx.fillText(medals[i], 76, pY + 32);

      ctx.font = "bold 22px sans-serif";
      ctx.fillStyle = metricVal;
      ctx.fillText(podium[i].display_name || "跑者", 185, pY + 32);

      ctx.font = "900 22px monospace";
      ctx.fillStyle = "#fc4c02";
      ctx.fillText(`${podium[i].distance_km} km`, W - 250, pY + 32);

      ctx.font = "20px monospace";
      ctx.fillStyle = isLight ? "#475569" : "#9ca3af";
      ctx.fillText(podium[i].avg_pace_str || "—", W - 145, pY + 32);
    }
  }

  const hY = 858;
  const hW = (W - 80 - 18) / 2;
  if (rep.hardcore_runner) {
    drawRoundedRectWeb(
      ctx,
      40,
      hY,
      hW,
      82,
      14,
      isLight ? "#F0F9FF" : "#151722",
      isLight ? "rgba(2, 132, 199, 0.25)" : "rgba(56, 189, 248, 0.25)"
    );
    ctx.font = "bold 18px sans-serif";
    ctx.fillStyle = isLight ? "#0369a1" : "#38bdf8";
    ctx.fillText("🌟 毅力先锋", 54, hY + 28);
    ctx.font = "bold 20px sans-serif";
    ctx.fillStyle = metricVal;
    ctx.fillText(`${rep.hardcore_runner.display_name}`, 54, hY + 54);
    ctx.font = "16px sans-serif";
    ctx.fillStyle = isLight ? "#475569" : "#9ca3af";
    ctx.fillText(`打卡 ${rep.hardcore_runner.runs_count} 次 · ${rep.hardcore_runner.distance_km}km`, 54, hY + 74);
  }
  if (rep.longest_run) {
    drawRoundedRectWeb(
      ctx,
      40 + hW + 18,
      hY,
      hW,
      82,
      14,
      isLight ? "#F0F9FF" : "#151722",
      isLight ? "rgba(2, 132, 199, 0.25)" : "rgba(56, 189, 248, 0.25)"
    );
    ctx.font = "bold 18px sans-serif";
    ctx.fillStyle = isLight ? "#0369a1" : "#38bdf8";
    ctx.fillText("🚀 最长突破", 54 + hW + 18, hY + 28);
    ctx.font = "bold 20px sans-serif";
    ctx.fillStyle = metricVal;
    ctx.fillText(`${rep.longest_run.runner_name}`, 54 + hW + 18, hY + 54);
    ctx.font = "16px sans-serif";
    ctx.fillStyle = isLight ? "#475569" : "#9ca3af";
    ctx.fillText(`单次 ${rep.longest_run.distance_km}km · ${rep.longest_run.avg_pace_str}`, 54 + hW + 18, hY + 74);
  }

  const cY = 955;
  drawRoundedRectWeb(
    ctx,
    40,
    cY,
    W - 80,
    225,
    18,
    isLight ? "#FAF5FF" : "#181624",
    isLight ? "rgba(147, 51, 234, 0.28)" : "rgba(191, 90, 242, 0.35)"
  );
  ctx.font = "bold 22px sans-serif";
  ctx.fillStyle = isLight ? "#6d28d9" : "#bf5af2";
  ctx.fillText("💡 Renato Canova 科学耐力团队复盘", 58, cY + 34);

  ctx.font = "italic 17px sans-serif";
  ctx.fillStyle = isLight ? "#1e293b" : "#d1d5db";
  drawWrappedTextWeb(ctx, `“${rep.canova_critique}”`, 58, cY + 68, W - 116, 26, 5);

  const fY = 1200;
  drawRoundedRectWeb(
    ctx,
    40,
    fY,
    W - 80,
    145,
    20,
    isLight ? "#FFFFFF" : "#121520",
    isLight ? "rgba(15, 23, 42, 0.1)" : "rgba(255, 255, 255, 0.1)"
  );

  ctx.font = "bold 18px sans-serif";
  ctx.fillStyle = "#fc4c02";
  ctx.fillText("🏃 万跑跑团助手 · 跑团官方认证战报", 64, fY + 42);

  ctx.font = "900 24px sans-serif";
  ctx.fillStyle = metricVal;
  ctx.fillText("微信扫码打开万跑跑团助手小程序", 64, fY + 78);

  ctx.font = "16px sans-serif";
  ctx.fillStyle = isLight ? "#475569" : "#9ca3af";
  ctx.fillText("万跑跑团助手 · 科学耐力训练与跑团系统 · 官方认证战报", 64, fY + 112);

  const qrSrc = rep.qrcode_base64
    ? `data:image/jpeg;base64,${rep.qrcode_base64}`
    : rep.qrcode_url || "";
  if (qrSrc) {
    await new Promise<void>((resolve) => {
      const qrImg = new Image();
      qrImg.crossOrigin = "anonymous";
      qrImg.onload = () => {
        const qrBoxX = W - 40 - 134;
        const qrBoxY = fY + 14;
        drawRoundedRectWeb(ctx, qrBoxX, qrBoxY, 118, 118, 14, "#ffffff");
        ctx.drawImage(qrImg, qrBoxX + 6, qrBoxY + 6, 106, 106);
        resolve();
      };
      qrImg.onerror = () => resolve();
      qrImg.src = qrSrc;
    });
  } else {
    drawRoundedRectWeb(
      ctx,
      W - 160,
      fY + 48,
      100,
      44,
      12,
      isLight ? "rgba(245, 158, 11, 0.14)" : "rgba(255, 215, 0, 0.15)",
      isLight ? "rgba(217, 119, 6, 0.4)" : "rgba(255, 215, 0, 0.4)"
    );
    ctx.font = "bold 18px sans-serif";
    ctx.fillStyle = isLight ? "#b45309" : "#ffd700";
    ctx.fillText("官方战报", W - 146, fY + 76);
  }

  return canvas;
}

export function filterAndSortCoachStudents(
  rawStudents: any[],
  opts: {
    statusFilter: string;
    groupFilter: string;
    planFilter: "all" | "draft_pending" | "published" | "none" | "alert";
    searchQuery: string;
    sortOrder: "danger_first" | "peak_first";
  }
): any[] {
  let list = [...(rawStudents || [])];
  if (opts.statusFilter !== "all") {
    list = list.filter((s: any) => s.status_level === opts.statusFilter);
  }
  if (opts.groupFilter !== "all") {
    list = list.filter(
      (s: any) =>
        s.plan_info?.template_group_code === opts.groupFilter ||
        s.recommended_group?.group_code === opts.groupFilter
    );
  }
  if (opts.planFilter !== "all") {
    list = list.filter((s: any) => {
      const pState = s.plan_info?.plan_state || "none";
      const wExec = s.plan_info?.week_execution || {};
      if (opts.planFilter === "draft_pending") return pState === "draft_pending" || s.plan_info?.has_draft_plan;
      if (opts.planFilter === "published") return pState === "published" || pState === "self_active" || s.plan_info?.has_active_plan;
      if (opts.planFilter === "none") return pState === "none";
      if (opts.planFilter === "alert") return Boolean(wExec.injury_note) || (wExec.low_hrv_days || 0) > 0 || (wExec.max_rpe || 0) >= 8;
      return true;
    });
  }
  if (opts.searchQuery.trim()) {
    const q = opts.searchQuery.trim().toLowerCase();
    list = list.filter(
      (s: any) =>
        (s.display_name || "").toLowerCase().includes(q) ||
        (s.user_id || "").toLowerCase().includes(q)
    );
  }

  const dangerFirstRanks: Record<string, number> = { danger: 1, tired: 2, optimal: 3, peak: 4, none: 5 };
  const peakFirstRanks: Record<string, number> = { peak: 1, optimal: 2, tired: 3, danger: 4, none: 5 };

  list.sort((a: any, b: any) => {
    if (opts.sortOrder === "danger_first") {
      const aInj = a.plan_info?.week_execution?.injury_note ? 1 : 0;
      const bInj = b.plan_info?.week_execution?.injury_note ? 1 : 0;
      if (aInj !== bInj) return bInj - aInj;
      const aDraft = a.plan_info?.plan_state === "draft_pending" ? 1 : 0;
      const bDraft = b.plan_info?.plan_state === "draft_pending" ? 1 : 0;
      if (aDraft !== bDraft) return bDraft - aDraft;
    }
    const rankMap = opts.sortOrder === "peak_first" ? peakFirstRanks : dangerFirstRanks;
    const rankA = rankMap[a.status_level] ?? 99;
    const rankB = rankMap[b.status_level] ?? 99;
    if (rankA !== rankB) return rankA - rankB;
    const tsbA = typeof a.tsb === "number" ? a.tsb : 0;
    const tsbB = typeof b.tsb === "number" ? b.tsb : 0;
    return opts.sortOrder === "peak_first" ? tsbB - tsbA : tsbA - tsbB;
  });

  return list;
}
