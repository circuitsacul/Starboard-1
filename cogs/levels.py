import discord, bot_config, disputils
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
            sql_member = await conn.fetchrow(get_member, user.id, ctx.guild.id)
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
        name='leaderboard', aliases=['lb', 'levels'],
        description='View users in order of their XP',
        brief='View leaderboard'
    )
    @commands.guild_only()
    async def show_leaderboard(self, ctx):
        get_members = \
            """SELECT * FROM members WHERE xp != 0 AND guild_id=$1"""

        conn = await self.bot.db.connect()
        async with self.bot.db.lock and conn.transaction():
            members = await conn.fetch(get_members, ctx.guild.id)
        await conn.close()
        _ordered = sorted(members, key=lambda m: m['xp'], reverse=True)
        ordered = []
        for m in _ordered:
            mobject = discord.utils.get(ctx.guild.members, id=m['user_id'])
            if mobject is None or mobject.bot:
                continue
            else:
                username = mobject.name
            ordered.append({'name': username, 'd': m})

        stringed = [
            f"__**{m['name']}**__: **Level {m['d']['lvl']} | XP {m['d']['xp']}**\n"
            for m in ordered
        ]
        size = 10
        grouped = [stringed[i:i+size] for i in range(0, len(stringed), size)]

        embeds = []
        for group in grouped:
            string = ""
            embed = discord.Embed(title=f"Leaderboard for {ctx.guild.name}", color=bot_config.COLOR)
            embed.set_thumbnail(url="https://i.ibb.co/CQvbvDq/trophy-1f3c6.png")
            for m in group:
                string += m
            embed.description = string
            embeds.append(embed)

        paginator = disputils.BotEmbedPaginator(ctx, embeds)
        await paginator.run()

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
            await conn.execute(set_points, user.id, ctx.guild.id)
        await conn.close()
        await ctx.send(f"Reset {user.name}'s levels and xp.")