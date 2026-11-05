import asyncio
import os
import re
from urllib.parse import parse_qs, urlparse
from typing import Union

import aiofiles
import aiohttp
import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from py_yt import VideosSearch, Playlist

try:
    from ytmusicapi import YTMusic
except Exception:  # ytmusicapi not installed
    YTMusic = None

API_URL = (
    os.environ.get("ApiUrl")
    or os.environ.get("SHRUTI_API_URL")
    or "https://api.shrutibots.in"
).rstrip("/")
SHRUTI_API_KEY = os.environ.get("SHRUTI_API_KEY") or os.environ.get("APIKey") or ""
ZEFRON_API_KEY = os.environ.get("ZEFRON_API_KEY", "")
YUKI_API_KEY = os.environ.get("YUKI_API_KEY", "")
YUKI_STREAM_URL = "https://music.yukiapi.site/stream"

DOWNLOAD_DIR = "downloads"
DOWNLOAD_CONCURRENCY = int(os.environ.get("DOWNLOAD_CONCURRENCY", "4"))
_semaphore = None


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(DOWNLOAD_CONCURRENCY)
    return _semaphore


def _env_dir(name: str) -> str:
    value = os.environ.get(name, "").strip()
    return os.path.abspath(os.path.expanduser(value)) if value else ""


AUDIO_DOWNLOAD_PATH = _env_dir("AUDIO_DOWNLOAD_PATH")
VIDEO_DOWNLOAD_PATH = _env_dir("VIDEO_DOWNLOAD_PATH")
AUDIO_EXTENSIONS = ("webm", "m4a", "mp3", "ogg")
VIDEO_EXTENSIONS = ("mp4", "mkv", "webm")


def is_external_path(path) -> bool:
    if not path:
        return False
    full = os.path.abspath(str(path))
    for base in (AUDIO_DOWNLOAD_PATH, VIDEO_DOWNLOAD_PATH):
        if base and full.startswith(base + os.sep):
            return True
    return False


def _find_external(directory: str, video_id: str, extensions):
    for ext in extensions:
        path = os.path.join(directory, f"{video_id}.{ext}")
        if os.path.isfile(path) and os.path.getsize(path) > 0:
            return path
    return None


def time_to_seconds(time):
    stringt = str(time)
    return sum(int(x) * 60 ** i for i, x in enumerate(reversed(stringt.split(":"))))


def _video_id(link: str) -> str:
    value = str(link or "").strip()
    if "://" not in value:
        return value.split("&", 1)[0]
    parsed = urlparse(value)
    if parsed.hostname == "youtu.be":
        return parsed.path.strip("/").split("/", 1)[0]
    return parse_qs(parsed.query).get("v", [""])[0] or value


async def _download_provider(session, url, params, path, total_timeout, kind, fast=0):
    temp_path = f"{path}.part"
    timeout = aiohttp.ClientTimeout(
        total=total_timeout,
        connect=fast or 30,
        sock_connect=fast or 30,
        sock_read=fast or 60,
    )
    try:
        async with session.get(url, params=params, timeout=timeout) as response:
            if response.status != 200:
                return False
            content_type = response.headers.get("Content-Type", "").lower()
            if "json" in content_type or content_type.startswith("text/"):
                return False
            if kind == "audio" and content_type.startswith("video/"):
                return False
            async with aiofiles.open(temp_path, "wb") as output:
                async for chunk in response.content.iter_chunked(131072):
                    await output.write(chunk)
        if os.path.getsize(temp_path) > 0:
            os.replace(temp_path, path)
            return True
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
        pass
    finally:
        if os.path.exists(temp_path):
            try:
                await asyncio.to_thread(os.remove, temp_path)
            except OSError:
                pass
    return False


async def _download_unlimited(link: str, kind: str) -> str | None:
    video_id = _video_id(link)
    if not video_id or len(video_id) < 3:
        return None

    is_audio = kind == "audio"
    external = AUDIO_DOWNLOAD_PATH if is_audio else VIDEO_DOWNLOAD_PATH
    extensions = AUDIO_EXTENSIONS if is_audio else VIDEO_EXTENSIONS

    if external:
        found = _find_external(external, video_id, extensions)
        if found:
            return found

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    path = os.path.join(DOWNLOAD_DIR, f"{video_id}.{'mp3' if is_audio else 'mp4'}")
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path

    sources = []
    if ZEFRON_API_KEY:
        sources.append((
            "https://zefronapi.me/download",
            {"api_key": ZEFRON_API_KEY, "type": kind, "url": video_id},
            4,
        ))
    if YUKI_API_KEY:
        sources.append((
            f"{YUKI_STREAM_URL}/{video_id}",
            {"key": YUKI_API_KEY, "type": kind},
            0,
        ))
    if SHRUTI_API_KEY:
        endpoint = API_URL if API_URL.endswith("/download") else f"{API_URL}/download"
        sources.append((
            endpoint,
            {"url": video_id, "type": kind, "api_key": SHRUTI_API_KEY},
            0,
        ))

    total_timeout = 300 if is_audio else 600
    async with aiohttp.ClientSession() as session:
        for url, params, fast_response in sources:
            if await _download_provider(
                session, url, params, path, total_timeout, kind, fast_response
            ):
                return path
    return None


async def _download(link: str, kind: str) -> str | None:
    async with _get_semaphore():
        return await _download_unlimited(link, kind)


async def download_song(link: str) -> str | None:
    return await _download(link, "audio")


async def download_video(link: str) -> str | None:
    return await _download(link, "video")


# --------------------------------------------------------------- autoplay
AUTOPLAY_REQUEST_TIMEOUT = 20
AUTOPLAY_MAX_RETRIES = 3
AUTOPLAY_RETRY_DELAY = 1
MAX_TRACK_SECONDS = 900

_ytmusic = None
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def _length_to_seconds(value) -> int:
    try:
        parts = [int(x) for x in str(value).split(":")]
    except Exception:
        return 0
    seconds = 0
    for part in parts:
        seconds = seconds * 60 + part
    return seconds


def _ytmusic_radio(video_id: str, limit: int) -> list:
    global _ytmusic
    if YTMusic is None:
        return []
    if _ytmusic is None:
        _ytmusic = YTMusic()
    data = _ytmusic.get_watch_playlist(videoId=video_id, radio=True, limit=limit)
    tracks = []
    for item in data.get("tracks", []):
        vid = item.get("videoId")
        if not vid or vid == video_id or not _ID_RE.match(vid):
            continue
        duration = item.get("duration_seconds") or _length_to_seconds(item.get("length"))
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


async def get_autoplay(
    video_id: str,
    timeout: int = AUTOPLAY_REQUEST_TIMEOUT,
    retries: int = AUTOPLAY_MAX_RETRIES,
    seed_id: str = None,
) -> list:
    video_id = _video_id(video_id)
    if not video_id or len(video_id) < 3:
        return []

    loop = asyncio.get_event_loop()
    sources = [video_id]
    if seed_id and seed_id != video_id and _ID_RE.match(str(seed_id)):
        sources.append(seed_id)

    for attempt in range(1, retries + 1):
        try:
            results = []
            for source in sources:
                found = await asyncio.wait_for(
                    loop.run_in_executor(None, _ytmusic_radio, source, 25),
                    timeout,
                )
                results.append(found)
            merged, seen = [], set()
            for i in range(max((len(r) for r in results), default=0)):
                for r in results:
                    if i < len(r) and r[i]["video_id"] not in seen:
                        seen.add(r[i]["video_id"])
                        merged.append(r[i])
            if merged:
                return merged
        except Exception:
            pass
        if attempt < retries:
            await asyncio.sleep(AUTOPLAY_RETRY_DELAY)
    return []


def _extract_formats(link: str):
    with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
        info = ydl.extract_info(link, download=False)
    formats_available = []
    for item in info["formats"]:
        try:
            if "dash" not in str(item["format"]).lower():
                formats_available.append(
                    {
                        "format": item["format"],
                        "filesize": item.get("filesize"),
                        "format_id": item["format_id"],
                        "ext": item["ext"],
                        "format_note": item["format_note"],
                        "yturl": link,
                    }
                )
        except Exception:
            continue
    return formats_available, link


class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        for message in messages:
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        return text[entity.offset: entity.offset + entity.length]
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        return None

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result["duration"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
            vidid = result["id"]
            duration_sec = int(time_to_seconds(duration_min)) if duration_min else 0
        return title, duration_min, duration_sec, thumbnail, vidid

    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return result["title"]

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return result["duration"]

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return result["thumbnails"][0]["url"].split("?")[0]

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        try:
            downloaded_file = await download_video(link)
            if downloaded_file:
                return 1, downloaded_file
            return 0, "Video download failed"
        except Exception as e:
            return 0, f"Video download error: {e}"

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]
        try:
            plist = await Playlist.get(link)
        except Exception:
            return []
        videos = plist.get("videos") or []
        ids = []
        for data in videos[:limit]:
            if not data:
                continue
            vid = data.get("id")
            if not vid:
                continue
            ids.append(vid)
        return ids

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result["duration"]
            vidid = result["id"]
            yturl = result["link"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        track_details = {
            "title": title,
            "link": yturl,
            "vidid": vidid,
            "duration_min": duration_min,
            "thumb": thumbnail,
        }
        return track_details, vidid

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        ytdl_opts = {"quiet": True}
        ydl = yt_dlp.YoutubeDL(ytdl_opts)
        with ydl:
            formats_available = []
            r = ydl.extract_info(link, download=False)
            for format in r["formats"]:
                try:
                    if "dash" not in str(format["format"]).lower():
                        formats_available.append(
                            {
                                "format": format["format"],
                                "filesize": format.get("filesize"),
                                "format_id": format["format_id"],
                                "ext": format["ext"],
                                "format_note": format["format_note"],
                                "yturl": link,
                            }
                        )
                except Exception:
                    continue
        return formats_available, link

    async def slider(self, link: str, query_type: int, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        a = VideosSearch(link, limit=10)
        result = (await a.next()).get("result")
        title = result[query_type]["title"]
        duration_min = result[query_type]["duration"]
        vidid = result[query_type]["id"]
        thumbnail = result[query_type]["thumbnails"][0]["url"].split("?")[0]
        return title, duration_min, thumbnail, vidid

    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ) -> str:
        if videoid:
            link = self.base + link
        try:
            if video:
                downloaded_file = await download_video(link)
            else:
                downloaded_file = await download_song(link)
            if downloaded_file:
                return downloaded_file, True
            return None, False
        except Exception:
            return None, False


YouTube = YouTubeAPI()
