from typing import Union, Optional

import discord
from discord.ext import commands

import errors
import functions
from database.database import Database  # for type hinting
from errors import DoesNotExist


async def change_starboard_settings(
    db: Database,
    starboard_id: int,
    self_star: bool = None,
    link_edits: bool = None,
    link_deletes: bool = None,
    bots_on_sb: bool = None,
    required: int = None,
    rtl: int = None
) -> Optional[bool]:
    get_starboard = \
        """SELECT * FROM starboards WHERE id=$1"""
    update_starboard = \
        """UPDATE starboards
        SET self_star=$1,
        link_edits=$2,
        link_deletes=$3,
        bots_on_sb=$4,
        required=$5,
        rtl=$6
        WHERE id=$7"""

    if required is not None:
        if required > 100:
            required = 100
        elif required < 1:
            required = 1
    if rtl is not None:
        if rtl > 95:
            rtl = 95
        elif rtl < -1:
            rtl = -1

    async with db.lock:
        conn = await db.connect()
        status = True
        async with conn.transaction():
            rows = await conn.fetch(get_starboard, starboard_id)
            if len(rows) == 0:
                status = None
            else:
                ssb = rows[0]

                s = {}
                s['ss'] = self_star if self_star is not None \
                    else ssb['self_star']
                s['le'] = link_edits if link_edits is not None \
                    else ssb['link_edits']
                s['ld'] = link_deletes if link_deletes is not None \
                    else ssb['link_deletes']
                s['bos'] = bots_on_sb if bots_on_sb is not None \
                    else ssb['bots_on_sb']
                s['r'] = required if required is not None \
                    else ssb['required']
                s['rtl'] = rtl if rtl is not None \
                    else ssb['rtl']

                if s['r'] <= s['rtl']:
                    status = False
                else:
                    try:
                        await conn.execute(
                            update_starboard,
                            s['ss'], s['le'], s['ld'], s['bos'], s['r'],
                            s['rtl'], starboard_id
                        )
                    except Exception as e:
                        print(e)
                        status = False
    return status


async def change_aschannel_settings(
    db: Database,
    aschannel_id: int,
    min_chars: int = None,
    require_image: bool = None,
    delete_invalid: bool = None
) -> None:
    get_aschannel = \
        """SELECT * FROM aschannels WHERE id=$1"""
    update_aschannel = \
        """UPDATE aschannels
        SET min_chars=$1,
        require_image=$2,
        delete_invalid=$3
        WHERE id=$4"""

    conn = db.conn
    async with db.lock:
        async with conn.transaction():
            sasc = await conn.fetchrow(
                get_aschannel, aschannel_id
            )
            if sasc is None:
                raise errors.DoesNotExist("That is not an AutoStar Channel!")

            s = {}
            s['mc'] = min_chars if min_chars is not None else sasc['min_chars']
            s['ri'] = require_image if require_image is not None\
                else sasc['require_image']
            s['di'] = delete_invalid if delete_invalid is not None\
                else sasc['delete_invalid']

            if s['mc'] < 0:
                s['mc'] = 0
            elif s['mc'] > 1024:
                s['mc'] = 1024

            await conn.execute(
                update_aschannel, s['mc'], s['ri'], s['di'],
                aschannel_id
            )


async def add_aschannel(
    bot: commands.Bot,
    channel: discord.TextChannel
) -> None:
    check_aschannel = \
        """SELECT * FROM aschannels WHERE id=$1"""
    check_starboard = \
        """SELECT * FROM starboards WHERE id=$1"""
    get_aschannels = \
        """SELECT * FROM aschannels WHERE guild_id=$1"""

    # just in case we messed something up earlier and it's already in there
    if channel.id not in bot.db.as_cache:
        bot.db.as_cache.add(channel.id)

    guild = channel.guild
    perms = channel.permissions_for(guild.me)
    limit = await functions.get_limit(
        bot, 'aschannels', guild.id
    )
    conn = bot.db.conn

    if not perms.read_messages:
        raise errors.BotNeedsPerms(
            "I need the 'READ MESSAGES' permission in that channel."
        )
    elif not perms.manage_messages:
        raise errors.BotNeedsPerms(
            "I need the `MANAGE MESSAGES` permission in that channel."
        )
    elif not perms.add_reactions:
        raise errors.BotNeedsPerms(
            "I need the `ADD REACTIONS` permission in that channel."
        )

    await functions.check_or_create_existence(
        bot, guild_id=guild.id
    )

    async with bot.db.lock:
        async with conn.transaction():
            all_aschannels = await conn.fetch(
                get_aschannels, guild.id
            )

            if len(all_aschannels) >= limit:
                raise errors.NoPremiumError(
                    "You have reached your limit for AutoStar Channels"
                    " in this server.\nSee the last page of `sb!tutorial` "
                    "for more info."
                )

            sql_aschannel = await conn.fetchrow(
                check_aschannel, channel.id
            )

            if sql_aschannel is not None:
                raise errors.AlreadyExists(
                    "That is already an AutoStar Channel!"
                )

            sql_starboard = await conn.fetchrow(
                check_starboard, channel.id
            )

            if sql_starboard is not None:
                raise errors.AlreadyExists(
                    "That channel is already a starboard!\n"
                    "A channel can't be both a starboard and an "
                    "AutoStar channel."
                )

            await bot.db.q.create_aschannel.fetch(
                channel.id, guild.id
            )


async def remove_aschannel(
    bot: commands.Bot,
    channel_id: int,
    guild_id: int
) -> None:
    check_aschannel = \
        """SELECT * FROM aschannels WHERE id=$1 AND guild_id=$2"""
    del_aschannel = \
        """DELETE FROM aschannels WHERE id=$1"""

    conn = bot.db.conn
    # just in case we messed something up earlier and it's not in there
    if channel_id in bot.db.as_cache:
        bot.db.as_cache.remove(channel_id)

    async with bot.db.lock:
        async with conn.transaction():
            sql_aschannel = await conn.fetchrow(
                check_aschannel, channel_id, guild_id
            )

            if sql_aschannel is None:
                raise errors.DoesNotExist("That is not an AutoStar Channel!")

            await conn.execute(del_aschannel, channel_id)

    await functions.refresh_guild_premium(bot, guild_id, send_alert=False)


async def add_asemoji(
    bot: commands.Bot,
    aschannel: discord.TextChannel,
    name: str
) -> None:
    check_aschannel = \
        """SELECT * FROM aschannels WHERE id=$1"""
    check_asemoji = \
        """SELECT * FROM asemojis WHERE name=$1 and aschannel_id=$2"""

    conn = bot.db.conn

    async with bot.db.lock:
        async with conn.transaction():
            sasc = await conn.fetchrow(
                check_aschannel, aschannel.id
            )
            if sasc is None:
                raise errors.DoesNotExist("That is not an AutoStar Channel!")

            se = await conn.fetchrow(
                check_asemoji, name, aschannel.id
            )
            if se is not None:
                raise errors.AlreadyExists(
                    "That emoji is already on this AutoStar Channel!"
                )

            await bot.db.q.create_asemoji.fetch(
                aschannel.id, name
            )


async def remove_asemoji(
    bot: commands.Bot,
    aschannel: discord.TextChannel,
    name: str
) -> None:
    check_aschannel = \
        """SELECT * FROM aschannels WHERE id=$1"""
    check_asemoji = \
        """SELECT * FROM asemojis WHERE name=$1 AND aschannel_id=$2"""
    del_asemojis = \
        """DELETE FROM asemojis WHERE id=$1"""

    conn = bot.db.conn

    async with bot.db.lock:
        async with conn.transaction():
            sasc = await conn.fetchrow(
                check_aschannel, aschannel.id
            )
            if sasc is None:
                raise errors.DoesNotExist("That is not an AutoStar Channel!")

            se = await conn.fetchrow(
                check_asemoji, name, aschannel.id
            )
            if se is None:
                raise errors.DoesNotExist(
                    "That emoji is not on that AutoStar Channel!"
                )

            await conn.execute(
                del_asemojis, se['id']
            )


async def add_starboard(
    bot: commands.Bot,
    channel: discord.TextChannel
) -> None:
    check_starboard = \
        """SELECT * FROM starboards WHERE id=$1"""
    check_aschannel = \
        """SELECT * FROM aschannels WHERE id=$1"""
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
        bot, 'starboards', guild.id
    )
    conn = bot.db.conn

    await functions.check_or_create_existence(
        bot, channel.guild.id
    )
    async with bot.db.lock:
        async with conn.transaction():
            all_starboards = await conn.fetch(
                get_starboards, guild.id
            )

            if len(all_starboards) + 1 > limit:
                raise errors.NoPremiumError(
                    "You have reached your limit for starboards on this server"
                    "\nSee the last page of `sb!tutorial` for more info."
                )

            sql_starboard = await conn.fetchrow(
                check_starboard, channel.id
            )

            if sql_starboard is not None:
                raise errors.AlreadyExists(
                    "That is already a starboard!"
                )

            sql_aschannel = await conn.fetchrow(
                check_aschannel, channel.id
            )

            if sql_aschannel is not None:
                raise errors.AlreadyExists(
                    "That channel is already an AutoStar channel!\n"
                    "A channel can't be both an AutoStar channel "
                    "and a starboard."
                )

            await bot.db.q.create_starboard.fetch(channel.id, guild.id)

    await add_starboard_emoji(bot, channel.id, channel.guild, '⭐')


async def remove_starboard(
    bot: commands.Bot,
    channel_id: int,
    guild_id: int
) -> None:
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

    await functions.refresh_guild_premium(bot, guild_id, send_alert=False)


async def add_starboard_emoji(
    bot: commands.Bot,
    starboard_id: int,
    guild: discord.Guild,
    emoji: Union[discord.Emoji, str]
) -> None:
    check_sbemoji = \
        """SELECT * FROM sbemojis WHERE name=$1 AND starboard_id=$2"""
    get_all_sbemojis = \
        """SELECT * FROM sbemojis WHERE starboard_id=$1"""
    check_starboard = \
        """SELECT * FROM starboards WHERE id=$1"""

    if not isinstance(emoji, discord.Emoji):
        if not functions.is_emoji(emoji):
            raise errors.InvalidArgument(
                "I don't recognize that emoji. If it is a custom "
                "emoji, it has to be in this server."
            )

    emoji_name = str(emoji.id) if isinstance(
        emoji, discord.Emoji) else str(emoji)
    emoji_id = emoji.id if isinstance(
        emoji, discord.Emoji) else None

    limit = await functions.get_limit(bot, 'emojis', guild.id)
    conn = bot.db.conn

    async with bot.db.lock:
        async with conn.transaction():
            sql_starboard = await conn.fetchrow(
                check_starboard, starboard_id
            )

            if sql_starboard is None:
                raise errors.DoesNotExist("That is not a starboard!")

            all_sbemojis = await conn.fetch(
                get_all_sbemojis, starboard_id
            )

            if len(all_sbemojis) + 1 > limit:
                raise errors.NoPremiumError(
                    "You have reached your limit for emojis "
                    "on this starboard.\nSee the last page of "
                    "`sb!tutorial` for more info."
                )

            sbemoji = await conn.fetchrow(
                check_sbemoji, emoji_name, starboard_id
            )

            if sbemoji is not None:
                raise errors.AlreadyExists(
                    "That is already a starboard emoji!"
                )

            await bot.db.q.create_sbemoji.fetch(
                emoji_id, starboard_id, emoji_name, False
            )


async def remove_starboard_emoji(
    bot: commands.Bot,
    starboard_id: int,
    guild: discord.Guild,
    emoji: Union[discord.Emoji, str]
) -> None:
    check_sbemoji = \
        """SELECT * FROM sbemojis WHERE name=$1 AND starboard_id=$2"""
    check_starboard = \
        """SELECT * FROM starboards WHERE id=$1"""
    del_sbemoji = \
        """DELETE FROM sbemojis WHERE name=$1 AND starboard_id=$2"""

    emoji_name = str(emoji.id) if isinstance(emoji, discord.Emoji) else emoji
    conn = bot.db.conn

    async with bot.db.lock:
        async with conn.transaction():
            sql_starboard = await conn.fetchrow(
                check_starboard, starboard_id
            )

            if sql_starboard is None:
                raise DoesNotExist(
                    "That is not a starboard!"
                )

            sbemoji = await conn.fetchrow(
                check_sbemoji, emoji_name, starboard_id
            )

            if sbemoji is None:
                raise DoesNotExist(
                    "That is not a starboard emoji!"
                )

            await conn.execute(
                del_sbemoji, emoji_name, starboard_id
            )


async def add_channel_blacklist(
    bot: commands.Bot,
    channel_id: int,
    starboard_id: int,
    guild_id: int,
    is_whitelist: bool = False
) -> None:
    check_exists = \
        """SELECT * FROM channelbl WHERE channel_id=$1 AND starboard_id=$2"""
    check_starboard = \
        """SELECT * FROM starboards WHERE id=$1 AND guild_id=$2"""

    conn = bot.db.conn

    async with bot.db.lock:
        async with conn.transaction():
            sql_channelbl = await conn.fetchrow(
                check_exists, channel_id, starboard_id
            )
            if sql_channelbl is not None:
                raise errors.AlreadyExists(
                    "That channel is already whitelisted/blacklisted"
                )

            sql_starboard = await conn.fetchrow(
                check_starboard, starboard_id, guild_id
            )
            if sql_starboard is None:
                raise errors.DoesNotExist(
                    "That is not a starboard!"
                )

            await bot.db.q.create_channelbl.fetch(
                starboard_id, channel_id, guild_id, is_whitelist
            )


async def remove_channel_blacklist(
    bot: commands.Bot,
    channel_id: int,
    starboard_id: int
) -> None:
    check_exists = \
        """SELECT * FROM channelbl WHERE channel_id=$1 AND starboard_id=$2"""
    delete_channelbl = \
        """DELETE FROM channelbl WHERE channel_id=$1 AND starboard_id=$2"""

    conn = bot.db.conn

    async with bot.db.lock:
        async with conn.transaction():
            sql_channelbl = await conn.fetchrow(
                check_exists, channel_id, starboard_id
            )
            if sql_channelbl is None:
                raise errors.DoesNotExist(
                    "That channel is not blacklisted/whitelisted"
                )
            await conn.execute(
                delete_channelbl, channel_id, starboard_id
            )


async def add_role_blacklist(
    bot: commands.Bot,
    role_id: int,
    starboard_id: int,
    guild_id: int,
    is_whitelist: bool = False
) -> None:
    check_exists = \
        """SELECT * FROM rolebl WHERE role_id=$1 AND starboard_id=$2"""
    check_starboard = \
        """SELECT * FROM starboards WHERE id=$1 AND guild_id=$2"""

    conn = bot.db.conn

    async with bot.db.lock:
        async with conn.transaction():
            sql_rolebl = await conn.fetchrow(
                check_exists, role_id, starboard_id
            )
            if sql_rolebl is not None:
                raise errors.AlreadyExists(
                    "That role is already whitelisted/blacklisted"
                )
            sql_starboard = await conn.fetchrow(
                check_starboard, starboard_id, guild_id
            )
            if sql_starboard is None:
                raise errors.DoesNotExist(
                    "That is not a starboard!"
                )

            await bot.db.q.create_rolebl.fetch(
                starboard_id, role_id, guild_id, is_whitelist
            )


async def remove_role_blacklist(
    bot: commands.Bot,
    role_id: int,
    starboard_id: int,
) -> None:
    check_exists = \
        """SELECT * FROM rolebl WHERE role_id=$1 AND starboard_id=$2"""
    delete_rolebl = \
        """DELETE FROM rolebl WHERE role_id=$1 AND starboard_id=$2"""

    conn = bot.db.conn

    async with bot.db.lock:
        async with conn.transaction():
            sql_rolebl = await conn.fetchrow(
                check_exists, role_id, starboard_id
            )
            if sql_rolebl is None:
                raise errors.DoesNotExist(
                    "That role is not blacklisted/whitelisted"
                )

            await conn.execute(
                delete_rolebl, role_id, starboard_id
            )
