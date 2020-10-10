import discord
import functions
import bot_config
import converters
from discord.ext import commands
from typing import Set, Union
from .wizard import SetupWizard
from functions import change_starboard_settings


async def pretty_emoji_string(emojis, guild):
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
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    @commands.command(
        name='starboards', aliases=['boards', 'b'],
        description='List all the starboars for this server',
        brief='List starboards'
    )
    @commands.guild_only()
    async def list_starboards(self, ctx):
        get_starboards = """SELECT * FROM starboards WHERE guild_id=$1"""
        get_emojis = """SELECT * FROM sbemojis WHERE starboard_id=$1"""

        p = await functions.get_one_prefix(self.bot, ctx.guild.id)

        async with self.db.lock:
            conn = await self.db.connect()
            async with conn.transaction():
                _ = await functions.check_or_create_existence(
                    self.db, conn, self.bot, guild_id=ctx.guild.id,
                    user=ctx.message.author, do_member=True
                )
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
                        title=title, description=msg, color=bot_config.COLOR
                    )
                    embed.set_footer(
                        text=f'Do {p}settings <channel>'
                        '\nto view starboard settings.'
                    )
            #await conn.close()

        if message is not None:
            await ctx.send(message)
        else:
            await ctx.send(embed=embed)

    @commands.command(
        name='settings', aliases=['s'],
        description='View all of the settings for a specific starboards',
        brief='View settings for startboard'
    )
    @commands.guild_only()
    async def get_starboard_settings(
        self, ctx, starboard: discord.TextChannel
    ):
        get_starboard = """SELECT * FROM starboards WHERE id=$1"""
        get_emojis = """SELECT * FROM sbemojis WHERE starboard_id=$1"""

        async with self.db.lock:
            conn = await self.db.connect()
            async with conn.transaction():
                await functions.check_or_create_existence(
                    self.db, conn, self.bot, guild_id=ctx.guild.id,
                    user=ctx.message.author, do_member=True
                )
                sql_starboard = await conn.fetchrow(get_starboard, starboard.id)
                if sql_starboard is None:
                    await ctx.send("That is not a starboard!")
                else:
                    starboard = self.bot.get_channel(starboard.id)
                    emojis = await conn.fetch(get_emojis, starboard.id)
                    pretty_emojis = await pretty_emoji_string(emojis, ctx.guild)
                    title = f"Settings for {starboard.name}:"
                    string = f"**emojis: {pretty_emojis}**"
                    string += f"\n**requiredStars: {sql_starboard['required']}**"
                    string += f"\n**requiredToLose: {sql_starboard['rtl']}**"
                    string += f"\n**selfStar: {bool(sql_starboard['self_star'])}**"
                    string += "\n**linkEdits: "\
                        f"{bool(sql_starboard['link_edits'])}**"
                    string += "\n**linkDeletes: "\
                        f"{bool(sql_starboard['link_deletes'])}**"
                    string += "\n**botsOnStarboard: "\
                        f"{bool(sql_starboard['bots_on_sb'])}**"
                    string += f"\n**locked: {bool(sql_starboard['locked'])}**"

                    embed = discord.Embed(
                        title=title, description=string, color=bot_config.COLOR
                    )
                    await ctx.send(embed=embed)
            #await conn.close()

    @commands.command(
        name='add', aliases=['a'],
        description='Add a starboard',
        brief='Add a starboard'
    )
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True)
    async def add_starboard(self, ctx, starboard: discord.TextChannel):
        perms = starboard.permissions_for(ctx.guild.me)
        if not perms.send_messages:
            await ctx.send("I can't send messages there.")
            return
        elif not perms.add_reactions:
            await ctx.send(
                "I can't add reactions to messages there. "
                "If you want me to automatically add reactions, "
                "please enable this setting."
            )

        get_starboards = \
            """SELECT * FROM starboards WHERE guild_id=$1"""

        limit = await functions.get_limit(self.db, 'starboards', ctx.guild)

        async with self.db.lock:
            conn = await self.db.connect()
            async with conn.transaction():
                await functions.check_or_create_existence(
                    self.db, conn, self.bot, guild_id=ctx.guild.id,
                    user=ctx.message.author, do_member=True
                )
                rows = await conn.fetch(get_starboards, ctx.guild.id)
                num_starboards = len(rows)

                if num_starboards >= limit:
                    await ctx.send(
                        "You have reached your limit for starboards. "
                        "Please upgrade by becoming a patron."
                    )
                else:
                    exists = await functions.check_or_create_existence(
                        self.db, conn, self.bot, guild_id=ctx.guild.id,
                        starboard_id=starboard.id
                    )
                    if exists['se']:
                        await ctx.send("That is already a starboard!")
                    else:
                        await ctx.send(f"Added starboard {starboard.mention}")

            #await conn.close()

    @commands.command(
        name='remove', aliases=['r'],
        description='Remove a starboard',
        brief='Remove a starboard'
    )
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True, manage_messages=True)
    async def remove_starboard(
        self, ctx, starboard: Union[discord.TextChannel, int]
    ):
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

        async with self.db.lock:
            conn = await self.db.connect()
            exists = True
            async with conn.transaction():
                await functions.check_or_create_existence(
                    self.db, conn, self.bot, guild_id=ctx.guild.id,
                    user=ctx.message.author, do_member=True
                )
                existed = await functions.check_or_create_existence(
                    self.db, conn, self.bot, starboard_id=starboard_id,
                    guild_id=ctx.guild.id, create_new=False
                )
                if existed['se'] is False:
                    await ctx.send("That is not a starboard!")
                    exists = False
                else:
                    remove_starboard = """DELETE FROM starboards WHERE id=$1"""
                    await conn.execute(remove_starboard, starboard_id)
            #await conn.close()
        if exists:
            await ctx.send("Removed starboard")

    @commands.command(
        name='addEmoji', aliases=['ae'],
        description='Add emoji to a starboard',
        brief='Add emoji to starboard'
    )
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True, manage_messages=True)
    async def add_starboard_emoji(
        self, ctx, starboard: discord.TextChannel,
        emoji: Union[discord.Emoji, str]
    ):
        check_sbemoji = \
            """SELECT * FROM sbemojis WHERE name=$1 AND starboard_id=$2"""
        get_all_sbemoji = \
            """SELECT * FROM sbemojis WHERE starboard_id=$1"""
        if not isinstance(emoji, discord.Emoji):
            if not functions.is_emoji(emoji):
                await ctx.send(
                    "I don't recognize that emoji. "
                    "Please make sure it is correct, and if it's a "
                    "custom emoji it has to be in this server."
                )
                return
        emoji_name = str(emoji.id) if isinstance(
            emoji, discord.Emoji) else str(emoji)
        emoji_id = emoji.id if isinstance(
            emoji, discord.Emoji) else None

        limit = await functions.get_limit(self.db, 'emojis', ctx.guild)

        async with self.db.lock:
            conn = await self.db.connect()
            added = False
            async with conn.transaction():
                await functions.check_or_create_existence(
                    self.db, conn, self.bot, guild_id=ctx.guild.id,
                    user=ctx.message.author, do_member=True
                )
                exists = await functions.check_or_create_existence(
                    self.db, conn, self.bot, starboard_id=starboard.id,
                    guild_id=ctx.guild.id, create_new=False
                )
                if not exists['se']:
                    await ctx.send("That is not a starboard!")
                else:
                    rows = await conn.fetch(
                        check_sbemoji, emoji_name, starboard.id
                    )
                    exists = len(rows) > 0
                    if exists:
                        await ctx.send(
                            "That emoji is already on that starboard!"
                        )
                    else:
                        rows = await conn.fetch(get_all_sbemoji, starboard.id)
                        if len(rows) >= limit:
                            await ctx.send(
                                "You have reached your limit for emojis on "
                                "this starboard. Please upgrade by becoming "
                                "a patron."
                            )
                        else:
                            await self.db.q.create_sbemoji.fetch(
                                emoji_id,
                                starboard.id, emoji_name, False
                            )
                            added = True

            #await conn.close()
        if added:
            await ctx.send(f"Added {emoji} to {starboard.mention}")

    @commands.command(
        name='removeEmoji', aliases=['re'],
        description='Removes a starboard emoji',
        brief='Removes a starboard emoji'
    )
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True, manage_messages=True)
    async def remove_starboard_emoji(
        self, ctx, starboard: discord.TextChannel,
        emoji: Union[discord.Emoji, str]
    ):
        get_sbemoji = \
            """SELECT * FROM sbemojis WHERE name=$1 AND starboard_id=$2"""
        del_sbemoji = \
            """DELETE FROM sbemojis WHERE id=$1"""
        emoji_name = emoji.id if isinstance(emoji, discord.Emoji) else emoji
        # emoji_id = emoji.id if isinstance(emoji, discord.Emoji) else None

        async with self.db.lock:
            conn = await self.db.connect()
            removed = False
            async with conn.transaction():
                await functions.check_or_create_existence(
                    self.db, conn, self.bot, guild_id=ctx.guild.id,
                    user=ctx.message.author, do_member=True
                )
                exists = await functions.check_or_create_existence(
                    self.db, conn, self.bot, starboard_id=starboard.id,
                    guild_id=ctx.guild.id, create_new=False
                )
                if not exists['se']:
                    await ctx.send("That is not a starboard!")
                else:
                    rows = await conn.fetch(get_sbemoji, emoji_name, starboard.id)
                    if len(rows) == 0:
                        await ctx.send("That is not a starboard emoji!")
                    else:
                        sbemoji_id = rows[0]['id']
                        await conn.execute(del_sbemoji, sbemoji_id)
                        removed = True
            #await conn.close()
        if removed:
            await ctx.send(f"Removed {emoji} from {starboard.mention}")

    @commands.command(
        name='requiredStars', aliases=['rs', 'required'],
        description='Set\'s how many stars are needed before a message '
        'appears on the starboard',
        brief='Set\'s required stars'
    )
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True, manage_messages=True)
    async def set_required_stars(
        self, ctx, starboard: discord.TextChannel, value: int
    ):
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

    @commands.command(
        name='requiredToLose', aliases=['rtl'],
        description='Set\'s how few stars a message needs before the '
        'messages is removed from the starboard',
        brief='Sets requiredToLose'
    )
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True, manage_messages=True)
    async def set_required_to_lose(
        self, ctx, starboard: discord.TextChannel, value: int
    ):
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

    @commands.command(
        name='selfStar', aliases=['ss'],
        description='Set wether or not to allow a user to star '
        'their own message for starboard',
        brief='Set selfStar for starboard'
    )
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True)
    async def starboard_self_star(
        self, ctx, starboard: discord.TextChannel, value: bool
    ):
        status = await change_starboard_settings(
            self.db, starboard.id, self_star=value
        )
        if status is None:
            await ctx.send("That is not a starboard!")
        elif status is False:
            await ctx.send("Invalid Value")
        else:
            await ctx.send(f"Set selfStar to {value} for {starboard.mention}")

    @commands.command(
        name='linkEdits', aliases=['le'],
        description='Sets wether or not the bot should edit the starboard '
        'message if the user edits it',
        brief='Sets linkEdits for a starboard'
    )
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True, manage_messages=True)
    async def set_link_edits(
        self, ctx, starboard: discord.TextChannel, value: bool
    ):
        status = await change_starboard_settings(
            self.db, starboard.id, link_edits=value
        )
        if status is None:
            await ctx.send("That is not a starboard!")
        elif status is False:
            await ctx.send("Invalid Setting")
        else:
            await ctx.send(f"Set linkEdits to {value} for {starboard.mention}")

    @commands.command(
        name='linkDeletes', aliases=['ld'],
        description='Sets wether or not the bot should delete the starboard '
        'message if the original is deleted',
        brief='Sets linkDeletes for a starboard'
    )
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True, manage_messages=True)
    async def set_link_deletes(
        self, ctx, starboard: discord.TextChannel, value: bool
    ):
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

    @commands.command(
        name='botsOnStarboard', aliases=['botsOnSb', 'bos'],
        description="Sets wether or not to allow bot messages "
        "to be put on the starboard",
        brief='Sets botsOnStarboards for a starboard'
    )
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True, manage_messages=True)
    async def set_bots_on_starboard(
        self, ctx, starboard: discord.TextChannel, value: bool
    ):
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

    @commands.command(
        name='setup', aliases=['configure', 'config'],
        description="A setup wizard to make things easier for you",
        brief='A setup wizard'
    )
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True, manage_messages=True)
    @commands.bot_has_permissions(
        manage_messages=True, manage_channels=True,
        embed_links=True
    )
    async def run_setup_wizard(self, ctx):
        async with self.bot.db.lock:
            conn = self.bot.db.conn
            async with conn.transaction():
                await functions.check_or_create_existence(
                    self.db, conn, self.bot, guild_id=ctx.guild.id,
                    user=ctx.message.author, do_member=True
                )

        wizard = SetupWizard(ctx, self.bot)
        can_run = True
        async with self.bot.wizzard_lock():
            if ctx.guild.id in self.bot.running_wizzards:
                can_run = False
            else:
                self.bot.running_wizzards.append(ctx.guild.id)

        try:
            if can_run:
                await wizard.run()
            else:
                await ctx.send(
                    "A setup wizard is already running for this server!"
                )
        except Exception as e:
            print(e)

        if can_run:
            async with self.bot.wizzard_lock():
                self.bot.running_wizzards.remove(ctx.guild.id)
