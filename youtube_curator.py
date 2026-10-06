"""Part 2: find and rank YouTube videos for a roadmap stage.

Quota notes (YouTube Data API v3, default 10,000 units/day):
  - search.list   = 100 units  -> cached in SQLite for 7 days
  - videos.list   = 1 unit     -> not cached (view counts stay fresh)
  - channels.list = 1 unit     -> not cached
"""
import json
import math
import os
import re
import sqlite3
import time
from datetime import datetime, timezone

from dotenv import load_dotenv
from googleapiclient.discovery import build

from schemas import Stage, Video

load_dotenv()

DB_PATH = os.getenv("CACHE_DB", "cache.db")
CACHE_TTL_DAYS = 7
MIN_DURATION_SEC = 240      # drops Shorts and trailers
MIN_VIEWS = 1000
MAX_PER_CHANNEL = 2         # keeps results diverse

# Score weights (sum to 1.0)
W_VIEWS, W_LIKES, W_RECENCY, W_CHANNEL, W_DURATION = 0.40, 0.25, 0.15, 0.10, 0.10


# ---------------------------------------------------------------- cache
def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS search_cache ("
        "query TEXT PRIMARY KEY, video_ids TEXT, created_at REAL)"
    )
    return conn


def _youtube():
    key = os.getenv("YOUTUBE_API_KEY")
    if not key:
        raise RuntimeError("YOUTUBE_API_KEY is not set in .env")
    return build("youtube", "v3", developerKey=key, cache_discovery=False)


# ---------------------------------------------------------------- API calls
def search_video_ids(query: str, yt, max_results: int = 15) -> list[str]:
    conn = _db()
    try:
        row = conn.execute(
            "SELECT video_ids, created_at FROM search_cache WHERE query = ?", (query,)
        ).fetchone()
        if row and time.time() - row[1] < CACHE_TTL_DAYS * 86400:
            return json.loads(row[0])

        resp = yt.search().list(
            q=query,
            part="id",
            type="video",
            maxResults=max_results,
            relevanceLanguage="en",
            safeSearch="moderate",
            videoEmbeddable="true",
        ).execute()
        ids = [item["id"]["videoId"] for item in resp.get("items", [])]

        conn.execute(
            "INSERT OR REPLACE INTO search_cache VALUES (?, ?, ?)",
            (query, json.dumps(ids), time.time()),
        )
        conn.commit()
        return ids
    finally:
        conn.close()


def fetch_video_details(ids: list[str], yt) -> list[dict]:
    items = []
    for i in range(0, len(ids), 50):
        resp = yt.videos().list(
            part="snippet,statistics,contentDetails", id=",".join(ids[i : i + 50])
        ).execute()
        items.extend(resp.get("items", []))
    return items


def fetch_subscriber_counts(channel_ids: set[str], yt) -> dict[str, int]:
    counts: dict[str, int] = {}
    ids = list(channel_ids)
    for i in range(0, len(ids), 50):
        resp = yt.channels().list(part="statistics", id=",".join(ids[i : i + 50])).execute()
        for item in resp.get("items", []):
            stats = item.get("statistics", {})
            counts[item["id"]] = 0 if stats.get("hiddenSubscriberCount") else int(stats.get("subscriberCount", 0))
    return counts


# ---------------------------------------------------------------- scoring
_DURATION_RE = re.compile(r"^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$")


def parse_duration(iso: str) -> int:
    """'PT1H2M3S' -> 3723 seconds. Returns 0 for live streams ('P0D')."""
    m = _DURATION_RE.match(iso or "")
    if not m:
        return 0
    d, h, mi, s = (int(x) if x else 0 for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def score_video(views: int, likes: int | None, age_years: float, subs: int, duration_sec: int) -> float:
    views_s = min(math.log10(views + 1) / 7, 1.0)                       # 10M views -> 1.0
    likes_s = 0.5 if likes is None else min((likes / max(views, 1)) / 0.04, 1.0)  # 4% like rate -> 1.0
    recency_s = max(0.0, 1 - age_years / 6)                              # 6+ years old -> 0
    channel_s = min(math.log10(subs + 1) / 7, 1.0)                       # 10M subs -> 1.0
    if duration_sec < 600:
        duration_s = 0.6
    elif duration_sec <= 4 * 3600:
        duration_s = 1.0
    else:
        duration_s = 0.7                                                  # very long full courses
    total = (
        W_VIEWS * views_s + W_LIKES * likes_s + W_RECENCY * recency_s
        + W_CHANNEL * channel_s + W_DURATION * duration_s
    )
    return round(total, 4)


# ---------------------------------------------------------------- main entry
def curate_stage_videos(stage: Stage, top_n: int = 4, queries_per_stage: int = 2) -> list[Video]:
    yt = _youtube()

    ids: list[str] = []
    for q in stage.search_queries[:queries_per_stage]:
        for vid in search_video_ids(q, yt):
            if vid not in ids:
                ids.append(vid)
    if not ids:
        return []

    details = fetch_video_details(ids, yt)
    subs = fetch_subscriber_counts({d["snippet"]["channelId"] for d in details}, yt)
    now = datetime.now(timezone.utc)

    scored: list[Video] = []
    for d in details:
        snip, stats = d["snippet"], d.get("statistics", {})
        duration = parse_duration(d["contentDetails"].get("duration", ""))
        views = int(stats.get("viewCount", 0))
        if duration < MIN_DURATION_SEC or views < MIN_VIEWS:
            continue

        likes = int(stats["likeCount"]) if "likeCount" in stats else None
        published = datetime.fromisoformat(snip["publishedAt"].replace("Z", "+00:00"))
        age_years = (now - published).days / 365.25

        scored.append(
            Video(
                title=snip["title"],
                url=f"https://www.youtube.com/watch?v={d['id']}",
                channel=snip["channelTitle"],
                views=views,
                score=score_video(views, likes, age_years, subs.get(snip["channelId"], 0), duration),
                duration_minutes=round(duration / 60, 1),
                published=published.strftime("%Y-%m-%d"),
                thumbnail=snip.get("thumbnails", {}).get("medium", {}).get("url", ""),
            )
        )

    scored.sort(key=lambda v: v.score, reverse=True)

    # keep at most MAX_PER_CHANNEL videos from one channel
    result, per_channel = [], {}
    for v in scored:
        if per_channel.get(v.channel, 0) >= MAX_PER_CHANNEL:
            continue
        per_channel[v.channel] = per_channel.get(v.channel, 0) + 1
        result.append(v)
        if len(result) == top_n:
            break
    return result
