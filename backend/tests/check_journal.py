import sys
import os
sys.path.append("/Users/azwan/Projects/RGM/backend")
from firebase_config import db

uid = "X0B0663OudQ5pXqf1a0P2JcOqS73" # Need to find the actual UID, wait
# I can just get the uid from the last run or query all users
users = list(db.collection("users").limit(5).stream())
for u in users:
    print(f"User: {u.id}")
    journals = list(u.reference.collection("training_logs").stream())
    for j in journals:
        print(f"  Journal: {j.id}")
        entries = list(j.reference.collection("entries").stream())
        for e in entries:
            d = e.to_dict()
            if d.get("entry_type") == "weekly_summary":
                print(f"    Weekly Summary: {e.id} -> date: {d.get('date')}, week_number: {d.get('week_number')}")
