"""
Test script: Send Discord notification for the most recent activity.
Run from: backend/
Usage: venv/bin/python test_discord_notify.py [uid]
"""
import sys
import os
from dotenv import load_dotenv
load_dotenv()

# Bootstrap Firebase
import firebase_config  # noqa: F401
from firebase_config import db

# ── Pick user ──────────────────────────────────────────────────────────────────
uid = sys.argv[1] if len(sys.argv) > 1 else None

if not uid:
    print("Scanning Firestore for users with discord_webhook_url...")
    users = db.collection("users").stream()
    found = []
    for u in users:
        d = u.to_dict()
        if d.get("discord_webhook_url"):
            found.append((u.id, d))
            print(f"  ✓ {u.id} — {d.get('display_name') or d.get('strava_name')} — {d.get('discord_webhook_url')[:40]}...")
    if not found:
        print("No users with discord_webhook_url found. Please fill in Profile first.")
        sys.exit(1)
    uid, user_data = found[0]
    print(f"\nUsing user: {uid} ({user_data.get('display_name') or user_data.get('strava_name')})\n")
else:
    doc = db.collection("users").document(uid).get()
    if not doc.exists:
        print(f"User {uid} not found in Firestore.")
        sys.exit(1)
    user_data = doc.to_dict()

# ── Get most recent activity ────────────────────────────────────────────────────
print("Fetching most recent activity...")
acts = (
    db.collection("users").document(uid)
    .collection("activities")
    .order_by("start_date_local", direction="DESCENDING")
    .limit(5)
    .stream()
)
activities = [(a.id, a.to_dict()) for a in acts]

if not activities:
    print("No activities found for this user. Please sync Strava first.")
    sys.exit(1)

print(f"Found {len(activities)} recent activities. Latest ones:")
for i, (aid, a) in enumerate(activities):
    print(f"  [{i}] {a.get('start_date_local','')[:10]}  {a.get('distance_km')}km  @{a.get('avg_pace')}/km  — {a.get('name','')}")

# Pick today's run first, then yesterday's, then most recent
from datetime import date, timedelta
today     = date.today().isoformat()
yesterday = (date.today() - timedelta(days=1)).isoformat()

target_id, target_act = None, None
for aid, a in activities:
    if a.get("start_date_local", "")[:10] == today:
        target_id, target_act = aid, a
        print(f"\n✓ Found today's run: {target_act.get('name')}")
        break

if not target_act:
    for aid, a in activities:
        if a.get("start_date_local", "")[:10] == yesterday:
            target_id, target_act = aid, a
            print(f"\n✓ Found yesterday's run: {target_act.get('name')}")
            break

if not target_act:
    target_id, target_act = activities[0]
    print(f"\nUsing most recent: {target_act.get('name')} ({target_act.get('start_date_local','')[:10]})")

# ── Send notification ──────────────────────────────────────────────────────────
print(f"\nSending Discord notification for: {target_act.get('name')} ({target_act.get('start_date_local','')[:10]})")
print(f"  Distance: {target_act.get('distance_km')}km  Pace: {target_act.get('avg_pace')}/km")
print(f"  Generating AI coach tip (this may take a few seconds)...\n")

from utils.discord import send_activity_discord_notification
ok = send_activity_discord_notification(target_act, user_data, uid=uid)

if ok:
    print("\n🎉 Discord notification sent successfully! Check your Discord channel.")
else:
    print("\n❌ Failed to send. Check output above for details.")
    print("   Make sure discord_webhook_url is saved in your profile on the website.")
