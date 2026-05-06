import requests
import os
from dotenv import load_dotenv

load_dotenv()
client_id = os.getenv("STRAVA_CLIENT_ID")
client_secret = os.getenv("STRAVA_CLIENT_SECRET")

print(f"Using Client ID: {client_id}")
print(f"Using Client Secret: {client_secret}")

token_resp = requests.post("https://www.strava.com/oauth/token", data={
    "client_id": client_id,
    "client_secret": client_secret,
    "grant_type": "refresh_token",
    "refresh_token": "garbage_token",
})
print("With garbage token:")
print(f"Response status: {token_resp.status_code}")
print(f"Response body: {token_resp.text}")

token_resp2 = requests.post("https://www.strava.com/oauth/token", data={
    "client_id": "111",
    "client_secret": "222",
    "grant_type": "refresh_token",
    "refresh_token": "9d103f4105f03a0dd0805283fbe502ce2f99e65f",
})
print("\nWith bad secret:")
print(f"Response status: {token_resp2.status_code}")
print(f"Response body: {token_resp2.text}")
