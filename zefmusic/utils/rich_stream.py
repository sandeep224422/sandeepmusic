"""Now-playing player, queue card and shared card helpers.

Every control is a native Telegram inline button (``InlineKeyboardButton`` inside
an ``InlineKeyboardMarkup``) attached to a normal photo / text message.
"""

import math

from pyrogram import errors
from pyrogram.enums import ButtonStyle, ParseMode
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto

from zefmusic.misc import db
from zefmusic.utils.database import get_lang, is_autoplay
from zefmusic.utils.formatters import seconds_to_min, time_to_seconds
from strings import get_string

_consumed = set()

# chats whose player card currently shows the "More" submenu
_more_open = set()


def set_more_open(chat_id, value):
    if value:
        _more_open.add(chat_id)
    else:
        _more_open.discard(chat_id)


async def _lang(chat_id):
    return get_string(await get_lang(chat_id))


def _btn(text, data=None, style=None, url=None):
    """Native inline button. A URL button keeps its URL, otherwise callback_data."""
    kwargs = {"text": text}
    if url:
        kwargs["url"] = url
    else:
        kwargs["callback_data"] = data
    if style is not None and style != ButtonStyle.DEFAULT:
        kwargs["style"] = style
    return InlineKeyboardButton(**kwargs)


def _progress_line(played, dur):
    played_sec = time_to_seconds(played)
    duration_sec = time_to_seconds(dur)
    percentage = (played_sec / duration_sec) * 100 if duration_sec else 0
    umm = math.floor(percentage)
    if 0 < umm <= 10:
        bar = "◉—————————"
    elif 10 < umm < 20:
        bar = "—◉————————"
    elif 20 <= umm < 30:
        bar = "——◉———————"
    elif 30 <= umm < 40:
        bar = "———◉——————"
    elif 40 <= umm < 50:
        bar = "————◉—————"
    elif 50 <= umm < 60:
        bar = "—————◉————"
    elif 60 <= umm < 70:
        bar = "——————◉———"
    elif 70 <= umm < 80:
        bar = "———————◉——"
    elif 80 <= umm < 95:
        bar = "————————◉—"
    else:
        bar = "—————————◉"
    return f"{played}  {bar}  {dur}"


def _queue_len(chat_id):
    tracks = db.get(chat_id)
    return max(len(tracks) - 1, 0) if tracks else 0


def build_now_playing_markup(
    _, chat_id, played=None, dur=None, playing=True, autoplay_on=False
):
    """Player keyboard.

        ◉ progress bar (only once playback has started)
        🔁 Replay | ⏸ Pause / ▶️ Resume | ⏭ Skip
        📜 Queue · N | ✨ More  (becomes 🔙 Back while the submenu is open)
        🟢 Autoplay | 💡 Suggestions   (submenu only)
        ❌ End Queue
    """
    rows = []
    if played and dur:
        rows.append([_btn(_progress_line(played, dur), "GetTimer")])

    if playing:
        toggle = _btn(
            _["PLAYER_BTN_PAUSE"], f"ADMIN Pause|{chat_id}", ButtonStyle.PRIMARY
        )
    else:
        toggle = _btn(
            _["PLAYER_BTN_RESUME"], f"ADMIN Resume|{chat_id}", ButtonStyle.PRIMARY
        )
    rows.append(
        [
            _btn(_["PLAYER_BTN_REPLAY"], f"ADMIN Replay|{chat_id}"),
            toggle,
            _btn(_["PLAYER_BTN_SKIP"], f"ADMIN Skip|{chat_id}"),
        ]
    )

    queue_btn = _btn(
        _["PLAYER_BTN_QUEUE"].format(_queue_len(chat_id)),
        f"nowplaying_queue {chat_id}",
    )
    if chat_id in _more_open:
        rows.append(
            [queue_btn, _btn(_["PLAYER_BTN_BACK"], f"nowplaying_back {chat_id}")]
        )
        rows.append(
            [
                _btn(
                    _["PLAYER_BTN_AUTOPLAY_ON"]
                    if autoplay_on
                    else _["PLAYER_BTN_AUTOPLAY_OFF"],
                    f"nowplaying_autoplay {chat_id}",
                    ButtonStyle.SUCCESS if autoplay_on else None,
                ),
                _btn(
                    _["PLAYER_BTN_RECOMMEND"],
                    f"nowplaying_rec {chat_id}",
                    ButtonStyle.PRIMARY,
                ),
            ]
        )
    else:
        rows.append(
            [queue_btn, _btn(_["PLAYER_BTN_MORE"], f"nowplaying_more {chat_id}")]
        )

    rows.append(
        [_btn(_["PLAYER_BTN_END_QUEUE"], f"ADMIN Stop|{chat_id}", ButtonStyle.DANGER)]
    )
    return InlineKeyboardMarkup(rows)


def build_queue_markup(_, chat_id, qid):
    """Keyboard of a track that was added to a running queue.

        ▶️ Play Now
        ⏭ Skip | ❌ End
    """
    return InlineKeyboardMarkup(
        [
            [
                _btn(
                    _["PLAYER_BTN_PLAYNOW"],
                    f"ADMIN PlayNow|{chat_id}_{qid}",
                    ButtonStyle.SUCCESS,
                )
            ],
            [
                _btn(_["PLAYER_BTN_SKIP"], f"ADMIN Skip|{chat_id}"),
                _btn(_["PLAYER_BTN_END"], f"ADMIN Stop|{chat_id}", ButtonStyle.DANGER),
            ],
        ]
    )


def _message_key(message):
    return (message.chat.id, message.id)


async def _edit_card(message, text, markup, photo=None):
    """Edit a card in place: new photo + caption, caption only, or plain text."""
    try:
        if photo and message.photo:
            return await message.edit_media(
                InputMediaPhoto(photo, caption=text, parse_mode=ParseMode.HTML),
                reply_markup=markup,
            )
        if message.text:
            return await message.edit_text(
                text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
                reply_markup=markup,
            )
        return await message.edit_caption(
            text, parse_mode=ParseMode.HTML, reply_markup=markup
        )
    except errors.MessageNotModified:
        return message


async def _edit_markup(message, markup):
    try:
        return await message.edit_reply_markup(markup)
    except errors.MessageNotModified:
        return message


async def _send_card(client, target_chat_id, text, markup, photo=None):
    if photo:
        try:
            return await client.send_photo(
                target_chat_id,
                photo=photo,
                caption=text,
                parse_mode=ParseMode.HTML,
                reply_markup=markup,
            )
        except (errors.ChatSendPhotosForbidden, errors.ChatSendMediaForbidden):
            pass  # chat does not allow photos: fall back to a text card
    return await client.send_message(
        target_chat_id,
        text,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
        reply_markup=markup,
    )


async def _deliver(client, target_chat_id, text, markup, photo=None, replace=None):
    if replace is not None:
        # A text message can't turn into a photo, so a photo card only reuses a photo
        # message; everything else is replaced by a fresh message.
        if not photo or replace.photo:
            try:
                edited = await _edit_card(replace, text, markup, photo)
            except Exception:
                pass
            else:
                _consumed.add(_message_key(replace))
                return edited or replace
        try:
            await replace.delete()
        except Exception:
            pass
        _consumed.add(_message_key(replace))
    return await _send_card(client, target_chat_id, text, markup, photo)


async def edit_card(message, text, markup, photo=None):
    return await _edit_card(message, text, markup, photo)


async def deliver_card(client, target_chat_id, text, markup, photo=None, replace=None):
    result = await _deliver(client, target_chat_id, text, markup, photo, replace)
    if replace is not None:
        _consumed.discard(_message_key(replace))
    return result


async def release_mystic(mystic):
    if mystic is None:
        return
    key = _message_key(mystic)
    if key in _consumed:
        _consumed.discard(key)
        return
    try:
        await mystic.delete()
    except Exception:
        pass


async def send_now_playing_rich(
    client, chat_id, target_chat_id, photo, caption_html, replace=None
):
    _ = await _lang(chat_id)
    _more_open.discard(chat_id)
    markup = build_now_playing_markup(
        _, chat_id, autoplay_on=await is_autoplay(chat_id)
    )
    return await _deliver(
        client, target_chat_id, caption_html, markup, photo, replace
    )


async def send_queue_rich(
    client, chat_id, target_chat_id, caption_html, qid, replace=None
):
    _ = await _lang(chat_id)
    markup = build_queue_markup(_, chat_id, qid)
    return await _deliver(
        client, target_chat_id, caption_html, markup, None, replace
    )


async def update_now_playing_progress(mystic, chat_id, played, dur, playing=True):
    if not db.get(chat_id):
        return None
    _ = await _lang(chat_id)
    markup = build_now_playing_markup(
        _, chat_id, played, dur, playing, await is_autoplay(chat_id)
    )
    return await _edit_markup(mystic, markup)


async def set_now_playing_state(chat_id, playing):
    info = db.get(chat_id)
    if not info:
        return None
    mystic = info[0].get("mystic")
    if not mystic:
        return None
    played = seconds_to_min(info[0].get("played", 0)) or None
    dur = info[0].get("dur")
    _ = await _lang(chat_id)
    markup = build_now_playing_markup(
        _, chat_id, played, dur, playing, await is_autoplay(chat_id)
    )
    try:
        return await _edit_markup(mystic, markup)
    except Exception:
        return None
