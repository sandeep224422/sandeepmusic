"""Per-chat song recommendations: end-of-song message and the player's Rec button."""

from __future__ import annotations

import asyncio
import html
import re

from pyrogram.enums import ButtonStyle, ParseMode
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from zefmusic import nand
from zefmusic.logging import LOGGER
from zefmusic.platforms.Youtube import get_autoplay

RECOMMENDATION_LIMIT = 16
SONGS_PER_PAGE = 4
DELETE_AFTER = 300  # seconds (5 min)

_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")

# chat_id -> (source_video_id, tracks, version)
_cache: dict[int, tuple[str, list[dict], int]] = {}
_locks: dict[int, asyncio.Lock] = {}
_messages: dict[int, object] = {}
_tasks: dict[int, asyncio.Task] = {}


def is_youtube_id(value) -> bool:
    return bool(value) and bool(_ID_RE.match(str(value)))


async def get_recommendations(chat_id: int, video_id: str) -> list[dict]:
    """Up to 16 songs similar to `video_id` (the song's own YouTube Music radio)."""
    chat_id = int(chat_id)
    cached = _cache.get(chat_id)
    if cached and cached[0] == video_id and cached[1]:
        return list(cached[1])

    lock = _locks.setdefault(chat_id, asyncio.Lock())
    async with lock:
        cached = _cache.get(chat_id)
        if cached and cached[0] == video_id and cached[1]:
            return list(cached[1])
        try:
            songs = await get_autoplay(video_id)
        except Exception as error:
            LOGGER(__name__).warning(
                f"Could not fetch recommendations for chat {chat_id}: {error}"
            )
            songs = []
        songs = [s for s in songs if s.get("video_id") != video_id]
        songs = songs[:RECOMMENDATION_LIMIT]
        version = cached[2] + 1 if cached else 1
        _cache[chat_id] = (video_id, songs, version)
        return list(songs)


def get_recommendation(chat_id: int, index: int, version: int) -> dict | None:
    cached = _cache.get(int(chat_id))
    if (
        not cached
        or cached[2] != version
        or index < 0
        or index >= len(cached[1])
    ):
        return None
    return cached[1][index]


def build_recommendation_keyboard(
    chat_id: int, page: int = 0, version: int | None = None
) -> InlineKeyboardMarkup | None:
    cached = _cache.get(int(chat_id))
    songs = cached[1] if cached else []
    if not songs or (version is not None and cached[2] != version):
        return None

    version = cached[2]
    page_count = (len(songs) + SONGS_PER_PAGE - 1) // SONGS_PER_PAGE
    page = max(0, min(int(page), page_count - 1))
    start = page * SONGS_PER_PAGE
    visible = songs[start : start + SONGS_PER_PAGE]

    rows = [
        [
            InlineKeyboardButton(
                text=song["title"][:48],
                callback_data=f"rec:play:{chat_id}:{version}:{start + offset}",
                style=ButtonStyle.SUCCESS
                if start + offset == 0
                else ButtonStyle.PRIMARY,
            )
        ]
        for offset, song in enumerate(visible)
    ]

    navigation = []
    if page > 0:
        navigation.append(
            InlineKeyboardButton(
                text="‹ Back",
                callback_data=f"rec:page:{chat_id}:{version}:{page - 1}",
            )
        )
    navigation.append(
        InlineKeyboardButton(
            text=f"{page + 1}/{page_count}",
            callback_data=f"rec:page:{chat_id}:{version}:{page}",
        )
    )
    if page < page_count - 1:
        navigation.append(
            InlineKeyboardButton(
                text="More ›",
                callback_data=f"rec:page:{chat_id}:{version}:{page + 1}",
            )
        )
    rows.append(navigation)
    rows.append(
        [
            InlineKeyboardButton(
                text="Close",
                callback_data=f"rec:close:{chat_id}",
                style=ButtonStyle.DANGER,
            )
        ]
    )
    return InlineKeyboardMarkup(rows)


# ------------------------------------------------------- message lifecycle
async def _delete_later(chat_id: int, message, delay: int) -> None:
    try:
        await asyncio.sleep(delay)
        await message.delete()
    except asyncio.CancelledError:
        raise
    except Exception:
        pass
    finally:
        if _messages.get(chat_id) is message:
            _messages.pop(chat_id, None)
            _tasks.pop(chat_id, None)


async def clear_recommendation_message(chat_id: int) -> None:
    """Cancel the 5-minute timer and delete the chat's recommendation message."""
    chat_id = int(chat_id)
    task = _tasks.pop(chat_id, None)
    if task and not task.done():
        task.cancel()
    message = _messages.pop(chat_id, None)
    if message is not None:
        try:
            await message.delete()
        except Exception:
            pass


async def _send(
    chat_id: int, target_chat_id: int, video_id: str, title: str, ended: bool
) -> bool:
    songs = await get_recommendations(chat_id, video_id)
    keyboard = build_recommendation_keyboard(chat_id)
    if not songs or not keyboard:
        return False

    heading = (
        "Songs similar to the track that just ended:"
        if ended
        else "Songs similar to the current track:"
    )
    text = (
        "<blockquote>"
        f"🎧 <b>{heading}</b>\n"
        f"<b>{html.escape(title or 'Unknown')}</b>\n\n"
        "Choose a song to add it to the queue or start playback."
        "</blockquote>"
    )

    await clear_recommendation_message(chat_id)
    message = await nand.send_message(
        target_chat_id,
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard,
    )
    _messages[chat_id] = message
    _tasks[chat_id] = asyncio.ensure_future(
        _delete_later(chat_id, message, DELETE_AFTER)
    )
    return True


async def send_end_recommendations(chat_id: int, popped) -> bool:
    """Queue just ended: show 16 songs similar to the track that finished."""
    try:
        if not popped:
            return False
        video_id = popped.get("vidid")
        if not is_youtube_id(video_id):
            return False
        if str(popped.get("file")).startswith("live_"):
            return False
        target = popped.get("chat_id") or chat_id
        return await _send(
            chat_id, target, video_id, str(popped.get("title") or ""), ended=True
        )
    except asyncio.CancelledError:
        raise
    except Exception as error:
        LOGGER(__name__).warning(
            f"Could not send end recommendations for {chat_id}: {error}"
        )
        return False


async def send_current_recommendations(chat_id: int, target_chat_id: int) -> bool:
    """Player's Recommendations button: songs similar to what is playing now."""
    from zefmusic.misc import db

    queue = db.get(chat_id)
    if not queue:
        return False
    current = queue[0]
    video_id = current.get("vidid")
    if not is_youtube_id(video_id):
        return False
    try:
        return await _send(
            chat_id, target_chat_id, video_id, str(current.get("title") or ""), ended=False
        )
    except asyncio.CancelledError:
        raise
    except Exception as error:
        LOGGER(__name__).warning(
            f"Could not send recommendations for {chat_id}: {error}"
        )
        return False
