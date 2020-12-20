import functions
from events import starboard_events
from itertools import compress


# Check and recount stars on a message when necessary
async def needs_recount(bot, message):
    get_reactions = \
        """SELECT * FROM reactions WHERE message_id=$1"""

    if message is None:
        return False

    total = 0
    reactions = [
        str(r.emoji.id) if r.custom_emoji else str(r.emoji)
        for r in message.reactions
    ]
    reaction_mask = await functions.is_starboard_emoji(
        bot.db, message.guild.id, reactions, multiple=True
    )
    for r in compress(message.reactions, reaction_mask):
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
    check_reaction = \
        """SELECT * FROM reactions WHERE
        message_id=$1 AND name=$2 AND user_id=$3"""
    check_message = \
        """SELECT * FROM messages
        WHERE id=$1"""

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

        if not await functions.is_starboard_emoji(
            bot.db, message.guild.id, name
        ):
            continue

        async for user in reaction.users():
            if user is None:
                continue
            elif user.bot:
                continue
            to_add.append({
                'user': user, 'name': name
            })

    conn = bot.db.conn

    async with bot.db.lock:
        async with conn.transaction():
            sql_m = await conn.fetchrow(
                check_message, message.id
            )
            if sql_m and sql_m['is_orig'] is False:
                print("No")
                return
            elif sql_m is None:
                await bot.db.q.create_message.fetch(
                    message.id, message.guild.id,
                    message.author.id, None,
                    message.channel.id, True,
                    message.channel.is_nsfw()
                )

    for r in to_add:
        await functions.check_or_create_existence(
            bot,
            guild_id=message.guild.id,
            user=r['user'], do_member=True
        )

        async with bot.db.lock:
            async with conn.transaction():
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

    await starboard_events.handle_starboards(
        bot.db, bot, message.id, message.channel, message,
        message.guild
    )
