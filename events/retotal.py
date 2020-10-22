import functions


async def is_starboard_emoji(db, guild_id, emoji):
    emoji = str(emoji)
    get_starboards = \
        """SELECT * FROM starboards WHERE guild_id=$1"""
    get_sbeemojis = \
        """SELECT * FROM sbemojis WHERE starboard_id=$1"""

    async with db.lock:
        conn = await db.connect()
        async with conn.transaction():
            starboards = await conn.fetch(get_starboards, guild_id)
            all_emojis = []
            for starboard in starboards:
                emojis = await conn.fetch(get_sbeemojis, starboard['id'])
                #all_emojis += [
                #    str(e['name']) if e['d_id'] is None
                #    else str(e['d_id']) for e in emojis
                #]
                all_emojis += [e['name'] for e in emojis]
    return str(emoji) in all_emojis


# Check and recount stars on a message when necessary
async def needs_recount(bot, message):
    get_reactions = \
        """SELECT * FROM reactions WHERE message_id=$1"""

    if message is None:
        return False

    total = 0
    for r in message.reactions:
        if r.custom_emoji:
            name = str(r.emoji.id)
        else:
            name = str(r.emoji)
        if await is_starboard_emoji(bot.db, message.guild.id, name):
            total += r.count

    if total == 0:  # Don't recount if the message doesn't have reactions
        return False

    async with bot.db.lock:
        conn = bot.db.conn
        async with conn.transaction():
            reactions = await conn.fetch(
                get_reactions, message.id
            )
            sql_total = len(reactions)

    if sql_total < 0.5*total and total-sql_total > 2:
        # recount if the bot has logged less than 10% of the reactions
        return True
    return False


async def recount_reactions(bot, message):
    print("Recounting")
    check_reaction = \
        """SELECT * FROM reactions WHERE
        message_id=$1 AND name=$2 AND user_id=$3"""

    # hard to explain why, but I also remove the message
    # from the cache when recounting the stars on it
    await bot.db.cache.remove(message.id, message.guild.id)
    message = await functions.fetch(bot, message.id, message.channel)
    if message is None:
        return

    # [{'user_id': user_id, 'name': name}, ...]
    # other values can be determined from the message object
    to_add = []

    for reaction in message.reactions:
        if reaction.custom_emoji:
            name = str(reaction.emoji.id)
        else:
            name = str(reaction.emoji)

        if not await is_starboard_emoji(bot.db, message.guild.id, name):
            continue

        async for user in reaction.users():
            if user is None:
                continue
            elif user.bot:
                continue
            to_add.append({
                'user': user, 'name': name
            })

    async with bot.db.lock:
        conn = bot.db.conn
        async with conn.transaction():
            for r in to_add:
                await functions.check_or_create_existence(
                    bot.db, conn, bot,
                    guild_id=message.guild.id,
                    user=r['user'], do_member=True
                )

                sql_r = await conn.fetchrow(
                    check_reaction, message.id, r['name'],
                    r['user'].id
                )
                if sql_r is not None:
                    continue

                await bot.db.q.create_reaction.fetch(
                    message.guild.id, r['user'].id,
                    message.id, r['name']
                )
