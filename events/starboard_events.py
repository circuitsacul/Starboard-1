import discord
import functions
import bot_config
import asyncpg
from events import retotal
from discord.errors import Forbidden
from discord import utils
from events import leveling
from api import tenor


async def handle_reaction(
    db, bot, guild_id, _channel_id, user_id, _message_id, _emoji, is_add
):
    emoji_name = _emoji.name if _emoji.id is None else str(_emoji.id)

    check_reaction = \
        """SELECT * FROM reactions
        WHERE message_id=$1
        AND user_id=$2
        AND name=$3"""
    remove_reaction = \
        """DELETE FROM reactions
        WHERE message_id=$1
        AND user_id=$2
        AND name=$3"""
    get_message = \
        """SELECT * FROM messages WHERE id=$1"""
    get_user = \
        """SELECT * FROM users WHERE id=$1"""
    get_member = \
        """SELECT * FROM members WHERE user_id=$1 and guild_id=$2"""

    async with db.lock:
        conn = await db.connect()
        async with conn.transaction():
            message_id, orig_channel_id = await functions.orig_message_id(
                db, conn, _message_id
            )
            sql_user = await conn.fetchrow(get_user, user_id)
            sql_member = await conn.fetchrow(get_member, user_id, guild_id)

    channel_id = orig_channel_id if orig_channel_id is not None \
        else _channel_id

    guild = bot.get_guild(guild_id)
    channel = utils.get(guild.channels, id=int(channel_id))
    # user = utils.get(guild.members, id=user_id)

    user = None
    if sql_user is None or sql_member is None:
        _users = await functions.get_members([user_id], guild)
        if len(_users) == 0:
            user = None
        else:
            user = _users[0]

        async with db.lock:
            conn = db.conn
            async with conn.transaction():
                await functions.check_or_create_existence(
                    db, conn, bot, guild_id=guild_id,
                    user=user, do_member=True
                )

        if user is not None and user.bot:
            return
    elif sql_user is not None:
        if sql_user['is_bot']:
            return

    try:
        message = await functions.fetch(bot, int(message_id), channel)
    except (discord.errors.NotFound, discord.errors.Forbidden, AttributeError):
        message = None

    async with db.lock:
        conn = await db.connect()
        async with conn.transaction():
            if message:
                await functions.check_or_create_existence(
                    db, conn, bot, guild_id=guild_id,
                    user=message.author, do_member=True
                )
            await functions.check_or_create_existence(
                db, conn, bot,
                guild_id=guild_id
            )

            rows = await conn.fetch(get_message, message_id)
            if message:
                if len(rows) == 0:
                    await db.q.create_message.fetch(
                        message_id, guild_id,
                        message.author.id, None,
                        channel_id, True,
                        message.channel.is_nsfw()
                    )
            try:
                rows = await conn.fetch(
                    check_reaction, message_id, user_id, emoji_name
                )
                exists = len(rows) > 0
                if not exists and is_add:
                    await db.q.create_reaction.fetch(
                        guild_id, user_id,
                        message_id, emoji_name
                    )
                if exists and not is_add:
                    await conn.execute(
                        remove_reaction, message_id, user_id, emoji_name
                    )
            except asyncpg.exceptions.ForeignKeyViolationError:
                pass

    if message is not None:
        handle_level = False
        if user is None:
            if sql_user is not None:
                if not sql_user['is_bot']:
                    handle_level = True
        elif not user.bot:
            handle_level = True

        if handle_level:
            await leveling.handle_reaction(
                db, user_id, message.author, guild, _emoji, is_add
            )

    await handle_starboards(db, bot, message_id, channel, message)


async def handle_starboards(db, bot, message_id, channel, message):
    get_message = \
        """SELECT * FROM messages WHERE id=$1"""
    get_starboards = \
        """SELECT * FROM starboards
        WHERE guild_id=$1
        AND locked=False"""

    async with db.lock:
        conn = await db.connect()
        async with conn.transaction():
            sql_message = await conn.fetchrow(get_message, message_id)
            if sql_message is not None:
                sql_starboards = await conn.fetch(
                    get_starboards, sql_message['guild_id']
                )

    needs_recount = await retotal.needs_recount(bot, message)
    if needs_recount:
        await retotal.recount_reactions(bot, message)

    if sql_message is not None:
        for sql_starboard in sql_starboards:
            await handle_starboard(
                db, bot, sql_message, message, sql_starboard
            )


async def handle_starboard(db, bot, sql_message, message, sql_starboard):
    get_starboard_message = \
        """SELECT * FROM messages WHERE orig_message_id=$1 AND channel_id=$2"""
    delete_starboard_message = \
        """DELETE FROM messages WHERE orig_message_id=$1 and channel_id=$2"""
    get_author = \
        """SELECT * FROM users WHERE id=$1"""

    starboard_id = sql_starboard['id']
    starboard = bot.get_channel(int(starboard_id))

    if starboard is None:
        return

    async with db.lock:
        conn = await db.connect()
        async with conn.transaction():
            sql_author = await conn.fetchrow(
                get_author, sql_message['user_id']
            )
            rows = await conn.fetch(
                get_starboard_message, sql_message['id'], sql_starboard['id']
            )

    delete = False
    if len(rows) == 0:
        starboard_message = None
    else:
        sql_starboard_message = rows[0]
        starboard_message_id = sql_starboard_message['id']
        if starboard is not None:
            try:
                starboard_message = await functions.fetch(
                    bot, int(starboard_message_id), starboard
                )
            except discord.errors.NotFound:
                starboard_message = None
                async with db.lock:
                    conn = await db.connect()
                    async with conn.transaction():
                        await conn.execute(
                            delete_starboard_message, sql_message['id'],
                            sql_starboard['id']
                        )
        else:
            starboard_message = None
            delete = True

    async with db.lock:
        conn = await db.connect()
        async with conn.transaction():
            if delete:
                await conn.execute(
                    delete_starboard_message, sql_message['id'],
                    sql_starboard['id']
                )
            points, emojis = await calculate_points(
                conn, sql_message, sql_starboard, bot
            )

    deleted = message is None
    on_starboard = starboard_message is not None

    link_deletes = sql_starboard['link_deletes']
    link_edits = sql_starboard['link_edits']
    bots_on_sb = sql_starboard['bots_on_sb']
    is_bot = sql_author['is_bot']
    forced = sql_message['is_forced']
    frozen = sql_message['is_frozen']
    trashed = sql_message['is_trashed']

    add = False
    remove = False
    if deleted and link_deletes:
        remove = True
    elif points <= sql_starboard['rtl']:
        remove = True
    elif points >= sql_starboard['required']:
        add = True

    if on_starboard is True:
        add = False
    elif on_starboard is False:
        remove = False

    if is_bot and not bots_on_sb:
        add = False
        if on_starboard:
            remove = True

    if forced is True:
        remove = False
        if not on_starboard:
            add = True

    if not frozen:
        await update_message(
            db, message, sql_message['channel_id'], starboard_message,
            starboard, points, forced, trashed, add, remove, link_edits, emojis
        )


async def update_message(
    db, orig_message, orig_channel_id, sb_message, starboard, points,
    forced, trashed, add, remove, link_edits, emojis
):
    update = orig_message is not None

    if trashed:
        if sb_message is not None:
            embed = discord.Embed(title='Trashed Message')
            embed.description = "This message was trashed by a moderator."
            try:
                await sb_message.edit(embed=embed)
            except discord.errors.NotFound:
                pass
    elif remove:
        try:
            await sb_message.delete()
        except discord.errors.NotFound:
            pass
    else:
        plain_text = \
            f"**{points} | <#{orig_channel_id}>{' | 🔒' if forced else ''}**"

        embed = await get_embed_from_message(
            orig_message
        ) if orig_message is not None else None

        if add and embed is not None:
            try:
                sb_message = await starboard.send(plain_text, embed=embed)
            except Forbidden:
                pass
            else:
                async with db.lock:
                    conn = await db.connect()
                    async with conn.transaction():
                        await db.q.create_message.fetch(
                            sb_message.id, sb_message.guild.id,
                            orig_message.author.id, orig_message.id,
                            starboard.id, False,
                            orig_message.channel.is_nsfw()
                        )

        elif update and sb_message and link_edits:
            await sb_message.edit(
                content=plain_text, embed=embed
            )
        elif sb_message:
            await sb_message.edit(
                content=plain_text
            )
    if sb_message is not None and not remove and add:
        for _emoji in emojis:
            if _emoji['d_id'] is not None:
                emoji = utils.get(
                    starboard.guild.emojis, id=int(_emoji['d_id'])
                )
                if emoji is None:
                    continue
            else:
                emoji = _emoji['name']
            try:
                await sb_message.add_reaction(emoji)
            except Exception:
                pass


async def get_embed_from_message(message):
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

    for msg_embed in message.embeds:
        if msg_embed.type == 'rich':
            fields = [
                (f"\n**{x.name}**\n", f"{x.value}\n")
                for x in msg_embed.fields
            ]
            embed_text += f"__**{msg_embed.title}**__\n"
            embed_text += f"{msg_embed.description}\n"
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

    value_string = f"{message.content}\n{embed_text}"
    context_string = f"\n[**Jump to Message**]({message.jump_url})"
    if len(value_string + context_string) >= 2049:
        clip_msg = "... *message clipped*\n"
        to_clip = len(value_string+context_string+clip_msg)-(2048)
        full_string = value_string[0:-to_clip] + clip_msg +\
            context_string
    else:
        full_string = value_string + context_string
    embed.description = full_string

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


async def calculate_points(conn, sql_message, sql_starboard, bot):
    get_reactions = \
        """SELECT * FROM reactions WHERE message_id=$1 AND name=$2"""
    get_user = \
        """SELECT * FROM users WHERE id=$1"""
    get_sbemojis = \
        """SELECT * FROM sbemojis WHERE starboard_id=$1"""

    emojis = await conn.fetch(get_sbemojis, sql_starboard['id'])
    message_id = sql_message['id']
    self_star = sql_starboard['self_star']

    used_users = set()

    total_points = 0
    for emoji in emojis:
        emoji_id = int(emoji['d_id']) if emoji['d_id'] is not None else None
        emoji_name = None if emoji_id is not None else emoji['name']
        reactions = await conn.fetch(
            get_reactions, message_id,
            emoji_name if emoji_id is None else str(emoji_id)
        )
        for sql_reaction in reactions:
            user_id = sql_reaction['user_id']
            if user_id in used_users:
                continue
            used_users.add(user_id)
            if user_id == sql_message['user_id'] and self_star is False:
                continue
            rows = await conn.fetch(get_user, user_id)
            sql_user = rows[0]
            if sql_user['is_bot'] is True:
                continue

            total_points += 1

    return total_points, emojis
