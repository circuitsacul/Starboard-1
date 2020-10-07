from events.starboard_events import calculate_points
import discord
import functions
import bot_config
from discord.ext import commands
from events import starboard_events
from disputils import BotEmbedPaginator


async def handle_trashing(db, bot, ctx, _message_id, trash: bool):
    check_message = \
        """SELECT * FROM messages WHERE id=$1"""
    trash_message = \
        """UPDATE messages
        SET is_trashed=$1
        WHERE id=$2"""

    status = True

    async with db.lock:
        conn = await db.connect()
        async with conn.transaction():
            message_id, channel_id = await functions.orig_message_id(
                db, conn, _message_id
            )

            sql_message = await conn.fetchrow(check_message, message_id)
            if sql_message is None:
                await ctx.send(
                    "That message either has no reactions or does not exist"
                )
                status = False
            else:
                await conn.execute(trash_message, trash, message_id)
        #await conn.close()

    channel = bot.get_channel(int(channel_id))
    try:
        message = await functions.fetch(bot, message_id, channel)
    except discord.errors.NotFound:
        message = None

    if status is True:
        await starboard_events.handle_starboards(
            db, bot, message_id, channel, message
        )
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
            WHERE is_frozen = True AND guild_id=$1"""

        async with self.db.lock:
            conn = await self.db.connect()
            async with conn.transaction():
                frozen_messages = await conn.fetch(get_frozen, ctx.guild.id)
            #await conn.close()

        if len(frozen_messages) == 0:
            await ctx.send("You don't have any frozen messages")
        else:
            all_strings = []
            for i, msg in enumerate(frozen_messages):
                from_msg = f"**[{msg['id']}]"\
                    "(https://discordapp.com/channels/"\
                    "{msg['guild_id']}/{msg['channel_id']}/{msg['id']}/)**\n"
                all_strings.append(from_msg)

            size = 10
            grouped = [
                all_strings[i:i+size] for i in range(0, len(all_strings), size)
            ]

            all_embeds = []
            for group in grouped:
                embed = discord.Embed(
                    color=bot_config.COLOR, title='Frozen Messages'
                )
                string = ""
                for item in group:
                    string += item
                embed.description = string
                all_embeds.append(embed)

            paginator = BotEmbedPaginator(ctx, all_embeds)
            await paginator.run()

    @commands.command(
        name='freeze', brief='Freezes a message',
        description="Freezing a message means that it can't "
        "be removed or added to a starboard, "
        "and no new reactions will be logged."
    )
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def freeze_message(self, ctx, message: int):
        get_message = \
            """SELECT * FROM messages WHERE id=$1 AND guild_id=$2"""
        freeze_message = \
            """UPDATE messages
            SET is_frozen = True
            WHERE id=$1"""

        async with self.db.lock:
            conn = await self.db.connect()
            async with conn.transaction():
                message_id, _orig_channel_id = await functions.orig_message_id(
                    self.db, conn, message
                )
                sql_message = await conn.fetchrow(
                    get_message, message_id, ctx.guild.id
                )

            if not sql_message:
                message = "That message either has "\
                    "no reactions or does not exist"
            else:
                await conn.execute(freeze_message, message_id)
                message = f"Message **{message_id}** is now frozen"

            #await conn.close()

        await ctx.send(message)

    @commands.command(
        name='unfreeze', aliases=['uf'],
        description='Unfreezes a messages',
        brief="Unfreezes a message"
    )
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def unfreeze_message(self, ctx, message: int):
        get_message = \
            """SELECT * FROM messages WHERE id=$1 AND guild_id=$2"""
        freeze_message = \
            """UPDATE messages
            SET is_frozen = False
            WHERE id=$1"""

        async with self.db.lock:
            conn = await self.db.connect()
            async with conn.transaction():
                message_id, _orig_channel_id = await functions.orig_message_id(
                    self.db, conn, message
                )
                sql_message = await conn.fetchrow(
                    get_message, message_id, ctx.guild.id
                )
                if not sql_message:
                    message = "That message either has"\
                        " no reactions or does not exist"
                else:
                    await conn.execute(freeze_message, message_id)
                    message = f"Message **{message_id}** is now unfrozen"

            #await conn.close()
        await ctx.send(message)

    @commands.command(
        name='force',
        description='Forces a message to all starboards',
        brief='Forces a message to all starboards'
    )
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def force_message(
        self, ctx, _message_id, _channel: discord.TextChannel = None
    ):
        check_message = \
            """SELECT * FROM messages WHERE id=$1"""
        force_message = \
            """UPDATE messages
            SET is_forced=True
            WHERE id=$1"""

        _channel = ctx.channel if _channel is None else _channel

        try:
            await functions.fetch(
                self.bot, int(_message_id), _channel
            )
        except discord.errors.NotFound:
            await ctx.send("I couldn't find that message.")
            return
        except AttributeError:
            await ctx.send("I can't find that channel")
            return

        async with self.db.lock:
            conn = await self.db.connect()
            async with conn.transaction():
                message_id, channel_id = await functions.orig_message_id(
                    self.db, conn, _message_id
                )
            #await conn.close()

        channel = self.bot.get_channel(int(channel_id)) \
            if channel_id is not None else ctx.channel

        message = await functions.fetch(self.bot, int(message_id), channel)

        async with self.db.lock:
            conn = await self.db.connect()
            async with conn.transaction():
                sql_message = await conn.fetchrow(check_message, message_id)
                if sql_message is None:
                    await self.db.q.create_message.fetch(
                        message.id, ctx.guild.id, message.author.id,
                        None, message.channel.id, True,
                        message.channel.is_nsfw()
                    )
                await conn.execute(force_message, message.id)
            #await conn.close()

        await ctx.send("Message forced.")

        await starboard_events.handle_starboards(
            self.db, self.bot, message.id, message.channel, message
        )

    @commands.command(
        name='trash',
        description='Trashing a message prevents users '
        'from seeing it or reacting to it.',
        brief='Trashes a message'
    )
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def trash_message(self, ctx, _messsage_id):
        status = await handle_trashing(
            self.db, self.bot, ctx, _messsage_id, True
        )
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
        status = await handle_trashing(
            self.db, self.bot, ctx, _message_id, False
        )
        if status is True:
            await ctx.send("Message untrashed")

    @commands.command(
        name='clearCache', aliases=['cc', 'clearC'],
        brief='Clear message cache',
        description="You don't really need to worry about this. "
        "This is just in case something goes wrong with the message caching.",
        hidden=True
    )
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def clear_guild_cache(self, ctx):
        cache = self.bot.db.cache
        async with cache.lock:
            cache._messages[ctx.guild.id] = []
        await ctx.send("Message cache cleared")


    @commands.command(
        name='messageInfo', aliases=['messageStats', 'mi'],
        brief='View statistics on a message'
    )
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def get_message_statistics(self, ctx, message_id: int):
        get_message = \
            """SELECT * FROM messages WHERE id=$1 AND guild_id=$2"""
        get_starboard_message = \
            """SELECT * FROM messages WHERE is_orig=False
            AND orig_message_id=$1"""

        async with self.db.lock:
            conn = await self.bot.db.connect()
            async with conn.transaction():
                orig_message_id, _ = await functions.orig_message_id(
                    self.bot.db, conn, message_id
                )
                sql_message = await conn.fetchrow(
                    get_message, orig_message_id, ctx.guild.id
                )

                if sql_message is not None:
                    sql_sb_messages = await conn.fetch(
                        get_starboard_message, orig_message_id
                    )
            #await conn.close()

        if sql_message is None:
            await ctx.send(
                "That message either never existed or is not in the database."
            )
            return

        frozen = sql_message['is_frozen']
        forced = sql_message['is_forced']
        trashed = sql_message['is_trashed']
        author = self.bot.get_user(sql_message['user_id'])

        _channel = self.bot.get_channel(sql_message['channel_id'])
        try:
            message = await _channel.fetch_message(sql_message['id'])
        except (discord.errors.NotFound, AttributeError):
            message = None

        sb_msg_objs = []
        for sbm in sql_sb_messages:
            _channel = self.bot.get_channel(
                sbm['channel_id']
            )
            try:
                _message = await _channel.fetch_message(
                    sbm['id']
                )
            except (discord.errors.NotFound, AttributeError):
                _message = None

            if _message:
                sb_msg_objs.append(_message)

        embed = discord.Embed(
            title='Message Stats',
            color=bot_config.COLOR
        )

        if message is None:
            jump_string = "Message Deleted"
        else:
            jump_string = f"[Jump to Message]({message.jump_url})"

        embed.description = f"{jump_string}\n"\
            f"Original Message Id: {sql_message['id']}\n"\
            f"Author: <@{sql_message['user_id']}> | "\
            f"{sql_message['user_id']} | "\
            f"{str(author) if author is not None else 'Deleted User'}\n"\
            f"Frozen: {frozen}\nTrashed: {trashed}\nForced: {forced}"

        starboard_string = ""
        for sbm in sb_msg_objs:
            starboard_string += f"{sbm.channel.mention}: "\
                f"[Jump]({sbm.jump_url})\n"

        starboard_string = "This message is not on any starboards"\
            if starboard_string == "" else starboard_string

        embed.add_field(
            name="Starboards",
            value=starboard_string
        )

        await ctx.send(embed=embed)
