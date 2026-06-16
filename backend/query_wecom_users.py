import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import json
import os

# Ensure creds
if not firebase_admin._apps:
    try:
        cred = credentials.Certificate('serviceAccountKey.json')
        firebase_admin.initialize_app(cred)
    except Exception as e:
        print("Could not init with serviceAccountKey.json, trying default:", e)
        firebase_admin.initialize_app()

db = firestore.client()
users = db.collection('users').where('wecom_user_id', '!=', '').stream()

results = []
for u in users:
    d = u.to_dict()
    # Also include users that actually have wecom_user_id (where not-equal sometimes includes missing? No, firestore doesn't)
    results.append({
        'uid': u.id,
        'email': d.get('email'),
        'display_name': d.get('display_name'),
        'wecom_user_id': d.get('wecom_user_id')
    })

print(json.dumps(results, indent=2, ensure_ascii=False))
