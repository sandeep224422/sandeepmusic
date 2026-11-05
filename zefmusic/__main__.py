import asyncio
import importlib
import logging

from pyrogram import idle
from pytgcalls.exceptions import NoActiveGroupCall

import config
from zefmusic import LOGGER, nand, userbot
from zefmusic.core.call import zef
from zefmusic.misc import sudo
from zefmusic.plugins import ALL_MODULES
from zefmusic.utils.autoplay_state import load_autoplay_cache
from zefmusic.utils.database import get_banned_users, get_gbanned
from config import BANNED_USERS


class _EndedCallNoiseFilter(logging.Filter):
    def filter(self, record):
        message = record.getMessage()
        return not ("SetVideoCallStatus" in message and "GROUPCALL_FORBIDDEN" in message)


logging.getLogger("asyncio").addFilter(_EndedCallNoiseFilter())


async def init():
    if (
        not config.STRING1
        and not config.STRING2
        and not config.STRING3
        and not config.STRING4
        and not config.STRING5
    ):
        LOGGER(__name__).error("Assistant client variables not defined, exiting...")
        exit()
    await sudo()
    try:
        users = await get_gbanned()
        for user_id in users:
            BANNED_USERS.add(user_id)
        users = await get_banned_users()
        for user_id in users:
            BANNED_USERS.add(user_id)
    except:
        pass
    await load_autoplay_cache()
    await nand.start()
    for all_module in ALL_MODULES:
        importlib.import_module("zefmusic.plugins" + all_module)
    LOGGER("zefmusic.plugins").info("Successfully Imported Modules...")
    await userbot.start()
    await zef.start()
    try:
        await zef.stream_call("https://te.legra.ph/file/29f784eb49d230ab62e9e.mp4")
    except NoActiveGroupCall:
        LOGGER("zefmusic").error(
            "Please turn on the videochat of your log group\channel.\n\nStopping Bot..."
        )
        exit()
    except:
        pass
    await zef.decorators()
    LOGGER("zefmusic").info("zefmusic Music Bot Started Successfully.")
    await idle()
    await nand.stop()
    await userbot.stop()
    LOGGER("zefmusic").info("Stopping zefmusic Music Bot...")


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(init())
