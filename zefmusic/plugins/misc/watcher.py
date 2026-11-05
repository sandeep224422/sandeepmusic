from pyrogram import filters
from pyrogram.types import Message

from zefmusic import nand
from zefmusic.core.call import zef

welcome = 20
close = 30


@nand.on_message(filters.video_chat_started, group=welcome)
@nand.on_message(filters.video_chat_ended, group=close)
async def welcome(_, message: Message):
    await zef.stop_stream_force(message.chat.id)
