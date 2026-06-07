"""
Quick test: send a sample weekly report email to verify the email template + share card.
Run: python tests/test_report_email.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from utils.email import send_report_email

# Sample report data (mimics what generate_auto_weekly_report produces)
sample_report = {
    "summary": "本周训练质量很高！3次跑步覆盖了轻松跑、节奏跑和长距离跑三种训练类型，配速和心率控制合理，整体状态积极向上。",
    "weekly_score": 8,
    "week_stats": {
        "total_km": 32.5,
        "total_runs": 3,
        "total_elevation": 185,
        "avg_pace": "5:42",
        "avg_heart_rate": 152,
    },
    "week_stats_analysis": {
        "analysis": "跑量稳定在30km+的水平，配速控制合理。心率区间显示大部分训练在有氧区间完成，符合80/20法则。长距离跑的15km表现尤其出色，配速均匀无明显掉速。"
    },
    "achievements": [
        "长距离跑完成15km，配速稳定无掉速",
        "节奏跑配速达到5:15/km，创近4周最佳",
        "训练一致性保持良好，无缺勤",
    ],
    "concerns": [
        "周三轻松跑心率偏高(165bpm)，可能与前一天睡眠不足有关",
        "总爬升偏低，建议增加山坡训练",
    ],
    "next_week_plan": {
        "focus": "保持跑量，增加一次山坡间歇训练",
        "target_km": "33-36km",
    },
    "encouragement": "每一步都在让你变得更强，坚持就是最好的天赋！🔥",
}

to_email = os.getenv("GMAIL_ADDRESS", "azwan56@vanpower.live")
print(f"Sending test weekly report email to: {to_email}")

ok = send_report_email(
    to_email=to_email,
    user_name="Azwan",
    period_name="周",
    report=sample_report,
)

if ok:
    print("✅ Test email sent successfully! Check your inbox.")
else:
    print("❌ Email send failed. Check GMAIL_ADDRESS / GMAIL_APP_PASSWORD env vars.")
