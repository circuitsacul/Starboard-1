from discord import utils


def _get_id(string: str):
    string = string.replace('<', '').replace('>', '')\
        .replace('@', '').replace('&', '').replace('!', '')\
        .replace('#', '')
    try:
        as_int = int(string)
    except ValueError:
        return None
    return as_int


async def get_channel(guild, string: str):
    channel = None
    as_id = _get_id(string)
    if as_id is not None:
        channel = utils.get(guild.channels, id=as_id)
    else:
        channel = utils.get(guild.channels, name=string)
    return channel
