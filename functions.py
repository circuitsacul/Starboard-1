import datetime
from itertools import compress
from typing import Any, Iterable, List, Optional, Sequence, Tuple, Union

import asyncpg
import discord
import emoji
from discord import utils
from discord.ext import commands

import bot_config
import errors
import functions
from api import tenor
from cogs import starboard
from database.database import Database  # for typehinting
from paginators import disputils


async def can_manage_role(
    bot: commands.Bot,
    role: discord.Role
) -> bool:
    if role.is_default():
        print(1)
        return False
    if role.managed:
        print(2)
        return False
    if role.position >= role.guild.me.top_role.position:
        print(3)
        return False
    return True


async def needs_recount(
    bot: commands.Bot,
    message: discord.Message
) -> bool:
    get_reactions = \
        """SELECT * FROM reactions WHERE message_id=$1"""

    if message is None:
        return False

    total = 0
    reactions = [
        str(r.emoji.id) if r.custom_emoji else str(r.emoji)
        for r in message.reactions
    ]
    reaction_mask = await functions.is_starboard_emoji(
        bot.db, message.guild.id, reactions, multiple=True
    )
    for r in compress(message.reactions, reaction_mask):
        total += r.count

    if total == 0:  # Don't recount if the message doesn't have reactions
        return False

    async with bot.db.lock:
        conn = bot.db.conn
        async with conn.transaction():
            reactions = await conn.fetch(
                get_reactions, message.id
            )
            sql_total = len(reactions)

    if sql_total < 0.5*total and total-sql_total > 2:
        # recount if the bot has logged less than 10% of the reactions
        return True
    return False


async def recount_reactions(
    bot: commands.Bot,
    message: discord.Message
) -> None:
    check_reaction = \
        """SELECT * FROM reactions WHERE
        message_id=$1 AND name=$2 AND user_id=$3"""
    check_message = \
        """SELECT * FROM messages
        WHERE id=$1"""

    # hard to explain why, but I also remove the message
    # from the cache when recounting the stars on it
    await bot.db.cache.remove(message.id, message.guild.id)
    message = await functions.fetch(bot, message.id, message.channel)
    if message is None:
        return

    # [{'user_id': user_id, 'name': name}, ...]
    # other values can be determined from the message object
    to_add = []

    for reaction in message.reactions:
        if reaction.custom_emoji:
            name = str(reaction.emoji.id)
        else:
            name = str(reaction.emoji)

        if not await functions.is_starboard_emoji(
            bot.db, message.guild.id, name
        ):
            continue

        async for user in reaction.users():
            if user is None:
                continue
            elif user.bot:
                continue
            to_add.append({
                'user': user, 'name': name
            })

    conn = bot.db.conn

    async with bot.db.lock:
        async with conn.transaction():
            sql_m = await conn.fetchrow(
                check_message, message.id
            )
            if sql_m and sql_m['is_orig'] is False:
                print("No")
                return
            elif sql_m is None:
                await bot.db.q.create_message.fetch(
                    message.id, message.guild.id,
                    message.author.id, None,
                    message.channel.id, True,
                    message.channel.is_nsfw()
                )

    for r in to_add:
        await functions.check_or_create_existence(
            bot,
            guild_id=message.guild.id,
            user=r['user'], do_member=True
        )

        async with bot.db.lock:
            async with conn.transaction():
                sql_r = await conn.fetchrow(
                    check_reaction, message.id, r['name'],
                    r['user'].id
                )
                if sql_r is not None:
                    continue

                await bot.db.q.create_reaction.fetch(
                    message.guild.id, (r['user']).id,
                    message.id, r['name']
                )

    await starboard.handle_starboards(
        bot.db, bot, message.id, message.channel, message,
        message.guild
    )


async def is_starboard_emoji(
    db: Database,
    guild_id: int,
    emoji: Union[Sequence[Union[str, int]], Union[str, int]],
    multiple=False
) -> Union[List[bool], bool]:
    if not multiple:
        emoji = str(emoji)
    else:
        emoji = [str(emo) for emo in emoji]
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
    if not multiple:
        return str(emoji) in all_emojis
    else:
        return [emo in all_emojis for emo in emoji]


async def get_embed_from_message(
    message: discord.Message
) -> discord.Embed:
    nsfw = message.channel.is_nsfw()
    embed = discord.Embed(
        title="NSFW" if nsfw else discord.Embed.Empty, colour=bot_config.COLOR
    )
    embed.set_author(
        name=str(message.author), icon_url=message.author.avatar_url
    )
    embed_text = ''
    msg_attachments = message.attachments
    urls = []

    for attachment in msg_attachments:
        urls.append({
            'name': attachment.filename, 'display_url': attachment.url,
            'url': attachment.url, 'type': 'upload'
        })

    e = discord.embeds._EmptyEmbed

    for msg_embed in message.embeds:
        if msg_embed.type == 'rich':
            fields = [
                (
                    f"\n**{x.name if type(x.name) != e else ''}**\n",
                    f"{x.value if type(x.value) != e else ''}\n"
                )
                for x in msg_embed.fields
            ]
            embed_text += f"__**{msg_embed.title}**__\n"\
                if type(msg_embed.title) != e else ''
            embed_text += f"{msg_embed.description}\n"\
                if type(msg_embed.description) != e else ''

            for name, value in fields:
                embed_text += name + value
            if msg_embed.footer.text is not embed.Empty:
                embed_text += '\n' + str(msg_embed.footer.text) + '\n'
            if msg_embed.image.url is not embed.Empty:
                urls.append({
                    'name': 'Embed Image',
                    'url': msg_embed.image.url,
                    'display_url': msg_embed.image.url
                })
            if msg_embed.thumbnail.url is not embed.Empty:
                urls.append({
                    'name': 'Embed Thumbnail',
                    'url': msg_embed.thumbnail.url,
                    'display_url': msg_embed.thumbnail.url
                })
        elif msg_embed.type == 'image':
            if msg_embed.url != discord.Embed.Empty:
                urls.append({
                    'name': 'Image', 'display_url': msg_embed.thumbnail.url,
                    'url': msg_embed.url, 'type': 'image'
                })
        elif msg_embed.type == 'gifv':
            gifid = tenor.get_gif_id(msg_embed.url)
            if gifid is None:
                display_url = msg_embed.thumbnail.url
            else:
                display_url = await tenor.get_gif_url(gifid)
            if msg_embed.url != discord.Embed.Empty:
                urls.append({
                    'name': 'GIF', 'display_url': display_url,
                    'url': msg_embed.url, 'type': 'gif'
                })
        elif msg_embed.type == 'video':
            if msg_embed.url != discord.Embed.Empty:
                urls.append({
                    'name': 'Video', 'display_url': msg_embed.thumbnail.url,
                    'url': msg_embed.url, 'type': 'video'
                })

    value_string = f"{message.system_content}\n{embed_text}"
    context_string = f"\n[**Jump to Message**]({message.jump_url})"
    if len(value_string) > 2048:
        clip_msg = "... *message clipped*"
        to_clip = len(value_string+clip_msg)-2048
        full_string = value_string[0:-1*to_clip] + clip_msg
    else:
        full_string = value_string
    embed.description = full_string

    embed.add_field(name="Original", value=context_string)

    if len(urls) > 0:
        url_string = ''
        current = 0
        for item in urls:
            url_string += f"[**{item['name']}**]({item['url']})\n"
            if current == 0:
                embed.set_image(url=item['display_url'])
                current += 1
            elif current == 1:
                embed.set_thumbnail(url=item['display_url'])
                current += 1
        embed.add_field(name='Attachments', value=url_string, inline=False)

    embed.set_footer(text=f"ID: {message.id}")
    embed.timestamp = message.created_at

    return embed


async def calculate_points(
    conn: asyncpg.Connection,
    sql_message: dict,
    sql_starboard: dict,
    bot: commands.Bot,
    guild: discord.Guild
) -> Tuple[int, List[dict]]:
    get_reactions = \
        """SELECT * FROM reactions WHERE message_id=$1"""
    get_user = \
        """SELECT * FROM users WHERE id=$1"""
    get_sbemojis = \
        """SELECT * FROM sbemojis WHERE starboard_id=$1"""
    update_message = \
        """UPDATE messages
        SET points=$1
        WHERE orig_message_id=$2
        AND channel_id=$3"""

    message_id = int(sql_message['id'])
    self_star = sql_starboard['self_star']

    async with bot.db.lock:
        async with conn.transaction():
            emojis = await conn.fetch(get_sbemojis, sql_starboard['id'])
            all_reactions = await conn.fetch(get_reactions, message_id)

    used_users = set()

    total_points = 0
    for emoji_obj in emojis:
        emoji_id = int(emoji_obj['d_id']) if emoji_obj['d_id'] is not None\
            else None
        emoji_name = None if emoji_id is not None else emoji_obj['name']
        reactions = [
            r for r in all_reactions if r['name']
            in [str(emoji_id), emoji_name]
        ]
        for sql_reaction in reactions:
            user_id = sql_reaction['user_id']
            if user_id in used_users:
                continue
            used_users.add(user_id)
            if user_id == sql_message['user_id'] and self_star is False:
                continue

            async with bot.db.lock:
                async with conn.transaction():
                    sql_user = await conn.fetchrow(get_user, user_id)

            if sql_user['is_bot'] is True:
                continue

            member_list = await functions.get_members(
                [int(sql_user['id'])], guild
            )
            try:
                member = member_list[0]
                if member and await functions.is_user_blacklisted(
                    bot, member, int(sql_starboard['id'])
                ):
                    continue
            except IndexError:
                pass

            total_points += 1

    async with bot.db.lock:
        async with conn.transaction():
            await conn.execute(
                update_message, total_points,
                message_id, int(sql_starboard['id'])
            )

    return total_points, emojis


async def get_members(
    user_ids: Iterable[int],
    guild: discord.Guild
) -> List[discord.Member]:
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


async def fetch(
    bot: commands.Bot,
    msg_id: int,
    channel: Union[discord.TextChannel, int]
) -> discord.Message:
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


async def _prefix_callable(
    bot: commands.Bot,
    message: discord.Message
) -> List[str]:
    if not message.guild:
        return commands.when_mentioned_or(
            bot_config.DEFAULT_PREFIX
        )(bot, message)
    prefixes = await list_prefixes(bot, message.guild.id)
    return commands.when_mentioned_or(*prefixes)(bot, message)


async def get_one_prefix(
    bot: commands.Bot,
    guild_id: int
) -> str:
    prefixes = await list_prefixes(bot, guild_id)
    return prefixes[0] if len(prefixes) > 0 else '@' + bot.user.name + ' '


async def list_prefixes(
    bot: commands.Bot,
    guild_id: int
) -> List[str]:
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


async def add_prefix(
    bot: commands.Bot,
    guild_id: int,
    prefix: str
) -> Tuple[bool, str]:
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


async def remove_prefix(
    bot: commands.Bot,
    guild_id: int,
    prefix: str
) -> Tuple[bool, str]:
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


def is_emoji(
    string: str
) -> bool:
    return string in emoji.UNICODE_EMOJI


async def check_single_exists(
    conn: asyncpg.Connection,
    sql: str,
    params: List[Any]
) -> bool:
    rows = await conn.fetch(sql, *params)
    if len(rows) > 0:
        return True
    return False


async def check_or_create_existence(
    bot: commands.Bot,
    guild_id: int = None,
    user: Union[discord.User, discord.Member, int] = None,
    starboard_id: int = None,
    do_member: bool = False,
    create_new: bool = True,
    user_is_id: bool = False,
) -> dict:
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
                    conn, check_guild, [guild_id]
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
                            conn, check_user, [user.id]
                        )
                        if not uexists and create_new:
                            await db.q.create_user.fetch(user.id, user.bot)
        else:
            async with bot.db.lock:
                async with conn.transaction():
                    uexists = await check_single_exists(
                        conn, check_user, [user.id]
                    )
                    if not uexists and create_new:
                        await db.q.create_user.fetch(user.id, user.bot)
    else:
        uexists = None

    if starboard_id is not None and guild_id is not None:
        async with bot.db.lock:
            async with conn.transaction():
                s_exists = await check_single_exists(
                    conn, check_starboard, [starboard_id]
                )
                if not s_exists and create_new:
                    await db.q.create_starboard.fetch(starboard_id, guild_id)
    else:
        s_exists = None
    if do_member and user is not None and guild_id is not None:
        async with bot.db.lock:
            async with conn.transaction():
                mexists = await check_single_exists(
                    conn, check_member, [user.id, guild_id]
                )
                if not mexists and create_new:
                    await db.q.create_member.fetch(user.id, guild_id)
    else:
        mexists = None

    return dict(ge=gexists, ue=uexists, se=s_exists, me=mexists)


async def handle_role(
    bot: commands.Bot,
    db: Database,
    user_id: int,
    guild_id: int,
    role_id: int,
    add: bool
) -> None:
    guild = bot.get_guild(guild_id)
    member = (await functions.get_members([int(user_id)], guild))[0]
    role = utils.get(guild.roles, id=role_id)
    if add:
        await member.add_roles(role)
    else:
        await member.remove_roles(role)


async def set_sb_lock(
    bot: commands.Bot,
    id: int,
    locked: bool
) -> None:
    conn = bot.db.conn
    async with bot.db.lock:
        async with conn.transaction():
            await conn.execute(
                """UPDATE starboards
                SET locked=$1
                WHERE id=$2""", locked, id
            )


async def set_asc_lock(
    bot: commands.Bot,
    id: int,
    locked: bool
) -> None:
    conn = bot.db.conn
    async with bot.db.lock:
        async with conn.transaction():
            await conn.execute(
                """UPDATE aschannels
                SET locked=$1
                WHERE id=$2""", locked, id
            )


async def alert_user(
    bot: commands.Bot,
    user_id: int,
    text: str
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
    bot: commands.Bot,
    text: str
) -> None:
    owner = await bot.fetch_user(bot_config.OWNER_ID)
    await owner.send(text)


# PREMIUM FUNCTIONS
async def autoredeem(
    bot: commands.Bot,
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
    bot: commands.Bot,
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
    bot: commands.Bot,
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
    bot: commands.Bot,
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
    bot: commands.Bot,
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
    bot: commands.Bot,
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
    bot: commands.Bot,
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


async def do_payroll(
    bot: commands.Bot
) -> None:
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
    bot: commands.Bot,
    user_id: int,
    guild_id: int,
    months: int
) -> None:
    credits = months*bot_config.PREMIUM_COST
    await givecredits(bot, user_id, 0-credits)
    await give_months(bot, guild_id, months)
    await refresh_guild_premium(bot, guild_id)


async def givecredits(
    bot: commands.Bot,
    user_id: int,
    credits: int
) -> None:
    current_credits = await get_credits(bot, user_id)
    await setcredits(bot, user_id, current_credits+credits)


async def setcredits(
    bot: commands.Bot,
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
    bot: commands.Bot,
    user_id: int
) -> int:
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
    bot: commands.Bot,
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
    bot: commands.Bot,
    item: str,
    guild_id: int
) -> Union[int, bool]:
    max_of_item = bot_config.DEFAULT_LEVEL[item]

    # check guild premium status
    if await get_prem_endsat(bot, guild_id) is not None:
        max_of_item = bot_config.PREMIUM_PERKS[item]

    return max_of_item


async def is_patron(
    bot: commands.Bot,
    user_id: int
) -> Tuple[bool, int]:
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
    bot: commands.Bot,
    guild_id: int
) -> Union[datetime.datetime, None]:
    get_guild = \
        """SELECT * FROM guilds WHERE id=$1"""

    conn = bot.db.conn
    async with bot.db.lock:
        async with conn.transaction():
            sql_guild = await conn.fetchrow(get_guild, guild_id)

    return sql_guild['premium_end']


async def pretty_emoji_string(
    emojis: List[dict],
    guild: discord.Guild
) -> str:
    string = ""
    for demoji in emojis:
        emoji_name = demoji['name']
        try:
            emoji_id = int(emoji_name)
        except ValueError:
            emoji_id = None

        is_custom = emoji_id is not None
        if is_custom:
            emoji_string = str(
                discord.utils.get(
                    guild.emojis, id=int(emoji_id)
                ) or "Deleted Emoji"
            )
        else:
            emoji_string = emoji_name
        string += emoji_string + " "
    return string


async def confirm(
    bot: commands.Bot,
    channel: discord.TextChannel,
    text: str,
    user_id: int,
    embed=None,
    delete=True
) -> Optional[bool]:
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
    return None


async def multi_choice(
    bot: commands.Bot,
    channel: discord.TextChannel,
    user: Union[discord.User, discord.Member],
    title: str,
    description: str,
    _options: dict
) -> Any:
    options = [option for option in _options]
    mc = disputils.MultipleChoice(bot, options, title, description)
    await mc.run([user], channel)
    await mc.quit(mc.choice)
    return _options[mc.choice]


async def user_input(
    bot: commands.Bot,
    channel: discord.TextChannel,
    user: Union[discord.User, discord.Member],
    prompt: str,
    timeout: int = 30
) -> str:
    await channel.send(prompt)

    def check(msg):
        if msg.author.id != user.id:
            return False
        if msg.channel.id != channel.id:
            return False
        return True

    inp = await bot.wait_for('message', check=check, timeout=timeout)
    return inp


async def orig_message_id(
    db: Database,
    conn: asyncpg.Connection,
    message_id: int
) -> Tuple[int, Optional[int]]:
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
) -> bool:
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
