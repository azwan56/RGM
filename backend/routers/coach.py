from fastapi import APIRouter
from pydantic import BaseModel
from firebase_config import db
import os
import json
import asyncio

router = APIRouter()

_api_key = os.getenv("GEMINI_API_KEY")
_gemini_base_url = os.getenv("GEMINI_BASE_URL")  # Optional CDN proxy, e.g. https://your-proxy.example.com
_coach_client = None  # Lazy init

def _get_client():
    """Lazily creates the Gemini client on first call.
    If GEMINI_BASE_URL is set, routes requests through that proxy endpoint.
    """
    global _coach_client
    if _coach_client is None and _api_key:
        from google import genai
        from google.genai import types
        if _gemini_base_url:
            _coach_client = genai.Client(
                api_key=_api_key,
                http_options=types.HttpOptions(base_url=_gemini_base_url)
            )
        else:
            _coach_client = genai.Client(api_key=_api_key)
    return _coach_client

class CoachRequest(BaseModel):
    uid: str

# ── Firestore helpers (run in thread pool) ────────────────────────────────────

def _fetch_leaderboard(uid: str):
    doc = db.collection("leaderboard").document(uid).get()
    return doc.to_dict() if doc.exists else None

def _fetch_goal(uid: str):
    doc = db.collection("users").document(uid).collection("goals").document("current").get()
    return doc.to_dict() if doc.exists else None

def _fetch_recent_activities(uid: str, n: int = 5):
    docs = (
        db.collection("users").document(uid)
        .collection("activities")
        .order_by("start_date_local", direction="DESCENDING")
        .limit(n)
        .stream()
    )
    return [d.to_dict() for d in docs]

def _build_runs_str(acts: list) -> str:
    if not acts:
        return "No recent activities."
    lines = [
        f"{a.get('start_date_local','')[:10]} "
        f"{a.get('distance_km',0)}km "
        f"@{a.get('avg_pace','?')}/km "
        f"HR:{a.get('avg_heart_rate',0)}bpm "
        f"Elev:{a.get('total_elevation_gain',0)}m"
        for a in acts
    ]
    return " | ".join(lines)

_FALLBACK = {
    "status": "Keep Going",
    "summary": "Great consistency! Focus on form and build gradually.",
    "actionable_tips": [
        "Keep 80% of runs at an easy, conversational pace.",
        "Hydrate well and prioritize sleep for recovery.",
        "Increase weekly mileage by no more than 10%.",
    ]
}

# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("/analyze")
async def generate_coach_feedback(req: CoachRequest):
    """
    Returns structured AI coaching feedback.
    Parallel Firestore reads + new google-genai SDK.
    """
    loop = asyncio.get_event_loop()
    stats, goal_data, activities = await asyncio.gather(
        loop.run_in_executor(None, _fetch_leaderboard, req.uid),
        loop.run_in_executor(None, _fetch_goal, req.uid),
        loop.run_in_executor(None, _fetch_recent_activities, req.uid),
    )

    if not stats:
        return {"feedback": {
            "status": "No Data",
            "summary": "Sync your Strava data to get personalised coaching!",
            "actionable_tips": []
        }}

    goal_str = "No specific target set."
    if goal_data:
        goal_str = (
            f"Target {goal_data.get('target_distance',0)} km/"
            f"{goal_data.get('period','monthly')}, "
            f"pace goal: {goal_data.get('target_pace','N/A')}."
        )

    runs_str = _build_runs_str(activities)

    prompt = (
        "You are a professional running coach. Reply with ONLY a JSON object, no markdown.\n"
        f"Athlete overview ({stats.get('period','monthly')}): "
        f"{stats.get('total_distance_km',0)} km total, avg pace {stats.get('avg_pace','?')}/km, "
        f"avg HR {stats.get('avg_heart_rate',0)} bpm, goal {stats.get('goal_completion_percentage',0)}% done. "
        f"Goal: {goal_str}\n"
        f"Recent runs: {runs_str}\n\n"
        "Return JSON with exactly these keys:\n"
        '{"status":"<one of: Excellent|Good Base|Pacing Issue|Needs Rest|Keep Going>",'
        '"summary":"<2 concise sentences>",'
        '"actionable_tips":["tip1","tip2","tip3"]}'
    )

    if not _api_key:
        return {"feedback": {
            "status": "Offline",
            "summary": "AI Coach is offline – Gemini API key not configured.",
            "actionable_tips": ["Keep easy runs easy.", "Consistency beats intensity.", "Rest is part of training."]
        }}

    try:
        from google.genai import types
        client = _get_client()
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.4,
            max_output_tokens=512,
        )
        response = await loop.run_in_executor(
            None,
            lambda: client.models.generate_content(
                model="gemini-1.5-flash",
                contents=prompt,
                config=config,
            )
        )
        text = response.text.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        return {"feedback": json.loads(text)}

    except json.JSONDecodeError as e:
        print(f"Coach JSON parse error: {e}")
        return {"feedback": _FALLBACK}
    except Exception as e:
        print(f"Coach generation failed: {e}")
        return {"feedback": {
            **_FALLBACK,
            "summary": f"Distance so far: {stats.get('total_distance_km',0)} km. Keep it up!"
        }}


# ── Training Plan Generator ──────────────────────────────────────────────────

class TrainingPlanRequest(BaseModel):
    uid: str


def _fetch_profile(uid: str):
    doc = db.collection("users").document(uid).get()
    return doc.to_dict() if doc.exists else {}


def _fetch_recent_14d(uid: str):
    from datetime import date, timedelta
    cutoff = (date.today() - timedelta(days=14)).isoformat()
    docs = (db.collection("users").document(uid)
              .collection("activities")
              .where("start_date_local", ">=", cutoff)
              .order_by("start_date_local", direction="DESCENDING")
              .limit(30)
              .stream())
    return [d.to_dict() for d in docs]


@router.post("/training-plan")
async def generate_training_plan(req: TrainingPlanRequest):
    """
    Generates a personalized 7-day training plan using Gemini AI.
    Uses VDOT, profile, goals, recent activities, and fitness state.
    Saves to Firestore for history.
    """
    loop = asyncio.get_event_loop()

    profile, goal_data, activities, stats = await asyncio.gather(
        loop.run_in_executor(None, _fetch_profile, req.uid),
        loop.run_in_executor(None, _fetch_goal, req.uid),
        loop.run_in_executor(None, _fetch_recent_14d, req.uid),
        loop.run_in_executor(None, _fetch_leaderboard, req.uid),
    )

    if not profile:
        return {"error": "User profile not found. Please fill in your profile first."}

    # Build context
    vdot = profile.get("vdot") or None
    age = profile.get("age", 30)
    gender = profile.get("gender", "other")
    years_running = profile.get("years_running", 0) or 0
    training_goal = profile.get("training_goal", "fitness")
    fm_pb_sec = profile.get("marathon_pb_sec", 0) or 0
    half_pb_sec = profile.get("half_pb_sec", 0) or 0
    max_hr = profile.get("max_heart_rate", 190)
    rest_hr = profile.get("resting_heart_rate", 60)

    # Activity summary
    total_km_14d = sum(a.get("distance_km", 0) for a in activities)
    run_count_14d = len(activities)
    recent_summary = []
    for a in activities[:7]:
        recent_summary.append(
            f"{a.get('start_date_local','')[:10]} "
            f"{a.get('distance_km',0):.1f}km "
            f"@{a.get('avg_pace','?')}/km "
            f"HR:{a.get('avg_heart_rate',0)}"
        )

    goal_str = "No specific target."
    if goal_data:
        goal_str = (
            f"Target {goal_data.get('target_distance',0)} km/"
            f"{goal_data.get('period','monthly')}, "
            f"pace goal: {goal_data.get('target_pace','N/A')}."
        )

    def _fmt_pb(sec):
        if not sec: return "N/A"
        h, r = divmod(sec, 3600)
        m = r // 60
        return f"{h}:{m:02d}"

    prompt = (
        "You are a professional running coach creating a 7-day training plan. "
        "Reply with ONLY a valid JSON object, no markdown fences.\n\n"
        f"ATHLETE PROFILE:\n"
        f"- Age: {age}, Gender: {gender}, Running years: {years_running}\n"
        f"- VDOT: {vdot or 'Unknown'}\n"
        f"- Marathon PB: {_fmt_pb(fm_pb_sec)}, Half PB: {_fmt_pb(half_pb_sec)}\n"
        f"- Training goal: {training_goal}\n"
        f"- Max HR: {max_hr}, Rest HR: {rest_hr}\n"
        f"- Goal: {goal_str}\n\n"
        f"RECENT 14 DAYS: {run_count_14d} runs, {total_km_14d:.1f}km total\n"
        f"Last runs: {' | '.join(recent_summary) or 'No recent data'}\n\n"
        f"Current monthly stats: {stats.get('total_distance_km',0)}km, "
        f"pace {stats.get('avg_pace','?')}/km, "
        f"HR {stats.get('avg_heart_rate',0)}bpm\n\n"
        "Generate a 7-day plan starting from tomorrow. "
        "Use CHINESE for all text fields. "
        "Return JSON with exactly this structure:\n"
        '{\n'
        '  "plan_summary": "<1-2 sentence overview in Chinese>",\n'
        '  "weekly_km": <total km number>,\n'
        '  "days": [\n'
        '    {\n'
        '      "day": 1,\n'
        '      "type": "<Easy|Tempo|Interval|Long Run|Recovery|Rest|Cross Training>",\n'
        '      "title": "<Chinese title, e.g. 轻松跑>",\n'
        '      "distance_km": <number or 0 for rest>,\n'
        '      "pace_target": "<e.g. 5:30-6:00 or null for rest>",\n'
        '      "hr_zone": "<e.g. Zone 2 or null>",\n'
        '      "duration_min": <estimated minutes>,\n'
        '      "description": "<Chinese description of workout>",\n'
        '      "intensity": <1-5 scale>\n'
        '    }\n'
        '  ]\n'
        '}\n\n'
        "RULES:\n"
        "- Include 1-2 rest days\n"
        "- Follow 80/20 rule (80% easy, 20% hard)\n"
        "- Long run should be on weekend\n"
        "- Match intensity to athlete's current fitness level\n"
        "- If VDOT is unknown, estimate from recent pace data"
    )

    if not _api_key:
        return {"error": "AI Coach offline — Gemini API key not configured."}

    try:
        from google.genai import types
        client = _get_client()
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.5,
            max_output_tokens=2048,
        )
        response = await loop.run_in_executor(
            None,
            lambda: client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=config,
            )
        )
        text = response.text.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        plan = json.loads(text)

        # Save to Firestore
        from datetime import date
        today = date.today().isoformat()
        try:
            plan_ref = (db.collection("users").document(req.uid)
                          .collection("training_plans").document(today))
            plan_ref.set({
                **plan,
                "generated_at": today,
                "vdot_used": vdot,
                "training_goal": training_goal,
            }, merge=True)
        except Exception as e:
            print(f"[training-plan] Failed to save: {e}")

        return {"plan": plan, "generated_at": today}

    except json.JSONDecodeError as e:
        print(f"Training plan JSON parse error: {e}")
        return {"error": "AI returned invalid format. Please try again."}
    except Exception as e:
        print(f"Training plan generation failed: {e}")
        return {"error": f"Generation failed: {str(e)}"}

