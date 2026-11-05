from pyrogram import filters

import config
from zefmusic import YouTube, nand
from zefmusic.core.call import zef
from zefmusic.utils import time_to_seconds
from zefmusic.utils.database import is_active_chat
from zefmusic.utils.decorators.language import languageCB
from zefmusic.utils.recommendations import (
    build_recommendation_keyboard,
    clear_recommendation_message,
    get_recommendation,
)
from zefmusic.utils.stream.stream import stream
from config import BANNED_USERS


@nand.on_callback_query(filters.regex(r"^rec:page:") & ~BANNED_USERS)
async def recommend_page(client, CallbackQuery):
    try:
        _, _, chat_id, version, page = CallbackQuery.data.split(":")
        keyboard = build_recommendation_keyboard(int(chat_id), int(page), int(version))
    except Exception:
        return await CallbackQuery.answer()
    if not keyboard:
        return await CallbackQuery.answer(
            "These recommendations have expired.", show_alert=True
        )
    try:
        await CallbackQuery.edit_message_reply_markup(keyboard)
    except Exception:
        pass
    await CallbackQuery.answer()


@nand.on_callback_query(filters.regex(r"^rec:close:") & ~BANNED_USERS)
async def recommend_close(client, CallbackQuery):
    try:
        chat_id = int(CallbackQuery.data.split(":")[2])
    except Exception:
        return await CallbackQuery.answer()
    await CallbackQuery.answer()
    await clear_recommendation_message(chat_id)
    try:
        await CallbackQuery.message.delete()
    except Exception:
        pass


@nand.on_callback_query(filters.regex(r"^rec:play:") & ~BANNED_USERS)
@languageCB
async def recommend_play(client, CallbackQuery, _):
    try:
        _p, _a, chat_id, version, index = CallbackQuery.data.split(":")
        chat_id, version, index = int(chat_id), int(version), int(index)
    except Exception:
        return await CallbackQuery.answer()

    song = get_recommendation(chat_id, index, version)
    if not song:
        return await CallbackQuery.answer(
            "These recommendations have expired.", show_alert=True
        )

    await CallbackQuery.answer()
    original_chat_id = CallbackQuery.message.chat.id
    user_id = CallbackQuery.from_user.id
    user_name = CallbackQuery.from_user.first_name

    await clear_recommendation_message(chat_id)
    try:
        await CallbackQuery.message.delete()
    except Exception:
        pass

    mystic = await nand.send_message(original_chat_id, _["play_1"])
    try:
        details, _track_id = await YouTube.track(song["video_id"], True)
    except Exception:
        return await mystic.edit_text(_["play_3"])
    if not details["duration_min"]:
        return await mystic.edit_text(_["play_3"])
    if time_to_seconds(details["duration_min"]) > config.DURATION_LIMIT:
        return await mystic.edit_text(
            _["play_6"].format(config.DURATION_LIMIT_MIN, nand.mention)
        )

    early = False
    if not await is_active_chat(chat_id):
        early = await zef.prejoin_start(chat_id, video=False)
    try:
        await stream(
            _,
            mystic,
            user_id,
            details,
            chat_id,
            user_name,
            original_chat_id,
            None,
            streamtype="youtube",
        )
    except Exception as e:
        ex_type = type(e).__name__
        err = e if ex_type == "AssistantErr" else _["general_2"].format(f"{ex_type}: {e}")
        await mystic.edit_text(err)
    finally:
        if early:
            try:
                await zef.prejoin_settle(chat_id)
            except Exception:
                pass
