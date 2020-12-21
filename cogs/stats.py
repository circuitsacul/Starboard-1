# Put here for ease of use with statcord
from discord.ext import commands
from bot_config import OWNER_ID
import statcord
import os
import dbl
from dotenv import load_dotenv

load_dotenv()


STATCORD_TOKEN = os.getenv("STATCORD_TOKEN")
TOP_TOKEN = os.getenv("TOP_TOKEN")
TOP_AUTH = os.getenv("TOP_HOOK_AUTH")


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
