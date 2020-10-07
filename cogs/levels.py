import discord
import bot_config
import disputils
import functions
from discord.ext import commands
from events import leveling
from typing import Union


async def get_leaderboard(bot, guild):
    get_members = \
        """SELECT * FROM members WHERE xp != 0 AND guild_id=$1
        ORDER BY xp DESC"""

    conn = await bot.db.connect()
    async with bot.db.lock and conn.transaction():
        members = await conn.fetch(get_members, guild.id)
    await conn.close()
    ordered = []
    x = 0

    for m in members:
        mobject = discord.utils.get(guild.members, id=int(m['user_id']))
        print(type(mobject))
        if mobject is None or mobject.bot:
            print("Nope")
            continue
        x += 1
        username = str(mobject)
        user_id = mobject.id
        ordered.append({
            'name': username, 'user_id': user_id,
            'index': x, 'd': m
        })

    return ordered


async def get_rank(bot, user_id: int, guild):
    lb = await get_leaderboard(bot, guild)
    rank = None
    for i, dict in enumerate(lb):
        if dict['user_id'] == user_id:
            rank = i
            break
    return rank


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
            await functions.check_or_create_existence(
                self.bot.db, conn, self.bot, guild_id=ctx.guild.id, user=user,
                do_member=True
            )
            sql_member = await conn.fetchrow(get_member, user.id, ctx.guild.id)
        await conn.close()
        given = sql_member['given']
        received = sql_member['received']
        xp = sql_member['xp']
        lvl = sql_member['lvl']
        needed_xp = await leveling.next_level_xp(lvl)

        rank = await get_rank(self.bot, user.id, ctx.guild)
        rank = rank + 1 if rank is not None else rank

        embed = discord.Embed(
            title=str(user),
            description=f"Rank: **#{rank}**\nLevel: **{lvl}**\n"
            f"XP: **{xp} / {needed_xp}**",
            color=bot_config.COLOR
        )
        embed.set_thumbnail(url=user.avatar_url)
        embed.set_footer(
            text=f"Total Received: {received}\
            \nTotal Given: {given}"
        )

        await ctx.send(embed=embed)

    @commands.command(
        name='leaderboard', aliases=['lb', 'levels'],
        description='View users in order of their XP',
        brief='View leaderboard'
    )
    @commands.guild_only()
    async def show_leaderboard(self, ctx):
        ordered = await get_leaderboard(self.bot, ctx.guild)

        stringed = [
            f"#{m['index']}. __**{m['name']}**__:\n"
            f"Level {m['d']['lvl']} | "
            f"XP {m['d']['xp']}\n\n"
            for m in ordered
        ]
        size = 5
        grouped = [stringed[i:i+size] for i in range(0, len(stringed), size)]

        embeds = []
        for group in grouped:
            string = ""
            embed = discord.Embed(
                title="Leaderboard",
                color=bot_config.COLOR
            )
            embed.set_thumbnail(
                url="https://i.ibb.co/CQvbvDq/trophy-1f3c6.png"
            )
            for m in group:
                string += m
            embed.description = string
            embed.set_footer(icon_url=ctx.guild.icon_url, text=ctx.guild.name)
            embeds.append(embed)

        if len(embeds) == 0:
            await ctx.send("There isn't anyone on the leaderboard yet.")
            return

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
