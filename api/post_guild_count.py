from aiohttp_requests import requests
import json
import asyncio
import os

BOD_TOKEN = os.getenv("BOD_TOKEN")
DBL_TOKEN = os.getenv("DBL_TOKEN")
BOATS_TOKEN = os.getenv("BOATS_TOKEN")
DBGG_TOKEN = os.getenv("DBGG_TOKEN")


async def post_bod(guilds: int, bot_user_id: int):
    headers = {"Authorization": BOD_TOKEN, "Content-Type": "application/json"}
    data = json.dumps({"guildCount": guilds})
    url = f"https://bots.ondiscord.xyz/bot-api/bots/{bot_user_id}/guilds"

    r = await requests.post(url, data=data, headers=headers)
    return await r.text()


async def post_dbl(guilds: int, users: int, bot_user_id: int):
    headers = {"Authorization": DBL_TOKEN, "Content-Type": "application/json"}
    data = json.dumps({
        "users": users,
        "guilds": guilds
    })
    url = f"https://discordbotlist.com/api/v1/bots/{bot_user_id}/stats"

    r = await requests.post(url, data=data, headers=headers)
    return await r.text()


async def post_boats(guilds: int, bot_user_id: int):
    headers = {"Authorization": BOATS_TOKEN, "Content-Type": "application/json"}
    data = json.dumps({
        "server_count": guilds
    })
    url = f"https://discord.boats/api/bot/{bot_user_id}"

    r = await requests.post(url, data=data, headers=headers)
    return await r.text()


async def post_dbgg(guilds: int, bot_user_id: int):
    headers = {"Authorization": DBGG_TOKEN, "Content-Type": "application/json"}
    data = json.dumps({
        "guildCount": guilds
    })
    url = f"https://discord.bots.gg/api/v1/bots/{bot_user_id}/stats"

    r = await requests.post(url, data=data, headers=headers)
    return await r.text()


async def post_all(guilds: int, users: int, bot_user_id: int):
    bod = await post_bod(guilds, bot_user_id)
    dbl = await post_dbl(guilds, users, bot_user_id)
    boats = await post_boats(guilds, bot_user_id)
    dbgg = await post_dbgg(guilds, bot_user_id)
    return {
        'bots.ondiscord.xyz': bod,
        'discordbotlist.com': dbl,
        'discord.boats': boats,
        'bots.discord.gg': dbgg
    }


async def loop_post(bot):
    await bot.wait_until_ready()
    while True:
        await post_all(
            len(bot.guilds),
            len(bot.users),
            bot.user.id
        )
        await asyncio.sleep(60*10)
