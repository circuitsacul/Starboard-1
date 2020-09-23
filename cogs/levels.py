import discord
from discord.ext import commands
from events import leveling


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
    async def show_rank_card(self, ctx, user: discord.Member):
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
        await ctx.send(f"Given: {given}\nReceived: {received}\nLevel: {lvl} ({xp}/{needed_xp})")

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