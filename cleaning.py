from typing import Dict

import discord
from discord.ext import commands


async def clean_all(
    bot: commands.Bot,
    guild: discord.Guild
) -> Dict[str, int]:
    s = await clean_starboards(bot, guild)
    a = await clean_aschannels(bot, guild)
    se = await clean_sbemojis(bot, guild)
    ae = await clean_asemojis(bot, guild)
    xr = await clean_xproles(bot, guild)
    pr = await clean_posroles(bot, guild)
    cb = await clean_channelbl(bot, guild)
    rb = await clean_rolebl(bot, guild)
    return {
        'starboards': s,
        'aschannels': a,
        'sbemojis': se,
        'asemojis': ae,
        'xproles': xr,
        'posroles': pr,
        'channelbl': cb,
        'rolebl': rb
    }


async def clean_starboards(
    bot: commands.Bot,
    guild: discord.Guild
) -> int:
    conn = bot.db.conn

    async with bot.db.lock:
        async with conn.transaction():
            starboards = await conn.fetch(
                """SELECT * FROM starboards
                WHERE guild_id=$1""", guild.id
            )

    to_delete = []

    for sb in starboards:
        sid = int(sb['id'])
        channel = guild.get_channel(sid)
        if channel is None:
            to_delete.append(sid)

    async with bot.db.lock:
        async with conn.transaction():
            await conn.execute(
                """DELETE FROM starboards
                WHERE id=ANY($1::numeric[])""",
                to_delete
            )

    return len(to_delete)


async def clean_aschannels(
    bot: commands.Bot,
    guild: discord.Guild
) -> int:
    conn = bot.db.conn

    async with bot.db.lock:
        async with conn.transaction():
            aschannels = await conn.fetch(
                """SELECT * FROM starboards
                WHERE guild_id=$1""", guild.id
            )

    to_delete = []

    for asc in aschannels:
        aid = int(asc['id'])
        channel = guild.get_channel(aid)
        if channel is None:
            to_delete.append(aid)

    async with bot.db.lock:
        async with conn.transaction():
            await conn.execute(
                """DELETE FROM aschannels
                WHERE id=ANY($1::numeric[])""",
                to_delete
            )

    return len(to_delete)


async def clean_sbemojis(
    bot: commands.Bot,
    guild: discord.Guild
) -> int:
    conn = bot.db.conn

    async with bot.db.lock:
        async with conn.transaction():
            starboard_ids = [
                int(s['id']) for s in await conn.fetch(
                    """SELECT * FROM starboards
                    WHERE guild_id=$1""", guild.id
                )
            ]
            sbemojis = await conn.fetch(
                """SELECT * FROM sbemojis
                WHERE starboard_id=ANY($1::numeric[])""",
                starboard_ids
            )

    to_delete = []

    for emoji in sbemojis:
        try:
            eid = int(emoji['name'])
        except ValueError:
            continue
        emoji_obj = discord.utils.get(guild.emojis, id=eid)
        if emoji_obj is None:
            to_delete.append(str(eid))

    async with bot.db.lock:
        async with conn.transaction():
            await conn.execute(
                """DELETE FROM sbemojis
                WHERE name=ANY($1::text[])""",
                to_delete
            )

    return len(to_delete)


async def clean_asemojis(
    bot: commands.Bot,
    guild: discord.Guild
) -> int:
    conn = bot.db.conn

    async with bot.db.lock:
        async with conn.transaction():
            aschannels_ids = [
                int(s['id']) for s in await conn.fetch(
                    """SELECT * FROM aschannels
                    WHERE guild_id=$1""", guild.id
                )
            ]
            asemojis = await conn.fetch(
                """SELECT * FROM asemojis
                WHERE aschannel_id=ANY($1::numeric[])""",
                aschannels_ids
            )

    to_delete = []

    for ase in asemojis:
        try:
            eid = int(ase['name'])
        except ValueError:
            continue
        emoji_obj = discord.utils.get(guild.emojis, id=eid)
        if emoji_obj is None:
            to_delete.append(str(eid))

    async with bot.db.lock:
        async with conn.transaction():
            await conn.execute(
                """DELETE FROM asemojis
                WHERE name=ANY($1::text[])""",
                to_delete
            )

    return len(to_delete)


async def clean_xproles(
    bot: commands.Bot,
    guild: discord.Guild
) -> int:
    conn = bot.db.conn

    async with bot.db.lock:
        async with conn.transaction():
            xproles = await conn.fetch(
                """SELECT * FROM xproles
                WHERE guild_id=$1""", guild.id
            )

    to_delete = []

    for r in xproles:
        rid = int(r['id'])
        role = guild.get_role(rid)
        if role is None:
            to_delete.append(rid)

    async with bot.db.lock:
        async with conn.transaction():
            await conn.execute(
                """DELETE FROM xproles
                WHERE id=ANY($1::numeric[])""",
                to_delete
            )

    return len(to_delete)


async def clean_posroles(
    bot: commands.Bot,
    guild: discord.Guild
) -> int:
    conn = bot.db.conn

    async with bot.db.lock:
        async with conn.transaction():
            posroles = await conn.fetch(
                """SELECT * FROM posroles
                WHERE guild_id=$1""", guild.id
            )

    to_delete = []

    for r in posroles:
        rid = int(r['id'])
        role = guild.get_role(rid)
        if role is None:
            to_delete.append(rid)

    async with bot.db.lock:
        async with conn.transaction():
            await conn.execute(
                """DELETE FROM posroles
                WHERE id=ANY($1::numeric[])""",
                to_delete
            )

    return len(to_delete)


async def clean_channelbl(
    bot: commands.Bot,
    guild: discord.Guild
) -> int:
    conn = bot.db.conn

    async with bot.db.lock:
        async with conn.transaction():
            channelbl = await conn.fetch(
                """SELECT * FROM channelbl
                WHERE guild_id=$1""", guild.id
            )

    to_delete = []

    for c in channelbl:
        cid = int(c['channel_id'])
        channel = guild.get_channel(cid)
        if channel is None:
            to_delete.append(cid)

    async with bot.db.lock:
        async with conn.transaction():
            await conn.execute(
                """DELETE FROM channelbl
                WHERE channel_id=ANY($1::numeric[])""",
                to_delete
            )

    return len(to_delete)


async def clean_rolebl(
    bot: commands.Bot,
    guild: discord.Guild
) -> int:
    conn = bot.db.conn

    async with bot.db.lock:
        async with conn.transaction():
            rolebl = await conn.fetch(
                """SELECT * FROM rolebl
                WHERE guild_id=$1""", guild.id
            )

    to_delete = []

    for r in rolebl:
        rid = int(r['role_id'])
        role = guild.get_role(rid)
        if role is None:
            to_delete.append(rid)

    async with bot.db.lock:
        async with conn.transaction():
            await conn.execute(
                """DELETE FROM rolebl
                WHERE role_id=ANY($1::numeric[])""",
                to_delete
            )

    return len(to_delete)
