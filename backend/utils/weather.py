"""
Weather context for AI coach — powered by Open-Meteo (free, no API key).

Two main functions:
  1. get_training_weather()  — historical weather during the activity
  2. get_forecast_weather()  — tomorrow's forecast for training advice
"""

import requests
from datetime import datetime, timedelta
from typing import Optional, Tuple

_TIMEOUT = 6  # seconds


# ── Polyline decoding (Google encoded polyline → list of (lat, lng)) ──────────

def _decode_polyline(encoded: str) -> list:
    """Decode a Google encoded polyline string into a list of (lat, lng) tuples."""
    result = []
    index = 0
    lat = 0
    lng = 0
    while index < len(encoded):
        # Decode latitude
        shift = 0
        value = 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            value |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        lat += (~(value >> 1) if (value & 1) else (value >> 1))

        # Decode longitude
        shift = 0
        value = 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            value |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        lng += (~(value >> 1) if (value & 1) else (value >> 1))

        result.append((lat / 1e5, lng / 1e5))
    return result


def _extract_coords(activity: dict) -> Optional[Tuple[float, float]]:
    """Extract (lat, lng) from activity — tries start_latlng first, then polyline."""
    latlng = activity.get("start_latlng")
    if latlng and len(latlng) >= 2 and latlng[0] != 0:
        return (latlng[0], latlng[1])

    polyline = activity.get("summary_polyline", "")
    if polyline:
        try:
            points = _decode_polyline(polyline)
            if points:
                return points[0]  # First point = start location
        except Exception:
            pass
    return None


# ── Historical weather (for training analysis) ───────────────────────────────

def get_training_weather(activity: dict) -> Optional[dict]:
    """
    Fetch weather conditions during the activity from Open-Meteo Archive API.
    Returns dict with temperature, humidity, wind, feels_like, etc.
    Returns None if location or time data is unavailable.
    """
    coords = _extract_coords(activity)
    if not coords:
        return None

    lat, lng = coords

    # Parse activity start time
    start_str = activity.get("start_date_local", "")
    if not start_str:
        return None

    try:
        # Handle various ISO formats
        start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00").split("+")[0])
    except (ValueError, TypeError):
        return None

    activity_date = start_dt.strftime("%Y-%m-%d")
    activity_hour = start_dt.hour

    # Duration in hours (for avg over training window)
    moving_time = activity.get("moving_time", 3600)
    duration_hours = max(1, round(moving_time / 3600))

    try:
        # Use Archive API for past dates, Forecast API for today
        today = datetime.now().strftime("%Y-%m-%d")
        if activity_date < today:
            base_url = "https://archive-api.open-meteo.com/v1/archive"
        else:
            base_url = "https://api.open-meteo.com/v1/forecast"

        resp = requests.get(base_url, params={
            "latitude": round(lat, 4),
            "longitude": round(lng, 4),
            "start_date": activity_date,
            "end_date": activity_date,
            "hourly": "temperature_2m,relative_humidity_2m,apparent_temperature,"
                      "wind_speed_10m,precipitation,weather_code",
            "timezone": "auto",
        }, timeout=_TIMEOUT)

        if resp.status_code != 200:
            print(f"[weather] Archive API error: {resp.status_code}")
            return None

        data = resp.json()
        hourly = data.get("hourly", {})

        temps = hourly.get("temperature_2m", [])
        humidity = hourly.get("relative_humidity_2m", [])
        apparent = hourly.get("apparent_temperature", [])
        wind = hourly.get("wind_speed_10m", [])
        precip = hourly.get("precipitation", [])
        codes = hourly.get("weather_code", [])

        if not temps or activity_hour >= len(temps):
            return None

        # Average over the training window (start_hour to start_hour + duration)
        end_hour = min(activity_hour + duration_hours, len(temps))
        window = slice(activity_hour, end_hour)

        avg_temp = round(sum(temps[window]) / max(1, end_hour - activity_hour), 1)
        avg_humidity = round(sum(humidity[window]) / max(1, end_hour - activity_hour))
        avg_apparent = round(sum(apparent[window]) / max(1, end_hour - activity_hour), 1)
        avg_wind = round(sum(wind[window]) / max(1, end_hour - activity_hour), 1)
        total_precip = round(sum(precip[window]), 1)
        weather_code = codes[activity_hour] if activity_hour < len(codes) else 0

        return {
            "temperature": avg_temp,
            "feels_like": avg_apparent,
            "humidity": avg_humidity,
            "wind_speed": avg_wind,
            "precipitation": total_precip,
            "weather_code": weather_code,
            "weather_desc": _weather_code_to_text(weather_code),
            "location": {"lat": round(lat, 3), "lng": round(lng, 3)},
            "training_hour": activity_hour,
        }

    except requests.RequestException as e:
        print(f"[weather] Request failed: {e}")
        return None
    except Exception as e:
        print(f"[weather] Unexpected error: {e}")
        return None


# ── Forecast weather (for tomorrow's training advice) ─────────────────────────

def get_forecast_weather(activity: dict) -> Optional[dict]:
    """
    Fetch tomorrow's weather forecast for the training location.
    Returns morning (6-9am) and full-day summary for training planning.
    """
    coords = _extract_coords(activity)
    if not coords:
        return None

    lat, lng = coords

    try:
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

        resp = requests.get("https://api.open-meteo.com/v1/forecast", params={
            "latitude": round(lat, 4),
            "longitude": round(lng, 4),
            "start_date": tomorrow,
            "end_date": tomorrow,
            "hourly": "temperature_2m,relative_humidity_2m,apparent_temperature,"
                      "wind_speed_10m,precipitation_probability,precipitation,"
                      "weather_code",
            "timezone": "auto",
        }, timeout=_TIMEOUT)

        if resp.status_code != 200:
            return None

        data = resp.json()
        hourly = data.get("hourly", {})

        temps = hourly.get("temperature_2m", [])
        humidity = hourly.get("relative_humidity_2m", [])
        apparent = hourly.get("apparent_temperature", [])
        wind = hourly.get("wind_speed_10m", [])
        precip_prob = hourly.get("precipitation_probability", [])
        precip = hourly.get("precipitation", [])
        codes = hourly.get("weather_code", [])

        if len(temps) < 18:
            return None

        # Morning window (5-9am) — typical training time
        morning = slice(5, 9)
        # Evening window (17-20) — alternative training time
        evening = slice(17, 20)

        morning_temp = round(sum(temps[morning]) / 4, 1)
        morning_humidity = round(sum(humidity[morning]) / 4)
        morning_apparent = round(sum(apparent[morning]) / 4, 1)
        morning_wind = round(sum(wind[morning]) / 4, 1)
        morning_precip_prob = round(max(precip_prob[morning]))

        evening_temp = round(sum(temps[evening]) / 3, 1)
        evening_humidity = round(sum(humidity[evening]) / 3)

        day_high = round(max(temps), 1)
        day_low = round(min(temps), 1)
        total_precip = round(sum(precip), 1)
        main_code = codes[8] if len(codes) > 8 else 0  # 8am representative

        return {
            "date": tomorrow,
            "day_high": day_high,
            "day_low": day_low,
            "morning": {
                "temperature": morning_temp,
                "feels_like": morning_apparent,
                "humidity": morning_humidity,
                "wind_speed": morning_wind,
                "precip_probability": morning_precip_prob,
            },
            "evening": {
                "temperature": evening_temp,
                "humidity": evening_humidity,
            },
            "total_precipitation": total_precip,
            "weather_desc": _weather_code_to_text(main_code),
        }

    except Exception as e:
        print(f"[weather] Forecast failed: {e}")
        return None


# ── Weather code → human-readable text ────────────────────────────────────────

def _weather_code_to_text(code: int) -> str:
    """WMO Weather Interpretation Code → Chinese description."""
    mapping = {
        0: "晴天",
        1: "大部晴朗", 2: "多云", 3: "阴天",
        45: "雾", 48: "雾凇",
        51: "小毛毛雨", 53: "毛毛雨", 55: "大毛毛雨",
        56: "冻毛毛雨", 57: "冻雨",
        61: "小雨", 63: "中雨", 65: "大雨",
        66: "冻雨", 67: "大冻雨",
        71: "小雪", 73: "中雪", 75: "大雪",
        77: "雪粒",
        80: "小阵雨", 81: "阵雨", 82: "暴雨",
        85: "小阵雪", 86: "大阵雪",
        95: "雷暴", 96: "雷暴+小冰雹", 99: "雷暴+大冰雹",
    }
    return mapping.get(code, f"未知({code})")


# ── Format for AI prompt ──────────────────────────────────────────────────────

def format_training_weather_for_prompt(weather: dict) -> str:
    """Format historical weather data for the AI coach prompt."""
    temp = weather["temperature"]
    feels = weather["feels_like"]
    hum = weather["humidity"]
    wind = weather["wind_speed"]
    precip = weather["precipitation"]
    desc = weather["weather_desc"]

    lines = [
        f"【训练时天气】{desc}",
        f"- 气温：{temp}°C（体感：{feels}°C）",
        f"- 湿度：{hum}%",
        f"- 风速：{wind} km/h",
    ]
    if precip > 0:
        lines.append(f"- 降水：{precip} mm")

    # Add heat/cold stress notes
    if temp >= 32 or feels >= 35:
        lines.append("- ⚠️ 高温预警：极端高温条件，配速下降和心率升高属正常生理反应")
    elif temp >= 28 or feels >= 30:
        lines.append("- 注意：高温天气会导致配速下降2-5%、心率升高5-10bpm属正常现象")
    elif temp <= 5:
        lines.append("- 注意：低温环境需延长热身时间，肌肉受伤风险增加")

    if hum >= 80:
        lines.append("- 注意：高湿度会影响散热，实际体感温度更高，心率可能偏高")

    return "\n".join(lines) + "\n"


def format_forecast_for_prompt(forecast: dict) -> str:
    """Format tomorrow's forecast for the training suggestion."""
    m = forecast["morning"]
    e = forecast["evening"]

    lines = [
        f"【明日天气预报】{forecast['weather_desc']}",
        f"- 气温：{forecast['day_low']}°C ~ {forecast['day_high']}°C",
        f"- 晨跑时段（5-9时）：{m['temperature']}°C（体感{m['feels_like']}°C），湿度{m['humidity']}%，风速{m['wind_speed']}km/h",
    ]

    if m["precip_probability"] >= 50:
        lines.append(f"- ⚠️ 降雨概率 {m['precip_probability']}%，建议备好防雨装备或调整训练时段")
    elif m["precip_probability"] >= 30:
        lines.append(f"- 降雨概率 {m['precip_probability']}%，留意天气变化")

    if forecast["total_precipitation"] > 5:
        lines.append(f"- 全天预计降水 {forecast['total_precipitation']}mm，路面湿滑注意安全")

    # Heat advisory for training planning
    if forecast["day_high"] >= 32:
        lines.append("- ⚠️ 高温日：建议选择清晨或傍晚训练，携带充足水分")
    elif forecast["day_high"] >= 28:
        lines.append("- 天气较热：建议清晨跑步，适当降低配速目标，注意补水")

    if m["temperature"] <= 5:
        lines.append("- 晨跑偏冷：注意保暖，延长热身时间")

    if e["temperature"] > m["temperature"] + 5:
        lines.append(f"- 傍晚时段（17-20时）：{e['temperature']}°C，湿度{e['humidity']}%，也适合训练")

    return "\n".join(lines) + "\n"
