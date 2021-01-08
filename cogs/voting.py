# Receiving the vote webhook is done in webhook.py
# This is for handling that event, handling the
# vote role, and for posting when someone votes
import datetime

import discord
from discord.ext import commands, tasks

import bot_config
import functions


def now() -> datetime.datetime:
    ct = datetime.datetime.now()
    return ct.timestamp()


def expires() -> datetime.datetime:
    e = datetime.datetime.now() + datetime.timedelta(days=1)
    return e.timestamp()


async def handle_vote_role(
    bot: commands.Bot,
    user_id: int,
    add: bool
) -> None:
    support_guild = bot.get_guild(bot_config.SUPPORT_SERVER_ID)
    if support_guild is None:
        return

    users = await functions.get_members([user_id], support_guild)
    if len(users) == 0:
        return

    user = users[0]

    role = support_guild.get_role(bot_config.VOTE_ROLE_ID)
    if role is None:
        return

    try:
        if add:
            await user.add_roles(role)
        else:
            await user.remove_roles(role)
    except Exception:
        pass


async def add_vote(
    bot: commands.Bot,
    user_id: int
) -> None:
    e = expires()
    conn = bot.db.conn

    check_user = \
        """SELECT * FROM users WHERE id=$1"""

    async with bot.db.lock:
        async with conn.transaction():
            sql_user = await conn.fetchrow(
                check_user, user_id
            )
            if sql_user is None:
                await bot.db.q.create_user.fetch(
                    user_id, False
                )
            await bot.db.q.create_vote.fetch(
                user_id, e
            )


class Voting(commands.Cog):
    """Voting related commands"""
    def __init__(
        self,
        bot: commands.Bot
    ) -> None:
        self.bot = bot
        self.get_expired_votes.start()

    @commands.Cog.listener()
    async def on_top_vote(
        self,
        user_id: int
    ) -> None:
        """
        "top_vote" is dispatched in webhook.py
        """
        await add_vote(self.bot, user_id)

        await handle_vote_role(
            self.bot, user_id, True
        )

        vote_channel_id = bot_config.VOTE_LOG_ID
        vote_channel = self.bot.get_channel(vote_channel_id)
        if vote_channel is None:
            return

        message = (
            f"<@{user_id}> voted for Starboard!"
            "\nThey have received the **Voter** role"
            " for 1 day.\n"
        )

        embed = discord.Embed(
            title='New Vote!',
            description=message,
            color=bot_config.COLOR
        )

        await vote_channel.send(embed=embed)

    @tasks.loop(minutes=10)
    async def get_expired_votes(self) -> None:
        get_votes = \
            """SELECT * FROM votes WHERE expires<$1 AND expired=False"""
        get_user_votes = \
            """SELECT * FROM votes WHERE expired=False AND user_id=$1"""
        expire_vote = \
            """UPDATE votes
            SET expired=True
            WHERE id=$1"""
        ct = now()
        conn = self.bot.db.conn

        to_remove = []

        async with self.bot.db.lock:
            async with conn.transaction():
                expired_votes = await conn.fetch(
                    get_votes, ct
                )
                for e in expired_votes:
                    await conn.execute(
                        expire_vote, e['id']
                    )
                    non_expired = await conn.fetch(
                        get_user_votes, e['user_id']
                    )
                    if len(non_expired) == 0:
                        to_remove.append(e['user_id'])

        for uid in to_remove:
            await handle_vote_role(
                self.bot, uid, False
            )

    @commands.command(
        name='votes', aliases=['v'],
        description='View the total number of times you have voted',
        brief='View total votes'
    )
    @commands.cooldown(1, 2)
    async def view_user_votes(
        self,
        ctx: commands.Context,
        user: discord.User = None
    ) -> None:
        get_votes = \
            """SELECT * FROM votes WHERE user_id=$1"""

        user = user or ctx.message.author
        conn = self.bot.db.conn

        async with self.bot.db.lock:
            async with conn.transaction():
                votes = await conn.fetch(get_votes, user.id)

        t = len(votes)
        is_same = user.id == ctx.message.author.id

        embed = discord.Embed(
            title=f"{'You have' if is_same else str(user) + ' has'} "
            f"voted **{t}** time"
            f"{'' if t == 1 else 's'}{'!' if t != 0 else ' :('}",
            color=bot_config.COLOR
        )
        await ctx.send(embed=embed)


def setup(
    bot: commands.Bot
) -> None:
    bot.add_cog(Voting(bot))
