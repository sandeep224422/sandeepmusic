import asyncio
import os
import re

from ytmusicapi import YTMusic

from zefmusic import YouTube, nand
from zefmusic.misc import db
from zefmusic.platforms.Youtube import is_external_path
from zefmusic.utils.autoplay_state import (
    MAX_AUTOPLAY_TRACKS,
    get_autoplay_progress,
    increment_autoplay_progress,
)
from zefmusic.utils.database import get_lang, is_autoplay
from zefmusic.utils.formatters import seconds_to_min
from zefmusic.utils.logger import autoplay_logs
from zefmusic.utils.rich_stream import send_now_playing_rich
from zefmusic.utils.stream.history import record_played, was_recently_played
from zefmusic.utils.stream.queue import put_queue
from zefmusic.utils.stream.seed import get_seed
from zefmusic.utils.thumbnails import get_thumb
from strings import get_string

PREFETCH_AFTER = 5
DOWNLOAD_TIMEOUT = 90
FALLBACK_TIMEOUT = 40
READY_WAIT = 45
API_TIMEOUT = 25
API_RETRIES = 3
API_RETRY_DELAY = 1
RADIO_LIMIT = 25
MAX_TRACK_SECONDS = 900  # 15 min se lambe tracks autoplay me skip

_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_cache = {}
_ytmusic = None


# ---------------------------------------------------------------- ytmusicapi
def _length_to_seconds(value) -> int:
    try:
        parts = [int(x) for x in str(value).split(":")]
    except Exception:
        return 0
    seconds = 0
    for part in parts:
        seconds = seconds * 60 + part
    return seconds


def _radio_sync(video_id: str) -> list:
    global _ytmusic
    if _ytmusic is None:
        _ytmusic = YTMusic()
    data = _ytmusic.get_watch_playlist(
        videoId=video_id, radio=True, limit=RADIO_LIMIT
    )
    tracks = []
    for item in data.get("tracks", []):
        vid = item.get("videoId")
        if not vid or vid == video_id or not _ID_RE.match(vid):
            continue
        duration = item.get("duration_seconds") or _length_to_seconds(
            item.get("length")
        )
        if not duration or duration > MAX_TRACK_SECONDS:
            continue
        artists = ", ".join(
            a.get("name", "") for a in item.get("artists") or [] if a.get("name")
        )
        title = item.get("title") or "Autoplay Track"
        tracks.append(
            {
                "video_id": vid,
                "title": f"{title} - {artists}" if artists else title,
                "duration": int(duration),
            }
        )
    return tracks


async def _radio(video_id: str) -> list:
    loop = asyncio.get_event_loop()
    for attempt in range(1, API_RETRIES + 1):
        try:
            return await asyncio.wait_for(
                loop.run_in_executor(None, _radio_sync, video_id), API_TIMEOUT
            )
        except Exception:
            if attempt < API_RETRIES:
                await asyncio.sleep(API_RETRY_DELAY)
    return []


async def _recommendations(chat_id, source_id) -> list:
    """Current song ka radio + chat ke seed song ka radio, interleaved."""
    sources = [source_id]
    seed = get_seed(chat_id)
    if seed and seed != source_id and _ID_RE.match(str(seed)):
        sources.append(seed)

    results = [await _radio(src) for src in sources]
    merged, seen = [], set()
    for i in range(max((len(r) for r in results), default=0)):
        for r in results:
            if i < len(r) and r[i]["video_id"] not in seen:
                seen.add(r[i]["video_id"])
                merged.append(r[i])
    return merged


# --------------------------------------------------------------------- cache
def _new_entry(source_id, carry=None, video=False, failed=None):
    return {
        "source_id": source_id,
        "video": video,
        "tracks": [],
        "carry": carry or [],
        "failed": set(failed or ()),
        "ready": None,
        "inflight": None,
        "task": None,
    }


def _in_any_queue(path):
    for queue in db.values():
        for item in queue or []:
            if item.get("file") == path:
                return True
    return False


def _release_file(path):
    if not path or is_external_path(path) or _in_any_queue(path):
        return
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def _discard_entry(entry):
    picked = entry.get("ready")
    entry["ready"] = None
    if picked:
        _release_file(picked[3])


def discard_prefetch(chat_id):
    entry = _cache.pop(chat_id, None)
    if entry:
        _discard_entry(entry)


def _clean(chat_id, entry, tracks):
    out = []
    seen = {entry["source_id"]} | entry["failed"]
    for track in tracks or []:
        video_id = track.get("video_id")
        if not video_id or video_id in seen or was_recently_played(chat_id, video_id):
            continue
        seen.add(video_id)
        out.append(track)
    return out


async def _download(next_id, video, timeout):
    task = asyncio.ensure_future(
        YouTube.download(next_id, None, video=video, videoid=True)
    )
    try:
        return await asyncio.wait_for(asyncio.shield(task), timeout)
    except Exception:
        return None, False


async def _pick(chat_id, entry, video, timeout):
    while _cache.get(chat_id) is entry and entry["tracks"]:
        track = entry["tracks"].pop(0)
        next_id = track.get("video_id")
        if not next_id or was_recently_played(chat_id, next_id):
            continue
        entry["inflight"] = next_id
        thumb = asyncio.ensure_future(get_thumb(next_id))
        file_path, direct = await _download(next_id, video, timeout)
        entry["inflight"] = None
        if not file_path or not os.path.exists(file_path):
            entry["failed"].add(next_id)
            continue
        title = (track.get("title") or "Autoplay Track").title()
        duration_min = seconds_to_min(track.get("duration") or 0)
        img = await thumb
        return next_id, title, duration_min, file_path, direct, img
    return None


async def _fetch_tracks(chat_id, entry):
    try:
        fresh = await _recommendations(chat_id, entry["source_id"])
    except Exception:
        fresh = []
    tracks = _clean(chat_id, entry, fresh)
    if not tracks:
        tracks = _clean(chat_id, entry, entry["carry"])
    entry["tracks"] = tracks


async def _prefetch(chat_id, entry):
    try:
        await _fetch_tracks(chat_id, entry)
        if _cache.get(chat_id) is not entry:
            return
        picked = await _pick(chat_id, entry, entry["video"], DOWNLOAD_TIMEOUT)
    except Exception:
        picked = None
    if picked and _cache.get(chat_id) is not entry:
        _release_file(picked[3])
        picked = None
    entry["ready"] = picked


def _is_youtube_id(value):
    return bool(value) and bool(_ID_RE.match(str(value)))


async def schedule_prefetch(chat_id, playing):
    if not playing or len(playing) != 1:
        return
    item = playing[0]
    if item.get("played", 0) < PREFETCH_AFTER:
        return
    source_id = item.get("vidid")
    if not _is_youtube_id(source_id):
        return
    queued = str(item.get("file"))
    if queued.startswith("live_") or queued == "index_url":
        return
    entry = _cache.get(chat_id)
    if entry and entry["source_id"] == source_id:
        return
    if not await is_autoplay(chat_id):
        return
    carry = list(entry["tracks"]) if entry else []
    if entry:
        _discard_entry(entry)
    video = str(item.get("streamtype")) == "video"
    fresh = _new_entry(source_id, carry, video)
    _cache[chat_id] = fresh
    fresh["task"] = asyncio.ensure_future(_prefetch(chat_id, fresh))


async def try_autoplay(chat_id, popped) -> bool:
    if not popped:
        return False

    if not await is_autoplay(chat_id):
        return False

    if await get_autoplay_progress(chat_id) >= MAX_AUTOPLAY_TRACKS:
        return False

    source_id = popped.get("vidid")
    if not source_id or source_id in ("telegram", "soundcloud"):
        return False

    original_chat_id = popped.get("chat_id")
    video = str(popped.get("streamtype")) == "video"

    entry = _cache.get(chat_id)
    picked = None
    leftover = []
    failed = set()

    if entry and entry["source_id"] == source_id:
        task = entry.get("task")
        if task is not None and not task.done():
            try:
                await asyncio.wait_for(asyncio.shield(task), READY_WAIT)
            except Exception:
                pass
        picked = entry.get("ready")
        entry["ready"] = None
        if picked and not os.path.exists(picked[3]):
            picked = None
        leftover = list(entry["tracks"])
        failed = set(entry["failed"])
        if entry.get("inflight"):
            failed.add(entry["inflight"])
    elif entry:
        _discard_entry(entry)
        leftover = list(entry["tracks"])

    if not picked:
        same_source = bool(entry) and entry["source_id"] == source_id
        entry = _new_entry(source_id, leftover, video, failed)
        _cache[chat_id] = entry
        if same_source:
            entry["tracks"] = _clean(chat_id, entry, leftover)
        if not entry["tracks"]:
            await _fetch_tracks(chat_id, entry)
        picked = await _pick(chat_id, entry, video, FALLBACK_TIMEOUT)

    if not picked:
        return False

    next_id, title, duration_min, file_path, direct, img = picked

    from zefmusic.core.call import zef

    try:
        await zef.skip_stream(chat_id, file_path, video=video)
    except Exception:
        return False

    record_played(chat_id, next_id)
    await increment_autoplay_progress(chat_id)

    await put_queue(
        chat_id,
        original_chat_id,
        file_path if direct else f"vid_{next_id}",
        title,
        duration_min,
        "Autoplay",
        next_id,
        nand.id,
        "video" if video else "audio",
    )

    language = await get_lang(original_chat_id)
    _ = get_string(language)

    run = await send_now_playing_rich(
        nand,
        chat_id,
        original_chat_id,
        img,
        _["stream_1"].format(
            f"https://t.me/{nand.username}?start=info_{next_id}",
            title[:23],
            duration_min,
            "Autoplay",
        ),
    )
    db[chat_id][0]["mystic"] = run
    db[chat_id][0]["markup"] = "stream"
    await autoplay_logs(
        original_chat_id,
        title,
        next_id,
        popped.get("title"),
        video,
    )
    return True