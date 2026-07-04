"""Segment architecture for Briefly.

Each segment represents a discrete module in the daily brief run.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from typing import Any

from briefly.config import Config, get_user_dir
from briefly.llm.base import LanguageModelProvider
from briefly.models import Item

logger = logging.getLogger(__name__)


WEEKDAYS_EN = {
    0: "Monday",
    1: "Tuesday",
    2: "Wednesday",
    3: "Thursday",
    4: "Friday",
    5: "Saturday",
    6: "Sunday",
}

WEEKDAYS_DE = {
    0: "Montag",
    1: "Dienstag",
    2: "Mittwoch",
    3: "Donnerstag",
    4: "Freitag",
    5: "Samstag",
    6: "Sonntag",
}

MONTHS_EN = {
    1: "January",
    2: "February",
    3: "March",
    4: "April",
    5: "May",
    6: "June",
    7: "July",
    8: "August",
    9: "September",
    10: "October",
    11: "November",
    12: "December",
}

MONTHS_DE = {
    1: "Januar",
    2: "Februar",
    3: "März",
    4: "April",
    5: "Mai",
    6: "Juni",
    7: "Juli",
    8: "August",
    9: "September",
    10: "Oktober",
    11: "November",
    12: "Dezember",
}

WEATHER_CODES_EN = {
    0: "clear sky",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "foggy",
    48: "depositing rime fog",
    51: "light drizzle",
    53: "moderate drizzle",
    55: "dense drizzle",
    61: "slight rain",
    63: "moderate rain",
    65: "heavy rain",
    71: "slight snowfall",
    73: "moderate snowfall",
    75: "heavy snowfall",
    80: "slight rain showers",
    81: "moderate rain showers",
    82: "violent rain showers",
    95: "thunderstorm",
    96: "thunderstorm with slight hail",
    99: "thunderstorm with heavy hail",
}

WEATHER_CODES_DE = {
    0: "klarer Himmel",
    1: "überwiegend klar",
    2: "teilweise bewölkt",
    3: "bedeckt",
    45: "neblig",
    48: "Raureifnebel",
    51: "leichter Nieselregen",
    53: "mäßiger Nieselregen",
    55: "dichter Nieselregen",
    61: "leichter Regen",
    63: "mäßiger Regen",
    65: "starker Regen",
    71: "leichter Schneefall",
    73: "mäßiger Schneefall",
    75: "starker Schneefall",
    80: "leichte Regenschauer",
    81: "mäßige Regenschauer",
    82: "heftige Regenschauer",
    95: "Gewitter",
    96: "Gewitter mit leichtem Hagel",
    99: "Gewitter mit schwerem Hagel",
}


def geocode_location(location: str) -> tuple[float, float] | None:
    """Geocodes a location string using Open-Meteo geocoding API with caching."""
    cache_path = get_user_dir() / "weather_cache.json"
    cache = {}
    if cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    geocoding_cache = cache.setdefault("geocoding", {})
    if location in geocoding_cache:
        cached = geocoding_cache[location]
        return cached["latitude"], cached["longitude"]

    # Not cached, fetch
    import httpx
    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {"name": location, "count": 1, "language": "de"}
    try:
        response = httpx.get(url, params=params, timeout=5.0)
        if response.status_code == 200:
            data = response.json()
            results = data.get("results")
            if results:
                lat = results[0]["latitude"]
                lon = results[0]["longitude"]

                geocoding_cache[location] = {"latitude": lat, "longitude": lon}
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(json.dumps(cache), encoding="utf-8")
                return lat, lon
    except Exception as e:
        logger.warning("Geocoding failed for location %s: %s", location, e)
    return None


def fetch_weather(lat: float, lon: float) -> dict[str, Any] | None:
    """Fetches weather forecast using Open-Meteo API with caching."""
    cache_path = get_user_dir() / "weather_cache.json"
    cache = {}
    if cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    weather_cache = cache.setdefault("weather", {})
    cache_key = f"{lat:.4f},{lon:.4f}"

    if cache_key in weather_cache:
        cached = weather_cache[cache_key]
        try:
            cached_time = datetime.fromisoformat(cached["timestamp"])
            if datetime.now() - cached_time < timedelta(hours=1):
                return cached["data"]
        except Exception:
            pass

    # Query API
    import httpx
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code",
        "timezone": "auto",
    }
    try:
        response = httpx.get(url, params=params, timeout=5.0)
        if response.status_code == 200:
            data = response.json()
            weather_cache[cache_key] = {
                "timestamp": datetime.now().isoformat(),
                "data": data,
            }
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(cache), encoding="utf-8")
            return data
    except Exception as e:
        logger.warning("Weather API fetch failed for %s: %s", cache_key, e)
    return None


class BaseSegment:
    """Base class for all segment modules."""

    def __init__(self, segment_id: str, enabled: bool = True) -> None:
        self.id = segment_id
        self.enabled = enabled

    def collect(self, config: Config) -> Any:
        """Sammelt Daten für dieses Segment."""
        return None

    def script(
        self,
        config: Config,
        data: Any,
        llm_provider: LanguageModelProvider,
        language: str,
        episode_date: date | None = None,
    ) -> str:
        """Erzeugt das Skript (Sprechtext) für dieses Segment."""
        return ""


class GreetingSegment(BaseSegment):
    """Greeting segment for the daily episode."""

    def script(
        self,
        config: Config,
        data: Any,
        llm_provider: LanguageModelProvider,
        language: str,
        episode_date: date | None = None,
    ) -> str:
        d = episode_date or date.today()
        user_name = getattr(config, "user_name", "Anselm")

        weekday_idx = d.weekday()
        month_idx = d.month

        if language == "de":
            weekday = WEEKDAYS_DE.get(weekday_idx, "")
            month = MONTHS_DE.get(month_idx, "")
            return f"Guten Morgen, {user_name}. Es ist {weekday}, der {d.day}. {month}."
        else:
            weekday = WEEKDAYS_EN.get(weekday_idx, "")
            month = MONTHS_EN.get(month_idx, "")

            day = d.day
            if 11 <= day <= 13:
                suffix = "th"
            else:
                suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")

            return f"Good morning, {user_name}. It's {weekday}, {month} {day}{suffix}."


class WeatherSegment(BaseSegment):
    """Weather segment using Open-Meteo."""

    def collect(self, config: Config) -> dict[str, Any] | None:
        lat = config.weather.latitude
        lon = config.weather.longitude

        if lat is None or lon is None:
            if not config.weather.location:
                logger.warning("Weather location not configured.")
                return None
            coords = geocode_location(config.weather.location)
            if not coords:
                logger.warning("Could not geocode location: %s", config.weather.location)
                return None
            lat, lon = coords

        return fetch_weather(lat, lon)

    def script(
        self,
        config: Config,
        data: Any,
        llm_provider: LanguageModelProvider,
        language: str,
        episode_date: date | None = None,
    ) -> str:
        if not data:
            return ""

        current = data.get("current", {})
        daily = data.get("daily", {})

        temp = round(current.get("temperature_2m", 0))
        code = current.get("weather_code", 0)
        wind = round(current.get("wind_speed_10m", 0))

        # Max/min values for today
        max_temp = round(daily.get("temperature_2m_max", [0])[0])
        min_temp = round(daily.get("temperature_2m_min", [0])[0])
        rain_prob = round(daily.get("precipitation_probability_max", [0])[0])

        location = config.weather.location or "deinem Standort"

        if language == "de":
            condition = WEATHER_CODES_DE.get(code, "wechselhafte Bedingungen")

            if wind < 10:
                wind_desc = "schwachem Wind"
            elif wind < 25:
                wind_desc = "mäßigem Wind"
            else:
                wind_desc = "starkem Wind"

            return (
                f"Das Wetter in {location}: Aktuell sind es {temp} Grad und es ist {condition}. "
                f"Heute werden Höchstwerte von {max_temp} Grad und Tiefstwerte von {min_temp} Grad erwartet. "
                f"Die Regenwahrscheinlichkeit liegt bei {rain_prob} Prozent bei {wind_desc}."
            )
        else:
            condition = WEATHER_CODES_EN.get(code, "changing conditions")

            if wind < 10:
                wind_desc = "light winds"
            elif wind < 25:
                wind_desc = "moderate winds"
            else:
                wind_desc = "strong winds"

            return (
                f"The weather in {location}: Currently, it's {temp} degrees and {condition}. "
                f"Today's forecast shows a high of {max_temp} degrees and a low of {min_temp} degrees. "
                f"There is a {rain_prob}% chance of rain with {wind_desc}."
            )


class IntroSegment(BaseSegment):
    """Intro/Begrüßung des täglichen Briefings."""

    def script(
        self,
        config: Config,
        data: Any,
        llm_provider: LanguageModelProvider,
        language: str,
        episode_date: date | None = None,
    ) -> str:
        prompt = (
            f"Schreibe ein kurzes, freundliches Intro für das persönliche tägliche Audio-Briefing 'Briefly' auf {language}.\n"
            "Begrüße den Hörer und stimme ihn kurz auf den Tag ein. Schreibe ausschließlich den Sprechtext ohne jeglichen Begleittext."
        )
        return llm_provider.generate_segment_text(prompt)


class NewsSegment(BaseSegment):
    """Nachrichten-Segment aus konfigurierten RSS-Feeds (topic == 'news')."""

    def collect(self, config: Config) -> list[Item]:
        from briefly.curation import select_items
        from briefly.sources.rss import RssSource

        source = RssSource(config.sources.rss.feeds)
        items = source.fetch()
        selected = select_items(items, config)
        return [item for item in selected if item.topic == "news"]

    def script(
        self,
        config: Config,
        data: list[Item],
        llm_provider: LanguageModelProvider,
        language: str,
        episode_date: date | None = None,
    ) -> str:
        if not data:
            return ""
        prompt = _build_segment_prompt("news", data, language, config.target_minutes)
        return llm_provider.generate_segment_text(prompt)


class TopicsSegment(BaseSegment):
    """Themen/Inbox-Segment für sonstige RSS-Feeds und persönliche Notizen."""

    def collect(self, config: Config) -> list[Item]:
        from briefly.curation import select_items
        from briefly.sources.inbox import InboxSource
        from briefly.sources.rss import RssSource

        items = []
        try:
            items.extend(InboxSource(config.sources.inbox.path).fetch())
        except Exception as e:
            logger.warning("InboxSource im Topics-Segment fehlgeschlagen: %s", e)

        try:
            items.extend(RssSource(config.sources.rss.feeds).fetch())
        except Exception as e:
            logger.warning("RssSource im Topics-Segment fehlgeschlagen: %s", e)

        selected = select_items(items, config)
        return [item for item in selected if item.topic != "news"]

    def script(
        self,
        config: Config,
        data: list[Item],
        llm_provider: LanguageModelProvider,
        language: str,
        episode_date: date | None = None,
    ) -> str:
        if not data:
            return ""
        prompt = _build_segment_prompt("topics", data, language, config.target_minutes)
        return llm_provider.generate_segment_text(prompt)


class OutroSegment(BaseSegment):
    """Abschluss und Verabschiedung."""

    def script(
        self,
        config: Config,
        data: Any,
        llm_provider: LanguageModelProvider,
        language: str,
        episode_date: date | None = None,
    ) -> str:
        prompt = (
            f"Schreibe ein kurzes, freundliches Outro für das persönliche tägliche Audio-Briefing 'Briefly' auf {language}.\n"
            "Verabschiede den Hörer und wünsche ihm einen schönen Tag. Schreibe ausschließlich den Sprechtext ohne jeglichen Begleittext."
        )
        return llm_provider.generate_segment_text(prompt)


def _build_segment_prompt(
    segment_id: str, items: list[Item], language: str, target_minutes: int
) -> str:
    lines = [
        f"Du schreibst den Sprechtext für das Segment '{segment_id}' von 'Briefly', ein persönliches tägliches Audio-Briefing.",
        f"Schreibe die gesamte Ausgabe konsequent auf {language}, auch wenn das Quellmaterial gemischtsprachig ist.",
        f"Dieses Segment hat eine Ziel-Sprechzeit im Verhältnis zur Gesamtlänge von ca. {target_minutes} Minuten.",
        "Schreibe ausschließlich den fertigen Sprechtext für dieses Segment, ohne jegliche Einleitung, ohne Begleittext, und ohne Überschriften.",
        "",
    ]
    if items:
        lines.append(f"### Quellmaterial für das Segment '{segment_id}':")
        for item in items[:15]:
            lines.append(f"- {item.title}: {item.content}")
        lines.append("")
    return "\n".join(lines)


# Registry of segment implementations
_REGISTRY: dict[str, BaseSegment] = {
    "greeting": GreetingSegment("greeting"),
    "intro": IntroSegment("intro"),
    "weather": WeatherSegment("weather"),
    "news": NewsSegment("news"),
    "topics": TopicsSegment("topics"),
    "outro": OutroSegment("outro"),
}


def get_segment_impl(segment_id: str) -> BaseSegment | None:
    """Returns the segment implementation class based on its ID."""
    return _REGISTRY.get(segment_id)
