import functions
import errors
import discord
from discord.ext import commands


async def add_starboard(bot: commands.Bot, channel: discord.TextChannel):
    check_starboard = \
        """SELECT * FROM starboards WHERE id=$1"""
    get_starboards = \
        """SELECT * FROM starboards WHERE guild_id=$1"""

    guild = channel.guild
    perms = channel.permissions_for(guild.me)

    if not perms.read_messages:
        raise errors.BotNeedsPerms(
            "I need the `READ MESSAGES` permission in that channel."
        )
    elif not perms.read_message_history:
        raise errors.BotNeedsPerms(
            "I need the `READ MESSAGE HISTORY` permission in that channel."
        )
    elif not perms.send_messages:
        raise errors.BotNeedsPerms(
            "I need the `SEND MESSAGES` permission in that channel."
        )
    elif not perms.embed_links:
        raise errors.BotNeedsPerms(
            "I need the `EMBED LINKS` permission in that channel."
        )
    elif not perms.add_reactions:
        raise errors.BotNeedsPerms(
            "I need the `ADD REACTIONS` permission in that channel."
        )

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
                    "You have reached your limit for starboards on this server"
                    "\nTo add more starboards, the owner of this server must "
                    "become a patron."
                )

            sql_starboard = await conn.fetchrow(
                check_starboard, channel.id
            )

            if sql_starboard is not None:
                raise errors.AlreadyExists(
                    "That is already a starboard!"
                )

            await bot.db.q.create_starboard.fetch(channel.id, guild.id)


async def remove_starboard(bot: commands.Bot, channel_id: int, guild_id: int):
    check_starboard = \
        """SELECT * FROM starboards WHERE id=$1 AND guild_id=$2"""
    del_starboard = \
        """DELETE FROM starboards WHERE id=$1"""

    conn = bot.db.conn

    async with bot.db.lock:
        async with conn.transaction():
            sql_starboard = await conn.fetchrow(
                check_starboard, channel_id, guild_id
            )

            if sql_starboard is None:
                raise errors.DoesNotExist(
                    "That is not a starboard!"
                )

            await conn.execute(
                del_starboard, channel_id
            )
