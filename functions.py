from discord import utils
from discord.ext import commands
from typing import Tuple, Union, Iterable
from paginators import disputils
import emoji
import bot_config
import discord
import functions
import datetime
import errors


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
    get_guild = \
        """SELECT * FROM guilds WHERE id=$1"""

    await check_or_create_existence(
        bot, guild_id=guild_id
    )

    async with bot.db.lock:
        async with bot.db.conn.transaction():
            guild = await bot.db.conn.fetchrow(get_guild, guild_id)

    prefix_list = [p for p in guild['prefixes']]

    return prefix_list


async def add_prefix(bot, guild_id: int, prefix: str) -> Tuple[bool, str]:
    current_prefixes = await list_prefixes(bot, guild_id)
    if prefix in current_prefixes:
        return False, "That prefix already exists"
    if len(prefix) > 8:
        return False, \
            "That prefix is too long. It must be less than 9 characters."

    modify_guild = \
        """UPDATE guilds
        SET prefixes=$1
        WHERE id=$2"""

    current_prefixes.append(prefix)
    await check_or_create_existence(
        bot, guild_id=guild_id
    )
    async with bot.db.lock:
        conn = await bot.db.connect()
        async with conn.transaction():
            await conn.execute(modify_guild, current_prefixes, guild_id)
    return True, ''


async def remove_prefix(bot, guild_id: int, prefix: str) -> Tuple[bool, str]:
    current_prefixes = await list_prefixes(bot, guild_id)
    if prefix not in current_prefixes:
        return False, "That prefix does not exist"

    current_prefixes.remove(prefix)

    modify_guild = \
        """UPDATE guilds
        SET prefixes=$1
        WHERE id=$2"""

    async with bot.db.lock:
        conn = await bot.db.connect()
        async with conn.transaction():
            await conn.execute(modify_guild, current_prefixes, guild_id)

    return True, ''


def is_emoji(string) -> bool:
    return string in emoji.UNICODE_EMOJI


async def check_single_exists(conn, sql, params):
    rows = await conn.fetch(sql, *params)
    if len(rows) > 0:
        return True
    return False


async def check_or_create_existence(
    bot, guild_id=None, user=None,
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

    db = bot.db
    conn = bot.db.conn

    if guild_id is not None:
        async with bot.db.lock:
            async with conn.transaction():
                gexists = await check_single_exists(
                    conn, check_guild, (guild_id,)
                )
                if not gexists and create_new:
                    await db.q.create_guild.fetch(guild_id)
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
                async with bot.db.lock:
                    async with conn.transaction():
                        uexists = await check_single_exists(
                            conn, check_user, (user.id,)
                        )
                        if not uexists and create_new:
                            await db.q.create_user.fetch(user.id, user.bot)
        else:
            async with bot.db.lock:
                async with conn.transaction():
                    uexists = await check_single_exists(
                        conn, check_user, (user.id,)
                    )
                    if not uexists and create_new:
                        await db.q.create_user.fetch(user.id, user.bot)
    else:
        uexists = None

    if starboard_id is not None and guild_id is not None:
        async with bot.db.lock:
            async with conn.transaction():
                s_exists = await check_single_exists(
                    conn, check_starboard, (starboard_id,)
                )
                if not s_exists and create_new:
                    await db.q.create_starboard.fetch(starboard_id, guild_id)
    else:
        s_exists = None
    if do_member and user is not None and guild_id is not None:
        async with bot.db.lock:
            async with conn.transaction():
                mexists = await check_single_exists(
                    conn, check_member, (user.id, guild_id)
                )
                if not mexists and create_new:
                    await db.q.create_member.fetch(user.id, guild_id)

    else:
        mexists = None

    return dict(ge=gexists, ue=uexists, se=s_exists, me=mexists)


async def handle_role(bot, db, user_id, guild_id, role_id, add):
    guild = bot.get_guild(guild_id)
    member = (await functions.get_members([int(user_id)], guild))[0]
    role = utils.get(guild.roles, id=role_id)
    if add:
        await member.add_roles(role)
    else:
        await member.remove_roles(role)


async def set_sb_lock(bot, id: int, locked: bool) -> None:
    conn = bot.db.conn
    async with bot.db.lock:
        async with conn.transaction():
            await conn.execute(
                """UPDATE starboards
                SET locked=$1
                WHERE id=$2""", locked, id
            )


async def set_asc_lock(bot, id: int, locked: bool) -> None:
    conn = bot.db.conn
    async with bot.db.lock:
        async with conn.transaction():
            await conn.execute(
                """UPDATE aschannels
                SET locked=$1
                WHERE id=$2""", locked, id
            )


async def alert_user(
    bot, user_id: int, text: str
) -> None:
    user = await bot.fetch_user(user_id)
    if user is None:
        raise Exception(f"Couldn't Find User to alert {user_id}")
    try:
        await user.send(text)
    except Exception as e:
        raise Exception(
            f"Couldn't send alert to user {user_id}"
            f"\n\n{e}"
        )


async def alert_owner(
    bot, text: str
) -> None:
    owner = await bot.fetch_user(bot_config.OWNER_ID)
    await owner.send(text)


# PREMIUM FUNCTIONS
async def autoredeem(
    bot,
    guild_id: int
) -> bool:
    """Iterates over the list of users who have
    enabled autoredeem for this server, and if
    one of them does redeem some of their credits
    and alert the user."""
    await bot.wait_until_ready()
    conn = bot.db.conn

    guild = bot.get_guild(guild_id)
    if guild is None:
        return False

    async with bot.db.lock:
        async with conn.transaction():
            ar_members = await conn.fetch(
                """SELECT * FROM members
                WHERE guild_id=$1
                AND autoredeem=True""",
                guild_id
            )
    redeemed = False
    for m in ar_members:
        ms = await get_members([int(m['user_id'])], guild)
        if len(ms) == 0:
            continue
        current_credits = await get_credits(
            bot, int(m['user_id'])
        )
        if current_credits < bot_config.PREMIUM_COST:
            continue
        try:
            await alert_user(
                bot, int(m['user_id']),
                f"You have autoredeem enabled in {guild.name}, "
                f"so {bot_config.PREMIUM_COST} credits were taken "
                "from your account since they ran out of premium."
            )
        except Exception:
            continue
        try:
            await redeem(
                bot, int(m['user_id']),
                guild_id, 1
            )
            redeemed = True
        except errors.NotEnoughCredits:
            pass
    return redeemed


async def refresh_guild_premium(
    bot,
    guild_id: int,
    send_alert: bool = True
) -> None:
    ispremium = (await get_prem_endsat(bot, guild_id)) is not None
    if not ispremium:
        await remove_all_locks(bot, guild_id)
        await disable_guild_premium(bot, guild_id)
        if send_alert:
            await channel_alert(
                bot, guild_id, (
                    "Premium has expired on this server, "
                    "so this channel has been locked "
                    "(as it exceeds the non-premium limit). "
                    "If you reapply premium, this channel "
                    "will be automatically unlocked.\n"
                    "If you would rather have a different "
                    "channel locked, you can use the "
                    "`sb!movelock` command. Run "
                    "`sb!commands movelock` for more info."
                ), locked=True
            )
    else:
        if send_alert:
            await channel_alert(
                bot, guild_id, (
                    "Premium has been re-added to this "
                    "server, so this channel has been unlocked."
                ), locked=True
            )
        await remove_all_locks(bot, guild_id)


async def channel_alert(
    bot,
    guild_id: int,
    message: str,
    locked: Union[bool, None] = False,
    starboards: bool = True,
    aschannels: bool = True
) -> None:
    await bot.wait_until_ready()
    conn = bot.db.conn
    guild = bot.get_guild(int(guild_id))

    all_asc = []
    all_sb = []

    async with bot.db.lock:
        async with conn.transaction():
            if aschannels:
                all_asc = await conn.fetch(
                    """SELECT id FROM aschannels
                    WHERE guild_id=$1
                    AND ($2::bool is NULL or locked=$2)""",
                    guild_id, locked
                )
            if starboards:
                all_sb = await conn.fetch(
                    """SELECT id FROM starboards
                    WHERE guild_id=$1
                    AND ($2::bool is NULL or locked=$2)""",
                    guild_id, locked
                )

    for ascid in all_asc:
        c = guild.get_channel(int(ascid['id']))
        try:
            await c.send(message)
        except Exception:
            pass
    for sid in all_sb:
        c = guild.get_channel(int(sid['id']))
        try:
            await c.send(message)
        except Exception:
            pass


async def remove_all_locks(
    bot,
    guild_id: int
) -> None:  # only to be used by refresh_guild_premium
    conn = bot.db.conn

    async with bot.db.lock:
        async with conn.transaction():
            await conn.execute(
                """UPDATE starboards
                SET locked=False
                WHERE guild_id=$1""",
                guild_id
            )
            await conn.execute(
                """UPDATE aschannels
                SET locked=False
                WHERE guild_id=$1""",
                guild_id
            )


async def move_starboard_lock(
    bot,
    current_channel: discord.TextChannel,
    new_channel: discord.TextChannel
) -> None:
    conn = bot.db.conn
    async with bot.db.lock:
        async with conn.transaction():
            is_curr_locked = await conn.fetchval(
                """SELECT locked FROM starboards
                WHERE id=$1""", current_channel.id
            )
            is_new_unlocked = not await conn.fetchval(
                """SELECT locked FROM starboards
                WHERE id=$1""", new_channel.id
            )

    if is_curr_locked in [False, None]:
        raise errors.DoesNotExist(
            f"Either {current_channel.mention} is not a starboard, "
            "or it is not locked."
        )
    if is_new_unlocked in [False, None]:
        raise errors.DoesNotExist(
            f"Either {new_channel.mention} is not a starboard, "
            "or it is already locked."
        )

    await set_sb_lock(bot, current_channel.id, False)
    await set_sb_lock(bot, new_channel.id, True)
    await current_channel.send(
        "This channel has been unlocked, and "
        f"{new_channel.mention} has been locked instead."
    )
    await new_channel.send(
        f"{current_channel.mention} was unlocked, and "
        "this one was locked instead."
    )


async def move_aschannel_lock(
    bot,
    current_channel: discord.TextChannel,
    new_channel: discord.TextChannel
) -> None:
    conn = bot.db.conn
    async with bot.db.lock:
        async with conn.transaction():
            is_curr_locked = await conn.fetchval(
                """SELECT locked FROM aschannels
                WHERE id=$1""", current_channel.id
            )
            is_new_unlocked = not await conn.fetchval(
                """SELECT locked FROM aschannels
                WHERE id=$1""", new_channel.id
            )

    if is_curr_locked in [False, None]:
        raise errors.DoesNotExist(
            f"Either {current_channel.mention} is not an AutoStar channel, "
            "or it is not locked."
        )
    if is_new_unlocked in [False, None]:
        raise errors.DoesNotExist(
            f"Either {new_channel.mention} is not an AutoStar channel, "
            "or it is already locked."
        )

    await set_asc_lock(bot, current_channel.id, False)
    await set_asc_lock(bot, new_channel.id, True)
    await current_channel.send(
        "This channel has been unlocked, and "
        f"{new_channel.mention} has been locked instead."
    )
    await new_channel.send(
        f"{current_channel.mention} was unlocked, and "
        "this one was locked instead."
    )


async def disable_guild_premium(
    bot,
    guild_id: int
) -> None:
    conn = bot.db.conn

    # Get Values
    async with bot.db.lock:
        async with conn.transaction():
            num_starboards = int(await conn.fetchval(
                """SELECT COUNT(*) FROM starboards
                WHERE guild_id=$1 AND locked=False""", guild_id
            ))
            num_asc = int(await conn.fetchval(
                """SELECT COUNT(*) FROM aschannels
                WHERE guild_id=$1 AND locked=False""", guild_id
            ))

    limit_starboards = bot_config.DEFAULT_LEVEL['starboards']
    limit_asc = bot_config.DEFAULT_LEVEL['aschannels']

    sb_to_lock = num_starboards - limit_starboards
    asc_to_lock = num_asc - limit_asc

    # Lock extra starboards
    if sb_to_lock > 0:
        async with bot.db.lock:
            async with conn.transaction():
                sb_chosen = await conn.fetch(
                    """SELECT * FROM starboards
                    WHERE guild_id=$1 AND locked=False
                    LIMIT $2""",
                    guild_id, sb_to_lock
                )
        for s in sb_chosen:
            await set_sb_lock(bot, int(s['id']), True)

    # Lock extra aschannels
    if asc_to_lock > 0:
        async with bot.db.lock:
            async with conn.transaction():
                asc_chosen = await conn.fetch(
                    """SELECT * FROM aschannels
                    WHERE guild_id=$1 AND locked=False
                    LIMIT $2""", guild_id, asc_to_lock
                )
        for a in asc_chosen:
            await set_asc_lock(bot, int(a['id']), True)


async def do_payroll(bot) -> None:
    get_patrons = \
        """SELECT * FROM users WHERE payment != 0"""

    conn = bot.db.conn
    async with bot.db.lock:
        async with conn.transaction():
            sql_patrons = await conn.fetch(get_patrons)

    for sql_user in sql_patrons:
        user = await bot.fetch_user(int(sql_user['id']))
        await givecredits(
            bot, user.id, int(sql_user['payment'])
        )
        await user.send(
            "It is a new month, and you have received "
            f"{sql_user['payment']} credits for your "
            "pledge on Patreon! See `sb!premium` for more "
            "info."
        )


async def redeem(
    bot,
    user_id: int,
    guild_id: int,
    months: int
) -> None:
    credits = months*bot_config.PREMIUM_COST
    await givecredits(bot, user_id, 0-credits)
    await give_months(bot, guild_id, months)
    await refresh_guild_premium(bot, guild_id)


async def givecredits(
    bot,
    user_id: int,
    credits: int
) -> None:
    current_credits = await get_credits(bot, user_id)
    await setcredits(bot, user_id, current_credits+credits)


async def setcredits(
    bot,
    user_id: int,
    credits: int
) -> None:
    if credits < 0:
        raise errors.NotEnoughCredits(
            "You do not have enough credits to do this!"
        )

    update_user = \
        """UPDATE users
        SET credits=$1
        WHERE id=$2"""

    conn = bot.db.conn
    async with bot.db.lock:
        async with conn.transaction():
            await conn.execute(
                update_user, credits, user_id
            )


async def get_credits(
    bot,
    user_id: int
) -> None:
    get_user = \
        """SELECT * FROM users WHERE id=$1"""
    user = await bot.fetch_user(user_id)
    await check_or_create_existence(
        bot, user=user
    )
    conn = bot.db.conn
    async with bot.db.lock:
        async with conn.transaction():
            sql_user = await conn.fetchrow(
                get_user, user_id
            )
    return sql_user['credits']


async def give_months(
    bot,
    guild_id: int,
    months: int
) -> None:
    current_endsat = await get_prem_endsat(
        bot, guild_id
    )
    if current_endsat is None:
        current_endsat = datetime.datetime.now()
    months_append = datetime.timedelta(days=(31*months))
    new = current_endsat + months_append

    modify_guild = \
        """UPDATE guilds
        SET premium_end=$1
        WHERE id=$2"""

    conn = bot.db.conn
    async with bot.db.lock:
        async with conn.transaction():
            await conn.execute(modify_guild, new, guild_id)


async def get_limit(
    bot,
    item: str,
    guild_id: int
) -> Union[int, bool]:
    max_of_item = bot_config.DEFAULT_LEVEL[item]

    # check guild premium status
    if await get_prem_endsat(bot, guild_id) is not None:
        max_of_item = bot_config.PREMIUM_PERKS[item]

    return max_of_item


async def is_patron(
    bot,
    user_id: int
) -> bool:
    get_user = \
        """SELECT * FROM users WHERE id=$1"""

    conn = bot.db.conn
    async with bot.db.lock:
        async with conn.transaction():
            sql_user = await conn.fetchrow(
                get_user, user_id
            )

    return sql_user['payment'] != 0, sql_user['payment']


async def get_prem_endsat(
    bot,
    guild_id: int
) -> Union[datetime.datetime, None]:
    get_guild = \
        """SELECT * FROM guilds WHERE id=$1"""

    conn = bot.db.conn
    async with bot.db.lock:
        async with conn.transaction():
            sql_guild = await conn.fetchrow(get_guild, guild_id)

    return sql_guild['premium_end']


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


async def is_user_blacklisted(
    bot: commands.Bot,
    member: discord.Member,
    starboard_id: int
) -> None:
    get_blacklisted_roles = \
        """SELECT * FROM rolebl WHERE starboard_id=$1
        AND is_whitelist=False"""
    get_whitelisted_roles = \
        """SELECT * FROM rolebl WHERE starboard_id=$1
        AND is_whitelist=True"""

    status = True

    conn = bot.db.conn
    async with bot.db.lock:
        async with conn.transaction():
            sql_rolebl = await conn.fetch(
                get_blacklisted_roles, starboard_id
            )
            sql_rolewl = await conn.fetch(
                get_whitelisted_roles, starboard_id
            )

    rolebl = [int(r['role_id']) for r in sql_rolebl]
    rolewl = [int(r['role_id']) for r in sql_rolewl]

    if rolebl == [] and rolewl != []:
        status = False
    else:
        for rid in rolebl:
            if rid in [r.id for r in member.roles]:
                status = False
    for rid in rolewl:
        if rid in [r.id for r in member.roles]:
            status = True

    return not status


async def is_message_blacklisted(
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

    channelbl = [int(c['channel_id']) for c in sql_channelbl]
    channelwl = [int(c['channel_id']) for c in sql_channelwl]

    # Check channel status
    if channelwl != []:
        if message.channel.id not in channelwl:
            channel_status = False
    else:
        if message.channel.id in channelbl:
            channel_status = False

    return not channel_status  # both must be true
