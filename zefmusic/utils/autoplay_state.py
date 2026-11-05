"""Persistent per-chat autoplay state used by the player controls."""

from __future__ import annotations

import asyncio

import config
from zefmusic.core.mongo import mongodb
from zefmusic.logging import LOGGER

autoplaydb = mongodb.autoplay

_state: dict[int, bool] = {}
_progress: dict[int, int] = {}
_loading: set[int] = set()
_locks: dict[int, asyncio.Lock] = {}
MAX_AUTOPLAY_TRACKS = 5


def _default() -> bool:
    return bool(getattr(config, "AUTOPLAY_RECOMMENDATIONS", False))


def _doc_enabled(document: dict | None) -> bool:
    """Old docs only had {chat_id} and meant 'ON'; new docs carry `enabled`."""
    if not document:
        return _default()
    if "enabled" in document:
        return bool(document["enabled"])
    if "autoplay_played" in document:
        return _default()
    return True


def is_autoplay_enabled_sync(chat_id: int) -> bool:
    return _state.get(int(chat_id), _default())


async def load_autoplay_cache() -> None:
    """Load saved states before the bot starts rendering player keyboards."""
    try:
        async for document in autoplaydb.find({}):
            if "chat_id" not in document:
                continue
            chat_id = int(document["chat_id"])
            _state[chat_id] = _doc_enabled(document)
            _progress[chat_id] = max(0, int(document.get("autoplay_played", 0)))
    except Exception as error:
        LOGGER(__name__).warning(f"Could not preload autoplay settings: {error}")


async def get_autoplay(chat_id: int) -> bool:
    chat_id = int(chat_id)
    if chat_id in _state:
        return _state[chat_id]

    document = await autoplaydb.find_one({"chat_id": chat_id})
    enabled = _doc_enabled(document)
    _state[chat_id] = enabled
    return enabled


async def get_autoplay_progress(chat_id: int) -> int:
    chat_id = int(chat_id)
    if chat_id in _progress:
        return _progress[chat_id]

    document = await autoplaydb.find_one({"chat_id": chat_id})
    progress = max(0, int(document.get("autoplay_played", 0))) if document else 0
    _progress[chat_id] = progress
    return progress


async def increment_autoplay_progress(chat_id: int) -> int:
    chat_id = int(chat_id)
    lock = _locks.setdefault(chat_id, asyncio.Lock())
    async with lock:
        progress = await get_autoplay_progress(chat_id) + 1
        enabled = await get_autoplay(chat_id)
        await autoplaydb.update_one(
            {"chat_id": chat_id},
            {"$set": {"chat_id": chat_id, "enabled": enabled, "autoplay_played": progress}},
            upsert=True,
        )
        _progress[chat_id] = progress
        return progress


async def reset_autoplay_progress(chat_id: int) -> None:
    """Called when a user queues a track by hand: the autoplay streak restarts."""
    chat_id = int(chat_id)
    if not _progress.get(chat_id):
        return
    _progress[chat_id] = 0
    try:
        await autoplaydb.update_one(
            {"chat_id": chat_id},
            {"$set": {"autoplay_played": 0}},
        )
    except Exception as error:
        LOGGER(__name__).warning(f"Could not reset autoplay progress for {chat_id}: {error}")


async def set_autoplay(chat_id: int, enabled: bool) -> bool:
    chat_id = int(chat_id)
    enabled = bool(enabled)
    await autoplaydb.update_one(
        {"chat_id": chat_id},
        {
            "$set": {
                "chat_id": chat_id,
                "enabled": enabled,
                "autoplay_played": 0,
            }
        },
        upsert=True,
    )
    _state[chat_id] = enabled
    _progress[chat_id] = 0
    return enabled


async def toggle_autoplay(chat_id: int) -> bool:
    chat_id = int(chat_id)
    lock = _locks.setdefault(chat_id, asyncio.Lock())
    async with lock:
        return await set_autoplay(chat_id, not await get_autoplay(chat_id))


def schedule_autoplay_load(chat_id: int) -> None:
    """Warm a chat's saved state without making the keyboard builder async."""
    chat_id = int(chat_id)
    if chat_id in _state or chat_id in _loading:
        return
    _loading.add(chat_id)

    async def _load() -> None:
        try:
            await get_autoplay(chat_id)
        except Exception as error:
            LOGGER(__name__).warning(
                f"Could not load autoplay setting for {chat_id}: {error}"
            )
        finally:
            _loading.discard(chat_id)

    try:
        asyncio.create_task(_load())
    except RuntimeError:
        _loading.discard(chat_id)
