import discord
import functions
import bot_config
from discord.ext import commands


async def change_user_setting(
    db, user_id: int, lvl_up_msgs: bool = None
):
    get_user = \
        """SELECT * FROM users WHERE id=$1"""
    update_user = \
        """UPDATE users
        SET lvl_up_msgs=$1
        WHERE id=$2"""

    async with db.lock:
        conn = await db.connect()
        async with conn.transaction():
            sql_user = await conn.fetchrow(get_user, user_id)

            if sql_user is None:
                status = None
            else:
                lum = lvl_up_msgs if lvl_up_msgs is not None\
                    else sql_user['lvl_up_msgs']
                await conn.execute(update_user, lum, user_id)
                status = True

        #await conn.close()
    return status


class Settings(commands.Cog):
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    @commands.group(
        name='profile', aliases=['userConfig', 'uc', 'p'],
        brief='View/change personal settings',
        description='Change or view settings for yourself. '
        'Changes affect all servers, not just the current one.',
        invoke_without_command=True
    )
    async def user_settings(self, ctx):
        get_user = \
            """SELECT * FROM users WHERE id=$1"""

        async with self.db.lock:
            conn = await self.db.connect()
            async with conn.transaction():
                await functions.check_or_create_existence(
                    self.db, conn, self.bot,
                    guild_id=ctx.guild.id if ctx.guild is not None else None,
                    user=ctx.message.author,
                    do_member=True if ctx.guild is not None else None
                )
                sql_user = await conn.fetchrow(get_user, ctx.message.author.id)
            #await conn.close()

        settings_str = ""
        settings_str += f"\n**LevelUpMessages: {sql_user['lvl_up_msgs']}**"

        embed = discord.Embed(
            title=f"Settings for {str(ctx.message.author)}",
            description=settings_str,
            color=bot_config.COLOR
        )
        if ctx.guild is not None:
            p = await functions.get_one_prefix(self.bot, ctx.guild.id)
        else:
            p = bot_config.DEFAULT_PREFIX
        embed.set_footer(
            text=f"Use {p}profile <setting> <value> "
            "to change a setting."
        )
        await ctx.send(embed=embed)

    @user_settings.command(
        name='LevelUpMessages', aliases=['LvlUpMsgs', 'lum'],
        brief='Wether or not to send you level up messages',
        description='Wether or not to send you level up messages'
    )
    async def set_user_lvl_up_msgs(self, ctx, value: bool):
        status = await change_user_setting(
            self.db, ctx.message.author.id, lvl_up_msgs=value
        )
        if status is not True:
            await ctx.send("Somthing went wrong.")
        else:
            await ctx.send(f"Set LevelUpMessages to {value}")

    @commands.group(
        name='prefixes', aliases=['prefix'],
        description='List, add, remove and clear prefixes',
        brief='Manage prefixes',
        invoke_without_command=True
    )
    async def guild_prefixes(self, ctx):
        if ctx.guild is None:
            prefixes = ['sb!']
        else:
            async with self.bot.db.lock:
                prefixes = await functions.list_prefixes(
                    self.bot, ctx.guild.id
                )

        msg = f"**-** {self.bot.user.mention}"
        for prefix in prefixes:
            msg += f"\n**-** `{prefix}`"

        embed = discord.Embed(
            title=f"Prefixes",
            description=msg,
            color=bot_config.COLOR
        )
        await ctx.send(embed=embed)

    @guild_prefixes.command(
        name='add', aliases=['a'],
        description='Add a prefix',
        brief='Add a prefix'
    )
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def add_prefix(self, ctx, prefix: str):
        if len(prefix) > 8:
            await ctx.send(
                "That prefix is too long! It must be under 9 characters."
            )
            return

        async with self.bot.db.lock:
            status, status_msg = await functions.add_prefix(
                self.bot, ctx.guild.id, prefix
            )
        if status is True:
            await ctx.send(f"Added prefix `{prefix}`")
        else:
            await ctx.send(status_msg)

    @guild_prefixes.command(
        name='remove', aliases=['delete', 'd', 'r']
    )
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def remove_prefix(self, ctx, prefix: str):
        async with self.bot.db.lock:
            status, status_msg = await functions.remove_prefix(
                self.bot, ctx.guild.id, prefix
            )
        if status is True:
            await ctx.send(f"Removed prefix `{prefix}`")
        else:
            await ctx.send(status_msg)
