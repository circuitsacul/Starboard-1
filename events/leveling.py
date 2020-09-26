from inspect import Attribute
import discord, functions, bot_config
from discord.ext import commands
import datetime


async def next_level_xp(current_level):
    current_level += 1
    return round(current_level**2)


async def is_starboard_emoji(db, guild_id, emoji):
    emoji = str(emoji)
    get_starboards = \
        """SELECT * FROM starboards WHERE guild_id=$1"""
    get_sbeemojis = \
        """SELECT * FROM sbemojis WHERE starboard_id=$1"""

    conn = await db.connect()
    async with db.lock and conn.transaction():
        starboards = await conn.fetch(get_starboards, str(guild_id))
        all_emojis = []
        for starboard in starboards:
            emojis = await conn.fetch(get_sbeemojis, starboard['id'])
            all_emojis += [str(e['name']) if e['d_id'] in [None, 'None'] else str(e['d_id']) for e in emojis]
    await conn.close()
    return emoji in all_emojis


async def handle_reaction(db, reacter_id, receiver, guild, _emoji, is_add):
    guild_id = guild.id
    receiver_id = receiver.id
    if str(reacter_id) == str(receiver_id):
        return
    emoji = _emoji.id if _emoji.id is not None else _emoji.name
    is_sbemoji = await is_starboard_emoji(db, guild_id, emoji)
    if not is_sbemoji:
        return

    get_member = \
        """SELECT * FROM members WHERE user_id=$1 AND guild_id=$2"""
    set_points = \
        """UPDATE members
        SET {}=$1
        WHERE user_id=$2 AND guild_id=$3"""
    set_xp_level = \
        """UPDATE members
        SET xp=$1,
        lvl=$2
        WHERE user_id=$3 AND guild_id=$4"""

    points = 1 if is_add is True else -1

    conn = await db.connect()
    async with db.lock and conn.transaction():
        sql_reacter = await conn.fetchrow(get_member, str(reacter_id), str(guild_id))
        given = sql_reacter['given']+points
        await conn.execute(set_points.format('given'), given, str(reacter_id), str(guild_id))

        sql_receiver = await conn.fetchrow(get_member, str(receiver_id), str(guild_id))
        received = sql_receiver['received']+points
        await conn.execute(set_points.format('received'), received, str(receiver_id), str(guild_id))

        current_lvl = sql_receiver['lvl']
        current_xp = sql_receiver['xp']
        needed_xp = await next_level_xp(current_lvl)

        next_xp = current_xp + points
        next_lvl = current_lvl
        level_direction = 0
        if next_xp >= needed_xp:
            next_lvl += 1
            next_xp = next_xp-needed_xp
            level_direction = 1
        elif next_xp < 0:
            next_lvl -= 1
            next_lvl = 0 if next_lvl < 0 else next_lvl
            next_xp = await next_level_xp(next_lvl)-1
            level_direction = -1

        await conn.execute(
            set_xp_level, next_xp, next_lvl,
            sql_receiver['user_id'], str(guild_id)
        )

    await conn.close()

    if level_direction in [1]:
        embed = discord.Embed(
            title=f"Level Up!",
            description=f"You've reached a total of **{received} stars** and are now **level {next_lvl}**!",
            color=bot_config.COLOR
        )
        embed.set_thumbnail(url="https://i.ibb.co/bvYZ8V8/dizzy-1f4ab.png")
        embed.set_footer(text=guild.name, icon_url=guild.icon_url)
        embed.timestamp = datetime.datetime.now()
        try:
            await receiver.send(embed=embed)
        except (discord.errors.HTTPException, AttributeError):
            pass
