import functions
import errors
import discord


async def add_starboard(bot: discord.Bot, channel: discord.TextChannel):
    check_starboard = \
        """SELECT * FROM starboards WHERE id=?"""
    get_starboards = \
        """SELECT * FROM starboards WHERE guild_id=?"""

    guild = channel.guild
    limit = await functions.get_limit(
        bot.db, 'starboards', guild
    )
    conn = bot.db.conn

    async with bot.db.lock:
        async with conn.transaction():
            all_starboards = await conn.fetch(
                get_starboards, guild.id
            )

    if len(all_starboards) + 1 > limit:
        raise errors.NoPremiumError(
            "You have reached your limit for starboards on this server."
            "\nTo add more starboards, the owner of this server must "
            "become a patron."
        )

    async with bot.db.lock:
        async with conn.transaction():
            sql_starboard = await conn.fetchrow(
                check_starboard, channel.id
            )

    if sql_starboard is not None:
        raise errors.AlreadyExists(
            "That is already a starboard!"
        )

    async with bot.db.lock:
        async with conn.transaction():

