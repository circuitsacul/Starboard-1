from discord import utils
from discord.ext import commands
from typing import Tuple, Union, Iterable
import emoji
import bot_config
import discord
import disputils
import functions


async def get_members(user_ids: Iterable[int], guild: discord.Guild):
    unfound_ids = []
    users = []
    for uid in user_ids:
        u = guild.get_member(uid)
        if u is not None:
            users.append(u)
        else:
            unfound_ids.append(uid)
    if unfound_ids != []:
        users += await guild.query_members(limit=None, user_ids=unfound_ids)
    return users


async def change_starboard_settings(
    db, starboard_id, self_star=None, link_edits=None,
    link_deletes=None, bots_on_sb=None,
    required=None, rtl=None
):
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
    async with bot.db.lock:
        prefixes = await list_prefixes(bot, message.guild.id)
    return commands.when_mentioned_or(*prefixes)(bot, message)


async def get_one_prefix(bot, guild_id: int):
    async with bot.db.lock:
        prefixes = await list_prefixes(bot, guild_id)
    return prefixes[0] if len(prefixes) > 0 else '@' + bot.user.name + ' '


async def list_prefixes(bot, guild_id: int):
    get_prefixes = \
        """SELECT * FROM prefixes WHERE guild_id=$1"""

    conn = await bot.db.connect()
    prefixes = await conn.fetch(get_prefixes, guild_id)
    prefix_list = [bot_config.DEFAULT_PREFIX] if prefixes == [] else\
        [p['prefix'] for p in prefixes]

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
        gexists = await check_single_exists(conn, check_guild, (guild_id,))
        if not gexists and create_new:
            await db.q.create_guild.fetch(guild_id)
            prefixes = await list_prefixes(bot, guild_id)
            if len(prefixes) == 0:
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
    return rows


async def handle_role(bot, db, user_id, guild_id, role_id, add):
    guild = bot.get_guild(guild_id)
    #member = utils.get(guild.members, id=user_id)
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
    for sbemoji in emojis:
        is_custom = sbemoji['d_id'] is not None
        if is_custom:
            emoji_string = str(discord.utils.get(
                guild.emojis, id=int(sbemoji['d_id']))
            )
        else:
            emoji_string = sbemoji['name']
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
