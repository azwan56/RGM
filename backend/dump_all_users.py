import os
import sys

# Add the current dir to sys.path so we can import firebase_config
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from firebase_config import db
import json

users = db.collection('users').stream()

results = []
for u in users:
    d = u.to_dict()
    results.append({
        'uid': u.id,
        'email': d.get('email'),
        'display_name': d.get('display_name'),
        'strava_name': d.get('strava_name'),
        'wecom_user_id': d.get('wecom_user_id'),
        'strava_connected': d.get('strava_connected', False)
    })

print(json.dumps(results, indent=2, ensure_ascii=False))
