import sys
import os
import asyncio
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from firebase_config import db
from routers.coach import log_journal_entry, JournalLogRequest

async def main():
    users = db.collection('users').where('display_name', '>=', 'Vivian').where('display_name', '<=', 'Vivian\uf8ff').stream()
    uid = None
    for u in users:
        d = u.to_dict()
        print("Found user:", d.get('display_name'), "UID:", u.id)
        if 'Vivian' in d.get('display_name', ''):
            uid = u.id

    if not uid:
        users2 = db.collection('users').stream()
        for u in users2:
            d = u.to_dict()
            if d.get('display_name') and 'Vivian' in d.get('display_name', ''):
                uid = u.id
                print("Found via full scan:", d.get('display_name'), "UID:", u.id)
                break

    if uid:
        print(f"Triggering log_journal_entry for {uid}...")
        req = JournalLogRequest(uid=uid, activity_id="", force=True)
        res = await log_journal_entry(req)
        print("Result:", res)
    else:
        print("Vivian not found")

if __name__ == "__main__":
    asyncio.run(main())
