"""
YouTube Video Summarizer — Streamlit App
=========================================
Run with:
    streamlit run app.py

Requirements:
    pip install streamlit requests

Set your Groq API key either:
  - As environment variable:  export GROQ_API_KEY="gsk_..."
  - Or enter it in the app when running

Get a FREE API key at: https://console.groq.com
(Free tier: 14,400 requests/day — no credit card needed)
"""

import re
import html
import json
import os
import xml.etree.ElementTree as ET
import requests
import streamlit as st

# youtube-transcript-api gives much better caption coverage (auto-captions, translated, etc.)
try:
    from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled
    _YTA_AVAILABLE = True
except ImportError:
    _YTA_AVAILABLE = False

# ─────────────────────────────────────────────────────────────────────────────
# Config file helpers — store API key locally so users never have to retype it
# ─────────────────────────────────────────────────────────────────────────────
_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".yt_summarizer_config.json")

def _load_config() -> dict:
    try:
        with open(_CONFIG_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_config(data: dict):
    try:
        with open(_CONFIG_PATH, "w") as f:
            json.dump(data, f)
    except Exception:
        pass

# ─────────────────────────────────────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="YouTube Summarizer",
    page_icon="🎬",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────────────────────────────────────
# Custom CSS — dark tech, red accent
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap');

    /* ── Animations ─────────────────────────────────────────── */
    @keyframes pulse-ring {
        0%   { box-shadow: 0 0 0 0 rgba(220, 38, 38, 0.45); }
        70%  { box-shadow: 0 0 0 12px rgba(220, 38, 38, 0); }
        100% { box-shadow: 0 0 0 0 rgba(220, 38, 38, 0); }
    }
    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(18px); }
        to   { opacity: 1; transform: translateY(0); }
    }
    @keyframes dot-pulse {
        0%, 100% { opacity: 0.3; transform: scale(1); }
        50%       { opacity: 1;   transform: scale(1.5); }
    }
    @keyframes shimmer {
        0%   { background-position: -400px 0; }
        100% { background-position: 400px 0; }
    }

    /* ── Global ──────────────────────────────────────────────── */
    html, body,
    [data-testid="stAppViewContainer"],
    [data-testid="stApp"] {
        background-color: #09060a !important;
        font-family: 'Inter', sans-serif !important;
        color: #f0e8e8 !important;
    }

    /* Subtle red dot-grid overlay */
    [data-testid="stAppViewContainer"]::before {
        content: '';
        position: fixed;
        inset: 0;
        background-image: radial-gradient(rgba(220,38,38,0.09) 1px, transparent 1px);
        background-size: 30px 30px;
        pointer-events: none;
        z-index: 0;
    }

    /* ── Content container ───────────────────────────────────── */
    .main .block-container {
        padding-top: 2rem !important;
        padding-bottom: 3rem !important;
        max-width: 720px !important;
        position: relative;
        z-index: 1;
    }

    /* ── Hide sidebar toggle + chrome ────────────────────────── */
    [data-testid="stSidebar"]          { display: none !important; }
    [data-testid="collapsedControl"]   { display: none !important; }
    footer, #MainMenu                  { visibility: hidden !important; }
    [data-testid="stHeader"]           { background: transparent !important; }
    [data-testid="stToolbar"]          { display: none !important; }

    /* ── Hero ────────────────────────────────────────────────── */
    .hero-wrapper {
        text-align: center;
        padding: 1.2rem 0 1.8rem;
        animation: fadeInUp 0.6s ease both;
    }
    .hero-icon {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 66px; height: 66px;
        border-radius: 18px;
        background: linear-gradient(135deg, rgba(220,38,38,0.18), rgba(185,28,28,0.1));
        border: 1px solid rgba(220,38,38,0.4);
        font-size: 2rem;
        margin-bottom: 1.1rem;
        animation: pulse-ring 2.8s ease-out infinite;
        box-shadow: 0 0 30px rgba(220,38,38,0.12);
    }
    .hero-title {
        font-size: 2.4rem;
        font-weight: 800;
        letter-spacing: -0.025em;
        background: linear-gradient(135deg, #ffffff 0%, #ff6b6b 55%, #dc2626 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin: 0 0 0.35rem;
        line-height: 1.15;
    }
    .hero-sub {
        color: #9a7575;
        font-size: 0.93rem;
        font-weight: 400;
        margin: 0;
    }

    /* ── Input labels ────────────────────────────────────────── */
    .field-label {
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: #c07878;
        margin-bottom: 0.35rem;
    }

    /* ── Text inputs ─────────────────────────────────────────── */
    .stTextInput > div > div > input {
        background: #150d0d !important;
        border: 1px solid rgba(220,38,38,0.45) !important;
        border-radius: 10px !important;
        color: #f2e4e4 !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.87rem !important;
        padding: 0.7rem 1rem !important;
        transition: all 0.22s ease !important;
        box-shadow: inset 0 1px 4px rgba(0,0,0,0.5) !important;
    }
    .stTextInput > div > div > input:focus {
        border-color: rgba(220,38,38,0.85) !important;
        box-shadow: 0 0 0 3px rgba(220,38,38,0.15),
                    inset 0 1px 4px rgba(0,0,0,0.5) !important;
        outline: none !important;
    }
    .stTextInput > div > div > input::placeholder {
        color: #4a2e2e !important;
    }

    /* ── Buttons ─────────────────────────────────────────────── */
    .stButton > button {
        border-radius: 9px !important;
        font-weight: 700 !important;
        font-size: 0.87rem !important;
        letter-spacing: 0.05em !important;
        transition: all 0.2s ease !important;
        border: none !important;
        height: 46px !important;
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #dc2626, #991b1b) !important;
        color: #ffffff !important;
        box-shadow: 0 4px 22px rgba(220,38,38,0.4) !important;
    }
    .stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, #ef4444, #b91c1c) !important;
        box-shadow: 0 4px 32px rgba(220,38,38,0.6) !important;
        transform: translateY(-1px) !important;
    }
    .stButton > button[kind="secondary"] {
        background: #150d0d !important;
        color: #c08080 !important;
        border: 1px solid rgba(220,38,38,0.35) !important;
    }
    .stButton > button[kind="secondary"]:hover {
        border-color: rgba(220,38,38,0.7) !important;
        color: #ef4444 !important;
        background: rgba(220,38,38,0.1) !important;
    }

    /* ── Progress bar ────────────────────────────────────────── */
    [data-testid="stProgress"] > div > div {
        background: linear-gradient(90deg, #dc2626, #7f1d1d) !important;
        box-shadow: 0 0 10px rgba(220,38,38,0.5) !important;
        border-radius: 4px !important;
    }
    [data-testid="stProgress"] > div {
        background: #180d0d !important;
        border-radius: 4px !important;
        height: 4px !important;
    }

    /* ── Instructions card ───────────────────────────────────── */
    .instructions-card {
        background: #140c0c;
        border: 1px solid rgba(220,38,38,0.35);
        border-radius: 12px;
        padding: 1.1rem 1.4rem;
        margin: 1rem 0 0.5rem;
        animation: fadeInUp 0.5s 0.1s ease both;
    }
    .instructions-title {
        font-size: 0.7rem;
        font-weight: 700;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: #ef4444;
        margin: 0 0 0.75rem;
    }
    .instructions-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 0.65rem 1.5rem;
    }
    .instruction-step {
        display: flex;
        align-items: flex-start;
        gap: 0.6rem;
        font-size: 0.83rem;
        color: #c8a8a8;
        line-height: 1.5;
    }
    .step-num {
        flex-shrink: 0;
        width: 20px; height: 20px;
        border-radius: 50%;
        background: rgba(220,38,38,0.2);
        border: 1px solid rgba(220,38,38,0.5);
        color: #ef4444;
        font-size: 0.68rem;
        font-weight: 700;
        display: flex; align-items: center; justify-content: center;
    }

    /* ── Divider ─────────────────────────────────────────────── */
    hr {
        border: none !important;
        height: 1px !important;
        background: linear-gradient(90deg,
            transparent,
            rgba(220,38,38,0.45) 30%,
            rgba(220,38,38,0.45) 70%,
            transparent) !important;
        margin: 1.4rem 0 !important;
    }

    /* ── Video card (thumbnail + info) ──────────────────────── */
    [data-testid="stImage"] img {
        border-radius: 10px !important;
        border: 1px solid rgba(220,38,38,0.2) !important;
        box-shadow: 0 4px 24px rgba(0,0,0,0.6) !important;
    }

    /* ── Expander ────────────────────────────────────────────── */
    [data-testid="stExpander"] {
        background: #120a0a !important;
        border: 1px solid rgba(220,38,38,0.4) !important;
        border-radius: 12px !important;
        overflow: hidden !important;
        animation: fadeInUp 0.45s ease both;
        box-shadow: 0 4px 28px rgba(0,0,0,0.5) !important;
    }
    [data-testid="stExpander"] summary {
        background: #160c0c !important;
        color: #ff6b6b !important;
        font-weight: 700 !important;
        font-size: 0.82rem !important;
        letter-spacing: 0.08em !important;
        padding: 0.85rem 1.2rem !important;
        border-bottom: 1px solid rgba(220,38,38,0.3) !important;
        text-transform: uppercase !important;
    }
    [data-testid="stExpander"] summary:hover {
        background: rgba(220,38,38,0.08) !important;
    }
    [data-testid="stExpander"] > div > div {
        padding: 1rem 1.2rem !important;
        color: #ddc8c8 !important;
        font-size: 0.92rem !important;
        line-height: 1.75 !important;
    }

    /* ── Tabs ────────────────────────────────────────────────── */
    [data-testid="stTabs"] [role="tablist"] {
        background: #160c0c !important;
        border-radius: 12px 12px 0 0 !important;
        border: 1px solid rgba(220,38,38,0.4) !important;
        border-bottom: none !important;
        padding: 0.4rem 0.6rem 0 !important;
        gap: 4px !important;
    }
    [data-testid="stTabs"] [role="tab"] {
        color: #9a6060 !important;
        font-size: 0.8rem !important;
        font-weight: 700 !important;
        letter-spacing: 0.06em !important;
        border-radius: 8px 8px 0 0 !important;
        padding: 0.45rem 1rem !important;
        transition: all 0.2s !important;
        border: none !important;
        background: transparent !important;
        text-transform: uppercase !important;
    }
    [data-testid="stTabs"] [role="tab"]:hover {
        color: #ff8080 !important;
        background: rgba(220,38,38,0.1) !important;
    }
    [data-testid="stTabs"] [role="tab"][aria-selected="true"] {
        color: #ff6b6b !important;
        background: rgba(220,38,38,0.15) !important;
        box-shadow: inset 0 -2px 0 #ef4444 !important;
    }
    [data-testid="stTabs"] [role="tabpanel"] {
        background: #120a0a !important;
        border: 1px solid rgba(220,38,38,0.4) !important;
        border-top: none !important;
        border-radius: 0 0 12px 12px !important;
        padding: 1.2rem 1.4rem !important;
        color: #ddc8c8 !important;
        font-size: 0.92rem !important;
        line-height: 1.75 !important;
        animation: fadeInUp 0.35s ease both;
        box-shadow: 0 8px 32px rgba(0,0,0,0.4) !important;
    }

    /* Timestamps in tabs */
    [data-testid="stTabs"] a code {
        background: rgba(220,38,38,0.18) !important;
        color: #ff8080 !important;
        border: 1px solid rgba(220,38,38,0.45) !important;
        border-radius: 5px !important;
        padding: 1px 6px !important;
        font-size: 0.76rem !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-weight: 600 !important;
    }

    /* Blockquotes */
    [data-testid="stTabs"] blockquote {
        border-left: 3px solid #ef4444 !important;
        background: rgba(220,38,38,0.1) !important;
        padding: 0.6rem 1rem !important;
        border-radius: 0 8px 8px 0 !important;
        color: #e8c8c8 !important;
        font-style: italic !important;
        margin: 0.6rem 0 !important;
    }

    /* ── Raw textarea ────────────────────────────────────────── */
    .stTextArea textarea {
        background: #0e0808 !important;
        border: 1px solid rgba(220,38,38,0.35) !important;
        border-radius: 8px !important;
        color: #c09090 !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.77rem !important;
    }

    /* ── Status text ─────────────────────────────────────────── */
    .status-line {
        color: #ff8080;
        font-size: 0.84rem;
        padding: 0.45rem 0;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }

    /* ── Scrollbar ───────────────────────────────────────────── */
    ::-webkit-scrollbar { width: 4px; }
    ::-webkit-scrollbar-track { background: #09060a; }
    ::-webkit-scrollbar-thumb { background: rgba(220,38,38,0.35); border-radius: 4px; }
    ::-webkit-scrollbar-thumb:hover { background: rgba(220,38,38,0.6); }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Core logic
# ─────────────────────────────────────────────────────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

CHUNK_SECONDS = 60
GROQ_URL      = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL    = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """\
You are an expert video analyst. You receive a YouTube transcript in chunked paragraphs,
each prefixed with a timestamp like [MM:SS] or [H:MM:SS].

Produce a structured summary in this EXACT format (use these exact section headers):

## 📋 Video Overview
2–4 sentence executive summary of the whole video.

## 📌 Key Topics
For each major topic/section, output a line in this format:
**[TIMESTAMP] Topic Title** — 1–2 sentence description.

## 💡 Key Takeaways
- Bullet point insight 1
- Bullet point insight 2
(3–7 bullets total)

## 💬 Memorable Quotes
> "Exact quote from transcript." — [TIMESTAMP]
(1–3 quotes)

Use only these four sections. Be concise but substantive.
"""


def extract_video_id(url: str) -> str:
    m = re.search(r"(?:v=|youtu\.be/|embed/|shorts/)([A-Za-z0-9_-]{11})", url)
    if m:
        return m.group(1)
    raise ValueError(f"Could not find a YouTube video ID in: {url!r}")


def seconds_to_ts(seconds: float) -> str:
    s = int(seconds)
    h, m, s = s // 3600, (s % 3600) // 60, s % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def get_video_metadata(video_id: str) -> dict:
    try:
        resp = requests.get(
            f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json",
            headers=HEADERS, timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            return {
                "title":     data.get("title", "Unknown Title"),
                "channel":   data.get("author_name", "Unknown Channel"),
                "thumbnail": f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
            }
    except Exception:
        pass
    return {
        "title":     "YouTube Video",
        "channel":   "Unknown",
        "thumbnail": f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
    }


def get_video_info(video_id: str) -> dict:
    """Scrape description, duration, and chapter markers from the YouTube watch page."""
    result = {"description": "", "duration_seconds": 0, "chapters": []}
    try:
        url  = f"https://www.youtube.com/watch?v={video_id}"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        page = resp.text

        # Description
        m = re.search(r'"shortDescription"\s*:\s*"((?:[^"\\]|\\.)*)"', page)
        if m:
            raw = m.group(1)
            result["description"] = html.unescape(
                raw.replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\")
            )

        # Duration (lengthSeconds inside ytInitialPlayerResponse)
        m2 = re.search(r'"lengthSeconds"\s*:\s*"(\d+)"', page)
        if m2:
            result["duration_seconds"] = int(m2.group(1))

        # Chapters (if the creator added them — they appear in the description as timestamps)
        chapter_pattern = re.compile(r'(\d{1,2}:\d{2}(?::\d{2})?)\s+(.+)')
        chapters = []
        for line in result["description"].splitlines():
            cm = chapter_pattern.match(line.strip())
            if cm:
                chapters.append({"ts": cm.group(1), "title": cm.group(2).strip()})
        result["chapters"] = chapters

    except Exception:
        pass
    return result


def get_video_description(video_id: str) -> str:
    """Convenience wrapper kept for backward compat."""
    return get_video_info(video_id)["description"]


def get_caption_tracks(video_id: str) -> list:
    url  = f"https://www.youtube.com/watch?v={video_id}"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    page = resp.text

    match = re.search(r"ytInitialPlayerResponse\s*=\s*(\{.*?\});\s*(?:var|const|let|window)", page, re.DOTALL)
    if not match:
        match = re.search(r"ytInitialPlayerResponse\s*=\s*(\{.+)", page, re.DOTALL)

    if match:
        blob = match.group(1)
        depth, end = 0, 0
        for i, ch in enumerate(blob):
            if ch == '{':   depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        try:
            data   = json.loads(blob[:end])
            tracks = (data.get("captions", {})
                         .get("playerCaptionsTracklistRenderer", {})
                         .get("captionTracks", []))
            return tracks
        except Exception:
            pass
    return []


def parse_transcript_xml(xml_text: str) -> list:
    segments = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        xml_text = re.sub(r"<\?xml[^>]*\?>", "", xml_text)
        root = ET.fromstring(f"<root>{xml_text}</root>")
    for tag in root.iter("text"):
        start = float(tag.get("start", 0))
        dur   = float(tag.get("dur", 0))
        text  = html.unescape(tag.text or "").strip()
        if text:
            segments.append({"start": start, "duration": dur, "text": text})
    return segments


def _yta_segments(video_id: str) -> list:
    """Use youtube-transcript-api to fetch segments. Raises on failure."""
    # Try simple get_transcript first (fastest path)
    for langs in [["en", "en-US", "en-GB"], None]:
        try:
            kwargs = {} if langs is None else {"languages": langs}
            data = YouTubeTranscriptApi.get_transcript(video_id, **kwargs)
            segments = []
            for entry in data:
                if hasattr(entry, "start"):
                    start, dur, text = entry.start, getattr(entry, "duration", 0), getattr(entry, "text", "")
                else:
                    start, dur, text = entry.get("start", 0), entry.get("duration", 0), entry.get("text", "")
                text = html.unescape(str(text)).strip()
                if text:
                    segments.append({"start": start, "duration": dur, "text": text})
            if segments:
                return segments
        except Exception:
            continue
    raise RuntimeError("yta_failed")


def fetch_transcript(video_id: str) -> list:
    """Try three methods to get a real transcript, raise RuntimeError('no_captions') if all fail."""

    # ── Method 1: youtube-transcript-api (most reliable) ──────────────────────
    if _YTA_AVAILABLE:
        try:
            return _yta_segments(video_id)
        except Exception:
            pass

    # ── Method 2: manual scraping via ytInitialPlayerResponse ─────────────────
    tracks = get_caption_tracks(video_id)
    if tracks:
        def rank(t):
            code = t.get("languageCode", "")
            kind = t.get("kind", "")
            if code.startswith("en") and kind != "asr": return 0
            if code.startswith("en"):                   return 1
            if kind != "asr":                           return 2
            return 3

        tracks.sort(key=rank)
        try:
            resp = requests.get(tracks[0]["baseUrl"], headers=HEADERS, timeout=15)
            resp.raise_for_status()
            segments = parse_transcript_xml(resp.text)
            if segments:
                return segments
        except Exception:
            pass

    # ── Method 3: direct timedtext API (catches auto-generated captions) ───────
    # YouTube's timedtext endpoint works for many videos even when the track
    # list isn't exposed in the page HTML.
    for lang in ["en", "en-US", "en-GB"]:
        for kind in ["asr", ""]:   # asr = auto-generated speech recognition
            params = {
                "v":    video_id,
                "lang": lang,
                "fmt":  "json3",
            }
            if kind:
                params["kind"] = kind
            try:
                r = requests.get(
                    "https://www.youtube.com/api/timedtext",
                    params=params,
                    headers=HEADERS,
                    timeout=15,
                )
                if r.status_code == 200 and r.text.strip():
                    data = r.json()
                    events = data.get("events", [])
                    segments = []
                    for ev in events:
                        start_ms = ev.get("tStartMs", 0)
                        dur_ms   = ev.get("dDurationMs", 0)
                        segs     = ev.get("segs", [])
                        text     = html.unescape(
                            "".join(s.get("utf8", "") for s in segs)
                        ).strip()
                        if text and text != "\n":
                            segments.append({
                                "start":    start_ms / 1000,
                                "duration": dur_ms   / 1000,
                                "text":     text,
                            })
                    if segments:
                        return segments
            except Exception:
                continue

    raise RuntimeError("no_captions")


def build_transcript_text(segments: list) -> str:
    if not segments:
        return ""
    lines, chunk_start, current = [], segments[0]["start"], []
    for seg in segments:
        if seg["start"] - chunk_start >= CHUNK_SECONDS and current:
            lines.append(f"[{seconds_to_ts(chunk_start)}] {' '.join(current)}")
            chunk_start, current = seg["start"], []
        current.append(seg["text"])
    if current:
        lines.append(f"[{seconds_to_ts(chunk_start)}] {' '.join(current)}")
    return "\n\n".join(lines)


def _call_groq(prompt_text: str, api_key: str, max_tokens: int = 2048) -> str:
    """Core helper: send a prompt to Groq and return the response text."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt_text},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.4,
    }
    resp = requests.post(GROQ_URL, json=payload, headers=headers, timeout=90)
    if resp.status_code != 200:
        try:
            err = resp.json().get("error", {}).get("message", resp.text[:300])
        except Exception:
            err = resp.text[:300]
        raise RuntimeError(f"Groq API error {resp.status_code}: {err}")
    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Unexpected Groq response format: {e}\n{data}")


def summarize_with_groq(segments: list, video_url: str, api_key: str) -> str:
    """Build a chunked transcript and send to Groq for summarization."""
    if not segments:
        raise RuntimeError(
            "No captions could be extracted from this video. "
            "It may have auto-captions disabled, be age-restricted, or region-locked. "
            "Try a different video."
        )
    lines, chunk_start, current = [], segments[0]["start"], []
    for seg in segments:
        if seg["start"] - chunk_start >= CHUNK_SECONDS and current:
            lines.append(f"[{seconds_to_ts(chunk_start)}] {' '.join(current)}")
            chunk_start, current = seg["start"], []
        current.append(seg["text"])
    if current:
        lines.append(f"[{seconds_to_ts(chunk_start)}] {' '.join(current)}")
    transcript_text = "\n\n".join(lines)

    prompt = (
        f"Summarize this YouTube video.\nURL: {video_url}\n\n"
        f"--- TRANSCRIPT ---\n{transcript_text}\n--- END ---"
    )
    return _call_groq(prompt, api_key, max_tokens=2048)


def summarize_from_description(title: str, channel: str, description: str,
                               video_url: str, api_key: str,
                               duration_seconds: int = 0, chapters: list = None) -> str:
    """Fallback: generate a detailed summary with estimated timestamps from metadata."""
    if not description.strip() and not title.strip():
        raise RuntimeError(
            "No captions or description could be found for this video. "
            "It may be private, age-restricted, or region-locked."
        )

    chapters = chapters or []
    duration_str = seconds_to_ts(duration_seconds) if duration_seconds else "unknown"

    # Build chapter hints if the creator provided timestamps in the description
    chapter_hint = ""
    if chapters:
        chapter_hint = "\n\nChapter markers found in description:\n" + "\n".join(
            f"  [{c['ts']}] {c['title']}" for c in chapters
        )

    # Build duration hint for evenly-spaced estimated timestamps
    duration_hint = ""
    if duration_seconds and not chapters:
        n_sections = min(6, max(3, duration_seconds // 120))  # 1 section per ~2 min
        step = duration_seconds // n_sections
        duration_hint = (
            f"\n\nThe video is {duration_str} long. "
            f"Spread your Key Topics timestamps evenly: "
            + ", ".join(seconds_to_ts(i * step) for i in range(n_sections))
        )

    prompt = (
        f"Title: {title}\nChannel: {channel}\nURL: {video_url}\n"
        f"Video duration: {duration_str}\n\n"
        f"Description:\n{description}"
        f"{chapter_hint}"
        f"{duration_hint}\n\n"
        "IMPORTANT: No transcript was available, so you must infer the content "
        "from the title, description, and any chapter markers above.\n"
        "- For Key Topics: use the chapter markers if provided, otherwise spread "
        "timestamps evenly across the video duration to give realistic time references.\n"
        "- For Memorable Quotes: if no direct quotes exist, write the most likely "
        "insight or takeaway phrased as a quote, with an estimated timestamp.\n"
        "- Be specific and detailed — do not write vague summaries."
    )
    return _call_groq(prompt, api_key, max_tokens=1500)


def parse_summary_sections(summary: str) -> dict:
    sections = {"overview": "", "topics": "", "takeaways": "", "quotes": "", "raw": summary}
    mapping  = {
        "video overview":   "overview",
        "key topics":       "topics",
        "key takeaways":    "takeaways",
        "memorable quotes": "quotes",
    }
    current_key, buffer = None, []

    for line in summary.splitlines():
        header_match = re.match(r"^#{1,3}\s+(.+)", line)
        if header_match:
            if current_key and buffer:
                sections[current_key] = "\n".join(buffer).strip()
            header_text = re.sub(r"[^\w\s]", "", header_match.group(1)).strip().lower()
            current_key = next((v for k, v in mapping.items() if k in header_text), None)
            buffer = []
        elif current_key:
            buffer.append(line)

    if current_key and buffer:
        sections[current_key] = "\n".join(buffer).strip()
    return sections


# ─────────────────────────────────────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────────────────────────────────────

# Hero
st.markdown("""
<div class="hero-wrapper">
    <div class="hero-icon">🎬</div>
    <h1 class="hero-title">YouTube Summarizer</h1>
    <p class="hero-sub">Paste any YouTube URL and get an AI-powered summary in seconds</p>
</div>
""", unsafe_allow_html=True)

# API key — load from config file, then env var as fallback
_cfg = _load_config()
_saved_key   = _cfg.get("groq_api_key", "") or _cfg.get("gemini_api_key", "")
_env_key     = os.environ.get("GROQ_API_KEY", "")
_default_key = _saved_key or _env_key

_key_col, _status_col = st.columns([6, 1])
with _key_col:
    st.markdown('<div class="field-label">Groq API Key <span style="font-size:0.75rem;color:#9a6060">(free · console.groq.com)</span></div>', unsafe_allow_html=True)
    api_key_input = st.text_input(
        label="api_key",
        value=_default_key,
        type="password",
        placeholder="gsk_...",
        label_visibility="collapsed",
    )
with _status_col:
    st.markdown("<div style='height:1.6rem'></div>", unsafe_allow_html=True)
    if st.button("💾", help="Save key for future sessions"):
        if api_key_input:
            _save_config({**_cfg, "groq_api_key": api_key_input})
            st.success("Saved!")
        else:
            st.warning("No key entered.")

# Auto-save if a new key was typed (differs from what's stored)
if api_key_input and api_key_input != _saved_key:
    _save_config({**_cfg, "groq_api_key": api_key_input})

api_key = api_key_input or _default_key

if _default_key:
    st.markdown(
        '<p style="font-size:0.72rem;color:#7a9a6a;margin:-0.4rem 0 0.6rem">✔ API key loaded — ready to go</p>',
        unsafe_allow_html=True,
    )

# URL input
st.markdown('<div class="field-label" style="margin-top:0.85rem">YouTube URL</div>', unsafe_allow_html=True)
url_input = st.text_input(
    label="url",
    placeholder="https://www.youtube.com/watch?v=...",
    label_visibility="collapsed",
)

# Buttons
col1, col2 = st.columns([5, 1])
with col1:
    summarize_btn = st.button("▶  Analyze Video", type="primary", use_container_width=True)
with col2:
    clear_btn = st.button("✕", use_container_width=True)

if clear_btn:
    st.session_state.pop("last_summary", None)
    st.session_state.pop("last_url", None)
    st.rerun()

# ── How to use ───────────────────────────────────────────────────────────────
st.markdown("""
<div class="instructions-card">
    <div class="instructions-title">How to use</div>
    <div class="instructions-grid">
        <div class="instruction-step">
            <div class="step-num">1</div>
            <span>Get a <strong style="color:#ff8080">completely free</strong> API key at <strong style="color:#ff8080">console.groq.com</strong> — no credit card needed</span>
        </div>
        <div class="instruction-step">
            <div class="step-num">2</div>
            <span>Paste your Gemini API key into the field above — it's <strong style="color:#ff8080">saved automatically</strong> so you only need to do this once</span>
        </div>
        <div class="instruction-step">
            <div class="step-num">3</div>
            <span>Copy any YouTube URL and paste it into the URL field, then click <strong style="color:#ff6b6b">Analyze Video</strong></span>
        </div>
        <div class="instruction-step">
            <div class="step-num">4</div>
            <span>Browse your summary: Overview, Key Topics with clickable timestamps, Takeaways &amp; Quotes</span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown("---")

# ─────────────────────────────────────────────────────────────────────────────
# Analyze action
# ─────────────────────────────────────────────────────────────────────────────
if summarize_btn:
    if not url_input.strip():
        st.warning("Please paste a YouTube URL first.")
    elif not api_key:
        st.error("Please enter your Groq API key above.")
    else:
        st.session_state.pop("last_summary", None)
        status_area = st.empty()
        progress    = st.progress(0)

        def status(msg, pct):
            status_area.markdown(
                f"<div class='status-line'>◈ &nbsp;{msg}</div>",
                unsafe_allow_html=True,
            )
            progress.progress(pct)

        try:
            status("Resolving video ID…", 10)
            video_id = extract_video_id(url_input.strip())

            status("Fetching video metadata…", 25)
            meta = get_video_metadata(video_id)

            yta_status = "✓ installed" if _YTA_AVAILABLE else "✗ not found — run: pip install youtube-transcript-api"
            status(f"Fetching captions… (youtube-transcript-api: {yta_status})", 45)
            used_fallback = False
            try:
                segments = fetch_transcript(video_id)
                status(f"Got {len(segments)} caption segments — sending to Groq…", 65)
                summary = summarize_with_groq(segments, url_input.strip(), api_key)
            except RuntimeError:
                # No captions — fall back to description + duration + chapters
                used_fallback = True
                status("No captions — analysing video metadata for timestamps…", 52)
                info = get_video_info(video_id)
                status("Generating summary with estimated timestamps…", 68)
                summary = summarize_from_description(
                    meta.get("title", ""),
                    meta.get("channel", ""),
                    info["description"],
                    url_input.strip(),
                    api_key,
                    duration_seconds=info["duration_seconds"],
                    chapters=info["chapters"],
                )
            progress.progress(100)

            st.session_state["last_summary"]    = summary
            st.session_state["last_url"]        = url_input.strip()
            st.session_state["last_meta"]       = meta
            st.session_state["last_video_id"]   = video_id
            st.session_state["used_fallback"]   = used_fallback

            msg = "✅  Done — summary based on video description (no captions available)." if used_fallback else "✅  Done — your summary is ready below."
            status_area.success(msg)
            progress.empty()

        except ValueError as e:
            status_area.error(f"❌  Invalid URL: {e}")
            progress.empty()
        except RuntimeError as e:
            status_area.error(f"❌  {e}")
            progress.empty()
        except requests.RequestException as e:
            status_area.error(f"❌  Network error: {e}")
            progress.empty()


# ─────────────────────────────────────────────────────────────────────────────
# Render summary
# ─────────────────────────────────────────────────────────────────────────────
if "last_summary" in st.session_state:
    summary  = st.session_state["last_summary"]
    meta     = st.session_state.get("last_meta", {})
    video_id = st.session_state.get("last_video_id", "")
    yt_url   = st.session_state.get("last_url", f"https://www.youtube.com/watch?v={video_id}")

    # Video card
    col_thumb, col_info = st.columns([1, 2])
    with col_thumb:
        st.image(meta.get("thumbnail", ""), use_container_width=True)
    with col_info:
        st.markdown(
            f"<div style='padding-top:0.3rem'>"
            f"<p style='font-size:1rem;font-weight:700;color:#f5e8e8;margin:0 0 0.25rem'>"
            f"{meta.get('title','Video')}</p>"
            f"<p style='font-size:0.82rem;color:#9a6868;margin:0 0 0.7rem'>"
            f"{meta.get('channel','')}</p>"
            f"<a href='{yt_url}' target='_blank' "
            f"style='font-size:0.82rem;color:#ff6b6b;text-decoration:none;font-weight:600'>"
            f"▶ &nbsp;Watch on YouTube</a>"
            f"</div>",
            unsafe_allow_html=True,
        )

    if st.session_state.get("used_fallback"):
        st.markdown(
            "<div style='background:rgba(220,38,38,0.08);border:1px solid rgba(220,38,38,0.3);"
            "border-radius:8px;padding:0.6rem 1rem;font-size:0.82rem;color:#ff8080;margin-bottom:0.5rem'>"
            "⚠️ &nbsp;No captions were available for this video — summary generated from the video description only. "
            "Timestamps may not be accurate."
            "</div>",
            unsafe_allow_html=True,
        )

    st.markdown("---")

    sections = parse_summary_sections(summary)

    if sections["overview"]:
        with st.expander("◈  Video Overview", expanded=True):
            st.markdown(sections["overview"])

    tab1, tab2, tab3 = st.tabs(["◈  Key Topics", "◈  Takeaways", "◈  Quotes"])

    with tab1:
        if sections["topics"]:
            def make_ts_link(m):
                ts    = m.group(1)
                parts = ts.split(":")
                secs  = (int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                         if len(parts) == 3
                         else int(parts[0]) * 60 + int(parts[1]))
                return f"[`{ts}`]({yt_url}&t={secs}s)"

            for line in sections["topics"].splitlines():
                if line.strip():
                    st.markdown(re.sub(r"\[(\d+:\d+(?::\d+)?)\]", make_ts_link, line))
        else:
            st.markdown(summary)

    with tab2:
        st.markdown(sections["takeaways"] if sections["takeaways"] else "_No takeaways found._")

    with tab3:
        st.markdown(sections["quotes"] if sections["quotes"] else "_No memorable quotes found._")

    st.markdown("---")
    with st.expander("◈  Raw Markdown (copy-friendly)", expanded=False):
        st.text_area(label="raw", value=summary, height=320, label_visibility="collapsed")


# ─────────────────────────────────────────────────────────────────────────────
# PyCharm direct-run support
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import subprocess
    import sys

    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        _already_running = get_script_run_ctx() is not None
    except Exception:
        _already_running = False

    if not _already_running:
        sys.exit(subprocess.call(["streamlit", "run", __file__] + sys.argv[1:]))
