import sys
sys.path.append("/Users/azwan/Projects/RGM/backend")
from firebase_config import db

uid = "qC34flxZ7fRC5ADywofM9x9fj3g2"
journal_id = "utmb-备赛日志"
entries = db.collection("users").document(uid).collection("training_logs").document(journal_id).collection("entries").order_by("date").stream()
for e in entries:
    d = e.to_dict()
    print(f"{e.id} -> date: {d.get('date')}, type: {d.get('entry_type')}")
