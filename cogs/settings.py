import discord
import functions
import bot_config
import settings
from discord.ext import commands
from .wizard import SetupWizard
from typing import List, Union
from paginators import disputils


async def get_blacklist_config_embeds(
    bot: commands.Bot,
    guild_id: int
) -> List[discord.Embed]:
    get_rolelist = \
        """SELECT * FROM rolebl WHERE guild_id=$1"""
    get_channellist = \
        """SELECT * FROM channelbl WHERE guild_id=$1"""
    get_starboards = \
        """SELECT * FROM starboards WHERE guild_id=$1"""

    conn = bot.db.conn

    async with bot.db.lock:
        async with conn.transaction():
            starboards = await conn.fetch(get_starboards, guild_id)
            rolelist = await conn.fetch(get_rolelist, guild_id)
            channellist = await conn.fetch(get_channellist, guild_id)

    mapping = {}

    for s in starboards:
        sid = int(s['id'])
        mapping.setdefault(sid, {
            'rwl': [],
            'rbl': [],
            'cwl': [],
            'cbl': []
        })

    for r in rolelist:
        sid = int(r['starboard_id'])
        rid = int(r['role_id'])

        ltype = 'rwl' if r['is_whitelist'] else 'rbl'

        mapping[sid][ltype].append(f"<@&{rid}>")

    for c in channellist:
        sid = int(c['starboard_id'])
        cid = int(c['channel_id'])

        ltype = 'cwl' if c['is_whitelist'] else 'rbl'

        mapping[sid][ltype].append(f"<#{cid}>")

    embeds = []

    for sid in mapping:
        e = discord.Embed(
            title="Blacklist/Whitelist",
            description=f"<#{sid}>",
            color=bot_config.COLOR
        )

        rwl = ""
        for r in mapping[sid]['rwl']:
            rwl += r + ' '
        rbl = ""
        for r in mapping[sid]['rbl']:
            rbl += r + ' '
        cwl = ""
        for c in mapping[sid]['cwl']:
            cwl += c + ' '
        cbl = ""
        for c in mapping[sid]['cbl']:
            cbl += c + ' '

        if cwl != '':
            cbl += "(all channels are blacklisted if any channel "\
                "is whitelisted)."
        if rwl != '' and rbl == '':
            rbl = 'All roles are blacklisted, since none were '\
                'explicitly set and there is a whitelisted role.'

        if cwl == '':
            cwl = 'None'
        if cbl == '':
            cbl = 'None'
        if rwl == '':
            rwl = 'None'
        if rbl == '':
            rbl = 'None'

        e.add_field(name='Blacklisted Roles', value=rbl)
        e.add_field(name='Whitelisted Roles', value=rwl)
        e.add_field(name='Blacklisted Channels', value=cbl)
        e.add_field(name='Whitelisted Channels', value=cwl)

        embeds.append(e)

    return embeds


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

    return status


class Settings(commands.Cog):
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    #@commands.group(
    #    name='profile', aliases=['userConfig', 'uc', 'p'],
    #    brief='View/change personal settings',
    #    description='Change or view settings for yourself. '
    #    'Changes affect all servers, not just the current one.',
    #    invoke_without_command=True
    #)
    async def user_settings(self, ctx):
        return
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

    #@user_settings.command(
    #    name='LevelUpMessages', aliases=['LvlUpMsgs', 'lum'],
    #    brief='Wether or not to send you level up messages',
    #    description='Wether or not to send you level up messages'
    #)
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
            prefixes = await functions.list_prefixes(
                self.bot, ctx.guild.id
            )

        msg = f"**-** {self.bot.user.mention}"
        for prefix in prefixes:
            msg += f"\n**-** `{prefix}`"

        embed = discord.Embed(
            title="Prefixes",
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

    @commands.command(
        name='setup', aliases=['configure', 'config'],
        description="A setup wizard to make things easier for you",
        brief='A setup wizard'
    )
    @commands.has_permissions(manage_channels=True, manage_messages=True)
    @commands.bot_has_permissions(
        manage_messages=True, embed_links=True,
        add_reactions=True, read_messages=True,
        read_message_history=True
    )
    @commands.bot_has_guild_permissions(
        manage_channels=True, manage_roles=True
    )
    @commands.guild_only()
    async def run_setup_wizard(self, ctx):
        async with self.bot.db.lock:
            conn = self.bot.db.conn
            async with conn.transaction():
                await functions.check_or_create_existence(
                    self.db, conn, self.bot, guild_id=ctx.guild.id,
                    user=ctx.message.author, do_member=True
                )

        wizard = SetupWizard(ctx, self.bot)
        try:
            await wizard.run()
        except Exception:
            await ctx.send("Wizard exited due to a problem.")

    @commands.group(
        name='whitelist', aliases=['wl'],
        invoke_without_command=True,
        description="Manage channel/role whitelist",
        brief="Manage channel/role whitelist"
    )
    @commands.guild_only()
    async def whitelist(self, ctx) -> None:
        embeds = await get_blacklist_config_embeds(
            self.bot, ctx.guild.id
        )
        p = disputils.BotEmbedPaginator(
            ctx, pages=embeds
        )
        await p.run()

    @whitelist.command(
        name='addchannel', aliases=['ac'],
        description="Add a channel to the whitelist",
        brief="Add a channel to the whitelist"
    )
    @commands.has_permissions(manage_channels=True)
    @commands.guild_only()
    async def whitelist_add_channel(
        self, ctx,
        channel: discord.TextChannel,
        starboard: discord.TextChannel
    ) -> None:
        await settings.add_channel_blacklist(
            self.bot, channel.id, starboard.id, ctx.guild.id,
            True
        )
        await ctx.send(
            f"Added {channel.mention} to the whitelist "
            f"for {starboard.mention}"
        )

    @whitelist.command(
        name='removechannel', aliases=['rc'],
        description="Remove a channel from the whitelist",
        brief="Remove a channel from the whitelist"
    )
    @commands.has_permissions(manage_channels=True)
    @commands.guild_only()
    async def whitelist_remove_channel(
        self, ctx,
        channel: Union[discord.TextChannel, int],
        starboard: discord.TextChannel
    ) -> None:
        cid = channel if type(channel) is int else channel.id
        await settings.remove_channel_blacklist(
            self.bot, cid, starboard.id
        )
        await ctx.send(
            f"Removed **{channel}** from the whitelist for "
            f"{starboard.mention}"
        )

    @commands.group(
        name='blacklist', aliases=['bl'],
        invoke_without_command=True,
        description="Manage channel/role blacklist",
        brief="Manage channel/role blacklist"
    )
    async def blacklist(self, ctx) -> None:
        embeds = await get_blacklist_config_embeds(
            self.bot, ctx.guild.id
        )
        p = disputils.BotEmbedPaginator(
            ctx, pages=embeds
        )
        await p.run()


def setup(bot):
    bot.add_cog(Settings(bot, bot.db))
