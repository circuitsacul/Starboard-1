from discord import utils
from discord.ext import commands
from typing import Tuple, Union
import emoji
import bot_config
import discord


async def fetch(bot, msg_id: int, channel: Union[discord.TextChannel, int]):
    if isinstance(channel, int):
        channel = await bot.get_channel(int(channel))
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
    get_prefixes = \
        """SELECT * FROM prefixes WHERE guild_id=$1"""

    conn = await bot.db.connect()
    async with conn.transaction():
        prefixes = await conn.fetch(get_prefixes, guild_id)

    return [p['prefix'] for p in prefixes]


async def add_prefix(bot, guild_id: int, prefix: str) -> Tuple[bool, str]:
    current_prefixes = await list_prefixes(bot, guild_id)
    if prefix in current_prefixes:
        return False, "That prefix already exists"
    if len(prefix) > 8:
        return False, \
            "That prefix is too long. It must be less than 9 characters."

    async with bot.db.lock:
        conn = await bot.db.connect()
        async with conn.transaction():
            await bot.db.q.create_prefix.fetch(guild_id, prefix)
        #await conn.close()
    return True, ''


async def remove_prefix(bot, guild_id: int, prefix: str) -> Tuple[bool, str]:
    current_prefixes = await list_prefixes(bot, guild_id)
    if prefix not in current_prefixes:
        return False, "That prefix does not exist"

    del_prefix = \
        """DELETE FROM prefixes WHERE prefix=$1 AND guild_id=$2"""

    async with bot.db.lock:
        conn = await bot.db.connect()
        async with conn.transaction():
            await conn.execute(del_prefix, prefix, guild_id)
        #await conn.close()

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
    starboard_id=None, do_member=False, create_new=True
):
    check_guild = \
        """SELECT * FROM guilds WHERE id=$1"""
    check_user = \
        """SELECT * FROM users WHERE id=$1"""
    check_starboard = \
        """SELECT * FROM starboards WHERE id=$1"""
    check_member = \
        """SELECT * FROM members WHERE guild_id=$1 AND user_id=$2"""

    if guild_id is not None:
        print(1)
        gexists = await check_single_exists(conn, check_guild, (guild_id,))
        print(2)
        if not gexists and create_new:
            print(3)
            await db.q.create_guild.fetch(guild_id)
            print(4)
            prefixes = await list_prefixes(bot, guild_id)
            print(5)
            if len(prefixes) == 0:
                print(6)
                await add_prefix(bot, guild_id, bot_config.DEFAULT_PREFIX)
    else:
        gexists = None
    if user is not None:
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
            conn, check_member, (guild_id, user.id,)
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
        #await conn.close()
    return rows


async def handle_role(bot, db, user_id, guild_id, role_id, add):
    guild = bot.get_guild(guild_id)
    member = utils.get(guild.members, id=user_id)
    role = utils.get(guild.roles, id=role_id)
    if add:
        await member.add_roles(role)
    else:
        await member.remove_roles(role)


async def get_limit(db, item, guild):
    owner = guild.owner
    max_of_item = bot_config.DEFAULT_LEVEL[item]
    levels = await get_patron_levels(db, owner.id)
    for _patron in levels:
        product_id = _patron['product_id']
        temp_max = bot_config.PATRON_LEVELS[product_id]['perks'][item]
        if temp_max == float('inf') or temp_max > max_of_item:
            max_of_item = temp_max
    return max_of_item


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
