import requests
import json
import asyncio
import os

BOD_TOKEN = os.getenv("BOD_TOKEN")
DBL_TOKEN = os.getenv("DBL_TOKEN")
BOATS_TOKEN = os.getenv("BOATS_TOKEN")


def post_bod(guilds: int, bot_user_id: int):
    headers = {"Authorization": BOD_TOKEN, "Content-Type": "application/json"}
    data = json.dumps({"guildCount": guilds})
    url = f"https://bots.ondiscord.xyz/bot-api/bots/{bot_user_id}/guilds"

    requests.post(url, data=data, headers=headers)


def post_dbl(guilds: int, users: int, bot_user_id: int):
    # NOTE: This function, for some reason, does not actually work.
    # If you find a fix, please let me know, for now it does nothing.
    return
    headers = {"Authorization": DBL_TOKEN, "Content-Type": "application/json"}
    data = json.dumps({
        "users": users,
        "guilds": guilds
    })
    url = f"https://discordbotlist.com/api/v1/bots/:{bot_user_id}/stats"

    requests.post(url, data=data, headers=headers)


def post_boats(guilds: int, bot_user_id: int):
    headers = {"Authorization": BOATS_TOKEN, "Content-Type": "application/json"}
    data = json.dumps({
        "server_count": guilds
    })
    url = f"https://discord.boats/api/bot/:{bot_user_id}"

    requests.post(url, data=data, headers=headers)


def post_all(guilds: int, users: int, bot_user_id: int):
    post_bod(guilds, bot_user_id)
    #post_dbl(guilds, users, bot_user_id)
    post_boats(guilds, bot_user_id)


async def loop_post(bot):
    await bot.wait_until_ready()
    while True:
        post_all(
            len(bot.guilds),
            len(bot.users),
            bot.user.id
        )
        await asyncio.sleep(60*10)
