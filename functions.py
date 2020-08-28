from discord import utils
from bot_config import PATRON_LEVELS


async def check_single_exists(c, sql, params):
    await c.execute(sql, params)
    rows = await c.fetchall()
    if len(rows) > 0:
        return True
    return False


async def check_or_create_existence(db, c, bot, guild_id=None, user_id=None, starboard_id=None, do_member=False, create_new=True):
    check_guild = \
        """SELECT * FROM guilds WHERE id=?"""
    check_user = \
        """SELECT * FROM users WHERE id=?"""
    check_starboard = \
        """SELECT * FROM starboards WHERE id=?"""
    check_member = \
        """SELECT * FROM members WHERE guild_id=? AND user_id=?"""

    if guild_id is not None:
        gexists = await check_single_exists(c, check_guild, (guild_id,))
        if not gexists and create_new:
            await c.execute(db.q.create_guild, (guild_id,))
    else:
        gexists = None
    if user_id is not None:
        user = bot.get_user(user_id)
        uexists = await check_single_exists(c, check_user, (user_id,))
        if not uexists and create_new:
            await c.execute(db.q.create_user, (user_id, user.bot,))
    else:
        uexists = None
    if starboard_id is not None and guild_id is not None:
        s_exists = await check_single_exists(c, check_starboard, (starboard_id,))
        if not s_exists and create_new:
            await c.execute(db.q.create_starboard, (starboard_id, guild_id,))
    else:
        s_exists = None
    if do_member and user_id is not None and guild_id is not None:
        mexists = await check_single_exists(c, check_member, (guild_id, user_id,))
        if not mexists and create_new:
            await c.execute(db.q.create_member, (user_id, guild_id,))
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
        """SELECT * FROM patrons WHERE user_id=?"""

    conn = await db.connect()
    c = await conn.cursor()
    async with db.lock:
        await c.execute(get_patrons, [user_id])
        rows = await c.fetchall()
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