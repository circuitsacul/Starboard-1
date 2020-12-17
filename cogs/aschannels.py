# aschannels stand for auto-star channels
import discord
import bot_config
import settings
import functions
import datetime
from discord import utils
from discord.ext import commands
from typing import Union


async def converted_emojis(emojis, guild):
    all_emojis = []

    for emoji in emojis:
        emoji_name = emoji['name']
        try:
            emoji_id = int(emoji_name)
        except ValueError:
            emoji_id = None

        if emoji_id is not None:
            emoji_obj = utils.get(guild.emojis, id=emoji_id)
            if emoji_obj is not None:
                all_emojis.append(emoji_obj)
        else:
            all_emojis.append(emoji_name)

    return all_emojis


class AutoStarChannels(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cooldown = commands.CooldownMapping.from_cooldown(
            3, 10, commands.BucketType.channel
        )

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        if message.channel.id not in self.bot.db.as_cache:
            return

        bucket = self.cooldown.get_bucket(message)
        retry_after = bucket.update_rate_limit(
            message.created_at.replace(
                tzinfo=datetime.timezone.utc
            ).timestamp()
        )
        if retry_after:
            return
        get_emojis = \
            """SELECT * FROM asemojis WHERE aschannel_id=$1"""

        channel = message.channel
        guild = message.guild
        conn = self.bot.db.conn

        valid = True
        reason = None

        check_aschannel = \
            """SELECT * FROM aschannels WHERE ID=$1"""

        async with self.bot.db.lock:
            async with self.bot.db.conn.transaction():
                sasc = await self.bot.db.conn.fetchrow(
                    check_aschannel, channel.id
                )

        if sasc is None:
            return False

        if len(message.content) < sasc['min_chars']:
            valid = False
            reason = (
                f"messages must be at least {sasc['min_chars']} "
                "characters"
            )
        elif len(message.attachments) == 0 and sasc['require_image']:
            valid = False
            reason = "messages must have an image attached"

        if sasc['delete_invalid'] and not valid:
            try:
                await message.delete()
                await message.author.send(
                    f"Your message in {channel.mention} "
                    f"was deleted because {reason}.\n"
                    "I saved your message for you though, here it is:\n"
                    f"```\n{message.content}\n```"
                )
            except Exception:
                pass
            finally:
                return
        elif not valid:
            return True

        async with self.bot.db.lock:
            async with conn.transaction():
                s_emojis = await conn.fetch(
                    get_emojis, channel.id
                )

        asemojis = await converted_emojis(s_emojis, guild)

        for e in asemojis:
            try:
                await message.add_reaction(e)
            except Exception:
                pass

        return True

    @commands.group(
        name='aschannels', aliases=['asc', 'as', 'a'],
        description="Manage AutoStar Channels",
        invoke_without_command=True
    )
    @commands.guild_only()
    async def aschannels(self, ctx, aschannel: discord.TextChannel = None):
        """List and manage AutoStar Channels

        [aschannel]: An optional argument. If specified,
        it will list the configuration for that
        AutoStar Channel. Otherwise it lists all
        AutoStar Channels.
        """
        get_asemojis = \
            """SELECT * FROM asemojis WHERE aschannel_id=$1"""

        conn = self.bot.db.conn

        if aschannel is None:
            get_aschannels = \
                """SELECT * FROM aschannels WHERE guild_id=$1"""

            async with self.bot.db.lock:
                async with conn.transaction():
                    aschannels = await conn.fetch(
                        get_aschannels, ctx.guild.id
                    )

            if len(aschannels) == 0:
                await ctx.send("You don't have any AutoStarChannels.")
                return

            message = ""
            for asc in aschannels:
                channel = self.bot.get_channel(asc['id'])
                async with self.bot.db.lock:
                    async with conn.transaction():
                        s_emojis = await conn.fetch(
                            get_asemojis, asc['id']
                        )
                emoji_str = await functions.pretty_emoji_string(
                    s_emojis, ctx.guild
                )
                if channel is None:
                    message += f"Deleted Channel {asc['id']} {emoji_str}\n"
                else:
                    message += f"<#{asc['id']}> {emoji_str}\n"

            embed = discord.Embed(
                title="AutoStar Channels",
                description=message,
                color=bot_config.COLOR
            )

            await ctx.send(embed=embed)
        else:
            get_aschannel = \
                """SELECT * FROM aschannels WHERE id=$1"""

            async with self.bot.db.lock:
                conn = self.bot.db.conn
                async with conn.transaction():
                    sasc = await conn.fetchrow(
                        get_aschannel, aschannel.id
                    )
                    s_emojis = await conn.fetch(
                        get_asemojis, aschannel.id
                    )

            if sasc is None:
                await ctx.send("That is not an AutoStar Channel!")
                return

            emoji_str = await functions.pretty_emoji_string(
                s_emojis, ctx.guild
            )

            message = (
                f"**emojis:** {emoji_str}\n"
                f"**minChars:** {sasc['min_chars']}\n"
                f"**requireImage:** {sasc['require_image']}\n"
                f"**deleteInvalid:** {sasc['delete_invalid']}"
            )

            embed = discord.Embed(
                title=f"Settings for {aschannel.name}",
                description=message,
                color=bot_config.COLOR
            )

            await ctx.send(embed=embed)

    @aschannels.command(
        name='add', aliases=['a'],
        breif='Add an AutoStarChannel'
    )
    @commands.has_permissions(manage_channels=True)
    @commands.guild_only()
    async def add_aschannel(self, ctx, channel: discord.TextChannel):
        """Sets a channel as an AutoStar Channel

        <channel>: A required argument for which channel
        to set as an AutoStar Channel. Cannot be a starboard.
        """
        await settings.add_aschannel(self.bot, channel)
        await ctx.send(
            f"Created AutoStarChannel {channel.mention}"
        )

    @aschannels.command(
        name='remove', aliases=['r', 'delete', 'del', 'd'],
        brief="Remove an AutoStarChannel"
    )
    @commands.has_permissions(manage_channels=True)
    @commands.guild_only()
    async def remove_aschannel(
        self, ctx, channel: Union[discord.TextChannel, int]
    ):
        """Removes an AutoStar Channel

        <channel>: A required argument for which channel to remove
        """
        channel_id = channel.id if isinstance(channel, discord.TextChannel)\
            else channel
        await settings.remove_aschannel(self.bot, channel_id, ctx.guild.id)
        await ctx.send(
            f"Removed AutoStar Channel {channel}"
        )

    @aschannels.command(
        name='addEmoji', aliases=['ae'],
        brief='Add an emoji to the AutoStar Channel'
    )
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def add_asemoji(
        self, ctx, aschannel: discord.TextChannel,
        emoji: Union[discord.Emoji, str]
    ):
        """Adds an emoji to the list of AutoStar emojis for
        a specific AutoStar channel. These are the emojis
        that the bot will automatically react to messages
        with.

        <aschannel>: A required argument for which
        AutoStar Channel to add an emoji to.

        <emoji>: A required aregument for what emoji
        to add to the AutoStar Channel
        """
        if type(emoji) is str:
            if not functions.is_emoji(emoji):
                await ctx.send(
                    "I don't recoginize that emoji. If it"
                    " is a custom emoji, it must be in this server."
                )
                return
        emoji_name = emoji if type(emoji) is str else str(emoji.id)
        await settings.add_asemoji(
            self.bot, aschannel, emoji_name
        )
        await ctx.send(f"Added {emoji} to {aschannel.mention}")

    @aschannels.command(
        name='removeEmoji', aliases=['re'],
        brief='Remove autostar emoji'
    )
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def remove_asemoji(
        self, ctx, aschannel: discord.TextChannel,
        emoji: Union[discord.Emoji, str]
    ):
        """Removes an emoji from an AutoStar Channel,
        so that the bot no longer reacts to messages
        with it.

        <aschannel>: A required argument for which
        AutoStar Channel to remove the emoji from.

        <emoji>: A required argument for what
        emoji to remove from the AutoStar Channel.
        """
        emoji_name = emoji if type(emoji) is str else str(emoji.id)
        await settings.remove_asemoji(
            self.bot, aschannel, emoji_name
        )
        await ctx.send(f"Removed {emoji} from {aschannel.mention}")

    @aschannels.command(
        name='requireImage', aliases=['ri'],
        brief="Wether or not an image is required"
    )
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def set_require_image(
        self, ctx, aschannel: discord.TextChannel, value: bool
    ):
        """Sets whether or not messages sent in that
        AutoStar Channel are required to have an image.

        <aschannel>: A required argument for which
        AutoStar Channel to set the setting for.

        <value>: A reqruied argument for wether or not
        this setting is enabled (true or false).
        """
        await settings.change_aschannel_settings(
            self.bot.db, aschannel.id, require_image=value
        )
        await ctx.send(f"Set requireImage to {value} for {aschannel.mention}")

    @aschannels.command(
        name='minChars', aliases=['mc'],
        brief='Set the minimum characters for a message'
    )
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def set_min_chars(
        self, ctx, aschannel: discord.TextChannel, value: int
    ):
        """Sets the minimum character limit for
        messages sent in this AutoStar Channel.

        <aschannel>: A required argument for which
        AutoStar Channel to set this setting for.

        <value>: A required argument for the minimum
        number of characters required on messages.
        """
        await settings.change_aschannel_settings(
            self.bot.db, aschannel.id, min_chars=value
        )
        await ctx.send(f"Set minChars to {value} for {aschannel.mention}")

    @aschannels.command(
        name='deleteInvalid', aliases=['di'],
        brief='Wether or not to delete invalid messages'
    )
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def set_delete_invalid(
        self, ctx, aschannel: discord.TextChannel, value: bool
    ):
        """Sets whether or not messages that don't meet
        the requirements you have set should be deleted,
        or just ignored.

        If this is disabled, messages that don't meet the
        requirements will not be starred, but if it is
        enabled messages that don't meet the requirements
        will be deleted.

        <aschannel>: A required argument for which
        AutoStar Channel to set this setting for.

        <value>: A required argument for wether or not
        this setting is enabled (true or false).
        """
        await settings.change_aschannel_settings(
            self.bot.db, aschannel.id, delete_invalid=value
        )
        await ctx.send(f"Set deleteInvalid to {value} for {aschannel.mention}")


def setup(bot):
    bot.add_cog(AutoStarChannels(bot))
