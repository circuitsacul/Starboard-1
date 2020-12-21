from typing import Optional

from discord.ext import commands


class QuickActions(commands.Cog):
    """Allows trashing, forcing, and
    freezing with reactions"""

    def __init__(
        self,
        bot: commands.Bot
    ) -> None:
        self.bot = bot

    @commands.command(
        name='quickActions', aliases=['qa'],
        brief="Enable/disable quickactions"
    )
    @commands.has_guild_permissions(manage_guild=True)
    @commands.guild_only()
    async def quick_actions(
        self,
        ctx: commands.Context,
        enabled: Optional[bool] = None
    ) -> None:
        get_guild = \
            """SELECT * FROM guilds WHERE id=$1"""
        update_guild = \
            """UPDATE guilds
            SET is_qa_on=$1
            WHERE id=$2"""

        conn = self.bot.db.conn

        if enabled is None:
            async with self.bot.db.lock:
                async with conn.transaction():
                    sql_guild = await conn.fetch(
                        get_guild, ctx.guild.id
                    )
            is_enabled = sql_guild['is_qa_on']
            await ctx.send(
                "QuickActions are disabled for this server."
                if not is_enabled else
                "QuickActions are enabled for this server."
            )
        else:
            async with self.bot.db.lock:
                async with conn.transaction():
                    await conn.execute(
                        update_guild, enabled,
                        ctx.guild.id
                    )
            await ctx.send(
                "QuickActions have been enabled."
                if enabled else
                "QuickActions have been disabled."
            )
