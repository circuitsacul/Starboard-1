import functions
import errors
from discord.ext import commands
from bot_config import OWNER_ID
from discord.ext.commands.errors import NotOwner


def is_owner():
    async def predicate(ctx):
        if ctx.message.author.id != OWNER_ID:
            raise NotOwner("This command can only be run by the owner.")
        return True
    return commands.check(predicate)


def premium_guild():
    async def predicate(ctx):
        endsat = await functions.get_prem_endsat(
            ctx.bot, ctx.guild.id
        )
        if endsat is None:
            raise errors.NoPremiumError(
                "Only premium guilds can run this command."
            )
        return True
    return commands.check(predicate)
