import os
import requests
from dotenv import load_dotenv

load_dotenv()
client_id = os.getenv("STRAVA_CLIENT_ID")
client_secret = os.getenv("STRAVA_CLIENT_SECRET")

print(f"Using Client ID: {client_id}")
print(f"Using Client Secret: {client_secret}")

# Find a user to test from firebase
from firebase_config import db

users = db.collection("users").limit(1).stream()
for user in users:
    data = user.to_dict()
    uid = user.id
    refresh_token = data.get("strava_refresh_token")
    if refresh_token:
        print(f"Found user {uid} with refresh_token {refresh_token}")
        token_resp = requests.post("https://www.strava.com/oauth/token", data={
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        })
        print(f"Response status: {token_resp.status_code}")
        print(f"Response body: {token_resp.text}")
        break
else:
    print("No user found with a strava_refresh_token")
