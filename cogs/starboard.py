import random
from typing import List, Optional, Union

import asyncpg
import discord
from discord import utils
from discord.ext import commands, flags

import bot_config
import cooldowns
import functions
import settings
from cogs import levels
from database.database import Database
from settings import change_starboard_settings

edit_message_cooldown = cooldowns.CooldownMapping.from_cooldown(
    3, 5
)


async def pretty_emoji_string(
    emojis: List[dict],
    guild: discord.Guild
) -> str:
    string = ""
    for emoji in emojis:
        is_custom = emoji['d_id'] is not None
        if is_custom:
            emoji_string = str(discord.utils.get(
                guild.emojis, id=int(emoji['d_id']))
            )
        else:
            emoji_string = emoji['name']
        string += emoji_string + " "
    return string


class Starboard(commands.Cog):
    """Starboard related commands"""
    def __init__(
        self,
        bot: commands.Bot,
        db: Database
    ) -> None:
        self.bot = bot
        self.db = db

    @commands.Cog.listener()
    async def on_raw_reaction_add(
        self,
        payload: discord.RawReactionActionEvent
    ) -> None:
        guild_id = payload.guild_id
        if guild_id is None:
            return
        channel_id = payload.channel_id
        message_id = payload.message_id
        user_id = payload.user_id
        emoji = payload.emoji

        emoji_name = str(emoji.id) if emoji.id is not None\
            else emoji.name

        if not await functions.is_starboard_emoji(
            self.bot.db, guild_id, emoji_name
        ):
            return

        await handle_reaction(
            self.bot.db, self.bot, guild_id, channel_id,
            user_id, message_id, emoji, True
        )

    @commands.Cog.listener()
    async def on_raw_reaction_remove(
        self,
        payload: discord.RawReactionActionEvent
    ) -> None:
        guild_id = payload.guild_id
        if guild_id is None:
            return
        channel_id = payload.channel_id
        message_id = payload.message_id
        user_id = payload.user_id
        emoji = payload.emoji

        emoji_name = emoji.id if emoji.id is not None\
            else emoji.name

        if not await functions.is_starboard_emoji(
            self.bot.db, guild_id, emoji_name
        ):
            return

        await handle_reaction(
            self.bot.db, self.bot, guild_id, channel_id,
            user_id, message_id, emoji, False
        )

    @flags.add_flag('--by', type=discord.User, default=None)
    @flags.add_flag('--stars', type=int, default=None)
    @flags.add_flag('--in', type=discord.TextChannel, default=None)
    @flags.command(
        name='random', aliases=['explore'],
        brief="Get a random message from the starboard"
    )
    @commands.cooldown(3, 5, type=commands.BucketType.user)
    @commands.guild_only()
    async def random_message(
        self,
        ctx: commands.Context,
        **flags: dict
    ) -> None:
        """Gets a random message from the starboard.

        [--by] is an optional argument specifying the author
        of the message.

        [--stars] is an optional argument specifying the minimum
        number of stars a message must have

        [--in] is an optional argument specifying the starboard
        to search for messages in
        """

        stars = flags['stars']
        starboard = flags['in']
        user = flags['by']

        sid = None
        uid = None

        if starboard:
            sid = starboard.id
        if user:
            uid = user.id

        query = (
            """SELECT * FROM messages
            WHERE orig_message_id IN (
                SELECT id FROM messages
                WHERE is_trashed=False
                AND is_forced=False
                AND is_nsfw=False
                AND ($2::numeric is null or user_id=$2)
            )
            AND guild_id=$1
            AND is_orig=False
            AND ($3::int is null or points >= $3)
            AND ($4::numeric is null or channel_id=$4)
            """
        )
        conn = self.bot.db.conn
        async with self.bot.db.lock:
            async with conn.transaction():
                m = await conn.fetch(
                    query, ctx.guild.id, uid, stars, sid
                )

        if len(m) == 0:
            await ctx.send(
                "I couldn't find any messages that meet "
                "those requirements."
            )
            return
        sql_rand_message = random.choice(m)

        async with self.bot.db.lock:
            async with conn.transaction():
                orig_mid, orig_cid = await functions.orig_message_id(
                    self.bot.db, conn, int(sql_rand_message['id'])
                )

        channel = self.bot.get_channel(orig_cid)
        m = await channel.fetch_message(orig_mid)

        e, attachments = await functions.get_embed_from_message(m)

        await ctx.send(
            f"**{sql_rand_message['points']} | {channel.mention}**",
            embed=e, files=attachments
        )

    @random_message.error
    async def handle_random_error(
        self,
        ctx: commands.Context,
        error: Exception
    ) -> None:
        await ctx.send(
            "Example command usage: `sb!random --stars 5 --in #starboard2`"
        )

    @commands.group(
        name='starboards', aliases=['boards', 's', 'sb'],
        description='List and manage starboards',
        brief='List starboards', invoke_without_command=True
    )
    @commands.guild_only()
    async def sb_settings(
        self,
        ctx: commands.Context,
        starboard: discord.TextChannel = None
    ) -> None:
        get_starboards = """SELECT * FROM starboards WHERE guild_id=$1"""
        get_emojis = """SELECT * FROM sbemojis WHERE starboard_id=$1"""
        get_starboard = """SELECT * FROM starboards WHERE id=$1"""
        p = await functions.get_one_prefix(self.bot, ctx.guild.id)

        if starboard is None:
            _ = await functions.check_or_create_existence(
                self.bot, guild_id=ctx.guild.id,
                user=ctx.message.author, do_member=True
            )
            async with self.db.lock:
                conn = await self.db.connect()
                async with conn.transaction():
                    rows = await conn.fetch(get_starboards, ctx.guild.id)

                    if len(rows) == 0:
                        message = "You don't have any starboards"
                        embed = None
                    else:
                        message = None
                        title = f'Starboards: {len(rows)}\n'
                        msg = ''
                        for row in rows:
                            sb_id = row['id']
                            starboard = self.bot.get_channel(int(sb_id))
                            sb_title = starboard.mention if starboard \
                                else f"Deleted Channel {sb_id}"
                            emojis = await conn.fetch(get_emojis, sb_id)
                            emoji_string = await pretty_emoji_string(
                                emojis, ctx.guild
                            )
                            msg += f"{sb_title} {emoji_string}\n"

                        embed = discord.Embed(
                            title=title, description=msg,
                            color=bot_config.COLOR
                        )
                        embed.set_footer(
                            text=f'Do {p}starboards <channel>'
                            '\nto view starboard settings.'
                        )

            if message is not None:
                await ctx.send(message)
            else:
                await ctx.send(embed=embed)
        else:
            await functions.check_or_create_existence(
                self.bot, guild_id=ctx.guild.id,
                user=ctx.message.author, do_member=True
            )
            async with self.db.lock:
                conn = await self.db.connect()
                async with conn.transaction():
                    sql_starboard = await conn.fetchrow(
                        get_starboard, starboard.id
                    )
                    if sql_starboard is None:
                        await ctx.send("That is not a starboard!")
                    else:
                        starboard = self.bot.get_channel(starboard.id)
                        emojis = await conn.fetch(get_emojis, starboard.id)
                        pretty_emojis = await pretty_emoji_string(
                            emojis, ctx.guild
                        )
                        title = f"Settings for {starboard.name}:"
                        string = f"**emojis: {pretty_emojis}**"\
                            "\n**requiredStars: "\
                            f"{sql_starboard['required']}**"\
                            f"\n**requiredToLose: {sql_starboard['rtl']}**"\
                            "\n**selfStar: "\
                            f"{bool(sql_starboard['self_star'])}**"\
                            "\n**linkEdits: "\
                            f"{bool(sql_starboard['link_edits'])}**"\
                            "\n**linkDeletes: "\
                            f"{bool(sql_starboard['link_deletes'])}**"\
                            "\n**botsOnStarboard: "\
                            f"{bool(sql_starboard['bots_on_sb'])}**"\
                            "\n**requireImage: "\
                            f"{bool(sql_starboard['require_image'])}**"\
                            f"\n**locked: {bool(sql_starboard['locked'])}**"

                        embed = discord.Embed(
                            title=title, description=string,
                            color=bot_config.COLOR
                        )
                        await ctx.send(embed=embed)

    @sb_settings.command(
        name='add', aliases=['a'],
        description='Add a starboard',
        brief='Add a starboard'
    )
    @commands.has_permissions(manage_channels=True)
    @commands.guild_only()
    async def add_starboard(
        self,
        ctx: commands.Context,
        starboard: discord.TextChannel
    ) -> None:
        await settings.add_starboard(self.bot, starboard)
        await ctx.send(f"Created starboard {starboard.mention}")

    @sb_settings.command(
        name='remove', aliases=['r'],
        description='Remove a starboard',
        brief='Remove a starboard'
    )
    @commands.has_permissions(manage_channels=True, manage_messages=True)
    @commands.guild_only()
    async def remove_starboard(
        self,
        ctx: commands.Context,
        starboard: Union[discord.TextChannel, int]
    ) -> None:
        starboard_id = starboard.id if isinstance(
            starboard, discord.TextChannel
        ) else int(starboard)
        confirmed = await functions.confirm(
            self.bot, ctx.channel,
            "Are you sure? All starboard messages will be lost forever.",
            ctx.message.author.id
        )

        if not confirmed:
            await ctx.send("Cancelling")
            return

        await settings.remove_starboard(self.bot, starboard_id, ctx.guild.id)
        await ctx.send("Removed starboard")

    @sb_settings.command(
        name='addEmoji', aliases=['ae'],
        description='Add emoji to a starboard',
        brief='Add emoji to starboard'
    )
    @commands.has_permissions(manage_channels=True, manage_messages=True)
    @commands.guild_only()
    async def add_starboard_emoji(
        self,
        ctx: commands.Context,
        starboard: discord.TextChannel,
        emoji: Union[discord.Emoji, str]
    ) -> None:
        await settings.add_starboard_emoji(
            self.bot, starboard.id, ctx.guild, emoji
        )
        await ctx.send(f"Added {emoji} to {starboard.mention}")

    @sb_settings.command(
        name='removeEmoji', aliases=['re'],
        description='Removes a starboard emoji',
        brief='Removes a starboard emoji'
    )
    @commands.has_permissions(manage_channels=True, manage_messages=True)
    @commands.guild_only()
    async def remove_starboard_emoji(
        self,
        ctx: commands.Context,
        starboard: discord.TextChannel,
        emoji: Union[discord.Emoji, str]
    ) -> None:
        await settings.remove_starboard_emoji(
            self.bot, starboard.id, ctx.guild, emoji
        )
        await ctx.send(f"Remove {emoji} from {starboard.mention}")

    @sb_settings.command(
        name='requireImage', aliases=['ri', 'imagesOnly'],
        brief="Sets the requireImage setting for a starboard"
    )
    @commands.has_guild_permissions(
        manage_channels=True,
        manage_messages=True
    )
    @commands.guild_only()
    async def set_require_image(
        self,
        ctx: commands.Context,
        starboard: discord.TextChannel,
        value: bool
    ) -> None:
        status = await change_starboard_settings(
            self.db, starboard.id, require_image=value
        )
        if status is None:
            await ctx.send("That is not a starboard!")
        elif status is False:
            await ctx.send("Something went wrong.")
        else:
            await ctx.send(
                f"Set requireImage to {value} for {starboard.mention}"
            )

    @sb_settings.command(
        name='requiredStars', aliases=['rs', 'required'],
        description='Set\'s how many stars are needed before a message '
        'appears on the starboard',
        brief='Set\'s required stars'
    )
    @commands.has_permissions(manage_channels=True, manage_messages=True)
    @commands.guild_only()
    async def set_required_stars(
        self,
        ctx: commands.Context,
        starboard: discord.TextChannel,
        value: int
    ) -> None:
        value = 1 if value < 1 else value
        status = await change_starboard_settings(
            self.db, starboard.id, required=value
        )
        if status is None:
            await ctx.send("That is not a starboard!")
        elif status is False:
            await ctx.send(
                "RequiredStars cannot be less than or equal to RequiredToLose"
            )
        else:
            await ctx.send(
                f"Set requiredStars to {value} for {starboard.mention}"
            )

    @sb_settings.command(
        name='requiredToLose', aliases=['rtl'],
        description='Set\'s how few stars a message needs before the '
        'messages is removed from the starboard',
        brief='Sets requiredToLose'
    )
    @commands.has_permissions(manage_channels=True, manage_messages=True)
    @commands.guild_only()
    async def set_required_to_lose(
        self,
        ctx: commands.Context,
        starboard: discord.TextChannel,
        value: int
    ) -> None:
        value = -1 if value < -1 else value
        status = await change_starboard_settings(
            self.db, starboard.id, rtl=value
        )
        if status is None:
            await ctx.send("That is not a starboard!")
        elif status is False:
            await ctx.send(
                "RequiredToLose cannot be greater "
                "than or equal to RequiredStars"
            )
        elif status is True:
            await ctx.send(
                f"Set requiredToLose to {value} "
                f"for {starboard.mention}"
            )

    @sb_settings.command(
        name='selfStar', aliases=['ss'],
        description='Set wether or not to allow a user to star '
        'their own message for starboard',
        brief='Set selfStar for starboard'
    )
    @commands.has_permissions(manage_channels=True)
    @commands.guild_only()
    async def starboard_self_star(
        self,
        ctx: commands.Context,
        starboard: discord.TextChannel,
        value: bool
    ) -> None:
        status = await change_starboard_settings(
            self.db, starboard.id, self_star=value
        )
        if status is None:
            await ctx.send("That is not a starboard!")
        elif status is False:
            await ctx.send("Invalid Value")
        else:
            await ctx.send(f"Set selfStar to {value} for {starboard.mention}")

    @sb_settings.command(
        name='linkEdits', aliases=['le'],
        description='Sets wether or not the bot should edit the starboard '
        'message if the user edits it',
        brief='Sets linkEdits for a starboard'
    )
    @commands.has_permissions(manage_channels=True, manage_messages=True)
    @commands.guild_only()
    async def set_link_edits(
        self,
        ctx: commands.Context,
        starboard: discord.TextChannel,
        value: bool
    ) -> None:
        status = await change_starboard_settings(
            self.db, starboard.id, link_edits=value
        )
        if status is None:
            await ctx.send("That is not a starboard!")
        elif status is False:
            await ctx.send("Invalid Setting")
        else:
            await ctx.send(f"Set linkEdits to {value} for {starboard.mention}")

    @sb_settings.command(
        name='linkDeletes', aliases=['ld'],
        description='Sets wether or not the bot should delete the starboard '
        'message if the original is deleted',
        brief='Sets linkDeletes for a starboard'
    )
    @commands.has_permissions(manage_channels=True, manage_messages=True)
    @commands.guild_only()
    async def set_link_deletes(
        self,
        ctx: commands.Context,
        starboard: discord.TextChannel,
        value: bool
    ) -> None:
        status = await change_starboard_settings(
            self.db, starboard.id, link_deletes=value
        )
        if status is None:
            await ctx.send("That is not a starboard!")
        elif status is False:
            await ctx.send("Invalid Setting")
        else:
            await ctx.send(
                f"Set linkDeletes to {value} for {starboard.mention}"
            )

    @sb_settings.command(
        name='botsOnStarboard', aliases=['botsOnSb', 'bos'],
        description="Sets wether or not to allow bot messages "
        "to be put on the starboard",
        brief='Sets botsOnStarboards for a starboard'
    )
    @commands.has_permissions(manage_channels=True, manage_messages=True)
    @commands.guild_only()
    async def set_bots_on_starboard(
        self,
        ctx: commands.Context,
        starboard: discord.TextChannel,
        value: bool
    ) -> None:
        status = await change_starboard_settings(
            self.db, starboard.id, bots_on_sb=value
        )
        if status is None:
            await ctx.send("That is not a starboard!")
        elif status is False:
            await ctx.send("Invalid Setting")
        else:
            await ctx.send(
                f"Set botsOnStarboard to {value} for {starboard.mention}"
            )


# Functions:
async def handle_reaction(
    db: Database,
    bot: commands.Bot,
    guild_id: int,
    _channel_id: int,
    user_id: int,
    _message_id: int,
    _emoji: discord.PartialEmoji,
    is_add: bool
) -> None:
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

        await functions.check_or_create_existence(
            bot, guild_id=guild_id,
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

    if message:
        await functions.check_or_create_existence(
            bot, guild_id=guild_id,
            user=message.author, do_member=True
        )
    await functions.check_or_create_existence(
        bot,
        guild_id=guild_id
    )

    async with db.lock:
        conn = await db.connect()
        async with conn.transaction():
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
            await levels.handle_reaction(
                db, user_id, message.author, guild, _emoji, is_add
            )

    await handle_starboards(db, bot, message_id, channel, message, guild)


async def handle_starboards(
    db: Database,
    bot: commands.Bot,
    message_id: int,
    channel: discord.TextChannel,
    message: Optional[discord.Message],
    guild: discord.Guild
) -> None:
    get_message = \
        """SELECT * FROM messages WHERE id=$1"""
    get_starboards = \
        """SELECT * FROM starboards
        WHERE guild_id=$1
        AND locked=False"""

    sql_starboards = []

    async with db.lock:
        conn = await db.connect()
        async with conn.transaction():
            sql_message = await conn.fetchrow(get_message, message_id)
            if sql_message is not None:
                sql_starboards = await conn.fetch(
                    get_starboards, sql_message['guild_id']
                )

    b = edit_message_cooldown.get_bucket(message_id)
    retry_after = b.update_rate_limit()
    on_cooldown = False
    if retry_after:
        on_cooldown = True

    if sql_message is not None:
        for sql_starboard in sql_starboards:
            await handle_starboard(
                db, bot, sql_message, message, sql_starboard,
                guild, on_cooldown=on_cooldown
            )


async def handle_starboard(
    db: Database,
    bot: commands.Bot,
    sql_message: dict,
    message: Optional[discord.Message],
    sql_starboard: dict,
    guild: discord.Guild,
    on_cooldown=False
) -> None:
    get_starboard_message = \
        """SELECT * FROM messages WHERE orig_message_id=$1 AND channel_id=$2"""
    delete_starboard_message = \
        """DELETE FROM messages WHERE orig_message_id=$1 and channel_id=$2"""
    get_author = \
        """SELECT * FROM users WHERE id=$1"""
    get_sbemojis = \
        """SELECT * FROM sbemojis WHERE starboard_id=$1"""

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
            sql_starboard_message = await conn.fetchrow(
                get_starboard_message, sql_message['id'], sql_starboard['id']
            )

    delete = False
    if sql_starboard_message is None:
        starboard_message = None
    else:
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

    recount = True
    if sql_starboard_message is not None and\
            sql_starboard_message['points'] is not None:
        if sql_message['is_frozen']:
            recount = False
        if on_cooldown:
            recount = False

    if recount:
        points, emojis = await functions.calculate_points(
            conn, sql_message, sql_starboard, bot,
            guild
        )
    else:
        points = sql_starboard_message['points']
        async with bot.db.lock:
            async with conn.transaction():
                emojis = await conn.fetch(get_sbemojis, sql_starboard['id'])

    deleted = message is None
    blacklisted = False if deleted else \
        await functions.is_message_blacklisted(
            bot, message, int(sql_starboard['id'])
        )
    on_starboard = starboard_message is not None

    link_deletes = sql_starboard['link_deletes']
    link_edits = sql_starboard['link_edits']
    bots_on_sb = sql_starboard['bots_on_sb']
    require_image = sql_starboard['require_image']
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

    if message is not None:
        if require_image and len(message.attachments) == 0:
            add = False
            remove = True

    if is_bot and not bots_on_sb:
        add = False
        if on_starboard:
            remove = True

    if blacklisted:
        add = False

    if forced is True:
        remove = False
        if not on_starboard:
            add = True

    await update_message(
        db, message, sql_message['channel_id'], starboard_message,
        starboard, points, forced, frozen, trashed, add, remove, link_edits,
        emojis, on_cooldown=on_cooldown
    )


async def update_message(
    db: Database,
    orig_message: Optional[discord.Message],
    orig_channel_id: int,
    sb_message: Optional[discord.Message],
    starboard: discord.TextChannel,
    points: int,
    forced: bool,
    frozen: bool,
    trashed: bool,
    add: bool,
    remove: bool,
    link_edits: bool,
    emojis: List[dict],
    on_cooldown: bool = False
) -> None:
    update = orig_message is not None

    check_message = \
        """SELECT * FROM messages WHERE orig_message_id=$1 AND channel_id=$2"""

    if trashed:
        if sb_message is not None:
            embed = discord.Embed(title='Trashed Message')
            embed.description = "This message was trashed by a moderator."
            if not on_cooldown:
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
        plain_text = (
            f"**{points} | <#{orig_channel_id}>{' | 🔒' if forced else ''}"
            f"{' | ❄️' if frozen else ''}**"
        )

        embed, attachments = await functions.get_embed_from_message(
            orig_message
        ) if orig_message is not None else (None, None)

        if add and embed is not None:
            async with db.lock:
                conn = db.conn
                async with conn.transaction():
                    _message = await conn.fetchrow(
                        check_message, orig_message.id,
                        starboard.id
                    )
            if _message is not None:
                return
            try:
                sb_message = await starboard.send(
                    plain_text, embed=embed, files=attachments
                )
            except discord.errors.Forbidden:
                pass
            else:
                async with db.lock:
                    conn = await db.connect()
                    async with conn.transaction():
                        _message = await conn.fetchrow(
                            check_message, orig_message.id,
                            starboard.id
                        )
                        if _message is None:
                            await db.q.create_message.fetch(
                                sb_message.id, sb_message.guild.id,
                                orig_message.author.id, orig_message.id,
                                starboard.id, False,
                                orig_message.channel.is_nsfw()
                            )
                if _message is not None:
                    print("### DUPLICATE DELETED ###")
                    await sb_message.delete()

        elif update and sb_message and link_edits:
            if not on_cooldown:
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


def setup(
    bot: commands.Bot
) -> None:
    bot.add_cog(Starboard(bot, bot.db))
