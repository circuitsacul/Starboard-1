from math import sqrt
from typing import List, Optional, Union

import discord
from discord import utils
from discord.ext import commands

import bot_config
import cooldowns
import functions
from database.database import Database
from paginators import disputils

give_cooldown = cooldowns.CooldownMapping.from_cooldown(
    3, 60
)
recv_cooldown = cooldowns.CooldownMapping.from_cooldown(
    3, 60
)


async def next_level_xp(
    current_level: int
) -> int:
    current_level += 1
    return int(current_level**2)


async def current_level(
    xp: int
) -> int:
    return int(sqrt(xp))


async def handle_reaction(
    bot: commands.Bot,
    reacter_id: int,
    receiver: Union[discord.Member, discord.User],
    guild: discord.Guild,
    _emoji: discord.PartialEmoji,
    is_add: bool
) -> None:
    guild_id = guild.id
    receiver_id = receiver.id
    if reacter_id == receiver_id:
        return
    emoji = _emoji.id if _emoji.id is not None else _emoji.name
    is_sbemoji = await functions.is_starboard_emoji(bot.db, guild_id, emoji)
    if not is_sbemoji:
        print(emoji)
        return

    cooldown_over = True
    if is_add:
        b = give_cooldown.get_bucket(reacter_id)
    else:
        b = recv_cooldown.get_bucket(reacter_id)
    retry_after = b.update_rate_limit()
    if retry_after:
        cooldown_over = False

    get_member = \
        """SELECT * FROM members WHERE user_id=$1 AND guild_id=$2"""
    # get_user = \
    #    """SELECT * FROM users WHERE id=$1"""
    set_points = \
        """UPDATE members
        SET {}=$1
        WHERE user_id=$2 AND guild_id=$3"""
    set_xp_level = \
        """UPDATE members
        SET xp=$1,
        lvl=$2
        WHERE user_id=$3 AND guild_id=$4"""

    points = 1 if is_add is True else -1

    # leveled_up = False

    async with bot.db.lock:
        conn = await bot.db.connect()
        async with conn.transaction():
            sql_reacter = await conn.fetchrow(get_member, reacter_id, guild_id)
            given = sql_reacter['given']+points
            given = 0 if given < 0 else given
            await conn.execute(
                set_points.format('given'), given, reacter_id, guild_id
            )

            sql_receiver = await conn.fetchrow(
                get_member, receiver_id, guild_id
            )
            received = sql_receiver['received']+points
            received = 0 if received < 0 else received
            await conn.execute(
                set_points.format('received'), received, receiver_id, guild_id
            )

            # sql_receiver_user = await conn.fetchrow(get_user, receiver_id)
            # send_lvl_msgs = sql_receiver_user['lvl_up_msgs']

            current_lvl = sql_receiver['lvl']
            current_xp = sql_receiver['xp']
            needed_xp = await next_level_xp(current_lvl)

            new_xp = current_xp + points
            new_xp = 0 if new_xp < 0 else new_xp
            new_lvl = current_lvl + 1 if new_xp >= needed_xp else current_lvl
            # leveled_up = new_lvl > current_lvl if cooldown_over else False

            if cooldown_over:
                await conn.execute(
                    set_xp_level, new_xp, new_lvl,
                    sql_receiver['user_id'], guild_id
                )

    # if leveled_up and send_lvl_msgs:
    #    embed = discord.Embed(
    #        title="Level Up!",
    #        description=f"You've reached **{new_xp} XP** "
    #        f"and are now **level {new_lvl}**!",
    #        color=bot_config.COLOR
    #    )
    #    embed.set_thumbnail(url="https://i.ibb.co/bvYZ8V8/dizzy-1f4ab.png")
    #    embed.set_author(name=guild.name, icon_url=guild.icon_url)
    #    embed.set_footer(
    #        text="Tip: Disable these messages by running"
    #        " sb!profile lum false"
    #    )
    #    embed.timestamp = datetime.datetime.now()
    #    try:
    #        await receiver.send(
    #            embed=embed
    #        )
    #        pass
    #    except (discord.errors.HTTPException, AttributeError):
    #        pass


async def get_leaderboard(
    bot: commands.Bot,
    guild: discord.Guild
) -> List[dict]:
    get_members = \
        """SELECT * FROM members WHERE xp != 0 AND guild_id=$1
        ORDER BY xp DESC"""

    async with bot.db.lock:
        conn = await bot.db.connect()
        async with conn.transaction():
            members = await conn.fetch(get_members, guild.id)

    ordered = []
    x = 0

    member_objects = await functions.get_members(
        [int(m['user_id']) for m in members],
        guild
    )

    for m in members:
        mobject = utils.get(member_objects, id=m['user_id'])
        if mobject is None or mobject.bot:
            continue
        x += 1
        username = str(mobject)
        user_id = mobject.id
        ordered.append({
            'name': username, 'user_id': user_id,
            'index': x, 'd': m
        })

    return ordered


async def get_rank(
    bot: commands.Bot,
    user_id: int,
    guild: discord.Guild
) -> Optional[int]:
    lb = await get_leaderboard(bot, guild)
    rank = None
    for i, dict in enumerate(lb):
        if dict['user_id'] == user_id:
            rank = i
            break
    return rank


class Levels(commands.Cog):
    """View your rank and your servers leaderboard"""
    def __init__(
        self,
        bot: commands.Bot,
        db: Database
    ) -> None:
        self.bot = bot
        self.db = db

    @commands.command(
        name='setxp', aliases=['setlvl'],
        brief="Set the XP of a user",
        description="Set the XP of a user; sb!setxp (user) (xp)"
    )
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def set_member_xp(
        self,
        ctx: commands.Context,
        _user: Union[discord.Member, int],
        xp: int
    ) -> None:
        if isinstance(_user, discord.Member):
            _user = _user.id
        user = await functions.get_members([_user], ctx.guild)
        username = user[0].name
        user = user[0].id
        get_member = \
            """SELECT * FROM members WHERE user_id=$1 and guild_id=$2"""
        update_member = \
            """UPDATE members
            SET xp=$1,
            lvl=$2
            WHERE id=$3"""

        await functions.check_or_create_existence(
            self.bot,
            guild_id=ctx.guild.id, user=user,
            do_member=True, user_is_id=True
        )

        conn = self.bot.db.conn
        async with self.bot.db.lock:
            async with conn.transaction():
                sql_member = await conn.fetchrow(
                    get_member, user, ctx.guild.id
                )

        if sql_member is None:
            await ctx.send("Couldn't find that user.")
            return

        level = await current_level(xp)

        async with self.bot.db.lock:
            async with conn.transaction():
                await conn.execute(
                    update_member, xp, level,
                    sql_member['id']
                )

        await ctx.send(
            f"Set **{username}**'s XP to {xp} and level to {level}."
            f" (It was {sql_member['xp']} XP and "
            f"level {sql_member['lvl']})"
        )

    @commands.command(
        name='givexp', aliases=['givelvl'],
        brief="Give a user XP",
        description="Give a user XP; sb!givexp (user) (xp)"
    )
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def give_member_xp(
        self,
        ctx: commands.Context,
        _user: Union[discord.Member, int],
        xp: int
    ) -> None:
        if isinstance(_user, discord.Member):
            _user = _user.id
        user = await functions.get_members([_user], ctx.guild)
        username = user[0].name
        user = user[0].id
        get_member = \
            """SELECT * FROM members WHERE user_id=$1 and guild_id=$2"""
        update_member = \
            """UPDATE members
            SET xp=$1,
            lvl=$2
            WHERE id=$3"""

        await functions.check_or_create_existence(
            self.bot,
            guild_id=ctx.guild.id, user=user,
            do_member=True, user_is_id=True
        )

        conn = self.bot.db.conn
        async with self.bot.db.lock:
            async with conn.transaction():
                sql_member = await conn.fetchrow(
                    get_member, user, ctx.guild.id
                )

        if sql_member is None:
            await ctx.send("Couldn't find that user.")
            return

        xp = int(sql_member['xp']) + xp

        level = await current_level(xp)

        async with self.bot.db.lock:
            async with conn.transaction():
                await conn.execute(
                    update_member, xp, level,
                    sql_member['id']
                )

        await ctx.send(
            f"Gave **{username}** XP, which made their XP {xp} "
            f"and level {level}."
            f" (They had {sql_member['xp']} XP and were at "
            f"level {sql_member['lvl']})"
        )

    @commands.command(
        name='rank',
        brief='View rank card',
        description='View rank card'
    )
    @commands.guild_only()
    async def show_rank_card(
        self,
        ctx: commands.Context,
        user: Union[discord.Member, None]
    ) -> None:
        user = user if user else ctx.message.author
        get_member = \
            """SELECT * FROM members WHERE user_id=$1 and guild_id=$2"""

        await functions.check_or_create_existence(
            self.bot, guild_id=ctx.guild.id,
            user=user, do_member=True
        )

        async with self.db.lock:
            conn = await self.db.connect()
            async with conn.transaction():
                sql_member = await conn.fetchrow(
                    get_member, user.id, ctx.guild.id
                )

        given = sql_member['given']
        received = sql_member['received']
        xp = sql_member['xp']
        lvl = sql_member['lvl']
        needed_xp = await next_level_xp(lvl)

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
    async def show_leaderboard(
        self,
        ctx: commands.Context
    ) -> None:
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
        name='resetuser', brief='Resets XP and Levels for a user',
        description='Resets XP and Levels for a user'
    )
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def reset_levels(
        self,
        ctx: commands.Context,
        user: discord.Member
    ) -> None:
        set_points = \
            """UPDATE members
            SET xp=0,
            lvl=0
            WHERE user_id=$1 AND guild_id=$2"""

        async with self.db.lock:
            conn = await self.db.connect()
            async with conn.transaction():
                await conn.execute(set_points, user.id, ctx.guild.id)

        await ctx.send(f"Reset {user.name}'s levels and xp.")

    @commands.command(
        name='resetlb',
        brief="Resets the entire leaderboard"
    )
    @commands.has_guild_permissions(manage_guild=True)
    @commands.guild_only()
    async def reset_entire_leaderboard(
        self,
        ctx: commands.Context
    ) -> None:
        update_members = \
            """UPDATE MEMBERS
            SET xp=0,
            lvl=0
            WHERE guild_id=$1"""
        c = disputils.Confirmation(
            self.bot, color=bot_config.COLOR
        )
        await c.confirm(
            "Are you sure? This is irreversable!",
            ctx.message.author, ctx.channel
        )
        if c.confirmed:
            await c.quit("Resetting the leaderboard, please wait...")
            conn = self.bot.db.conn
            async with ctx.typing():
                async with self.bot.db.lock:
                    async with conn.transaction():
                        await conn.execute(update_members, ctx.guild.id)
            await ctx.send("Finished!")
        else:
            await c.quit("Leaderboard reset cancelled.")


def setup(
    bot: commands.Bot
) -> None:
    bot.add_cog(Levels(bot, bot.db))
