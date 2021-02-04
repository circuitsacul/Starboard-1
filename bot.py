import discord
import sys
import asyncio
import os
import dotenv
import functions
import pretty_help
from discord.ext import commands
from asyncio import Lock

dotenv.load_dotenv()

import bot_config
from database.database import Database

from cogs.webhook import HttpWebHook

_TOKEN = os.getenv('TOKEN')
_BETA_TOKEN = os.getenv('BETA_TOKEN')

BETA = True if len(sys.argv) > 1 and sys.argv[1] == 'beta' else False
TOKEN = _BETA_TOKEN if BETA and _BETA_TOKEN is not None else _TOKEN
BOT_DESCRIPTION = """
An advanced starboard that allows for multiple starboards and multiple emojis
per starboard.
To get started, run the "setup" command.
If you need help, just mention me for a link to the support server.
"""

db = Database()

emojis = bot_config.PAGINATOR_EMOJIS
navigation = pretty_help.Navigation(
    page_left=emojis[0], page_right=emojis[1], remove=emojis[2]
)

intents = discord.Intents(
    messages=True, guilds=True, reactions=True,
    emojis=True, members=True
)


class Bot(commands.AutoShardedBot):
    def __init__(self, db, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.db = db
        self.wizzard_lock = Lock
        self.allowed_mentions = discord.AllowedMentions.none()

    async def on_message(self, *args, **kwargs):
        pass


help_command = pretty_help.PrettyHelp(
    color=bot_config.COLOR,
    command_attrs={
        "name": "commands",
        'hidden': True
    }
)


bot = Bot(
    db, command_prefix=functions._prefix_callable,
    case_insensitive=True,
    intents=intents,
    help_command=help_command,
    description=BOT_DESCRIPTION,
    shard_count=bot_config.SHARD_COUNT
)
web_server = HttpWebHook(bot, db)


# Load Cache
async def load_aschannels(
    bot: commands.Bot
) -> None:
    check_aschannel = \
        """SELECT * FROM aschannels"""

    async with bot.db.lock:
        async with bot.db.conn.transaction():
            asc = await bot.db.conn.fetch(
                check_aschannel
            )

    if asc != []:
        bot.db.as_cache = set([int(a['id']) for a in asc])
    else:
        bot.db.as_cache = set()


async def main() -> None:
    await db.open(bot)

    await load_aschannels(bot)

    await web_server.start()

    extensions = [
        'cogs.aschannels',
        'cogs.levels',
        'cogs.owner',
        'cogs.premium',
        'cogs.settings',
        'cogs.starboard',
        'cogs.quickactions',
        'cogs.stats',
        'cogs.utility',
        'cogs.voting',
        'cogs.rand_messages',
        'cogs.base',
        'cogs.logging',
        'cogs.xproles',
        'cogs.posroles',
        'jishaku'
    ]

    for ext in extensions:
        bot.load_extension(ext)

    await bot.start(TOKEN)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except Exception as e:
        print(type(e), e)
    finally:
        print("Logging out")
        loop.run_until_complete(bot.logout())
        loop.run_until_complete(web_server.close())
        exit(1)
