import sys
import os
import asyncio
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from firebase_config import db
from routers.coach import log_journal_entry, JournalLogRequest
from utils.discord import send_activity_wecom_notification

async def main():
    uid = "AIDZCDyWeHUtS3FxpoYm3PTT7dj2"
    user_doc = db.collection("users").document(uid).get()
    user_data = user_doc.to_dict()

    act_doc = db.collection("users").document(uid).collection("activities").document("18966551895").get().to_dict()
    if not act_doc:
        print("Activity not found!")
        return

    req = JournalLogRequest(uid=uid, activity_id="18966551895")
    res = await log_journal_entry(req)
    
    entry = res.get("entry", {})
    coach_tip = entry.get("ai_comment", "")
    
    print("Sending WeCom notification...")
    success = send_activity_wecom_notification(act_doc, user_data, uid=uid, coach_tip=coach_tip, journal_entry=entry)
    print("Result:", success)

if __name__ == "__main__":
    asyncio.run(main())
