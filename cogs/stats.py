# Put here for ease of use with statcord
from discord.ext import commands
from bot_config import OWNER_ID
import statcord
import os

STATCORD_TOKEN = os.getenv("STATCORD_TOKEN")


class StatcordPost(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.key = STATCORD_TOKEN
        self.api = statcord.Client(self.bot, self.key)
        self.api.start_loop()

    @commands.Cog.listener()
    async def on_command(self, ctx):
        if ctx.message.author.id == OWNER_ID:
            print("nope")
            return
        self.api.command_run(ctx)
