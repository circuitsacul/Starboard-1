import functions
import cooldowns
from math import sqrt


give_cooldown = cooldowns.CooldownMapping.from_cooldown(
    3, 60
)
recv_cooldown = cooldowns.CooldownMapping.from_cooldown(
    3, 60
)


async def next_level_xp(current_level):
    current_level += 1
    return int(current_level**2)


async def current_level(xp):
    return int(sqrt(xp))


async def handle_reaction(db, reacter_id, receiver, guild, _emoji, is_add):
    guild_id = guild.id
    receiver_id = receiver.id
    if reacter_id == receiver_id:
        return
    emoji = _emoji.id if _emoji.id is not None else _emoji.name
    is_sbemoji = await functions.is_starboard_emoji(db, guild_id, emoji)
    if not is_sbemoji:
        print(emoji)
        return

    cooldown_over = True
    if is_add:
        b = give_cooldown.get_bucket(reacter_id)
    else:
        b = recv_cooldown.get_bucket(reacter_id)
    retry_after = b.update_rate_limit()
    if retry_after:
        cooldown_over = False

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

    async with db.lock:
        conn = await db.connect()
        async with conn.transaction():
            sql_reacter = await conn.fetchrow(get_member, reacter_id, guild_id)
            given = sql_reacter['given']+points
            given = 0 if given < 0 else given
            await conn.execute(
                set_points.format('given'), given, reacter_id, guild_id
            )

            sql_receiver = await conn.fetchrow(
                get_member, receiver_id, guild_id
            )
            received = sql_receiver['received']+points
            received = 0 if received < 0 else received
            await conn.execute(
                set_points.format('received'), received, receiver_id, guild_id
            )

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
                await conn.execute(
                    set_xp_level, new_xp, new_lvl,
                    sql_receiver['user_id'], guild_id
                )

    #if leveled_up and send_lvl_msgs:
    #    embed = discord.Embed(
    #        title="Level Up!",
    #        description=f"You've reached **{new_xp} XP** "
    #        f"and are now **level {new_lvl}**!",
    #        color=bot_config.COLOR
    #    )
    #    embed.set_thumbnail(url="https://i.ibb.co/bvYZ8V8/dizzy-1f4ab.png")
    #    embed.set_author(name=guild.name, icon_url=guild.icon_url)
    #    embed.set_footer(
    #        text="Tip: Disable these messages by running"
    #        " sb!profile lum false"
    #    )
    #    embed.timestamp = datetime.datetime.now()
    #    try:
    #        await receiver.send(
    #            embed=embed
    #        )
    #        pass
    #    except (discord.errors.HTTPException, AttributeError):
    #        pass
