from discord import utils
from discord.ext import commands
from typing import Tuple, Union, Iterable
from paginators import disputils
import emoji
import bot_config
import discord
import functions


async def is_starboard_emoji(db, guild_id, emoji):
    emoji = str(emoji)
    get_starboards = \
        """SELECT * FROM starboards WHERE guild_id=$1"""
    get_sbeemojis = \
        """SELECT * FROM sbemojis WHERE starboard_id=any($1::numeric[])"""

    async with db.lock:
        conn = await db.connect()
        async with conn.transaction():
            starboards = await conn.fetch(get_starboards, guild_id)
            sql_all_emojis = await conn.fetch(
                get_sbeemojis, [starboard['id'] for starboard in starboards]
            )
            all_emojis = [e['name'] for e in sql_all_emojis]
    return str(emoji) in all_emojis


async def get_members(user_ids: Iterable[int], guild: discord.Guild):
    unfound_ids = []
    users = []
    for _uid in user_ids:
        uid = int(_uid)
        u = guild.get_member(uid)
        if u is not None:
            users.append(u)
        else:
            unfound_ids.append(uid)
    if unfound_ids != []:
        users += await guild.query_members(limit=None, user_ids=unfound_ids)
    return users


async def fetch(bot, msg_id: int, channel: Union[discord.TextChannel, int]):
    if isinstance(channel, int):
        channel = bot.get_channel(int(channel))
    if channel is None:
        return

    msg = await bot.db.cache.get(channel.guild.id, id=msg_id)
    if msg is not None:
        return msg
    msg = await channel.fetch_message(msg_id)
    if msg is None:
        return None

    await bot.db.cache.push(msg, channel.guild.id)
    return msg


async def _prefix_callable(bot, message):
    if not message.guild:
        return commands.when_mentioned_or(
            bot_config.DEFAULT_PREFIX
        )(bot, message)
    prefixes = await list_prefixes(bot, message.guild.id)
    return commands.when_mentioned_or(*prefixes)(bot, message)


async def get_one_prefix(bot, guild_id: int):
    prefixes = await list_prefixes(bot, guild_id)
    return prefixes[0] if len(prefixes) > 0 else '@' + bot.user.name + ' '


async def list_prefixes(bot, guild_id: int):
    prefixes = bot.db.prefix_cache.get(guild_id, [])
    prefix_list = [bot_config.DEFAULT_PREFIX] if prefixes == [] else\
        [p for p in prefixes]

    return prefix_list


async def add_prefix(bot, guild_id: int, prefix: str) -> Tuple[bool, str]:
    current_prefixes = await list_prefixes(bot, guild_id)
    if prefix in current_prefixes:
        return False, "That prefix already exists"
    if len(prefix) > 8:
        return False, \
            "That prefix is too long. It must be less than 9 characters."

    conn = await bot.db.connect()
    async with conn.transaction():
        await check_or_create_existence(
            bot.db, conn, bot, guild_id=guild_id
        )
        await bot.db.q.create_prefix.fetch(guild_id, prefix)
    bot.db.prefix_cache[guild_id].append(prefix)
    return True, ''


async def remove_prefix(bot, guild_id: int, prefix: str) -> Tuple[bool, str]:
    current_prefixes = await list_prefixes(bot, guild_id)
    if prefix not in current_prefixes:
        return False, "That prefix does not exist"

    del_prefix = \
        """DELETE FROM prefixes WHERE prefix=$1 AND guild_id=$2"""

    conn = await bot.db.connect()
    async with conn.transaction():
        await conn.execute(del_prefix, prefix, guild_id)

    bot.db.prefix_cache[guild_id].remove(prefix)

    return True, ''


def is_emoji(string) -> bool:
    return string in emoji.UNICODE_EMOJI


async def check_single_exists(conn, sql, params):
    rows = await conn.fetch(sql, *params)
    if len(rows) > 0:
        return True
    return False


async def check_or_create_existence(
    db, conn, bot, guild_id=None, user=None,
    starboard_id=None, do_member=False, create_new=True,
    user_is_id=False,
):
    check_guild = \
        """SELECT * FROM guilds WHERE id=$1"""
    check_user = \
        """SELECT * FROM users WHERE id=$1"""
    check_starboard = \
        """SELECT * FROM starboards WHERE id=$1"""
    check_member = \
        """SELECT * FROM members WHERE user_id=$1 AND guild_id=$2"""

    if guild_id is not None:
        gexists = await check_single_exists(conn, check_guild, (guild_id,))
        if not gexists and create_new:
            await db.q.create_guild.fetch(guild_id)
            prefixes = await list_prefixes(bot, guild_id)
            if len(prefixes) == 0:
                await add_prefix(bot, guild_id, bot_config.DEFAULT_PREFIX)
    else:
        gexists = None

    if user is not None:
        if user_is_id:
            guild = bot.get_guild(guild_id)
            users = await functions.get_members([user], guild)
            if len(users) == 0:
                uexists = None
            else:
                user = users[0]
                uexists = await check_single_exists(
                    conn, check_user, (user.id,)
                )
                if not uexists and create_new:
                    await db.q.create_user.fetch(user.id, user.bot)
        else:
            uexists = await check_single_exists(conn, check_user, (user.id,))
            if not uexists and create_new:
                await db.q.create_user.fetch(user.id, user.bot)
    else:
        uexists = None

    if starboard_id is not None and guild_id is not None:
        s_exists = await check_single_exists(
            conn, check_starboard, (starboard_id,)
        )
        if not s_exists and create_new:
            await db.q.create_starboard.fetch(starboard_id, guild_id)
    else:
        s_exists = None
    if do_member and user is not None and guild_id is not None:
        mexists = await check_single_exists(
            conn, check_member, (user.id, guild_id)
        )
        if not mexists and create_new:
            await db.q.create_member.fetch(user.id, guild_id)

    else:
        mexists = None

    return dict(ge=gexists, ue=uexists, se=s_exists, me=mexists)


async def required_patron_level(db, user_id, level):
    all_levels = [
        bot_config.PATRON_LEVELS[p['product_id']]['num']
        for p in await get_patron_levels(db, user_id)
    ]
    largest = max(all_levels) if all_levels != [] else None
    if largest is not None and largest >= level:
        return True
    else:
        return False


async def get_patron_levels(db, user_id):
    get_patrons = \
        """SELECT * FROM patrons WHERE user_id=$1"""

    async with db.lock:
        conn = await db.connect()
        async with conn.transaction():
            rows = await conn.fetch(get_patrons, user_id)
    return rows


async def handle_role(bot, db, user_id, guild_id, role_id, add):
    guild = bot.get_guild(guild_id)
    member = (await functions.get_members([int(user_id)], guild))[0]
    role = utils.get(guild.roles, id=role_id)
    if add:
        await member.add_roles(role)
    else:
        await member.remove_roles(role)


async def get_limit(db, item, guild):
    owner_id = guild.owner_id
    max_of_item = bot_config.DEFAULT_LEVEL[item]
    levels = await get_patron_levels(db, owner_id)
    for _patron in levels:
        product_id = _patron['product_id']
        temp_max = bot_config.PATRON_LEVELS[product_id]['perks'][item]
        if temp_max == float('inf') or temp_max > max_of_item:
            max_of_item = temp_max
    return max_of_item


async def pretty_emoji_string(emojis, guild):
    string = ""
    for demoji in emojis:
        emoji_name = demoji['name']
        try:
            emoji_id = int(emoji_name)
        except ValueError:
            emoji_id = None

        is_custom = emoji_id is not None
        if is_custom:
            emoji_string = str(discord.utils.get(
                guild.emojis, id=int(emoji_id))
            )
        else:
            emoji_string = emoji_name
        string += emoji_string + " "
    return string


async def confirm(bot, channel, text, user_id, embed=None, delete=True):
    message = await channel.send(text, embed=embed)
    await message.add_reaction('✅')
    await message.add_reaction('❌')

    def check(reaction, user):
        if user.id != user_id or str(reaction) not in ['✅', '❌']:
            return False
        if reaction.message.id != message.id:
            return False
        return True

    reaction, _user = await bot.wait_for('reaction_add', check=check)
    if str(reaction) == '✅':
        if delete:
            try:
                await message.delete()
            except Exception:
                pass
        return True
    elif str(reaction) == '❌':
        if delete:
            try:
                await message.delete()
            except Exception:
                pass
        return False


async def multi_choice(bot, channel, user, title, description, _options):
    options = [option for option in _options]
    mc = disputils.MultipleChoice(bot, options, title, description)
    await mc.run([user], channel)
    await mc.quit(mc.choice)
    return _options[mc.choice]


async def user_input(bot, channel, user, prompt, timeout=30):
    await channel.send(prompt)

    def check(msg):
        if msg.author.id != user.id:
            return False
        if msg.channel.id != channel.id:
            return False
        return True

    inp = await bot.wait_for('message', check=check, timeout=timeout)
    return inp


async def orig_message_id(db, conn, message_id):
    get_message = \
        """SELECT * FROM messages WHERE id=$1"""

    rows = await conn.fetch(get_message, message_id)
    if len(rows) == 0:
        return message_id, None
    sql_message = rows[0]
    if sql_message['is_orig'] is True:
        return message_id, sql_message['channel_id']
    orig_messsage_id = sql_message['orig_message_id']
    rows = await conn.fetch(get_message, orig_messsage_id)
    sql_orig_message = rows[0]
    return int(orig_messsage_id), int(sql_orig_message['channel_id'])


async def is_blacklisted(
    bot: commands.Bot,
    message: discord.Message,  # assumes that it is the original,
    starboard_id: int
) -> bool:
    get_blacklisted_channels = \
        """SELECT * FROM channelbl WHERE starboard_id=$1
        AND is_whitelist=False"""
    get_whitelisted_channels = \
        """SELECT * FROM channelbl WHERE starboard_id=$1
        AND is_whitelist=True"""
    get_blacklisted_roles = \
        """SELECT * FROM rolebl WHERE starboard_id=$1
        AND is_whitelist=False"""
    get_whitelisted_roles = \
        """SELECT * FROM rolebl WHERE starboard_id=$1
        AND is_whitelist=True"""

    role_status = True
    channel_status = True

    conn = bot.db.conn
    async with bot.db.lock:
        async with conn.transaction():
            sql_channelbl = await conn.fetch(
                get_blacklisted_channels, starboard_id
            )
            sql_channelwl = await conn.fetch(
                get_whitelisted_channels, starboard_id
            )
            sql_rolebl = await conn.fetch(
                get_blacklisted_roles, starboard_id
            )
            sql_rolewl = await conn.fetch(
                get_whitelisted_roles, starboard_id
            )

    channelbl = [int(c['channel_id']) for c in sql_channelbl]
    channelwl = [int(c['channel_id']) for c in sql_channelwl]
    rolebl = [int(r['role_id']) for r in sql_rolebl]
    rolewl = [int(r['role_id']) for r in sql_rolewl]

    try:
        member = (await get_members([message.author.id], message.guild))[0]
    except IndexError:
        member = None

    # Check role status
    if member:
        if rolebl == [] and rolewl != []:
            role_status = False
        else:
            for rid in rolebl:
                if rid in [r.id for r in member.roles]:
                    role_status = False
        for rid in rolewl:
            if rid in [r.id for r in member.roles]:
                role_status = True

    # Check channel status
    if channelwl != []:
        if message.channel.id not in channelwl:
            channel_status = False
    else:
        if message.channel.id in channelbl:
            channel_status = False

    return not (role_status and channel_status)  # both must be true
