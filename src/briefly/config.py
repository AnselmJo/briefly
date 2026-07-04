"""Laden und Validieren der YAML-Konfiguration (pydantic)."""

from __future__ import annotations

import sys
import warnings
from pathlib import Path
from typing import Literal, Any, get_origin, get_args

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator, ValidationError

# Default-Ausschluss-Themen laut Briefing §2.5: Krieg/Kriminalität/Katastrophen.
DEFAULT_EXCLUDE_KEYWORDS = [
    "Krieg",
    "Kriminalität",
    "Katastrophe",
    "war",
    "crime",
    "disaster",
]

DEFAULT_SEGMENT_PROFILE = ["intro", "news", "topics", "outro"]


class ConfigValidationError(ValueError):
    """Custom exception raised when configuration validation fails."""
    def __init__(self, key: str, invalid_value: Any, msg: str, fix: str):
        self.key = key
        self.invalid_value = invalid_value
        self.msg = msg
        self.fix = fix
        super().__init__(
            f"Invalid configuration key '{key}': '{invalid_value}'\n"
            f"Error: {msg}\n"
            f"Suggested fix: {fix}"
        )


def format_pydantic_error(e: ValidationError) -> ConfigValidationError:
    """Formats a Pydantic ValidationError into a user-friendly ConfigValidationError."""
    err = e.errors()[0]
    loc = err.get("loc", [])
    key = ".".join(str(x) for x in loc)
    invalid_value = err.get("input")
    msg = err.get("msg", "Validation failed")
    
    if msg.startswith("Value error, "):
        msg = msg[len("Value error, "):]

    # Custom suggested fixes
    fix = "Please verify the setting value in config.yaml."
    
    if "port" in key:
        fix = "Set a port number in the range 1-65535 (e.g., 8787)."
    elif "base_url" in key or "url" in key:
        fix = "Ensure the URL starts with 'http://' or 'https://' and is valid."
    elif "host" in key:
        fix = "Ensure the host string is not empty (e.g., '0.0.0.0' or 'localhost')."
    elif "length_scale" in key:
        fix = "Set length_scale to a positive decimal number (e.g., 1.0, 1.2), or leave it empty (null)."
    elif "pause_ms" in key:
        fix = "Set the pause to a non-negative integer in milliseconds (e.g., 250)."
    elif "hour" in key:
        fix = "Set the hour to an integer between 0 and 23."
    elif "minute" in key:
        fix = "Set the minute to an integer between 0 and 59."
    elif "target_minutes" in key:
        fix = "Set target_minutes to a positive integer (e.g., 10)."
    elif "profile" in key:
        fix = "Define a list of non-empty segment names (e.g. ['intro', 'news', 'topics', 'outro'])."
    elif "topics.include" in key or "topics.exclude" in key:
        fix = "Ensure topics are a list of non-empty strings (e.g., ['news', 'tech'])."
    elif "exclude_keywords" in key:
        fix = "Ensure sources.exclude_keywords is a list of non-empty strings."
    elif "path" in key or "voices_dir" in key or "output_dir" in key:
        fix = f"Ensure '{key}' is a valid non-empty path."
    elif "provider" in key:
        if "llm" in key:
            fix = "Set llm.provider to 'ollama'."
        elif "tts" in key:
            fix = "Set tts.provider to 'piper'."
        elif "delivery" in key:
            fix = "Set delivery.provider to 'local_feed'."
        else:
            fix = "Use a supported provider for this setting."
    elif err.get("type") == "int_parsing":
        fix = f"Ensure the value for {key} is a valid integer."
    elif err.get("type") == "float_parsing":
        fix = f"Ensure the value for {key} is a valid decimal number."
    elif err.get("type") == "bool_parsing":
        fix = f"Ensure the value for {key} is true or false."
    elif err.get("type") == "missing":
        fix = f"Define the required key '{key}' in your configuration."

    return ConfigValidationError(key, invalid_value, msg, fix)


def install_excepthook() -> None:
    def custom_excepthook(type_: type[BaseException], value: BaseException, traceback: Any) -> None:
        if issubclass(type_, ConfigValidationError):
            print("Fehler: Ungültige Konfiguration:", file=sys.stderr)
            print(f"  Schlüssel:       {value.key}", file=sys.stderr)
            print(f"  Ungültiger Wert: {value.invalid_value}", file=sys.stderr)
            print(f"  Fehlermeldung:   {value.msg}", file=sys.stderr)
            print(f"  Behebung:        {value.fix}", file=sys.stderr)
            sys.exit(1)
        sys.__excepthook__(type_, value, traceback)
    sys.excepthook = custom_excepthook

install_excepthook()


def check_unknown_keys(data: Any, model_class: type[BaseModel], prefix: str = "") -> list[str]:
    """Recursively checks for fields in the input data that are not defined on the Pydantic models."""
    warnings_list = []
    if not isinstance(data, dict):
        return warnings_list

    known_fields = model_class.model_fields.keys()
    for key, value in data.items():
        full_key = f"{prefix}{key}" if not prefix else f"{prefix}.{key}"
        if key not in known_fields:
            warnings_list.append(f"Unbekannter Konfigurationsschlüssel: {full_key}")
            continue
        
        field_info = model_class.model_fields[key]
        annotation = field_info.annotation
        
        origin = get_origin(annotation)
        args = get_args(annotation)
        
        model_types = []
        if origin is Literal:
            pass
        elif origin is list or annotation is list:
            if args:
                item_type = args[0]
                if isinstance(item_type, type) and issubclass(item_type, BaseModel):
                    model_types.append(item_type)
        elif origin is None:
            if isinstance(annotation, type) and issubclass(annotation, BaseModel):
                model_types.append(annotation)
        else:
            for arg in args:
                if isinstance(arg, type) and issubclass(arg, BaseModel):
                    model_types.append(arg)
                elif get_origin(arg) is list:
                    list_args = get_args(arg)
                    if list_args and isinstance(list_args[0], type) and issubclass(list_args[0], BaseModel):
                        model_types.append(list_args[0])
                        
        if model_types:
            target_model = model_types[0]
            if isinstance(value, dict):
                warnings_list.extend(check_unknown_keys(value, target_model, full_key))
            elif isinstance(value, list):
                for idx, item in enumerate(value):
                    if isinstance(item, dict):
                        warnings_list.extend(check_unknown_keys(item, target_model, f"{full_key}[{idx}]"))
    return warnings_list


# --- Child Configuration Models ---

class TopicsConfig(BaseModel):
    include: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)

    @field_validator("include", "exclude")
    @classmethod
    def validate_topics(cls, v: list[str]) -> list[str]:
        for item in v:
            if not isinstance(item, str) or not item.strip():
                raise ValueError("Topics list must contain only non-empty strings")
        return v


class InboxSourceConfig(BaseModel):
    path: Path = Path("data/inbox")

    @field_validator("path", mode="before")
    @classmethod
    def validate_path(cls, v: Any) -> Any:
        if isinstance(v, str) and not v.strip():
            raise ValueError("Inbox path cannot be empty")
        return v


class RssFeedConfig(BaseModel):
    url: str
    topic: str | None = None
    weight: float = 1.0

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("RSS feed URL cannot be empty")
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("RSS feed URL must start with http:// or https://")
        try:
            from urllib.parse import urlparse
            result = urlparse(v)
            if not result.scheme or not result.netloc:
                raise ValueError("RSS feed URL is not a valid absolute URL")
        except Exception as e:
            raise ValueError(f"RSS feed URL is invalid: {e}")
        return v

    @field_validator("topic")
    @classmethod
    def validate_topic(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("RSS feed topic cannot be empty if provided")
        return v

    @field_validator("weight")
    @classmethod
    def validate_weight(cls, v: float) -> float:
        if v < 0.0:
            raise ValueError("RSS feed weight must be a non-negative float (>= 0.0)")
        return v


class RssSourceConfig(BaseModel):
    feeds: list[RssFeedConfig] = Field(default_factory=list)


class SourcesConfig(BaseModel):
    inbox: InboxSourceConfig = Field(default_factory=InboxSourceConfig)
    rss: RssSourceConfig = Field(default_factory=RssSourceConfig)
    topics: TopicsConfig = Field(default_factory=TopicsConfig)
    exclude_keywords: list[str] = Field(default_factory=lambda: list(DEFAULT_EXCLUDE_KEYWORDS))

    @field_validator("exclude_keywords")
    @classmethod
    def validate_exclude_keywords(cls, v: list[str]) -> list[str]:
        for item in v:
            if not isinstance(item, str) or not item.strip():
                raise ValueError("Exclude keywords list must contain only non-empty strings")
        return v


class LlmConfig(BaseModel):
    provider: Literal["ollama"] = "ollama"
    model: str = "qwen3:8b"

    @field_validator("model")
    @classmethod
    def validate_model(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("llm.model cannot be empty")
        return v


class TtsConfig(BaseModel):
    provider: Literal["piper"] = "piper"
    voice_de: str = "de_DE-thorsten-medium"
    voice_en: str = "en_US-lessac-medium"
    voices_dir: Path = Path("data/voices")
    length_scale: float | None = None
    sentence_pause_ms: int = 250
    paragraph_pause_ms: int = 600
    language: str = "en"

    @field_validator("voice_de", "voice_en", "language")
    @classmethod
    def validate_non_empty_str(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Field cannot be empty")
        return v

    @field_validator("voices_dir", mode="before")
    @classmethod
    def validate_voices_dir(cls, v: Any) -> Any:
        if isinstance(v, str) and not v.strip():
            raise ValueError("tts.voices_dir cannot be empty")
        return v

    @field_validator("length_scale")
    @classmethod
    def validate_length_scale(cls, v: float | None) -> float | None:
        if v is not None and v <= 0.0:
            raise ValueError("tts.length_scale must be greater than 0.0")
        return v

    @field_validator("sentence_pause_ms", "paragraph_pause_ms")
    @classmethod
    def validate_pause(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Pause must be a non-negative integer (>= 0)")
        return v


class DeliveryConfig(BaseModel):
    provider: Literal["local_feed"] = "local_feed"
    output_dir: Path = Path("output")
    base_url: str = "http://localhost:8787"
    host: str = "0.0.0.0"
    port: int = 8787

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("delivery.base_url cannot be empty")
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("delivery.base_url must start with http:// or https://")
        try:
            from urllib.parse import urlparse
            result = urlparse(v)
            if not result.scheme or not result.netloc:
                raise ValueError("delivery.base_url is not a valid absolute URL")
        except Exception as e:
            raise ValueError(f"delivery.base_url is invalid: {e}")
        return v

    @field_validator("output_dir", mode="before")
    @classmethod
    def validate_output_dir(cls, v: Any) -> Any:
        if isinstance(v, str) and not v.strip():
            raise ValueError("delivery.output_dir cannot be empty")
        return v

    @field_validator("host")
    @classmethod
    def validate_host(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("delivery.host cannot be empty")
        return v

    @field_validator("port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        if not (1 <= v <= 65535):
            raise ValueError("delivery.port must be an integer between 1 and 65535")
        return v


class SegmentConfig(BaseModel):
    id: str
    enabled: bool = True

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("segment ID cannot be empty")
        return v.strip()


class ScheduleConfig(BaseModel):
    hour: int = 5
    minute: int = 30

    @field_validator("hour")
    @classmethod
    def validate_hour(cls, v: int) -> int:
        if not (0 <= v <= 23):
            raise ValueError("schedule.hour must be between 0 and 23")
        return v

    @field_validator("minute")
    @classmethod
    def validate_minute(cls, v: int) -> int:
        if not (0 <= v <= 59):
            raise ValueError("schedule.minute must be between 0 and 59")
        return v


# --- Legacy Proxies for Backward Compatibility ---

class LegacyLanguageProxy:
    def __init__(self, tts_config: TtsConfig):
        self._tts_config = tts_config

    @property
    def target(self) -> str:
        return self._tts_config.language

    @target.setter
    def target(self, value: str) -> None:
        self._tts_config.language = value


class LegacyWebProxy:
    def __init__(self, delivery_config: DeliveryConfig):
        self._delivery_config = delivery_config

    @property
    def host(self) -> str:
        return self._delivery_config.host

    @host.setter
    def host(self, value: str) -> None:
        self._delivery_config.host = value

    @property
    def port(self) -> int:
        return self._delivery_config.port

    @port.setter
    def port(self, value: int) -> None:
        self._delivery_config.port = value


class LegacyEpisodeProxy:
    def __init__(self, config: Config):
        self._config = config

    @property
    def target_minutes(self) -> int:
        return self._config.target_minutes

    @target_minutes.setter
    def target_minutes(self, value: int) -> None:
        self._config.target_minutes = value


# --- Main Configuration Model ---

class Config(BaseModel):
    delivery: DeliveryConfig = Field(default_factory=DeliveryConfig)
    tts: TtsConfig = Field(default_factory=TtsConfig)
    llm: LlmConfig = Field(default_factory=LlmConfig)
    sources: SourcesConfig = Field(default_factory=SourcesConfig)
    segments: list[SegmentConfig] = Field(default_factory=lambda: [
        SegmentConfig(id="greeting", enabled=True),
        SegmentConfig(id="intro", enabled=True),
        SegmentConfig(id="news", enabled=True),
        SegmentConfig(id="topics", enabled=True),
        SegmentConfig(id="outro", enabled=True),
    ])
    user_name: str = "Anselm"
    target_minutes: int = 10
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)

    @field_validator("user_name")
    @classmethod
    def validate_user_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("user_name cannot be empty")
        return v.strip()

    @field_validator("segments")
    @classmethod
    def validate_segments(cls, v: list[SegmentConfig]) -> list[SegmentConfig]:
        if not v:
            raise ValueError("segments list cannot be empty")
        return v

    @field_validator("target_minutes")
    @classmethod
    def validate_target_minutes(cls, v: int) -> int:
        if v < 1:
            raise ValueError("target_minutes must be at least 1")
        return v

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_keys(cls, data: Any) -> Any:
        """Migrates older configuration schemas/keys to the new grouped configuration schema."""
        if isinstance(data, dict):
            # Migrate segment_profile -> segments list
            if "segment_profile" in data:
                profile = data.pop("segment_profile")
                if isinstance(profile, list):
                    data["segments"] = [{"id": s_id, "enabled": True} for s_id in profile]

            # If segments is a dict, it's legacy
            if "segments" in data and isinstance(data["segments"], dict):
                seg_dict = data["segments"]
                if "target_minutes" in seg_dict:
                    data["target_minutes"] = seg_dict.pop("target_minutes")
                if "profile" in seg_dict:
                    profile = seg_dict.pop("profile")
                    if isinstance(profile, list):
                        data["segments"] = [{"id": s_id, "enabled": True} for s_id in profile]
                else:
                    data.pop("segments", None)

            # Migrate episode.target_minutes -> target_minutes
            if "episode" in data:
                episode_data = data.pop("episode")
                if isinstance(episode_data, dict) and "target_minutes" in episode_data:
                    data["target_minutes"] = episode_data["target_minutes"]
                        
            # Migrate language.target -> tts.language
            if "language" in data:
                lang_data = data.pop("language")
                if isinstance(lang_data, dict) and "target" in lang_data:
                    if "tts" not in data or not isinstance(data["tts"], dict):
                        data["tts"] = {}
                    if "language" not in data["tts"]:
                        data["tts"]["language"] = lang_data["target"]
            
            # Migrate web.host/port -> delivery.host/port
            if "web" in data:
                web_data = data.pop("web")
                if isinstance(web_data, dict):
                    if "delivery" not in data or not isinstance(data["delivery"], dict):
                        data["delivery"] = {}
                    if "host" in web_data and "host" not in data["delivery"]:
                        data["delivery"]["host"] = web_data["host"]
                    if "port" in web_data and "port" not in data["delivery"]:
                        data["delivery"]["port"] = web_data["port"]

            # Migrate topics -> sources.topics
            if "topics" in data:
                topics_data = data.pop("topics")
                if isinstance(topics_data, dict):
                    if "sources" not in data or not isinstance(data["sources"], dict):
                        data["sources"] = {}
                    if "topics" not in data["sources"]:
                        data["sources"]["topics"] = topics_data
            
            # Migrate exclude_keywords -> sources.exclude_keywords
            if "exclude_keywords" in data:
                exc_data = data.pop("exclude_keywords")
                if "sources" not in data or not isinstance(data["sources"], dict):
                    data["sources"] = {}
                if "exclude_keywords" not in data["sources"]:
                    data["sources"]["exclude_keywords"] = exc_data
                    
        return data

    @property
    def language(self) -> LegacyLanguageProxy:
        return LegacyLanguageProxy(self.tts)

    @property
    def web(self) -> LegacyWebProxy:
        return LegacyWebProxy(self.delivery)

    @property
    def episode(self) -> LegacyEpisodeProxy:
        return LegacyEpisodeProxy(self)

    @property
    def topics(self) -> TopicsConfig:
        return self.sources.topics

    @property
    def exclude_keywords(self) -> list[str]:
        return self.sources.exclude_keywords

    @exclude_keywords.setter
    def exclude_keywords(self, value: list[str]) -> None:
        self.sources.exclude_keywords = value

    @property
    def segment_profile(self) -> list[str]:
        return [s.id for s in self.segments if s.enabled]

    @segment_profile.setter
    def segment_profile(self, value: list[str]) -> None:
        self.segments = [SegmentConfig(id=s_id, enabled=True) for s_id in value]


def get_user_dir() -> Path:
    """Gibt das plattform-spezifische Benutzer-Datenverzeichnis zurück."""
    import os
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Briefly"
    elif sys.platform == "win32" or sys.platform == "cygwin":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "Briefly"
        return Path.home() / "AppData" / "Roaming" / "Briefly"
    else:
        # Fallback für Linux
        return Path.home() / ".briefly"


def get_default_config_path() -> Path:
    """Gibt den Pfad zur Standard-Konfigurationsdatei zurück (lokal oder im Benutzerverzeichnis)."""
    local_config = Path("config.yaml")
    if local_config.exists():
        return local_config.resolve()
    return get_user_dir() / "config.yaml"


def load_config(path: Path) -> Config:
    """Liest eine YAML-Konfigurationsdatei ein, validiert sie und warnt bei unbekannten Schlüsseln."""
    path = Path(path).resolve()
    with path.open(encoding="utf-8") as config_file:
        raw = yaml.safe_load(config_file) or {}
    
    # Migrieren auf eine temporäre Struktur für den Unknown-Keys Check
    import copy
    migrated = copy.deepcopy(raw)
    migrated = Config.migrate_legacy_keys(migrated)

    # Warnung bei unbekannten Schlüsseln
    warnings_list = check_unknown_keys(migrated, Config)
    for warning in warnings_list:
        warnings.warn(warning, UserWarning)
        # Auch auf stderr ausgeben für CLI-Benutzer
        print(f"Warnung: {warning}", file=sys.stderr)
        
    try:
        config = Config.model_validate(raw)
    except ValidationError as e:
        raise format_pydantic_error(e) from e

    # Relative Pfade auflösen relativ zum Ordner der Konfigurationsdatei
    config_dir = path.parent
    if not config.sources.inbox.path.is_absolute():
        config.sources.inbox.path = (config_dir / config.sources.inbox.path).resolve()
    if not config.tts.voices_dir.is_absolute():
        config.tts.voices_dir = (config_dir / config.tts.voices_dir).resolve()
    if not config.delivery.output_dir.is_absolute():
        config.delivery.output_dir = (config_dir / config.delivery.output_dir).resolve()

    return config


def save_config(config: Config, path: Path) -> None:
    """Schreibt eine Config zurück nach YAML."""
    # Vor dem Speichern den aktuellen Zustand validieren
    try:
        Config.model_validate(config.model_dump(mode="json"))
    except ValidationError as e:
        raise format_pydantic_error(e) from e

    data = config.model_dump(mode="json")
    with Path(path).open("w", encoding="utf-8") as config_file:
        yaml.safe_dump(data, config_file, sort_keys=False, allow_unicode=True)


