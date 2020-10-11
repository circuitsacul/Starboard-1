# Put here for ease of use with statcord
from discord.ext import commands
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
        if ctx.message.author.id == self.bot.owner_id:
            return
        self.api.command_run(ctx)
