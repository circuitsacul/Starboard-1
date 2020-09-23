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
            """SELECT * FROM members WHERE user_id=? and guild_id=?"""

        conn = await self.db.connect()
        c = await conn.cursor()
        async with self.db.lock:
            await c.execute(get_member, [user.id, ctx.guild.id])
            sql_member = await c.fetchone()
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
            WHERE user_id=? AND guild_id=?"""

        conn = await self.db.connect()
        c = await conn.cursor()
        async with self.db.lock:
            await c.execute(set_points, [user.id, ctx.guild.id])
            await conn.commit()
            await conn.close()
        await ctx.send(f"Reset {user.name}'s levels and xp.")