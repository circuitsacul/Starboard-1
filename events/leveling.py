from inspect import Attribute
import discord, functions, bot_config
from discord.ext import commands
import datetime


async def next_level_xp(current_level):
    current_level += 1
    return int(current_level**2)


async def is_starboard_emoji(db, guild_id, emoji):
    emoji = str(emoji)
    get_starboards = \
        """SELECT * FROM starboards WHERE guild_id=$1"""
    get_sbeemojis = \
        """SELECT * FROM sbemojis WHERE starboard_id=$1"""

    conn = await db.connect()
    async with db.lock and conn.transaction():
        starboards = await conn.fetch(get_starboards, guild_id)
        all_emojis = []
        for starboard in starboards:
            emojis = await conn.fetch(get_sbeemojis, starboard['id'])
            all_emojis += [str(e['name']) if e['d_id'] is None else e['d_id'] for e in emojis]
    await conn.close()
    return emoji in all_emojis


async def handle_reaction(db, reacter_id, receiver, guild, _emoji, is_add):
    guild_id = guild.id
    receiver_id = receiver.id
    if reacter_id == receiver_id:
        return
    emoji = _emoji.id if _emoji.id is not None else _emoji.name
    is_sbemoji = await is_starboard_emoji(db, guild_id, emoji)
    if not is_sbemoji:
        return

    now = datetime.datetime.now()
    timestamp = now.timestamp()
    cooldown_end = now + datetime.timedelta(minutes=1)

    cooldown_over = True
    async with db.lock:
        db_stars = db.cooldowns['giving_stars']
        db_stars.setdefault(guild_id, {})
        if timestamp < db_stars[guild_id].get(reacter_id, 0): # Y2038 (was 2147483647)
            cooldown_over = False
        if cooldown_over:
            db_stars[guild_id][reacter_id] = cooldown_end.timestamp()

    get_member = \
        """SELECT * FROM members WHERE user_id=$1 AND guild_id=$2"""
    get_user = \
        """SELECT * FROM users WHERE id=$1"""
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

    leveled_up = False

    conn = await db.connect()
    async with db.lock and conn.transaction():
        sql_reacter = await conn.fetchrow(get_member, reacter_id, guild_id)
        given = sql_reacter['given']+points
        await conn.execute(set_points.format('given'), given, reacter_id, guild_id)

        sql_receiver = await conn.fetchrow(get_member, receiver_id, guild_id)
        received = sql_receiver['received']+points
        await conn.execute(set_points.format('received'), received, receiver_id, guild_id)

        sql_receiver_user = await conn.fetchrow(get_user, receiver_id)
        send_lvl_msgs = sql_receiver_user['lvl_up_msgs']

        current_lvl = sql_receiver['lvl']
        current_xp = sql_receiver['xp']
        needed_xp = await next_level_xp(current_lvl)
        
        new_xp = current_xp + points
        new_xp = 0 if new_xp < 0 else new_xp
        new_lvl = current_lvl + 1 if new_xp >= needed_xp else current_lvl
        leveled_up = new_lvl > current_lvl if cooldown_over else False


        if cooldown_over:
        #    current_lvl = sql_receiver['lvl']
        #    current_xp = sql_receiver['xp']
        #    needed_xp = await next_level_xp(current_lvl)

        #    next_xp = current_xp + points
        #    next_lvl = current_lvl
        #    if next_xp >= needed_xp:
        #       next_lvl += 1
        #       leveled_up = True
        #    #elif next_xp < 0:
        #    #    next_lvl -= 1
        #    #    next_lvl = 0 if next_lvl < 0 else next_lvl
        #    #    next_xp = await next_level_xp(next_lvl)-1
        #    #    level_direction = -1

            await conn.execute(
                set_xp_level, new_xp, new_lvl,
                sql_receiver['user_id'], guild_id
            )

    await conn.close()

    if leveled_up and send_lvl_msgs:
        embed = discord.Embed(
            title=f"Level Up!",
            description=f"You've reached **{new_xp} XP** and are now **level {new_lvl}**!",
            color=bot_config.COLOR
        )
        embed.set_thumbnail(url="https://i.ibb.co/bvYZ8V8/dizzy-1f4ab.png")
        embed.set_footer(text=guild.name, icon_url=guild.icon_url)
        embed.timestamp = datetime.datetime.now()
        try:
            await receiver.send(embed=embed)
            pass
        except (discord.errors.HTTPException, AttributeError):
            pass
