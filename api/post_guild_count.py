from aiohttp_requests import requests
from discord.ext import commands
import json
import asyncio
import os

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


async def loop_post(
    bot: commands.Bot
) -> None:
    await bot.wait_until_ready()
    while True:
        await post_all(
            len(bot.guilds),
            len(bot.users),
            bot.user.id
        )
        await asyncio.sleep(60*10)
