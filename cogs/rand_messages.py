import random
import bot_config
from discord.ext import commands


def do_now() -> bool:
    if random.randint(0, 400) == 0:
        return True
    return False


class RandomMessages(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command(self, ctx):
        if do_now():
            await ctx.send(random.choice(bot_config.RANDOM_MESSAGES))


def setup(bot):
    bot.add_cog(RandomMessages(bot))
