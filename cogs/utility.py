import discord, functions
from discord.ext import commands
from events import starboard_events


async def handle_trashing(db, bot, ctx, _message_id, trash: bool):
    check_message = \
        """SELECT * FROM messages WHERE id=?"""
    trash_message = \
        """UPDATE messages
        SET is_trashed=?
        WHERE id=?"""

    status = True

    conn = await db.connect()
    c = await conn.cursor()
    async with db.lock:
        message_id, channel_id = await functions.orig_message_id(db, c, _message_id)

        await c.execute(check_message, [message_id])
        sql_message = await c.fetchone()
        if sql_message is None:
            await ctx.send("That message either has no reactions or does not exist")
            status = False
        else:
            await c.execute(trash_message, [trash, message_id])
            await conn.commit()
        await conn.close()

    channel = bot.get_channel(channel_id)
    try:
        message = await channel.fetch_message(message_id) if channel is not None else None
    except discord.errors.NotFound:
        message = None

    if status is True:
        await starboard_events.handle_starboards(db, bot, message_id, channel, message)
    return status


class Utility(commands.Cog):
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    @commands.command(
        name='frozen', aliases=['f'],
        brief='Lists all frozen messages',
        description='Lists all frozen messages'
    )
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def list_frozen_messages(self, ctx):
        get_frozen = \
            """SELECT * FROM messages
            WHERE is_frozen = 1 AND guild_id=?"""

        conn = await self.db.connect()
        c = await conn.cursor()
        async with self.db.lock:
            await c.execute(get_frozen, [ctx.guild.id])
            frozen_messages = await c.fetchall()
        await conn.close()

        if len(frozen_messages) == 0:
            await ctx.send("You don't have any frozen messages")
        else:
            p = commands.Paginator(prefix='', suffix='')
            for msg in frozen_messages:
                p.add_line(f"**{msg['id']}**")
            for page in p.pages:
                await ctx.send(page)

    @commands.command(
        name='freeze', brief='Freezes a message',
        description="Freezing a message means that it can't be removed or added to a starboard, and no new reactions will be logged."
    )
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def freeze_message(self, ctx, message: int):
        get_message = \
            """SELECT * FROM messages WHERE id=? AND guild_id=?"""
        freeze_message = \
            """UPDATE messages
            SET is_frozen = 1
            WHERE id=?"""

        conn = await self.db.connect()
        c = await conn.cursor()
        async with self.db.lock:
            message_id, _orig_channel_id = await functions.orig_message_id(self.db, c, message)
            await c.execute(get_message, [message_id, ctx.guild.id])
            sql_message = await c.fetchone()
        
        if not sql_message:
            await ctx.send("That message either has no reactions or does not exist")

        else:
            async with self.db.lock:
                await c.execute(freeze_message, [message_id])
                await conn.commit()

            await ctx.send(f"Message **{message_id}** is now frozen")

        await conn.close()

    @commands.command(
        name='unfreeze', aliases=['uf'],
        description='Unfreezes a messages',
        brief="Unfreezes a message"
    )
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def unfreeze_message(self, ctx, message: int):
        get_message = \
            """SELECT * FROM messages WHERE id=? AND guild_id=?"""
        freeze_message = \
            """UPDATE messages
            SET is_frozen = 0
            WHERE id=?"""

        conn = await self.db.connect()
        c = await conn.cursor()
        async with self.db.lock:
            message_id, _orig_channel_id = await functions.orig_message_id(self.db, c, message)
            await c.execute(get_message, [message_id, ctx.guild.id])
            sql_message = await c.fetchone()

        if not sql_message:
            await ctx.send("That message either has not reactions or does not exist")

        else:
            async with self.db.lock:
                await c.execute(freeze_message, [message_id])
                await conn.commit()

            await ctx.send(f"Message **{message_id}** is now unfrozen")

        await conn.close()

    @commands.command(
        name='force',
        description='Forces a message to all starboards',
        brief='Forces a message to all starboards'
    )
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def force_message(self, ctx, _message_id, _channel: discord.TextChannel = None):
        check_message = \
            """SELECT * FROM messages WHERE id=?"""
        force_message = \
            """UPDATE messages
            SET is_forced=1
            WHERE id=?"""

        _channel = ctx.channel if _channel is None else _channel

        try:
            _message = await _channel.fetch_message(_message_id)
        except discord.errors.NotFound:
            await ctx.send("I couldn't find that message.")
            return
        except AttributeError:
            await ctx.send("I can't find that channel")
            return
        
        conn = await self.db.connect()
        c = await conn.cursor()
        async with self.db.lock:
            message_id, channel_id = await functions.orig_message_id(self.db, c, _message_id)

        channel = self.bot.get_channel(channel_id) if channel_id is not None else ctx.channel
        message = await channel.fetch_message(message_id)

        async with self.db.lock:
            await c.execute(check_message, [message_id])
            sql_message = await c.fetchone()
            if sql_message is None:
                await c.execute(
                    self.db.q.create_message,
                    [
                        message.id, ctx.guild.id, message.author.id,
                        None, message.channel.id, True, message.channel.is_nsfw()
                    ]
                )
            await c.execute(force_message, [message.id])
            await conn.commit()
            await conn.close()
        print('forced')
        
        await starboard_events.handle_starboards(self.db, self.bot, message.id, message.channel, message)

    @commands.command(
        name='trash',
        description='Trashing a message prevents users from seeing it or reacting to it.',
        brief='Trashes a message'
    )
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def trash_message(self, ctx, _messsage_id):
        status = await handle_trashing(self.db, self.bot, ctx, _messsage_id, True)
        if status is True:
            await ctx.send("Message Trashed")

    @commands.command(
        name='untrash',
        description='Untrashes a message',
        brief='Untrashes a message'
    )
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def untrash_message(self, ctx, _message_id):
        status = await handle_trashing(self.db, self.bot, ctx, _message_id, False)
        if status is True:
            await ctx.send("Message untrashed")