import discord
from discord import utils
from typing import Optional


def _get_id(
    string: str
) -> int:
    string = string.replace('<', '').replace('>', '')\
        .replace('@', '').replace('&', '').replace('!', '')\
        .replace('#', '')
    try:
        as_int = int(string)
    except ValueError:
        return None
    return as_int


async def get_channel(
    guild: discord.Guild,
    string: str
) -> Optional[discord.TextChannel]:
    channel = None
    as_id = _get_id(string)
    if as_id is not None:
        channel = utils.get(guild.channels, id=as_id)
    else:
        channel = utils.get(guild.channels, name=string)
    return channel
