import requests
import json
import asyncio
import os

BOD_TOKEN = os.getenv("BOD_TOKEN")


def post_bod(bot):
    headers = {"Authorization": BOD_TOKEN, "Content-Type": "application/json"}
    data = json.dumps({"guildCount": len(bot.guilds)})
    url = "https://bots.ondiscord.xyz/bot-api/bots/700796664276844612/guilds"

    requests.post(url, data=data, headers=headers)


async def loop_post(bot):
    await bot.wait_until_ready()
    while True:
        post_bod(bot)
        await asyncio.sleep(60*10)
