import firebase_admin
from firebase_admin import credentials, firestore
import os
import json


def init_firebase():
    if not firebase_admin._apps:
        # Priority 1: JSON string from environment variable (for Docker/Render/Vercel)
        json_str = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
        if json_str:
            cred_dict = json.loads(json_str)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
        else:
            # Priority 2: File path (local development)
            cert_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "serviceAccountKey.json")
            if os.path.exists(cert_path):
                cred = credentials.Certificate(cert_path)
                firebase_admin.initialize_app(cred)
            else:
                # Priority 3: Default credentials (GCP environments)
                firebase_admin.initialize_app()
    return firestore.client(database_id="gentrain")

db = init_firebase()
