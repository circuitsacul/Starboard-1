from functions import pretty_emoji_string
from discord.errors import NotFound
from discord.ext import commands
from bot_config import OWNER_ID
from discord.ext.commands.errors import NotOwner


class WizzardRunningError(commands.CheckFailure):
    pass


def no_wizzard_running():
    async def predicate(ctx):
        can_run = True
        async with ctx.bot.wizzard_lock():
            if ctx.guild.id in ctx.bot.running_wizzards:
                raise WizzardRunningError(
                    "This command cannot be called while a setup"
                    " wizzard is running."
                )
        return can_run
    return commands.check(predicate)


def is_owner():
    async def predicate(ctx):
        if ctx.message.author.id != OWNER_ID:
            raise NotOwner("This command can only be run by the owner.")
        return True
    return commands.check(predicate)