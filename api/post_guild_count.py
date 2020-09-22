import requests
import json
import asyncio


def post_bod(bot):
    headers = {"Authorization": "397006357cfdb58b33143eafa0f3d696", "Content-Type": "application/json"}
    data = json.dumps({"guildCount": len(bot.guilds)})
    url = "https://bots.ondiscord.xyz/bot-api/bots/700796664276844612/guilds"

    requests.post(url, data=data, headers=headers)


async def loop_post(bot):
    await bot.wait_until_ready()
    while True:
        print("Posting")
        post_bod(bot)
        await asyncio.sleep(60*10)