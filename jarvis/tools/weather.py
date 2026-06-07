"""Weather via wttr.in — no API key required."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request

from jarvis.core.logger import get_logger

log = get_logger(__name__)

DEFINITION = {
    "name": "weather",
    "description": (
        "Get current weather or forecast. No API key needed. "
        "Use for: 'what's the weather', 'will it rain', 'temperature in London', "
        "'weather forecast for this week'."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": "City or location. Leave empty for current location.",
            },
            "days": {
                "type": "integer",
                "description": "Forecast days ahead (1=today, 3=3-day). Default 1.",
            },
        },
        "required": [],
    },
}


def execute(location: str = "", days: int = 1) -> str:
    try:
        loc = urllib.parse.quote(location.strip()) if location.strip() else "auto"
        url = f"https://wttr.in/{loc}?format=j1"
        req = urllib.request.Request(url, headers={"User-Agent": "JARVIS/1.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())

        cur = data["current_condition"][0]
        area = data.get("nearest_area", [{}])[0]
        city = area.get("areaName", [{}])[0].get("value", location or "your location")

        temp_c   = cur["temp_C"]
        feels    = cur["FeelsLikeC"]
        desc     = cur["weatherDesc"][0]["value"]
        humidity = cur["humidity"]
        wind_kph = cur["windspeedKmph"]
        uv       = cur.get("uvIndex", "N/A")

        lines = [
            f"{city}: {desc}, {temp_c}°C (feels like {feels}°C). "
            f"Humidity {humidity}%, wind {wind_kph} km/h, UV index {uv}."
        ]

        if days > 1:
            for w in data.get("weather", [])[:days]:
                date  = w["date"]
                hi    = w["maxtempC"]
                lo    = w["mintempC"]
                dhour = w.get("hourly", [{}])[4]
                desc2 = dhour.get("weatherDesc", [{}])[0].get("value", "")
                lines.append(f"{date}: {desc2}, high {hi}°C / low {lo}°C.")

        return "\n".join(lines)

    except Exception as e:
        log.warning(f"weather failed: {e}")
        return f"Weather unavailable: {e}"
