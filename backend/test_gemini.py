import os
import asyncio
from google import genai
from google.genai import types

async def test():
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        print("No API key")
        return
    client = genai.Client(api_key=key)
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        temperature=0.5,
        max_output_tokens=2048,
    )
    prompt = "Generate a simple 7-day training plan in JSON with 'plan_summary', 'weekly_km', and 'days' list."
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=config,
        )
        print("SUCCESS:")
        print(response.text)
    except Exception as e:
        print("ERROR:", e)

asyncio.run(test())
