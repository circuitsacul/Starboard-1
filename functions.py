from discord import utils


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