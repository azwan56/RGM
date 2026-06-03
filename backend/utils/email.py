"""
Email Utility — sends transactional emails via Gmail SMTP (Google Workspace).

Usage:
    from utils.email import send_welcome_email
    send_welcome_email("user@example.com", "跑者小明")

Requires env vars:
    GMAIL_ADDRESS      — your Workspace Gmail address (e.g. admin@rgm.run)
    GMAIL_APP_PASSWORD — 16-char App Password (NOT your login password)

To generate an App Password:
    1. Go to https://myaccount.google.com/apppasswords
    2. Select "Mail" → "Other (custom name)" → enter "RGM Backend"
    3. Copy the 16-character password into GMAIL_APP_PASSWORD
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime


SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587


def _get_welcome_html(user_name: str) -> str:
    """Generates a beautiful HTML welcome email in Chinese."""
    year = datetime.now().year
    return f"""\
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>欢迎加入 RGM 跑团管理平台</title>
</head>
<body style="margin:0;padding:0;background:#0a0a0a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Hiragino Sans GB','Microsoft YaHei',sans-serif;">

<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#0a0a0a;padding:40px 16px;">
<tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#141414;border:1px solid rgba(255,255,255,0.08);border-radius:16px;overflow:hidden;">

  <!-- Header gradient bar -->
  <tr>
    <td style="height:4px;background:linear-gradient(90deg,#FC4C02,#f97316,#FC4C02);"></td>
  </tr>

  <!-- Logo & Title -->
  <tr>
    <td style="padding:40px 36px 20px;text-align:center;">
      <div style="display:inline-block;width:56px;height:56px;line-height:56px;border-radius:16px;background:rgba(252,76,2,0.15);border:1px solid rgba(252,76,2,0.3);font-size:28px;text-align:center;">
        🏃
      </div>
      <h1 style="margin:20px 0 8px;font-size:24px;font-weight:700;color:#ffffff;">
        欢迎加入 <span style="color:#FC4C02;">RGM</span>
      </h1>
      <p style="margin:0;font-size:15px;color:#a1a1aa;">
        Hi {user_name}，你的跑步数据管理之旅开始了！
      </p>
    </td>
  </tr>

  <!-- Divider -->
  <tr>
    <td style="padding:0 36px;">
      <div style="height:1px;background:rgba(255,255,255,0.06);"></div>
    </td>
  </tr>

  <!-- Feature cards -->
  <tr>
    <td style="padding:28px 36px 8px;">
      <p style="margin:0 0 20px;font-size:15px;color:#d4d4d8;line-height:1.7;">
        RGM 是一个面向跑团的一站式管理平台，以下是你可以使用的核心功能：
      </p>

      <!-- Feature 1 -->
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:16px;">
      <tr>
        <td style="width:44px;vertical-align:top;padding-top:2px;">
          <div style="width:36px;height:36px;line-height:36px;text-align:center;border-radius:10px;background:rgba(252,76,2,0.12);font-size:18px;">⚡</div>
        </td>
        <td style="padding-left:12px;">
          <p style="margin:0 0 4px;font-size:14px;font-weight:600;color:#ffffff;">Strava 自动同步</p>
          <p style="margin:0;font-size:13px;color:#a1a1aa;line-height:1.6;">连接 Strava 后，你的每次跑步数据将自动同步到平台，无需手动操作。</p>
        </td>
      </tr>
      </table>

      <!-- Feature 2 -->
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:16px;">
      <tr>
        <td style="width:44px;vertical-align:top;padding-top:2px;">
          <div style="width:36px;height:36px;line-height:36px;text-align:center;border-radius:10px;background:rgba(59,130,246,0.12);font-size:18px;">🏆</div>
        </td>
        <td style="padding-left:12px;">
          <p style="margin:0 0 4px;font-size:14px;font-weight:600;color:#ffffff;">团队排行榜</p>
          <p style="margin:0;font-size:13px;color:#a1a1aa;line-height:1.6;">设定每周或每月跑量目标，实时跟踪完成率，和跑友一起竞跑进步。</p>
        </td>
      </tr>
      </table>

      <!-- Feature 3 -->
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:16px;">
      <tr>
        <td style="width:44px;vertical-align:top;padding-top:2px;">
          <div style="width:36px;height:36px;line-height:36px;text-align:center;border-radius:10px;background:rgba(34,197,94,0.12);font-size:18px;">🤖</div>
        </td>
        <td style="padding-left:12px;">
          <p style="margin:0 0 4px;font-size:14px;font-weight:600;color:#ffffff;">AI 教练分析</p>
          <p style="margin:0;font-size:13px;color:#a1a1aa;line-height:1.6;">基于你的配速、心率和体能状态，AI 教练为每次训练生成深度分析和个性化建议。</p>
        </td>
      </tr>
      </table>

      <!-- Feature 4 -->
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:16px;">
      <tr>
        <td style="width:44px;vertical-align:top;padding-top:2px;">
          <div style="width:36px;height:36px;line-height:36px;text-align:center;border-radius:10px;background:rgba(168,85,247,0.12);font-size:18px;">📊</div>
        </td>
        <td style="padding-left:12px;">
          <p style="margin:0 0 4px;font-size:14px;font-weight:600;color:#ffffff;">训练日志 & 周报</p>
          <p style="margin:0;font-size:13px;color:#a1a1aa;line-height:1.6;">自动记录每次训练的 AI 点评，每周生成训练总结报告，追踪长期进步趋势。</p>
        </td>
      </tr>
      </table>

      <!-- Feature 5 -->
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:4px;">
      <tr>
        <td style="width:44px;vertical-align:top;padding-top:2px;">
          <div style="width:36px;height:36px;line-height:36px;text-align:center;border-radius:10px;background:rgba(234,179,8,0.12);font-size:18px;">📈</div>
        </td>
        <td style="padding-left:12px;">
          <p style="margin:0 0 4px;font-size:14px;font-weight:600;color:#ffffff;">VDOT & 体能追踪</p>
          <p style="margin:0;font-size:13px;color:#a1a1aa;line-height:1.6;">实时追踪 VDOT 跑力指数、CTL 体能和 TSB 状态趋势，科学量化你的进步。</p>
        </td>
      </tr>
      </table>
    </td>
  </tr>

  <!-- Divider -->
  <tr>
    <td style="padding:20px 36px 0;">
      <div style="height:1px;background:rgba(255,255,255,0.06);"></div>
    </td>
  </tr>

  <!-- CTA: Get started -->
  <tr>
    <td style="padding:24px 36px;text-align:center;">
      <p style="margin:0 0 20px;font-size:15px;color:#d4d4d8;line-height:1.6;">
        第一步：连接你的 Strava 账号，开始自动同步跑步数据 🎉
      </p>
      <a href="https://rgm.run/dashboard" target="_blank" style="display:inline-block;padding:14px 32px;background:linear-gradient(135deg,#FC4C02,#f97316);color:#ffffff;font-size:15px;font-weight:600;text-decoration:none;border-radius:12px;">
        进入 Dashboard →
      </a>
    </td>
  </tr>

  <!-- Divider -->
  <tr>
    <td style="padding:0 36px;">
      <div style="height:1px;background:rgba(255,255,255,0.06);"></div>
    </td>
  </tr>

  <!-- Feedback section -->
  <tr>
    <td style="padding:24px 36px;text-align:center;">
      <p style="margin:0 0 6px;font-size:14px;color:#a1a1aa;line-height:1.6;">
        💡 如果你有任何功能建议或改进意见，欢迎直接回复此邮件！
      </p>
      <p style="margin:0;font-size:13px;color:#71717a;">
        我们非常重视每一位用户的反馈，你的意见将帮助我们做得更好。
      </p>
    </td>
  </tr>

  <!-- Footer -->
  <tr>
    <td style="padding:20px 36px 28px;text-align:center;border-top:1px solid rgba(255,255,255,0.04);">
      <p style="margin:0;font-size:12px;color:#52525b;">
        © {year} RGM 跑团管理平台 · Powered by Strava
      </p>
    </td>
  </tr>

</table>
</td></tr>
</table>

</body>
</html>"""


def _send_via_gmail(to_email: str, subject: str, plain_text: str, html_content: str) -> bool:
    """Internal helper to send email via Gmail SMTP."""
    gmail_address = os.getenv("GMAIL_ADDRESS", "").strip()
    gmail_app_password = os.getenv("GMAIL_APP_PASSWORD", "").strip()

    if not gmail_address or not gmail_app_password:
        print("[email] GMAIL_ADDRESS / GMAIL_APP_PASSWORD not configured — skipping email")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"RGM 跑团助手 <{gmail_address}>"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg["Reply-To"] = gmail_address

        msg.attach(MIMEText(plain_text, "plain", "utf-8"))
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(gmail_address, gmail_app_password)
            server.sendmail(gmail_address, [to_email], msg.as_string())

        return True
    except Exception as e:
        print(f"[email] Send error to {to_email}: {e}")
        return False


def send_welcome_email(to_email: str, user_name: "str | None" = None) -> bool:
    """
    Sends a styled welcome email to a newly registered user via Gmail SMTP.
    Returns True on success, False on failure (never raises).
    """
    display_name = user_name or to_email.split("@")[0]
    subject = f"🏃 欢迎加入 RGM 跑团管理平台，{display_name}！"
    
    plain_text = (
        f"Hi {display_name}，欢迎加入 RGM 跑团管理平台！\n\n"
        f"核心功能：\n"
        f"• Strava 自动同步 — 连接一次，跑步数据自动同步\n"
        f"• 团队排行榜 — 设定目标，和跑友一起竞跑\n"
        f"• AI 教练分析 — 配速、心率、体能智能反馈\n"
        f"• 训练日志 & 周报 — 自动记录 AI 点评，每周生成训练报告\n"
        f"• VDOT & 体能追踪 — 科学量化你的进步\n\n"
        f"第一步：连接你的 Strava 账号 → https://rgm.run/dashboard\n\n"
        f"如果你有任何功能建议或改进意见，欢迎直接回复此邮件！\n"
    )
    
    html_content = _get_welcome_html(display_name)
    ok = _send_via_gmail(to_email, subject, plain_text, html_content)
    if ok:
        print(f"[email] Welcome email sent to {to_email} via Gmail SMTP")
    return ok


def _get_report_html(period_name: str, display_name: str, report: dict) -> str:
    """Generates a beautiful HTML report email in Chinese."""
    year = datetime.now().year
    
    # Extract data from the report dict
    summary = report.get("summary", "")
    week_stats = report.get("week_stats", {})
    km = week_stats.get("total_km", 0)
    runs = week_stats.get("total_runs", 0)
    elev = week_stats.get("total_elevation", 0)
    score = report.get("weekly_score", "-")
    
    # Generate lists for HTML
    achievements = report.get("achievements", [])
    concerns = report.get("concerns", [])
    achievements_html = "".join([f"<li style='margin-bottom:8px;'>{item}</li>" for item in achievements])
    concerns_html = "".join([f"<li style='margin-bottom:8px;'>{item}</li>" for item in concerns])
    
    # Next plan
    plan = report.get("next_week_plan", {})
    focus = plan.get("focus", "")
    target_km = plan.get("target_km", "")
    
    # Analysis
    analysis = report.get("week_stats_analysis", {}).get("analysis", "")
    encouragement = report.get("encouragement", "")

    return f"""\
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>你的 RGM {period_name}报告出炉啦！</title>
</head>
<body style="margin:0;padding:0;background:#0a0a0a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Hiragino Sans GB','Microsoft YaHei',sans-serif;">

<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#0a0a0a;padding:40px 16px;">
<tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;background:#141414;border:1px solid rgba(255,255,255,0.08);border-radius:16px;overflow:hidden;">

  <!-- Header gradient bar -->
  <tr>
    <td style="height:4px;background:linear-gradient(90deg,#3b82f6,#2563eb,#1d4ed8);"></td>
  </tr>

  <!-- Title -->
  <tr>
    <td style="padding:40px 36px 20px;">
      <h1 style="margin:0 0 8px;font-size:24px;font-weight:700;color:#ffffff;">
        你的 RGM {period_name}报告
      </h1>
      <p style="margin:0;font-size:15px;color:#a1a1aa;">
        Hi {display_name}，这是你的{period_name}训练总结与 AI 教练分析。
      </p>
    </td>
  </tr>

  <!-- Stats Cards -->
  <tr>
    <td style="padding:10px 36px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <!-- Total Distance -->
          <td width="31%" style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.05);border-radius:12px;padding:16px;text-align:center;">
            <p style="margin:0 0 4px;font-size:12px;color:#a1a1aa;text-transform:uppercase;letter-spacing:0.5px;">跑量</p>
            <p style="margin:0;font-size:24px;font-weight:700;color:#ffffff;">{km}<span style="font-size:14px;color:#71717a;font-weight:500;">km</span></p>
          </td>
          <td width="3%"></td>
          <!-- Runs -->
          <td width="31%" style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.05);border-radius:12px;padding:16px;text-align:center;">
            <p style="margin:0 0 4px;font-size:12px;color:#a1a1aa;text-transform:uppercase;letter-spacing:0.5px;">次数</p>
            <p style="margin:0;font-size:24px;font-weight:700;color:#ffffff;">{runs}<span style="font-size:14px;color:#71717a;font-weight:500;">次</span></p>
          </td>
          <td width="3%"></td>
          <!-- Score -->
          <td width="32%" style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.05);border-radius:12px;padding:16px;text-align:center;">
            <p style="margin:0 0 4px;font-size:12px;color:#a1a1aa;text-transform:uppercase;letter-spacing:0.5px;">AI 评分</p>
            <p style="margin:0;font-size:24px;font-weight:700;color:#3b82f6;">{score}<span style="font-size:14px;color:#71717a;font-weight:500;">/10</span></p>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- Overview -->
  <tr>
    <td style="padding:24px 36px 12px;">
      <h2 style="margin:0 0 12px;font-size:16px;font-weight:600;color:#ffffff;border-left:3px solid #3b82f6;padding-left:10px;">总体评价</h2>
      <p style="margin:0;font-size:14px;color:#d4d4d8;line-height:1.6;">
        {summary}
      </p>
    </td>
  </tr>
  
  <!-- Analysis -->
  {"<tr><td style='padding:12px 36px;'><h2 style='margin:0 0 12px;font-size:16px;font-weight:600;color:#ffffff;border-left:3px solid #a855f7;padding-left:10px;'>深度分析</h2><p style='margin:0;font-size:14px;color:#d4d4d8;line-height:1.6;'>" + analysis + "</p></td></tr>" if analysis else ""}

  <!-- Highlights & Concerns -->
  <tr>
    <td style="padding:12px 36px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <!-- Highlights -->
          <td width="48%" style="vertical-align:top;background:rgba(34,197,94,0.05);border:1px solid rgba(34,197,94,0.1);border-radius:12px;padding:20px;">
            <h3 style="margin:0 0 12px;font-size:14px;font-weight:600;color:#4ade80;">✨ 本期亮点</h3>
            <ul style="margin:0;padding-left:20px;font-size:13px;color:#d4d4d8;line-height:1.6;">
              {achievements_html or "<li style='color:#71717a;list-style:none;margin-left:-20px;'>暂无明显亮点</li>"}
            </ul>
          </td>
          <td width="4%"></td>
          <!-- Concerns -->
          <td width="48%" style="vertical-align:top;background:rgba(239,68,68,0.05);border:1px solid rgba(239,68,68,0.1);border-radius:12px;padding:20px;">
            <h3 style="margin:0 0 12px;font-size:14px;font-weight:600;color:#f87171;">⚠️ 需注意</h3>
            <ul style="margin:0;padding-left:20px;font-size:13px;color:#d4d4d8;line-height:1.6;">
              {concerns_html or "<li style='color:#71717a;list-style:none;margin-left:-20px;'>暂无明显问题</li>"}
            </ul>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- Next Plan -->
  <tr>
    <td style="padding:12px 36px 24px;">
      <div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.05);border-radius:12px;padding:20px;">
        <h2 style="margin:0 0 12px;font-size:15px;font-weight:600;color:#ffffff;display:flex;align-items:center;">
          📅 下期计划建议
        </h2>
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td width="50%" style="padding-bottom:8px;">
              <span style="font-size:12px;color:#a1a1aa;">训练重点：</span><br>
              <span style="font-size:14px;color:#e4e4e7;">{focus or "—"}</span>
            </td>
            <td width="50%" style="padding-bottom:8px;">
              <span style="font-size:12px;color:#a1a1aa;">目标跑量：</span><br>
              <span style="font-size:14px;color:#e4e4e7;">{target_km or "—"}</span>
            </td>
          </tr>
        </table>
      </div>
    </td>
  </tr>

  <!-- Encouragement -->
  {"<tr><td style='padding:0 36px 24px;text-align:center;'><p style='margin:0;font-size:15px;font-style:italic;color:#38bdf8;'>“" + encouragement + "”</p></td></tr>" if encouragement else ""}

  <!-- CTA -->
  <tr>
    <td style="padding:0 36px 32px;text-align:center;">
      <a href="https://rgm.run/journal" target="_blank" style="display:inline-block;padding:12px 28px;background:#3b82f6;color:#ffffff;font-size:14px;font-weight:600;text-decoration:none;border-radius:8px;">
        查看完整训练日志
      </a>
    </td>
  </tr>

  <!-- Share Card Section -->
  <tr>
    <td style="padding:0 20px 32px;text-align:center;">
      <p style="margin:0 0 12px;font-size:12px;color:#a1a1aa;text-transform:uppercase;letter-spacing:1px;">
        ⬇️ 截图下方卡片与跑友分享 ⬇️
      </p>
      
      <!-- The Card -->
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:400px;margin:0 auto;background:linear-gradient(145deg,#1f2937,#111827);border:1px solid rgba(255,255,255,0.1);border-radius:20px;overflow:hidden;box-shadow:0 10px 30px rgba(0,0,0,0.5);">
        <tr>
          <td style="padding:32px 24px 24px;">
            <!-- Header -->
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
              <tr>
                <td align="left">
                  <h3 style="margin:0;font-size:16px;font-weight:600;color:#93c5fd;">RGM 跑团</h3>
                  <p style="margin:4px 0 0;font-size:13px;color:#9ca3af;">{period_name}度训练总结</p>
                </td>
                <td align="right" style="vertical-align:top;">
                  <div style="background:rgba(59,130,246,0.1);color:#60a5fa;padding:4px 10px;border-radius:12px;font-size:12px;font-weight:600;">
                    {year}
                  </div>
                </td>
              </tr>
            </table>
            
            <!-- Runner Name -->
            <h2 style="margin:0 0 20px;font-size:28px;font-weight:700;color:#ffffff;text-align:left;">
              {display_name}
            </h2>

            <!-- Core Stats -->
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:rgba(0,0,0,0.2);border-radius:16px;padding:20px;margin-bottom:24px;">
              <tr>
                <td width="33%" style="text-align:center;border-right:1px solid rgba(255,255,255,0.05);">
                  <p style="margin:0 0 4px;font-size:11px;color:#9ca3af;">跑量</p>
                  <p style="margin:0;font-size:22px;font-weight:700;color:#ffffff;">{km}<span style="font-size:12px;color:#6b7280;font-weight:normal;">km</span></p>
                </td>
                <td width="33%" style="text-align:center;border-right:1px solid rgba(255,255,255,0.05);">
                  <p style="margin:0 0 4px;font-size:11px;color:#9ca3af;">次数</p>
                  <p style="margin:0;font-size:22px;font-weight:700;color:#ffffff;">{runs}</p>
                </td>
                <td width="34%" style="text-align:center;">
                  <p style="margin:0 0 4px;font-size:11px;color:#9ca3af;">AI评分</p>
                  <p style="margin:0;font-size:22px;font-weight:700;color:#fcd34d;">{score}</p>
                </td>
              </tr>
            </table>

            <!-- Footer mark -->
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td align="center">
                  <p style="margin:0;font-size:13px;font-weight:600;color:#3b82f6;letter-spacing:0.5px;">
                    RGM.vanpower.live
                  </p>
                  <p style="margin:4px 0 0;font-size:11px;color:#6b7280;">
                    智能跑团管理 · AI 教练分析
                  </p>
                </td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- Footer -->
  <tr>
    <td style="padding:20px 36px 28px;text-align:center;border-top:1px solid rgba(255,255,255,0.04);">
      <p style="margin:0;font-size:12px;color:#52525b;">
        © {year} RGM 跑团管理平台
      </p>
    </td>
  </tr>

</table>
</td></tr>
</table>

</body>
</html>"""


def send_report_email(to_email: str, user_name: "str | None", period_name: str, report: dict) -> bool:
    """
    Sends a styled weekly/monthly report email.
    period_name should be "周" or "月".
    """
    display_name = user_name or to_email.split("@")[0]
    subject = f"📊 你的 RGM {period_name}度训练报告"
    
    # Generate plain-text fallback
    km = report.get("week_stats", {}).get("total_km", 0)
    runs = report.get("week_stats", {}).get("total_runs", 0)
    score = report.get("weekly_score", "-")
    summary = report.get("summary", "")
    encouragement = report.get("encouragement", "")
    
    plain_text = (
        f"Hi {display_name}，你的{period_name}度训练报告出炉了！\n\n"
        f"🏃 数据概览：\n"
        f"跑量：{km}km | 次数：{runs}次 | AI评分：{score}/10\n\n"
        f"📝 总体评价：\n{summary}\n\n"
        f"💡 {encouragement}\n\n"
        f"详细分析和建议请在 RGM Dashboard 的「训练日志」中查看：\n"
        f"https://rgm.run/journal\n"
    )
    
    html_content = _get_report_html(period_name, display_name, report)
    ok = _send_via_gmail(to_email, subject, plain_text, html_content)
    if ok:
        print(f"[email] {period_name} report email sent to {to_email}")
    return ok
