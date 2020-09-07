import discord, functions
from discord.ext import commands


class Utility(commands.Cog):
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    @commands.command(
        name='frozen', brief='Lists all frozen messages',
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