from discord import utils
from bot_config import PATRON_LEVELS
import bot_config, emoji


def is_emoji(string):
    return string in emoji.UNICODE_EMOJI


async def check_single_exists(conn, sql, params):
    rows = await conn.fetch(sql, *params)
    if len(rows) > 0:
        return True
    return False


async def check_or_create_existence(db, conn, bot, guild_id=None, user=None, starboard_id=None, do_member=False, create_new=True):
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
            #await conn.execute(db.q.create_guild, guild_id)
            await db.q.create_guild.fetch(guild_id)
    else:
        gexists = None
    if user is not None:
        uexists = await check_single_exists(conn, check_user, (user.id,))
        if not uexists and create_new:
            await db.q.create_user.fetch(user.id, user.bot)
    else:
        uexists = None
    if starboard_id is not None and guild_id is not None:
        s_exists = await check_single_exists(conn, check_starboard, (starboard_id,))
        if not s_exists and create_new:
            await db.q.create_starboard.fetch(starboard_id, guild_id)
    else:
        s_exists = None
    if do_member and user is not None and guild_id is not None:
        mexists = await check_single_exists(conn, check_member, (guild_id, user.id,))
        if not mexists and create_new:
            await db.q.create_member.fetch(user.id, guild_id)
    else:
        mexists = None

    return dict(ge=gexists, ue=uexists, se=s_exists, me=mexists)


async def required_patron_level(db, user_id, level):
    all_levels = [PATRON_LEVELS[p['product_id']]['num'] for p in await get_patron_levels(db, user_id)]
    largest = max(all_levels) if all_levels != [] else None
    if largest is not None and largest >= level:
        return True
    else:
        return False


async def get_patron_levels(db, user_id):
    get_patrons = \
        """SELECT * FROM patrons WHERE user_id=$1"""

    conn = await db.connect()
    async with db.lock and conn.transaction():
        rows = await conn.fetch(get_patrons, user_id)
    await conn.close()
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
            except:
                pass
        return True
    elif str(reaction) == '❌':
        if delete:
            try:
                await message.delete()
            except:
                pass
        return False


async def orig_message_id(db, conn, message_id):
    get_message = \
        """SELECT * FROM messages WHERE id=$1"""

    rows = await conn.fetch(get_message, message_id)
    if len(rows) == 0:
        return message_id, None
    sql_message = rows[0]
    if sql_message['is_orig'] == True:
        return message_id, sql_message['channel_id']
    orig_messsage_id = sql_message['orig_message_id']
    rows = await conn.fetch(get_message, orig_messsage_id)
    sql_orig_message = rows[0]
    return int(orig_messsage_id), int(sql_orig_message['channel_id'])
