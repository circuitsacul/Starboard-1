import discord, functions
from discord import utils


async def handle_reaction(db, bot, guild_id, _channel_id, user_id, _message_id, _emoji, is_add):
    emoji_id = _emoji.id
    emoji_name = _emoji.name

    conn = await db.connect()
    c = await conn.cursor()

    check_reaction = \
        """SELECT * FROM reactions
        WHERE message_id=?
        AND user_id=?
        AND name=?"""
    remove_reaction = \
        """DELETE FROM reactions
        WHERE message_id=?
        AND user_id=?
        AND name=?"""
    get_message = \
        """SELECT * FROM messages WHERE id=?"""

    async with db.lock:
        await functions.check_or_create_existence(
            db, c, bot,
            guild_id=guild_id, user_id=user_id, do_member=True
        )
        message_id, orig_channel_id = await _orig_message_id(db, c, _message_id)
        channel_id = orig_channel_id if orig_channel_id is not None else _channel_id
        channel = bot.get_channel(channel_id)
        try:
            message = await channel.fetch_message(message_id)
        except discord.errors.NotFound:
            message = None
        await c.execute(get_message, [message_id])
        if len(await c.fetchall()) == 0:
            await c.execute(db.q.create_message, [
                message_id, guild_id, message.author.id, None, channel_id, True,
                message.channel.is_nsfw()
            ])

        await c.execute(check_reaction, [message_id, user_id, emoji_name])
        rows = await c.fetchall()
        exists = len(rows) > 0
        if not exists and is_add:
            await c.execute(db.q.create_reaction, [
                emoji_id, guild_id, user_id, message_id, emoji_name
            ])
        if exists and not is_add:
            await c.execute(remove_reaction, (message_id, user_id, emoji_name))

        await conn.commit()
        await conn.close()
    await handle_starboards(db, bot, message_id, message)


async def _orig_message_id(db, c, message_id):
    get_message = \
        """SELECT * FROM messages WHERE id=?"""

    await c.execute(get_message, (message_id,))
    rows = await c.fetchall()
    if len(rows) == 0:
        return message_id, None
    sql_message = rows[0]
    if sql_message['is_orig'] == True:
        return message_id, sql_message['channel_id']
    orig_messsage_id = sql_message['orig_message_id']
    await c.execute(get_message, [orig_messsage_id])
    rows = await c.fetchall()
    sql_orig_message = rows[0]
    return orig_messsage_id, sql_orig_message['channel_id']


async def handle_starboards(db, bot, message_id, message):
    get_message = \
        """SELECT * FROM messages WHERE id=?"""
    get_starboards = \
        """SELECT * FROM starboards
        WHERE guild_id=?
        AND locked=False"""

    conn = await db.connect()
    c = await conn.cursor()
    async with db.lock:
        await c.execute(get_message, [message_id])
        sql_message = await c.fetchall()[0]
        channel_id = sql_message['channel_id']
        message_id = sql_message['id']
        channel = bot.get_channel(channel_id)
        if channel is None:
            return
        #try:
        #    message = await channel.fetch_message(message_id)
        #except discord.errors.NotFound:
        #    message = None
        await c.execute(get_starboards, [sql_message['guild_id']])
        sql_starboards = await c.fetchall()
        await conn.commit()
        await conn.close()
    for sql_starboard in sql_starboards:
        await handle_starboard(db, bot, sql_message, message, sql_starboard)


async def handle_starboard(db, bot, sql_message, message, sql_starboard):
    get_starboard_message = \
        """SELECT * FROM messages WHERE orig_message_id=? AND channel_id=?"""
    delete_starboard_message = \
        """DELETE FROM messages WHERE orig_message_id=? and channel_id=?"""

    starboard_id = sql_starboard['id']
    starboard = bot.get_channel(starboard_id)

    conn = await db.connect()
    c = await conn.cursor()
    async with db.lock:
        await c.execute(get_starboard_message, (sql_message['id'], sql_starboard['id']))
        rows = await c.fetchall()
        if len(rows) == 0:
            starboard_message = None
        else:
            sql_starboard_message = rows[0]
            starboard_message_id = sql_starboard_message['id']
            if starboard is not None:
                try:
                    starboard_message = await starboard.fetch_message(starboard_message_id)
                except discord.errors.NotFound:
                    starboard_message = None
                    await c.execute(delete_starboard_message, [sql_message['id'], sql_starboard['id']])
            else:
                starboard_message = None
                await c.execute(delete_starboard_message, [sql_message['id'], sql_starboard['id']])
        points, emojis = await calculate_points(c, sql_message, sql_starboard)

    deleted = message is None
    on_starboard = starboard_message is not None

    link_deletes = sql_starboard['link_deletes']
    link_edits = sql_starboard['link_edits']
    forced = sql_message['is_forced']
    frozen = sql_message['is_frozen']

    add = False
    remove = False
    if deleted and link_deletes:
        remove = True
    elif points <= sql_starboard['rtl']:
        remove = True
    elif points >= sql_starboard['required']:
        add = True

    if on_starboard == True:
        add = False
    elif on_starboard == False:
        remove = False

    if forced == True:
        remove = False
        if not on_starboard:
            add = True

    if not frozen:
        await update_message(c, db, message, sql_message['channel_id'], starboard_message, starboard, points, forced, add, remove, link_edits, emojis)
    await conn.commit()
    await conn.close()


async def update_message(c, db, orig_message, orig_channel_id, sb_message, starboard, points, forced, add, remove, link_edits, emojis):
    update = orig_message is not None
    async with db.lock:
        if remove:
            await sb_message.delete()
            return
        plain_text = f"**⭐ {points} | <#{orig_channel_id}>{' | 🔒' if forced else ''}**"
        embed = await get_embed_from_message(orig_message) if orig_message is not None else None
        if add and embed is not None:
            sb_message = await starboard.send(plain_text, embed=embed)
            await c.execute(db.q.create_message, [
                sb_message.id, sb_message.guild.id, orig_message.author.id,
                orig_message.id, starboard.id, False,
                orig_message.channel.is_nsfw()
            ])
        elif update and sb_message:
            if link_edits:
                await sb_message.edit(
                    content=plain_text, embed=embed
                )
            else:
                await sb_message.edit(
                    content=plain_text
                )
    if sb_message is not None:
        for _emoji in emojis:
            if _emoji['d_id'] is not None:
                emoji = utils.get(starboard.guild.emojis, id=int(_emoji['id']))
                if emoji is None:
                    continue
            else:
                emoji = _emoji['name']
            await sb_message.add_reaction(emoji)


async def get_embed_from_message(message):
    nsfw = message.channel.is_nsfw()
    embed = discord.Embed(title="NSFW" if nsfw else discord.Embed.Empty, colour=0xFCFF00)
    embed.set_author(name=message.author.name, icon_url=message.author.avatar_url)
    embed_text = ''
    msg_attachments = message.attachments
    urls = []

    for attachment in msg_attachments:
        urls.append({'name': attachment.filename, 'display_url': attachment.url, 'url': attachment.url, 'type': 'upload'})

    for msg_embed in message.embeds:
        if msg_embed.type == 'rich':
            fields = [(f"\n**{x.name}**\n", f"{x.value}\n") for x in msg_embed.fields]
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
                urls.append({'name': 'Image', 'display_url': msg_embed.thumbnail.url, 'url': msg_embed.url, 'type': 'image'})
        elif msg_embed.type == 'gifv':
            if msg_embed.url != discord.Embed.Empty:
                urls.append({'name': 'GIF', 'display_url': msg_embed.thumbnail.url, 'url': msg_embed.url, 'type': 'gif'})
        elif msg_embed.type == 'video':
            if msg_embed.url != discord.Embed.Empty:
                urls.append({'name': 'Video', 'display_url': msg_embed.thumbnail.url, 'url': msg_embed.url, 'type': 'video'})

    value_string = f"{message.content}\n{embed_text}"
    context_string = f"\n[**Jump to Message**]({message.jump_url})"
    if len(value_string + context_string) >= 1000:
        full_string = value_string[0:800] + "... *message clipped*\n" + context_string
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

    embed.set_footer(text=f"{message.id}")
    embed.timestamp = message.created_at

    return embed


async def calculate_points(c, sql_message, sql_starboard):
    get_reactions = \
        """SELECT * FROM reactions WHERE message_id=? AND name=?"""
    get_user = \
        """SELECT * FROM users WHERE id=?"""
    get_sbemojis = \
        """SELECT * FROM sbemojis WHERE starboard_id=?"""

    await c.execute(get_sbemojis, [sql_starboard['id']])
    emojis = await c.fetchall()
    message_id = sql_message['id']
    self_star = sql_starboard['self_star']
    bots_react = sql_starboard['bots_react']

    used_users = set()

    total_points = 0
    for emoji in emojis:
        await c.execute(get_reactions, [message_id, emoji['name']])
        reactions = await c.fetchall()
        for sql_reaction in reactions:
            user_id = sql_reaction['user_id']
            if user_id in used_users:
                continue
            used_users.add(user_id)
            if user_id == sql_message['user_id'] and self_star == False:
                continue
            await c.execute(get_user, [user_id])
            rows = await c.fetchall()
            sql_user = rows[0]
            if sql_user['is_bot'] == True and bots_react == False:
                continue
            total_points += 1
    
    return total_points, emojis
