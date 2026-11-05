from pyrogram import filters
from pyrogram.types import Message

from zefmusic import nand
from zefmusic.core.call import zef
from zefmusic.utils.database import is_music_playing, music_off
from zefmusic.utils.decorators import AdminRightsCheck
from zefmusic.utils.inline import close_markup
from zefmusic.utils.rich_stream import set_now_playing_state
from config import BANNED_USERS


@nand.on_message(filters.command(["pause", "cpause"]) & filters.group & ~BANNED_USERS)
@AdminRightsCheck
async def pause_admin(cli, message: Message, _, chat_id):
    if not await is_music_playing(chat_id):
        return await message.reply_text(_["admin_1"])
    await music_off(chat_id)
    await zef.pause_stream(chat_id)
    await set_now_playing_state(chat_id, playing=False)
    await message.reply_text(
        _["admin_2"].format(message.from_user.mention), reply_markup=close_markup(_)
    )
