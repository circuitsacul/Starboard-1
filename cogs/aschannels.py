# aschannels stand for auto-star channels
import discord
import bot_config
import settings
from discord.ext import commands
from typing import Union


class AutoStarChannels(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(
        name='aschannels', aliases=['asc', 'as', 'a'],
        description="Manage AutoStar Channels",
        brief="Manage AutoStar Channels", invoke_without_command=True
    )
    @commands.guild_only()
    async def aschannels(self, ctx, aschannel: discord.TextChannel = None):
        get_aschannels = \
            """SELECT * FROM aschannels WHERE guild_id=$1"""

        async with self.bot.db.lock:
            conn = self.bot.db.conn
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
            if channel is None:
                message += f"Deleted Channel {asc['id']}\n"
            else:
                message += f"<#{asc['id']}>\n"

        embed = discord.Embed(
            title="AutoStar Channels",
            description=message,
            color=bot_config.COLOR
        )

        await ctx.send(embed=embed)

    @aschannels.command(
        name='add', aliases=['a'],
        description='Sets a channel as an AutoStarChannel',
        breif='Add an AutoStarChannel'
    )
    @commands.has_permissions(manage_channels=True)
    @commands.guild_only()
    async def add_aschannel(self, ctx, channel: discord.TextChannel):
        await settings.add_aschannel(self.bot, channel)
        await ctx.send(
            f"Created AutoStarChannel {channel.mention}"
        )

    @aschannels.command(
        name='remove', aliases=['r', 'delete', 'del', 'd'],
        description="Remove an AutoStarChannel",
        brief="Remove an AutoStarChannel"
    )
    @commands.has_permissions(manage_channels=True)
    @commands.guild_only()
    async def remove_aschannel(
        self, ctx, channel: Union[discord.TextChannel, int]
    ):
        channel_id = channel.id if isinstance(channel, discord.TextChannel)\
            else channel
        await settings.remove_aschannel(self.bot, channel_id, ctx.guild.id)
        await ctx.send(
            f"Removed AutoStar Channel {channel}"
        )
