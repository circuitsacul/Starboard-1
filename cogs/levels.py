import discord, bot_config
from discord.ext import commands
from events import leveling
from typing import Union


class Levels(commands.Cog):
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    @commands.command(
        name='rank',
        brief='View rank card',
        description='View rank card'
    )
    @commands.guild_only()
    async def show_rank_card(self, ctx, user: Union[discord.Member, None]):
        user = user if user else ctx.message.author
        get_member = \
            """SELECT * FROM members WHERE user_id=$1 and guild_id=$2"""

        conn = await self.db.connect()
        async with self.db.lock and conn.transaction():
            sql_member = await conn.fetchrow(get_member, str(user.id), str(ctx.guild.id))
        await conn.close()
        given = sql_member['given']
        received = sql_member['received']
        xp = sql_member['xp']
        lvl = sql_member['lvl']
        needed_xp = await leveling.next_level_xp(lvl)

        embed = discord.Embed(
            title=str(user),
            description=f"Rank: **#01**\nLevel: **{lvl}**\nXP: **{xp} / {needed_xp}**",
            color=bot_config.COLOR
        )
        embed.set_thumbnail(url=user.avatar_url)
        embed.set_footer(text=f"Total Received: {received}\nTotal Given: {given}")

        await ctx.send(embed=embed)

    @commands.command(
        name='reset', brief='Resets XP and Levels for a user',
        description='Resets XP and Levels for a user'
    )
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def reset_levels(self, ctx, user: discord.Member):
        set_points = \
            """UPDATE members
            SET xp=0,
            lvl=0
            WHERE user_id=$1 AND guild_id=$2"""

        conn = await self.db.connect()
        async with self.db.lock and conn.transaction():
            await conn.execute(set_points, str(user.id), str(ctx.guild.id))
        await conn.close()
        await ctx.send(f"Reset {user.name}'s levels and xp.")