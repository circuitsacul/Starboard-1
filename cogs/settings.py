import discord, functions, bot_config
from discord.ext import commands


async def change_user_setting(db, user_id: int, lvl_up_msgs: bool=None):
    get_user = \
        """SELECT * FROM users WHERE id=$1"""
    update_user = \
        """UPDATE users
        SET lvl_up_msgs=$1
        WHERE id=$2"""

    conn = await db.connect()
    async with db.lock and conn.transaction():
        sql_user = await conn.fetchrow(get_user, user_id)

        if sql_user is None:
            status = None
        else:
            lum = lvl_up_msgs if lvl_up_msgs is not None else sql_user['lvl_up_msgs']
            await conn.execute(update_user, lum, user_id)
            status = True

    await conn.close()
    return status


class Settings(commands.Cog):
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    @commands.group(
        name='profile', aliases=['userConfig', 'uc', 'p'],
        brief='View/change personal settings',
        description='''Change or view settings for yourself. Changes affect all servers, not just the current one.''',
        invoke_without_command=True
    )
    async def user_settings(self, ctx):
        get_user = \
            """SELECT * FROM users WHERE id=$1"""

        conn = await self.db.connect()
        async with self.db.lock and conn.transaction():
            await functions.check_or_create_existence(
                self.db, conn, self.bot, guild_id=ctx.guild.id,
                user=ctx.message.author, do_member=True
            )
            sql_user = await conn.fetchrow(get_user, ctx.message.author.id)
        await conn.close()

        settings_str = ""
        settings_str += f"\n**LevelUpMessages: {sql_user['lvl_up_msgs']}**"

        embed = discord.Embed(
            title=f"Settings for {str(ctx.message.author)}",
            description=settings_str,
            color=bot_config.COLOR
        )
        embed.set_footer(text="Use `sb!profile <setting> <value>` to change a setting.")
        await ctx.send(embed=embed)

    @user_settings.command(
        name='LvlUpMsgs', aliases=['LevelUpMessages', 'lum'],
        brief='Wether or not to send you level up messages',
        description='Wether or not to send you level up messages'
    )
    async def set_user_lvl_up_msgs(self, ctx, value: bool):
        status = await change_user_setting(self.db, ctx.message.author.id, lvl_up_msgs=value)
        if status is not True:
            await ctx.send("Somthing went wrong.")
        else:
            await ctx.send(f"Set LevelUpMessages to {value}")