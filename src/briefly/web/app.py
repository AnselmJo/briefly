"""FastAPI-Anwendung: Eingabe/Einstellungs-Oberfläche + Auslieferung von Feed/Audio.

Läuft dauerhaft im Heim-WLAN (siehe `scripts/launchd/com.briefly.web.plist`).
Bewusst ohne Authentifizierung – Zugriff ist laut Projektentscheidung auf das
Heim-WLAN beschränkt (kein Tunnel/VPN in Phase 1).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from briefly import pipeline
from briefly.config import Config, RssFeedConfig, load_config, save_config, ConfigValidationError, get_default_config_path

_APP_DIR = Path(__file__).parent
_CONFIG_PATH = get_default_config_path()
_ALLOWED_EPISODE_SUFFIXES = {".m4b", ".txt", ".json"}

app = FastAPI(title="Briefly")
app.mount("/static", StaticFiles(directory=str(_APP_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(_APP_DIR / "templates"))


@app.exception_handler(ConfigValidationError)
def config_validation_error_handler(request: Request, exc: ConfigValidationError):
    import sys
    print(f"Fehler: Ungültige Konfiguration:\n{exc}", file=sys.stderr)
    
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        html_content = f"""
        <html>
            <head>
                <title>Konfigurationsfehler</title>
                <style>
                    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 40px; line-height: 1.6; color: #333; }}
                    .error-card {{ border: 1px solid #f5c2c2; background-color: #fcf2f2; padding: 20px; border-radius: 6px; max-width: 600px; margin: auto; }}
                    h1 {{ color: #d9534f; margin-top: 0; }}
                    pre {{ background: #eee; padding: 10px; border-radius: 4px; overflow-x: auto; }}
                    .fix {{ font-weight: bold; color: #2e7d32; }}
                </style>
            </head>
            <body>
                <div class="error-card">
                    <h1>Ung&uuml;ltige Konfiguration</h1>
                    <p><strong>Schl&uuml;ssel:</strong> <code>{exc.key}</code></p>
                    <p><strong>Ung&uuml;ltiger Wert:</strong> <code>{exc.invalid_value}</code></p>
                    <p><strong>Fehlermeldung:</strong> {exc.msg}</p>
                    <p class="fix"><strong>L&ouml;sungsvorschlag:</strong> {exc.fix}</p>
                    <p><a href="javascript:history.back()">Zur&uuml;ck</a></p>
                </div>
            </body>
        </html>
        """
        return HTMLResponse(content=html_content, status_code=400)
    
    return PlainTextResponse(
        f"Fehler: Ungültige Konfiguration:\n"
        f"  Schlüssel:       {exc.key}\n"
        f"  Ungültiger Wert: {exc.invalid_value}\n"
        f"  Fehlermeldung:   {exc.msg}\n"
        f"  Behebung:        {exc.fix}",
        status_code=400
    )


def _get_config() -> Config:
    return load_config(_CONFIG_PATH)


@app.get("/")
def dashboard(request: Request):
    config = _get_config()
    episodes_dir = config.delivery.output_dir / "episodes"
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "latest_episode": _latest_episode_date(episodes_dir),
            "feed_url": f"{config.delivery.base_url}/feed.xml",
        },
    )


@app.post("/run")
def trigger_run(background_tasks: BackgroundTasks):
    config = _get_config()
    background_tasks.add_task(pipeline.run_all, config)
    return RedirectResponse("/", status_code=303)


@app.get("/settings")
def settings_form(request: Request):
    return templates.TemplateResponse(request, "settings.html", {"config": _get_config()})


@app.post("/settings")
def settings_save(
    language_target: str = Form(...),
    segment_profile: str = Form(...),
    topics_include: str = Form(""),
    topics_exclude: str = Form(""),
    exclude_keywords: str = Form(""),
    tts_length_scale: str = Form(""),
    tts_sentence_pause_ms: int = Form(250),
    tts_paragraph_pause_ms: int = Form(600),
):
    config = _get_config()
    config.language.target = language_target.strip()
    config.segment_profile = _split_lines(segment_profile)
    config.topics.include = _split_lines(topics_include)
    config.topics.exclude = _split_lines(topics_exclude)
    config.exclude_keywords = _split_lines(exclude_keywords)
    
    val = tts_length_scale.strip()
    config.tts.length_scale = float(val) if val else None
    config.tts.sentence_pause_ms = tts_sentence_pause_ms
    config.tts.paragraph_pause_ms = tts_paragraph_pause_ms
    
    save_config(config, _CONFIG_PATH)
    return RedirectResponse("/settings", status_code=303)


@app.get("/feeds")
def feeds_list(request: Request):
    config = _get_config()
    return templates.TemplateResponse(request, "feeds.html", {"feeds": config.sources.rss.feeds})


@app.post("/feeds")
def feeds_add(url: str = Form(...), topic: str = Form(""), weight: float = Form(1.0)):
    config = _get_config()
    config.sources.rss.feeds.append(
        RssFeedConfig(url=url.strip(), topic=topic.strip() or None, weight=weight)
    )
    save_config(config, _CONFIG_PATH)
    return RedirectResponse("/feeds", status_code=303)


@app.post("/feeds/delete")
def feeds_delete(url: str = Form(...)):
    config = _get_config()
    config.sources.rss.feeds = [feed for feed in config.sources.rss.feeds if feed.url != url]
    save_config(config, _CONFIG_PATH)
    return RedirectResponse("/feeds", status_code=303)


@app.get("/inbox")
def inbox_list(request: Request):
    config = _get_config()
    inbox_path = config.sources.inbox.path
    entries = sorted(inbox_path.glob("*.txt")) if inbox_path.is_dir() else []
    return templates.TemplateResponse(request, "inbox.html", {"entries": entries})


@app.post("/inbox")
def inbox_add(topic: str = Form(""), priority: int = Form(0), content: str = Form(...)):
    config = _get_config()
    inbox_path = config.sources.inbox.path
    inbox_path.mkdir(parents=True, exist_ok=True)

    header_lines = []
    if topic.strip():
        header_lines.append(f"#thema: {topic.strip()}")
    if priority:
        header_lines.append(f"#prio: {priority}")
    entry_text = "\n".join([*header_lines, content.strip()])

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    (inbox_path / f"web-{timestamp}.txt").write_text(entry_text + "\n", encoding="utf-8")
    return RedirectResponse("/inbox", status_code=303)


@app.post("/inbox/delete")
def inbox_delete(filename: str = Form(...)):
    if "/" in filename or ".." in filename or not filename.endswith(".txt"):
        raise HTTPException(status_code=400, detail="Ungültiger Dateiname.")
    config = _get_config()
    file_path = config.sources.inbox.path / filename
    if file_path.is_file():
        file_path.unlink()
    return RedirectResponse("/inbox", status_code=303)


@app.get("/feed.xml")
def feed_xml():
    config = _get_config()
    feed_path = config.delivery.output_dir / "feed.xml"
    if not feed_path.is_file():
        raise HTTPException(status_code=404, detail="Noch keine Episode erzeugt.")
    return FileResponse(feed_path, media_type="application/rss+xml")


@app.get("/episodes/{filename}")
def episode_file(filename: str):
    if "/" in filename or ".." in filename or Path(filename).suffix not in _ALLOWED_EPISODE_SUFFIXES:
        raise HTTPException(status_code=404)
    config = _get_config()
    file_path = config.delivery.output_dir / "episodes" / filename
    if not file_path.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(file_path)


def _latest_episode_date(episodes_dir: Path) -> str | None:
    if not episodes_dir.is_dir():
        return None
    audio_files = sorted(episodes_dir.glob("*.m4b"))
    return audio_files[-1].stem if audio_files else None


def _split_lines(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]
