"""Small OpenWeather current-conditions client using store-catalog coordinates."""
import json
import os
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

from src.simulator.generators import CITIES

BASE_URL = "https://api.openweathermap.org/data/2.5/weather"

def fetch_weather_events(api_key=None):
    api_key = api_key if api_key is not None else os.getenv("OPENWEATHER_API_KEY", "")
    if not api_key.strip():
        return []
    events = []
    for city, lat, lon, _ in CITIES:
        url = BASE_URL + "?" + urlencode({"lat":lat,"lon":lon,"appid":api_key,"units":"metric"})
        try:
            request = Request(url, headers={"User-Agent":"grocery-supply-intelligence/1.0"})
            with urlopen(request, timeout=12) as response:
                data = json.load(response)
            weather = (data.get("weather") or [{}])[0]
            observed = datetime.fromtimestamp(data.get("dt", datetime.now(timezone.utc).timestamp()), tz=timezone.utc)
            payload = {"city":city,"country":data.get("sys",{}).get("country","DE"),"latitude":lat,"longitude":lon,
                       "temperature_c":data.get("main",{}).get("temp"),"feels_like_c":data.get("main",{}).get("feels_like"),
                       "humidity_pct":data.get("main",{}).get("humidity"),"pressure_hpa":data.get("main",{}).get("pressure"),
                       "wind_speed_mps":data.get("wind",{}).get("speed"),"rain_1h_mm":data.get("rain",{}).get("1h",0),
                       "weather_main":weather.get("main","Unknown"),"description":weather.get("description",""),
                       "icon":weather.get("icon",""),"source":"openweathermap","source_city":data.get("name",city)}
            events.append({"event_id":str(uuid4()),"event_type":"weather_observation","event_time":observed.isoformat(),"source":"openweathermap","payload":payload})
        except Exception as exc:
            # Do not print or expose request URLs: they contain the API key.
            raise RuntimeError(f"OpenWeather request failed for {city} ({type(exc).__name__})") from None
    return events
