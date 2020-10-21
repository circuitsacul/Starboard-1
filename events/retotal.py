import functions


# Check and recount stars on a message when necessary
async def needs_recount(bot, message):
    get_reactions = \
        """SELECT * FROM reactions WHERE message_id=$1"""

    total = 0
    for r in message.reactions:
        total += r.count

    if total <= 1:  # Don't recount if the message only has 1 reaction (or 0)
        return False

    async with bot.db.lock:
        conn = bot.db.conn
        async with conn.transaction():
            reactions = await conn.fetch(
                get_reactions, message.id
            )
            sql_total = len(reactions)

    if sql_total < 0.3*total:
        # recount if the bot has logged less than 30% of the reactions
        return True
    return False


async def recount_reactions(bot, message):
    check_reaction = \
        """SELECT * FROM reactions WHERE
        message_id=$1 AND name=$2 AND user_id=$3"""

    # hard to explain why, but I also remove the message
    # from the cache when recounting the stars on it
    await bot.db.cache.remove(message.id, message.guild.id)

    # [{'user_id': user_id, 'name': name}, ...]
    # other values can be determined from the message object
    to_add = []

    for reaction in message.reactions:
        if reaction.custom_emoji:
            name = str(reaction.emoji.id)
        else:
            name = str(reaction.emoji)
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
