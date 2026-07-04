"""Segment architecture for Briefly.

Each segment represents a discrete module in the daily brief run.
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

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

AFFIRMATIONS_EN = [
    "I am capable of achieving my goals today.",
    "I choose to focus on what I can control.",
    "My mind is clear, and my focus is sharp.",
    "I am resilient, strong, and brave.",
    "Every challenge is an opportunity to grow.",
    "I trust my intuition and make wise decisions.",
    "I am proud of who I am becoming.",
    "I surround myself with positive energy.",
    "Today is full of possibilities and growth.",
    "I deserve happiness, success, and peace.",
]

AFFIRMATIONS_DE = [
    "Ich bin fähig, meine heutigen Ziele zu erreichen.",
    "Ich entscheide mich, mich auf das zu konzentrieren, was ich beeinflussen kann.",
    "Mein Geist ist klar und mein Fokus ist scharf.",
    "Ich bin widerstandsfähig, stark und mutig.",
    "Jede Herausforderung ist eine Gelegenheit zu wachsen.",
    "Ich vertraue meiner Intuition und treffe kluge Entscheidungen.",
    "Ich bin stolz darauf, wer ich werde.",
    "Ich umgebe mich mit positiver Energie.",
    "Der heutige Tag ist voller Möglichkeiten und Wachstum.",
    "Ich verdiene Glück, Erfolg und Frieden.",
]

FUNFACT_TOPICS = [
    "nature",
    "history",
    "science",
    "space",
    "human body",
    "geography",
    "technology",
    "art",
]

FALLBACK_FUNFACTS_EN = {
    "nature": "Today's interesting fact: Honeybees can recognize human faces. They use a method called configural processing, piecing together eyes, ears, and noses just like we do.",
    "history": "Today's interesting fact: The shortest war in history lasted only 38 minutes. It was fought between the British Empire and the Zanzibar Sultanate in 1896.",
    "science": "Today's interesting fact: Water can boil and freeze at the same time. This is known as the triple point, where temperature and pressure allow all three states of matter to coexist.",
    "space": "Today's interesting fact: One day on Venus is longer than one year. Venus takes 243 Earth days to rotate once on its axis, but only 225 Earth days to travel around the Sun.",
    "human body": "Today's interesting fact: Human bone is about four times stronger than concrete. A block of bone the size of a matchbox can support up to nine tons of weight.",
    "geography": "Today's interesting fact: Canada has more lakes than the rest of the world combined. Over nine percent of the country's total area is covered by freshwater.",
    "technology": "Today's interesting fact: The first computer bug was a real moth. In 1947, engineers at Harvard found a moth stuck in a relay of the Harvard Mark II computer.",
    "art": "Today's interesting fact: Leonardo da Vinci could write with one hand and draw with the other at the same time. This rare ability is known as ambidexterity.",
}

FALLBACK_FUNFACTS_DE = {
    "nature": "Die heutige interessante Tatsache: Honigbienen können menschliche Gesichter erkennen. Sie nutzen eine Methode, bei der sie Augen, Ohren und Nasen zusammensetzen, genau wie wir.",
    "history": "Die heutige interessante Tatsache: Der kürzeste Krieg der Geschichte dauerte nur 38 Minuten. Er wurde 1896 zwischen dem Britischen Empire und dem Sultanat Sansibar geführt.",
    "science": "Die heutige interessante Tatsache: Wasser kann gleichzeitig kochen und gefrieren. Dies wird als Tripelpunkt bezeichnet, an dem Temperatur und Druck es erlauben, dass alle drei Aggregatzustände koexistieren.",
    "space": "Die heutige interessante Tatsache: Ein Tag auf der Venus ist länger als ein Venus-Jahr. Die Venus benötigt 243 Erdentage für eine Drehung um die eigene Achse, aber nur 225 Tage für einen Umlauf um die Sonne.",
    "human body": "Die heutige interessante Tatsache: Menschliche Knochen sind etwa viermal stabiler als Beton. Ein Knochenblock in der Größe einer Streichholzschachtel kann bis zu neun Tonnen Gewicht tragen.",
    "geography": "Die heutige interessante Tatsache: Kanada hat mehr Seen als der Rest der Welt zusammen. Über neun Prozent der Gesamtfläche des Landes sind von Süßwasser bedeckt.",
    "technology": "Die heutige interessante Tatsache: Der erste Computer-Bug war eine echte Motte. Im Jahr 1947 fanden Ingenieure in Harvard eine Motte, die in einem Relais des Mark-Zwei-Computers eingeklemmt war.",
    "art": "Die heutige interessante Tatsache: Leonardo da Vinci konnte mit einer Hand schreiben und gleichzeitig mit der anderen zeichnen. Diese seltene Fähigkeit wird als Beidhändigkeit bezeichnet.",
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


def parse_ics_datetime(value: str, params: dict[str, str]) -> datetime | date | None:
    """Parses standard ICS date/datetime format into date or datetime object."""
    value = value.strip()
    if "VALUE=DATE" in params.get("VALUE", "") or len(value) == 8:
        try:
            return date(int(value[0:4]), int(value[4:6]), int(value[6:8]))
        except ValueError:
            return None

    if len(value) >= 15:
        try:
            is_utc = value.endswith("Z")
            clean_val = value[:-1] if is_utc else value

            dt = datetime(
                int(clean_val[0:4]),
                int(clean_val[4:6]),
                int(clean_val[6:8]),
                int(clean_val[9:11]),
                int(clean_val[11:13]),
                int(clean_val[13:15]),
            )
            if is_utc:
                return dt.replace(tzinfo=ZoneInfo("UTC"))
            return dt
        except Exception:
            return None
    return None


def fetch_calendar_data(source: str) -> str | None:
    """Fetches an ICS source (local file or remote URL) with 1-hour caching."""
    user_dir = get_user_dir()
    cache_dir = user_dir / "calendar_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    if not source.startswith(("http://", "https://")):
        # Treat as local file
        from pathlib import Path
        path = Path(source)
        if path.exists():
            return path.read_text(encoding="utf-8")
        logger.warning("Local calendar file does not exist: %s", source)
        return None

    # Remote URL
    url_hash = hashlib.md5(source.encode("utf-8")).hexdigest()
    cache_path = cache_dir / f"{url_hash}.ics"

    if cache_path.exists():
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        if datetime.now() - mtime < timedelta(hours=1):
            return cache_path.read_text(encoding="utf-8")

    import httpx
    try:
        response = httpx.get(source, timeout=10.0)
        if response.status_code == 200:
            text = response.text
            cache_path.write_text(text, encoding="utf-8")
            return text
    except Exception as e:
        logger.warning("Failed to fetch remote calendar %s: %s", source, e)
        if cache_path.exists():
            logger.info("Using expired cached calendar for %s", source)
            return cache_path.read_text(encoding="utf-8")

    return None


def parse_ics(content: str) -> list[dict[str, Any]]:
    """Simple parser to unfold lines and group VEVENT properties."""
    lines = []
    for line in content.splitlines():
        if line.startswith((" ", "\t")):
            if lines:
                lines[-1] += line[1:]
        else:
            lines.append(line)

    events = []
    current_event = None

    for line in lines:
        if not line.strip():
            continue

        if line.startswith("BEGIN:VEVENT"):
            current_event = {}
        elif line.startswith("END:VEVENT"):
            if current_event is not None:
                events.append(current_event)
                current_event = None
        elif current_event is not None:
            parts = line.split(":", 1)
            if len(parts) == 2:
                name_params, val = parts
                name_parts = name_params.split(";", 1)
                name = name_parts[0].upper()
                params = {}
                if len(name_parts) == 2:
                    for p in name_parts[1].split(";"):
                        p_parts = p.split("=", 1)
                        if len(p_parts) == 2:
                            params[p_parts[0].upper()] = p_parts[1]
                current_event[name] = {"value": val, "params": params}

    return events


def get_events_for_date(events: list[dict[str, Any]], target_date: date) -> list[dict[str, Any]]:
    """Filters VEVENT dicts that fall on target_date, returning list of unified dicts."""
    matching_events = []

    for event in events:
        dtstart_data = event.get("DTSTART")
        if not dtstart_data:
            continue

        val = dtstart_data["value"]
        params = dtstart_data["params"]

        start = parse_ics_datetime(val, params)
        if not start:
            continue

        rrule_data = event.get("RRULE")
        rrule = rrule_data["value"] if rrule_data else None

        is_on_date = False
        if isinstance(start, datetime):
            tzid = params.get("TZID")
            if tzid:
                try:
                    event_tz = ZoneInfo(tzid.strip('"'))
                    start_local = start.replace(tzinfo=event_tz)
                    is_on_date = (start_local.date() == target_date)
                except Exception:
                    is_on_date = (start.date() == target_date)
            else:
                if val.endswith("Z"):
                    try:
                        local_tz = datetime.now().astimezone().tzinfo
                        start_local = start.astimezone(local_tz)
                        is_on_date = (start_local.date() == target_date)
                    except Exception:
                        is_on_date = (start.date() == target_date)
                else:
                    is_on_date = (start.date() == target_date)
        else:
            is_on_date = (start == target_date)

        if not is_on_date and rrule:
            if "FREQ=YEARLY" in rrule:
                is_on_date = (start.month == target_date.month and start.day == target_date.day)

        if is_on_date:
            summary = event.get("SUMMARY", {}).get("value", "Unbenannter Termin")
            summary = summary.replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\").strip()

            event_time = None
            if isinstance(start, datetime):
                if start.tzinfo is not None:
                    local_tz = datetime.now().astimezone().tzinfo
                    start_local = start.astimezone(local_tz)
                    event_time = start_local.strftime("%H:%M")
                else:
                    event_time = start.strftime("%H:%M")

            matching_events.append({
                "summary": summary,
                "time": event_time,
                "is_all_day": not isinstance(start, datetime),
            })

    return matching_events


def filter_events(events: list[dict[str, Any]], include: list[str], exclude: list[str]) -> list[dict[str, Any]]:
    """Filters events based on keyword lists (case-insensitive)."""
    filtered = []
    for e in events:
        summary_lower = e["summary"].lower()

        if exclude:
            if any(kw.lower() in summary_lower for kw in exclude):
                continue

        if include:
            if not any(kw.lower() in summary_lower for kw in include):
                continue

        filtered.append(e)
    return filtered


def get_birthday_name(summary: str) -> str | None:
    """Extracts a capitalized name from a birthday event summary."""
    summary_lower = summary.lower()
    if "geburtstag" in summary_lower or "birthday" in summary_lower or "bday" in summary_lower:
        for word in ["'s birthday", "'s bday", " birthday", " bday", " geburtstag", "s geburtstag"]:
            if word in summary_lower:
                idx = summary_lower.find(word)
                if idx > 0:
                    return summary[:idx].strip()
        for prep in ["geburtstag von ", "birthday of "]:
            if prep in summary_lower:
                idx = summary_lower.find(prep)
                return summary[idx + len(prep):].strip()
        for colon in ["geburtstag:", "birthday:", "bday:"]:
            if colon in summary_lower:
                idx = summary_lower.find(colon)
                return summary[idx + len(colon):].strip()
        return summary
    return None


def format_calendar_programmatically(events: list[dict[str, Any]], language: str) -> str:
    """Determined programmatic formatting when local Ollama LLM provider is unavailable."""
    if not events:
        return "Du hast heute keine Termine." if language == "de" else "You have no events scheduled for today."

    parts = []
    birthdays = []
    regular_events = []

    for e in events:
        bday_name = get_birthday_name(e["summary"])
        if bday_name:
            birthdays.append(bday_name)
        else:
            regular_events.append(e)

    if birthdays:
        names_str = " und ".join(birthdays) if language == "de" else " and ".join(birthdays)
        if language == "de":
            parts.append(f"Heute hat {names_str} Geburtstag.")
        else:
            parts.append(f"Today is {names_str}'s birthday.")

    if regular_events:
        for e in regular_events:
            summary = e["summary"]
            t = e["time"]
            if language == "de":
                if t:
                    try:
                        hr = int(t.split(":")[0])
                        time_str = f"um {hr} Uhr"
                    except Exception:
                        time_str = f"um {t}"
                else:
                    time_str = "heute"
                parts.append(f"Du hast {time_str} einen Termin: {summary}.")
            else:
                if t:
                    try:
                        hr = int(t.split(":")[0])
                        ampm = "am" if hr < 12 else "pm"
                        hr_12 = hr if hr <= 12 else hr - 12
                        if hr_12 == 0:
                            hr_12 = 12
                        time_str = f"at {hr_12} {ampm}"
                    except Exception:
                        time_str = f"at {t}"
                else:
                    time_str = "today"
                parts.append(f"You have an event {time_str}: {summary}.")

    return " ".join(parts)


def _build_calendar_prompt(events: list[dict[str, Any]], language: str) -> str:
    lines = [
        "Du bist der Sprecher für 'Briefly', ein persönliches tägliches Audio-Briefing.",
        "Formuliere die folgenden Kalendereinträge für heute in einen flüssigen, freundlichen, gesprochenen Text um.",
        "Schreibe ausschließlich den fertigen Sprechtext, ohne jeglichen Begleittext und ohne Einleitung/Überschrift.",
        "Wichtig: Lies nicht einfach stur Zeiten und Titel vor (kein '10:00 Meeting'), sondern sprich in ganzen Sätzen.",
        "Beispiele:",
        "- 'Du hast um 16 Uhr einen Termin beim Kinderarzt Müller.'" if language == "de" else "- 'You have an appointment at pediatrician Müller at 4 pm.'",
        "- 'Heute hat Lisa Geburtstag.'" if language == "de" else "- 'Today is Lisa's birthday.'",
        "",
        "Hier sind die heutigen Kalendereinträge:",
    ]
    for e in events:
        time_str = f"um {e['time']}" if e["time"] else "Ganztägig"
        if language != "de":
            time_str = f"at {e['time']}" if e["time"] else "All-day"
        lines.append(f"- {e['summary']} ({time_str})")

    return "\n".join(lines)


def _build_funfact_prompt(topic: str, language: str) -> str:
    if language == "de":
        return (
            "Du bist der Sprecher für 'Briefly', ein persönliches tägliches Audio-Briefing.\n"
            f"Erzähle eine kurze, interessante und überraschende Tatsache zum Thema '{topic}'.\n"
            "Wichtig:\n"
            "- Schreibe ausschließlich den fertigen Sprechtext in 2 bis 4 Sätzen.\n"
            "- Beginne den Text mit 'Die heutige interessante Tatsache:' oder einer ähnlichen Formulierung.\n"
            "- Schreibe keinen Begleittext, keine Überschrift, und keine Kommentare.\n"
            "- Formuliere den Text flüssig und ansprechend für die Audio-Ausgabe."
        )
    else:
        return (
            "You are the speaker for 'Briefly', a personal daily audio briefing.\n"
            f"Share a short, interesting, and surprising fact about '{topic}'.\n"
            "Important:\n"
            "- Write exactly the spoken text in 2 to 4 sentences.\n"
            "- Begin the text with 'Today's interesting fact:' or a similar phrase.\n"
            "- Do not write any metadata, headings, or commentary.\n"
            "- Make it sound natural and engaging for audio playback."
        )


def _build_summarize_prompt(content: str, max_words: int, language: str) -> str:
    if language == "de":
        return (
            "Du bist ein Assistent für ein persönliches tägliches Audio-Briefing.\n"
            f"Fasse den folgenden Eintrag so zusammen, dass er flüssig gesprochen werden kann und maximal {max_words} Wörter lang ist.\n"
            "Wichtig: Antworte ausschließlich mit der fertigen Zusammenfassung ohne Einleitung, Begleittext oder Anmerkungen.\n\n"
            f"Eintrag:\n{content}"
        )
    else:
        return (
            "You are an assistant for a personal daily audio briefing.\n"
            f"Summarize the following entry so that it can be read aloud naturally and is at most {max_words} words long.\n"
            "Important: Output only the summary itself without any introductory or concluding remarks.\n\n"
            f"Entry:\n{content}"
        )


def truncate_words(text: str, max_words: int) -> str:
    """Fallback truncation of words."""
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + "..."


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


class CalendarSegment(BaseSegment):
    """Calendar segment based on ICS feeds."""

    def collect(self, config: Config) -> list[dict[str, Any]] | None:
        if not config.calendar.feeds:
            return None

        events = []
        for feed in config.calendar.feeds:
            content = fetch_calendar_data(feed.url)
            if not content:
                continue

            try:
                raw_events = parse_ics(content)
                for raw_e in raw_events:
                    events.append({
                        "event": raw_e,
                        "include": feed.include,
                        "exclude": feed.exclude,
                    })
            except Exception as e:
                logger.warning("Failed to parse calendar feed %s: %s", feed.url, e)

        return events

    def script(
        self,
        config: Config,
        data: Any,
        llm_provider: LanguageModelProvider,
        language: str,
        episode_date: date | None = None,
    ) -> str:
        if not data:
            return "Du hast heute keine Termine." if language == "de" else "You have no events scheduled for today."

        target_date = episode_date or date.today()

        processed_events = []
        for item in data:
            raw_e = item["event"]
            include = item["include"]
            exclude = item["exclude"]

            evs = get_events_for_date([raw_e], target_date)
            filtered = filter_events(evs, include, exclude)
            processed_events.extend(filtered)

        if not processed_events:
            return "Du hast heute keine Termine." if language == "de" else "You have no events scheduled for today."

        prompt = _build_calendar_prompt(processed_events, language)
        try:
            return llm_provider.generate_segment_text(prompt)
        except Exception:
            return format_calendar_programmatically(processed_events, language)


class InboxSegment(BaseSegment):
    """Inbox segment."""

    def collect(self, config: Config) -> list[dict[str, Any]] | None:
        from pathlib import Path
        inbox_dir = Path(config.sources.inbox.path)
        if not inbox_dir.is_dir():
            return None

        import re

        _ENTRY_SEPARATOR = re.compile(r"^---$", re.MULTILINE)
        _TOPIC_HEADER = re.compile(r"^#thema:\s*(.+)$", re.IGNORECASE)
        _PRIORITY_HEADER = re.compile(r"^#prio:\s*(\d+)$", re.IGNORECASE)
        _RECURRING_HEADER = re.compile(r"^(?:#recurring|#wiederkehrend):\s*(true|yes|ja|1)\s*$", re.IGNORECASE)

        collected_entries = []
        archive_dir = inbox_dir / "archive"

        for file_path in sorted(inbox_dir.glob("*.txt")):
            try:
                text = file_path.read_text(encoding="utf-8")

                blocks = _ENTRY_SEPARATOR.split(text)
                recurring_blocks = []
                archived_blocks = []

                for block in blocks:
                    block_stripped = block.strip()
                    if not block_stripped:
                        continue

                    lines = block_stripped.splitlines()
                    topic = None
                    priority = 0
                    recurring = False
                    body_start = 0

                    for line in lines:
                        line_stripped = line.strip()
                        if match := _TOPIC_HEADER.match(line_stripped):
                            topic = match.group(1).strip()
                            body_start += 1
                        elif match := _PRIORITY_HEADER.match(line_stripped):
                            priority = int(match.group(1))
                            body_start += 1
                        elif match := _RECURRING_HEADER.match(line_stripped):
                            val = match.group(1).lower()
                            recurring = val in ("true", "yes", "ja", "1")
                            body_start += 1
                        else:
                            break

                    content = "\n".join(lines[body_start:]).strip()
                    if not content:
                        continue

                    entry_item = {
                        "content": content,
                        "topic": topic,
                        "priority": priority,
                        "recurring": recurring,
                        "source_name": file_path.name,
                    }

                    collected_entries.append(entry_item)

                    if recurring:
                        recurring_blocks.append(block_stripped)
                    else:
                        archived_blocks.append(block_stripped)

                if archived_blocks:
                    archive_dir.mkdir(parents=True, exist_ok=True)
                    archive_file = archive_dir / f"archived_{file_path.name}"

                    existing_archive_text = ""
                    if archive_file.exists():
                        existing_archive_text = archive_file.read_text(encoding="utf-8")
                        if existing_archive_text.strip():
                            existing_archive_text += "\n---\n"

                    new_archive_text = existing_archive_text + "\n---\n".join(archived_blocks)
                    archive_file.write_text(new_archive_text, encoding="utf-8")

                if recurring_blocks:
                    file_path.write_text("\n---\n".join(recurring_blocks), encoding="utf-8")
                else:
                    file_path.unlink(missing_ok=True)

            except Exception as e:
                logger.warning("Failed to process inbox file %s: %s", file_path, e)

        return collected_entries

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

        max_duration = getattr(config.inbox, "max_duration_seconds", 60)
        max_words = int(max_duration * 2.5)

        script_parts = []

        if language == "de":
            script_parts.append("Hier sind einige Einträge aus deinen persönlichen Notizen.")
        else:
            script_parts.append("Here are some entries from your personal inbox.")

        for item in data:
            content = item["content"]
            topic = item["topic"]

            word_count = len(content.split())
            if word_count > max_words:
                prompt = _build_summarize_prompt(content, max_words, language)
                try:
                    summary = llm_provider.generate_segment_text(prompt)
                    content = summary.strip()
                except Exception as e:
                    logger.warning("Failed to summarize long inbox entry via LLM: %s", e)
                    content = truncate_words(content, max_words)

            transition = ""
            if language == "de":
                if topic == "book":
                    transition = "Aus deinen Buchnotizen:"
                elif topic == "reading":
                    transition = "Aus deinen Lesezeichen:"
                elif topic == "link":
                    transition = "Aus deinen gespeicherten Links:"
                elif topic:
                    transition = f"Zum Thema {topic}:"
                else:
                    transition = "Aus deinem Posteingang:"
            else:
                if topic == "book":
                    transition = "From your book notes:"
                elif topic == "reading":
                    transition = "From your reading notes:"
                elif topic == "link":
                    transition = "From your saved links:"
                elif topic:
                    transition = f"Regarding {topic}:"
                else:
                    transition = "From your inbox:"

            script_parts.append(f"{transition} {content}")

        return " ".join(script_parts)


class AffirmationSegment(BaseSegment):
    """Affirmation segment."""

    def script(
        self,
        config: Config,
        data: Any,
        llm_provider: LanguageModelProvider,
        language: str,
        episode_date: date | None = None,
    ) -> str:
        d = episode_date or date.today()

        user_list = getattr(config.affirmation, "user_list", [])
        if user_list:
            affirmations = user_list
        else:
            if language == "de":
                affirmations = AFFIRMATIONS_DE
            else:
                affirmations = AFFIRMATIONS_EN

        if not affirmations:
            return ""

        n = len(affirmations)

        indices = list(range(n))
        random.Random(42).shuffle(indices)

        idx = indices[d.toordinal() % n]
        return affirmations[idx]


class FunFactSegment(BaseSegment):
    """Fun fact segment using local LLM."""

    def script(
        self,
        config: Config,
        data: Any,
        llm_provider: LanguageModelProvider,
        language: str,
        episode_date: date | None = None,
    ) -> str:
        d = episode_date or date.today()

        topic = FUNFACT_TOPICS[d.toordinal() % len(FUNFACT_TOPICS)]
        prompt = _build_funfact_prompt(topic, language)

        try:
            return llm_provider.generate_segment_text(prompt)
        except Exception:
            if language == "de":
                return FALLBACK_FUNFACTS_DE.get(topic, "")
            else:
                return FALLBACK_FUNFACTS_EN.get(topic, "")


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
    """Themen-Segment für sonstige RSS-Feeds."""

    def collect(self, config: Config) -> list[Item]:
        from briefly.curation import select_items
        from briefly.sources.rss import RssSource

        items = []
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
    "calendar": CalendarSegment("calendar"),
    "inbox": InboxSegment("inbox"),
    "news": NewsSegment("news"),
    "topics": TopicsSegment("topics"),
    "affirmation": AffirmationSegment("affirmation"),
    "funfact": FunFactSegment("funfact"),
    "outro": OutroSegment("outro"),
}


def get_segment_impl(segment_id: str) -> BaseSegment | None:
    """Returns the segment implementation class based on its ID."""
    return _REGISTRY.get(segment_id)
