from functions import pretty_emoji_string
from discord.errors import NotFound
from discord.ext import commands
from bot_config import OWNER_ID
from discord.ext.commands.errors import NotOwner


def is_owner():
    async def predicate(ctx):
        if ctx.message.author.id != OWNER_ID:
            raise NotOwner("This command can only be run by the owner.")
        return True
    return commands.check(predicate)