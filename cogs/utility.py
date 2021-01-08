import discord
from discord.ext import commands, flags
from discord.ext.commands import BucketType
from disputils import BotEmbedPaginator

import bot_config
import checks
import functions
from cogs.starboard import handle_starboards
from database.database import Database


async def scan_recount(
    bot: commands.Bot,
    channel: discord.TextChannel,
    messages: int,
    start_date=None
) -> None:
    async for m in channel.history(limit=messages, before=start_date):
        if await functions.needs_recount(bot, m):
            await functions.recount_reactions(bot, m)


async def handle_trashing(
    db: Database,
    bot: commands.Bot,
    ctx: commands.Context,
    _message_id: int,
    trash: bool
) -> None:
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

    channel = bot.get_channel(int(channel_id))
    try:
        message = await functions.fetch(bot, message_id, channel)
    except discord.errors.NotFound:
        message = None

    if status is True:
        await handle_starboards(
            db, bot, message_id, channel, message,
            ctx.guild
        )
    return status


async def handle_forcing(
    bot, ctx,
    _channel: discord.TextChannel,
    _message_id: int,
    force: bool
) -> None:
    check_message = \
        """SELECT * FROM messages WHERE id=$1"""
    force_message = \
        """UPDATE messages
        SET is_forced=$1
        WHERE id=$2"""

    _channel = ctx.channel if _channel is None else _channel

    try:
        await functions.fetch(
            bot, int(_message_id), _channel
        )
    except discord.errors.NotFound:
        await ctx.send("I couldn't find that message.")
        return
    except AttributeError:
        await ctx.send("I can't find that channel")
        return

    async with bot.db.lock:
        conn = await bot.db.connect()
        async with conn.transaction():
            message_id, channel_id = await functions.orig_message_id(
                bot.db, conn, _message_id
            )

    channel = bot.get_channel(int(channel_id)) \
        if channel_id is not None else ctx.channel

    message = await functions.fetch(bot, int(message_id), channel)

    await functions.check_or_create_existence(
        bot,
        guild_id=ctx.guild.id, user=message.author,
        do_member=True
    )

    async with bot.db.lock:
        conn = await bot.db.connect()
        async with conn.transaction():
            sql_message = await conn.fetchrow(check_message, message_id)
            if sql_message is None:
                await bot.db.q.create_message.fetch(
                    message.id, ctx.guild.id, message.author.id,
                    None, message.channel.id, True,
                    message.channel.is_nsfw()
                )
            await conn.execute(force_message, force, message.id)

    await ctx.send(
        "Message forced." if force else
        "Message unforced."
    )

    await handle_starboards(
        bot.db, bot, message.id, message.channel, message,
        ctx.guild
    )


class Utility(commands.Cog):
    """Useful utility commands for your server"""
    def __init__(
        self,
        bot: commands.Bot,
        db: Database
    ) -> None:
        self.bot = bot
        self.db = db

    @flags.add_flag('--message', type=str, default="0")
    @flags.command(
        name='scan', aliases=['recountChannel'],
        description='Recount X messages in a channel before '
        'a certain timestamp, or before I joined this server',
        brief='Retotal reactions on X messages in channel'
    )
    @commands.has_permissions(manage_guild=True)
    @commands.max_concurrency(1, BucketType.channel)
    @commands.guild_only()
    @checks.premium_guild()
    async def recount_channel(
        self,
        ctx: commands.Context,
        messages: int,
        **flags: dict
    ) -> None:
        if messages > 1000:
            await ctx.send("Can only recount up to 1000 messages")
            return

        message = flags['message']
        try:
            message = int(message)
        except ValueError:
            # it better be a link or we'll be mad
            try:
                message = int(message[-18:])
            except ValueError:
                await ctx.send("--message must be a message ID or a link!")
                return

        msg = None
        if message is not None:
            try:
                msg = await ctx.channel.fetch_message(message)
            except (discord.errors.NotFound, discord.errors.Forbidden):
                msg = None

        async with ctx.typing():
            await scan_recount(
                self.bot, ctx.channel, messages, msg
            )

        await ctx.send("Finished")

    @commands.command(
        name='frozen', aliases=['f'],
        brief='Lists all frozen messages',
        description='Lists all frozen messages'
    )
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def list_frozen_messages(
        self,
        ctx: commands.Context
    ) -> None:
        get_frozen = \
            """SELECT * FROM messages
            WHERE is_frozen = True AND guild_id=$1"""

        async with self.db.lock:
            conn = await self.db.connect()
            async with conn.transaction():
                frozen_messages = await conn.fetch(get_frozen, ctx.guild.id)

        if len(frozen_messages) == 0:
            await ctx.send("You don't have any frozen messages")
        else:
            all_strings = []
            for i, msg in enumerate(frozen_messages):
                from_msg = f"**[{msg['id']}]"\
                    "(https://discordapp.com/channels/"\
                    f"{msg['guild_id']}/{msg['channel_id']}/{msg['id']}/)**\n"
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
    async def freeze_message(
        self,
        ctx: commands.Context,
        message: int
    ) -> None:
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

        mid = int(sql_message['id'])
        cid = int(sql_message['channel_id'])
        channel = self.bot.get_channel(cid)
        try:
            message_obj = await functions.fetch(self.bot, mid, channel)
        except Exception:
            message_obj = None

        await handle_starboards(
            self.bot.db, self.bot, message_id, channel,
            message_obj, ctx.guild
        )

        await ctx.send(message)

    @commands.command(
        name='unfreeze', aliases=['uf'],
        description='Unfreezes a messages',
        brief="Unfreezes a message"
    )
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def unfreeze_message(
        self,
        ctx: commands.Context,
        message: int
    ) -> None:
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

        mid = int(sql_message['id'])
        cid = int(sql_message['channel_id'])
        channel = self.bot.get_channel(cid)
        try:
            message_obj = await functions.fetch(self.bot, mid, channel)
        except Exception:
            message_obj = None

        await handle_starboards(
            self.bot.db, self.bot, mid, channel,
            message_obj, ctx.guild
        )

        await ctx.send(message)

    @commands.command(
        name='force',
        description='Forces a message to all starboards',
        brief='Forces a message to all starboards'
    )
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def force_message(
        self,
        ctx: commands.Context,
        _message_id: int,
        _channel: discord.TextChannel = None
    ) -> None:
        await handle_forcing(
            self.bot, ctx, _channel,
            _message_id, True
        )

    @commands.command(
        name='unforce',
        description='Unforces a message from all starboards',
        brief='Unforces a message'
    )
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def unforce_message(
        self,
        ctx: commands.Context,
        _message_id: int,
        _channel: discord.TextChannel = None
    ) -> None:
        await handle_forcing(
            self.bot, ctx, _channel,
            _message_id, False
        )

    @commands.command(
        name='trash',
        description='Trashing a message prevents users '
        'from seeing it or reacting to it.',
        brief='Trashes a message'
    )
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def trash_message(
        self,
        ctx: commands.Context,
        _messsage_id: int
    ) -> None:
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
    async def untrash_message(
        self,
        ctx: commands.Context,
        _message_id: int
    ) -> None:
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
    async def clear_guild_cache(
        self,
        ctx: commands.Context
    ) -> None:
        cache = self.bot.db.cache
        cache._messages[ctx.guild.id] = []
        await ctx.send("Message cache cleared")

    @commands.command(
        name='messageInfo', aliases=['messageStats', 'mi'],
        brief='View statistics on a message'
    )
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def get_message_statistics(
        self,
        ctx: commands.Context,
        message_id: int
    ) -> None:
        get_message = \
            """SELECT * FROM messages WHERE id=$1 AND guild_id=$2"""
        get_starboard_message = \
            """SELECT * FROM messages WHERE is_orig=False
            AND orig_message_id=$1"""

        sql_sb_messages = []

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

        if sql_message is None:
            await ctx.send(
                "That message either never existed or is not in the database."
            )
            return

        frozen = sql_message['is_frozen']
        forced = sql_message['is_forced']
        trashed = sql_message['is_trashed']
        author = (await functions.get_members(
            [int(sql_message['user_id'])], ctx.guild))[0]

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

    @commands.command(
        name='recount', aliases=['recalc', 'refresh'],
        description="Recount the reactions on a message",
        brief="Recount the reaactions on a message"
    )
    @commands.max_concurrency(2, wait=True)
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def recount_msg_reactions(
        self,
        ctx: commands.Context,
        message_id: int,
        channel: discord.TextChannel = None
    ) -> None:
        if channel is None:
            channel = ctx.channel
        try:
            message = await channel.fetch_message(message_id)
        except discord.errors.NotFound:
            await ctx.send("I couldn't find that message.")
            return
        total_reactions = sum([r.count for r in message.reactions])
        eta = int(total_reactions / 100 * 5 + total_reactions * 0.1)

        check_message = \
            """SELECT * FROM messages WHERE id=$1"""

        await functions.check_or_create_existence(
            self.bot,
            guild_id=ctx.guild.id,
            user=message.author,
            do_member=True
        )

        conn = self.bot.db.conn
        async with self.bot.db.lock:
            async with conn.transaction():
                sql_message = await conn.fetchrow(
                    check_message, message.id
                )
                if sql_message is None:
                    await self.bot.db.q.create_message.fetch(
                        message.id, message.guild.id,
                        message.author.id, None,
                        message.channel.id, True,
                        message.channel.is_nsfw()
                    )

        if sql_message is not None:
            if not sql_message['is_orig']:
                await ctx.send(
                    "Please run this command on the"
                    " original message, not the starboard"
                    " message."
                )
                return

        await ctx.send(
            "Recounting reactions. "
            f"(ETA: {eta} seconds)"
        )

        async with ctx.typing():
            await functions.recount_reactions(self.bot, message)
            await handle_starboards(
                self.bot.db, self.bot, message.id,
                message.channel, message, ctx.guild
            )

        await ctx.send("Finished!")

    @commands.command(
        name='movelock',
        brief="Moves a premium lock from one channel to another"
    )
    @commands.has_permissions(manage_channels=True)
    @commands.cooldown(30, 120, type=commands.BucketType.guild)
    @commands.guild_only()
    async def move_prem_lock(
        self,
        ctx: commands.Context,
        current_channel: discord.TextChannel,
        new_channel: discord.TextChannel
    ) -> None:
        """Moves a premium lock from one channel to a different
        channel, for either starboards or AutoStar channels.

        [current_channel]: The channel that is currently locked
        (can be a starboard or autostar channel)

        [new_channel]: The channel that you want to move the
        lock to. Cannot already be locked (starboard or autostar
        channel)"""
        get_starboard = \
            """SELECT * FROM starboards
            WHERE id=$1"""
        get_aschannel = \
            """SELECT * FROM aschannels
            WHERE id=$1"""

        conn = self.bot.db.conn

        async with self.bot.db.lock:
            async with conn.transaction():
                is_sb = await conn.fetchrow(
                    get_starboard, current_channel.id
                ) is not None
                is_asc = await conn.fetchrow(
                    get_aschannel, current_channel.id
                ) is not None

        if is_sb:
            await functions.move_starboard_lock(
                self.bot, current_channel, new_channel
            )
        elif is_asc:
            await functions.move_aschannel_lock(
                self.bot, current_channel, new_channel
            )
        else:
            await ctx.send(
                f"{current_channel.mention} isn't a starboard "
                "or autostar channel."
            )
            return
        await ctx.send("Done")


def setup(
    bot: commands.Bot
) -> None:
    bot.add_cog(Utility(bot, bot.db))
