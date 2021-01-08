import random

from discord.ext import commands

import bot_config


def do_now() -> bool:
    if random.randint(0, bot_config.MESSAGE_CHANCE) == 0:
        return True
    return False


class RandomMessages(commands.Cog):
    """Occasionaly sends a random messages after a command is run"""
    def __init__(
        self,
        bot: commands.Bot
    ) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_command(
        self,
        ctx: commands.Context
    ) -> None:
        if do_now():
            await ctx.send(random.choice(bot_config.RANDOM_MESSAGES))


def setup(
    bot: commands.Bot
) -> None:
    bot.add_cog(RandomMessages(bot))
