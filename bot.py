import discord
import sys
import asyncio
import os
import dotenv
import functions
import pretty_help
import json
import time
import checks
import errors as cerrors

from discord.ext import commands
from asyncio import Lock
from discord.ext.ipc import Server

dotenv.load_dotenv()

import bot_config
from database.database import Database

from cogs.webhook import HttpWebHook

TOKEN = os.getenv('TOKEN')
IPC_KEY = os.getenv('IPC_KEY')

BETA = True if len(sys.argv) > 1 and sys.argv[1] == 'beta' else False
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
    emojis=True
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
ipc = Server(
    bot, 'localhost', 8765, IPC_KEY
)


# IPC Server Routes
@ipc.route('bot_stats')
async def get_bot_stats(data):
    mcount = 0
    gcount = len(bot.guilds)
    for g in bot.guilds:
        mcount += g.member_count
    return f"{gcount}-{mcount}"


@ipc.route('does_share')
async def check_shared_guild(data):
    if int(data.gid) in [g.id for g in bot.guilds]:
        return '1'
    else:
        return '0'


@ipc.route('guild_data')
async def get_guild_data(data):
    gid = data.gid
    get_guild = \
        """SELECT * FROM guilds WHERE id=$1"""

    await functions.check_or_create_existence(
        bot, guild_id=int(gid)
    )
    conn = bot.db.conn
    async with bot.db.lock:
        async with conn.transaction():
            guild_data = await conn.fetchrow(
                get_guild, int(gid)
            )
    prefixes = await functions.list_prefixes(
        bot, int(gid)
    )
    data = json.dumps({
        "id": str(guild_data['id']),
        "prefixes": list(prefixes)
    })
    return data


@ipc.route('modify_guild')
async def modify_guild(data):
    gid = data.gid
    action = data.action
    modifydata = json.loads(data.modifydata)

    try:
        if action == 'prefix.add':
            await functions.add_prefix(
                bot, int(gid), modifydata['prefix']
            )
        elif action == 'prefix.remove':
            await functions.remove_prefix(
                bot, int(gid), modifydata['prefix']
            )
    except Exception as e:
        print(e)

    print(f"Action {action} in {gid} with data {modifydata}")


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
        'jishaku'
    ]

    for ext in extensions:
        bot.load_extension(ext)

    await bot.start(TOKEN)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    try:
        ipc.start()
        loop.run_until_complete(main())
    except Exception as e:
        print(type(e), e)
    finally:
        print("Logging out")
        loop.run_until_complete(bot.logout())
        loop.run_until_complete(web_server.close())
        exit(1)
