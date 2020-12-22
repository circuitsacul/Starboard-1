# Put here for ease of use with statcord
import os
import json

import dbl
import statcord
from discord.ext import tasks
from aiohttp_requests import requests
from discord.ext import commands
from dotenv import load_dotenv

from bot_config import OWNER_ID

load_dotenv()


STATCORD_TOKEN = os.getenv("STATCORD_TOKEN")
TOP_TOKEN = os.getenv("TOP_TOKEN")
TOP_AUTH = os.getenv("TOP_HOOK_AUTH")

BOD_TOKEN = os.getenv("BOD_TOKEN")
DBL_TOKEN = os.getenv("DBL_TOKEN")
BOATS_TOKEN = os.getenv("BOATS_TOKEN")
DBGG_TOKEN = os.getenv("DBGG_TOKEN")
DEL_TOKEN = os.getenv("DEL_TOKEN")
LABS_TOKEN = os.getenv("LABS_TOKEN")


async def post_bod(
    guilds: int,
    bot_user_id: int
) -> str:
    headers = {"Authorization": BOD_TOKEN, "Content-Type": "application/json"}
    data = json.dumps({"guildCount": guilds})
    url = f"https://bots.ondiscord.xyz/bot-api/bots/{bot_user_id}/guilds"

    r = await requests.post(url, data=data, headers=headers)
    return await r.text()


async def post_dbl(
    guilds: int,
    users: int,
    bot_user_id: int
) -> str:
    headers = {"Authorization": DBL_TOKEN, "Content-Type": "application/json"}
    data = json.dumps({
        "users": users,
        "guilds": guilds
    })
    url = f"https://discordbotlist.com/api/v1/bots/{bot_user_id}/stats"

    r = await requests.post(url, data=data, headers=headers)
    return await r.text()


async def post_boats(
    guilds: int,
    bot_user_id: int
) -> str:
    headers = {
        "Authorization": BOATS_TOKEN,
        "Content-Type": "application/json"
    }
    data = json.dumps({
        "server_count": guilds
    })
    url = f"https://discord.boats/api/bot/{bot_user_id}"

    r = await requests.post(url, data=data, headers=headers)
    return await r.text()


async def post_dbgg(
    guilds: int,
    bot_user_id: int
) -> str:
    headers = {"Authorization": DBGG_TOKEN, "Content-Type": "application/json"}
    data = json.dumps({
        "guildCount": guilds
    })
    url = f"https://discord.bots.gg/api/v1/bots/{bot_user_id}/stats"

    r = await requests.post(url, data=data, headers=headers)
    return await r.text()


async def post_del(
    guilds: int,
    bot_user_id: int
) -> str:
    headers = {"Authorization": DEL_TOKEN, "Content-Type": "application/json"}
    data = json.dumps({
        "guildCount": guilds
    })
    url = f"https://api.discordextremelist.xyz/v2/bot/{bot_user_id}/stats"

    r = await requests.post(url, data=data, headers=headers)
    return await r.text()


async def post_labs(
    guilds: int,
    bot_user_id: int
) -> str:
    headers = {"Content-Type": "application/json"}
    data = json.dumps({
        "token": LABS_TOKEN,
        "server_count": str(guilds)
    })
    url = f"https://bots.discordlabs.org/v2/bot/{bot_user_id}/stats"

    r = await requests.post(url, data=data, headers=headers)
    return await r.text()


async def post_all(
    guilds: int,
    users: int,
    bot_user_id: int
) -> str:
    bod = await post_bod(guilds, bot_user_id)
    dbl = await post_dbl(guilds, users, bot_user_id)
    boats = await post_boats(guilds, bot_user_id)
    dbgg = await post_dbgg(guilds, bot_user_id)
    bdel = await post_del(guilds, bot_user_id)
    labs = await post_labs(guilds, bot_user_id)
    return {
        'bots.ondiscord.xyz': bod,
        'discordbotlist.com': dbl,
        'discord.boats': boats,
        'discord.bots.gg': dbgg,
        'discordextremelist.xyz': bdel,
        'bots.discordlabs.org': labs
    }


class PostOther(commands.Cog):
    """Posts bot stats to different bot lists"""
    def __init__(
        self,
        bot: commands.Bot
    ) -> None:
        self.bot = bot
        self.post_bot_stats.start()

    @tasks.loop(minutes=60)
    async def post_bot_stats(self):
        await self.bot.wait_until_ready()
        users = 0
        for g in self.bot.guilds:
            try:
                users += g.member_count
            except AttributeError:
                pass
        await post_all(
            len(self.bot.guilds),
            users,
            self.bot.user.id
        )


class StatcordPost(commands.Cog):
    """Handles interactions with statcord"""
    def __init__(
        self,
        bot: commands.Bot
    ) -> None:
        self.bot = bot
        self.key = STATCORD_TOKEN
        self.api = statcord.Client(self.bot, self.key)
        self.api.start_loop()

    @commands.Cog.listener()
    async def on_command(
        self,
        ctx: commands.Context
    ) -> None:
        if str(ctx.message.author.id) == str(OWNER_ID):
            return
        self.api.command_run(ctx)


class TopGG(commands.Cog):
    """Handles interactions with the top.gg API"""

    def __init__(
        self,
        bot: commands.Bot
    ) -> None:
        self.bot = bot
        self.token = TOP_TOKEN
        self.dblpy = dbl.DBLClient(
            self.bot, self.token, autopost=True,
        )
        # Autopost will post your guild count every 30 minutes

    async def on_guild_post():
        print("Posted to top.gg")


def setup(
    bot: commands.Bot
) -> None:
    bot.add_cog(StatcordPost(bot))
    bot.add_cog(TopGG(bot))
    bot.add_cog(PostOther(bot))
